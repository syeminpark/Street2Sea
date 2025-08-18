# googleAPI.py

import os
import requests
import datetime
import math
from types import SimpleNamespace
from dotenv import load_dotenv
from pydantic import ValidationError
from streetview import search_panoramas, get_panorama_meta, get_streetview
from io import BytesIO
from constants import PerspectiveMode

# ------------------- env & globals -------------------
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_STREET_VIEW_API_KEY")
SV_USE_JS_OUTDOOR = os.getenv("SV_USE_JS_OUTDOOR", "0") == "1"
SV_OUTDOOR_ENDPOINT = os.getenv("SV_OUTDOOR_ENDPOINT", "http://localhost:8000/find-outdoor-js")
SV_JS_FALLBACK_TO_CORE = os.getenv("SV_JS_FALLBACK_TO_CORE", "1") == "1"

_meta_cache: dict[str, object] = {}

# ------------------- geocode -------------------
def addressToCoordinates(address: str) -> str:
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    resp = requests.get(url, params={"address": address, "key": GOOGLE_API_KEY}, timeout=10)
    data = resp.json()
    if data.get("status") != "OK":
        err = data.get("error_message", "no details")
        raise RuntimeError(f"Geocode API error {data.get('status')}: {err}")
    loc = data["results"][0]["geometry"]["location"]
    return f"{loc['lat']},{loc['lng']}"

# ------------------- geometry -------------------
def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    dφ = math.radians(lat2 - lat1)
    dλ = math.radians(lon2 - lon1)
    a = math.sin(dφ/2)**2 + math.cos(φ1)*math.cos(φ2)*math.sin(dλ/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def haversine_and_bearing(lat1: float, lon1: float, lat2: float, lon2: float):
    dist = haversine(lat1, lon1, lat2, lon2)
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    Δλ = math.radians(lon2 - lon1)
    y = math.sin(Δλ) * math.cos(φ2)
    x = math.cos(φ1)*math.sin(φ2) - math.sin(φ1)*math.cos(φ2)*math.cos(Δλ)
    bearing = (math.degrees(math.atan2(y, x)) + 360) % 360
    return dist, bearing

# ------------------- metadata -------------------
def fetch_meta(pano_id: str):
    if pano_id in _meta_cache:
        return _meta_cache[pano_id]

    def _fallback_from_google(pid: str):
        raw = requests.get(
            "https://maps.googleapis.com/maps/api/streetview/metadata",
            params={"pano": pid, "key": GOOGLE_API_KEY},
            timeout=10,
        ).json()
        loc = raw.get("location") or {}
        return SimpleNamespace(
            date=raw.get("date"),
            location=SimpleNamespace(lat=loc.get("lat"), lng=loc.get("lng"))
        )

    try:
        meta = get_panorama_meta(pano_id=pano_id, api_key=GOOGLE_API_KEY)
        if getattr(meta, "date", None) in (None, ""):
            fb = _fallback_from_google(pano_id)
            if fb.date:
                try:
                    setattr(meta, "date", fb.date)
                except Exception:
                    meta = fb
    except (ValidationError, Exception):
        meta = _fallback_from_google(pano_id)

    _meta_cache[pano_id] = meta
    return meta

def _parse_pano_date(ds) -> datetime.date | None:
    if isinstance(ds, datetime.date):
        return ds.replace(day=1)
    if not ds:
        return None
    for fmt in ("%Y-%m", "%Y", "%B %Y"):
        try:
            parsed = datetime.datetime.strptime(ds, fmt)
            return parsed.date().replace(day=1)
        except ValueError:
            continue
    return None

# ------------------- pano selection (JS path) -------------------
def _find_best_panorama_via_js(coordinates: str, target_date: str, tolerance_m: float = 5.0):
    if not SV_OUTDOOR_ENDPOINT:
        raise RuntimeError("SV_OUTDOOR_ENDPOINT not set")

    lat, lon = map(float, coordinates.split(","))
    try:
        resp = requests.post(
            SV_OUTDOOR_ENDPOINT,
            json={
                "lat": lat,
                "lng": lon,
                "target_date": target_date,
                "radius": max(50, int(tolerance_m) + 50),
                "tolerance_m": int(tolerance_m),
                "max_hops": 3
            },
            timeout=30
        )
        resp.raise_for_status()
        body = resp.json()
        if not body.get("ok"):
            # Normalize message so the app can detect it consistently
            raise RuntimeError(f"No panoramas on or before {target_date} (outdoor)")
        p = body["pano"]  # {pano_id, date, lat, lng}

        pano = SimpleNamespace(pano_id=p["pano_id"])
        meta = SimpleNamespace(
            date=p.get("date"),
            location=SimpleNamespace(lat=p.get("lat"), lng=p.get("lng"))
        )
        return pano, meta
    except Exception as e:
        s = str(e).lower()
        if ("no outdoor pano on/before" in s) or ("no panoramas on or before" in s):
            # Re-raise normalized version
            raise RuntimeError(f"No panoramas on or before {target_date} (outdoor)")
        raise

# ------------------- pano selection (core Python path) -------------------
def _find_best_panorama_core(coordinates: str, target_date: str, tolerance_m: float = 5.0):
    user_dt = datetime.date.fromisoformat(target_date)
    lat, lon = map(float, coordinates.split(","))
    panos = search_panoramas(lat=lat, lon=lon)

    candidates = []
    for p in panos:
        ds = getattr(p, "date", None) or getattr(fetch_meta(p.pano_id), "date", None)
        dt = _parse_pano_date(ds)
        if not dt or dt > user_dt:
            continue

        meta = fetch_meta(p.pano_id)
        mlat = getattr(getattr(meta, "location", SimpleNamespace()), "lat", None)
        mlng = getattr(getattr(meta, "location", SimpleNamespace()), "lng", None)
        if mlat is None or mlng is None:
            continue

        dist = haversine(lat, lon, mlat, mlng)
        candidates.append((dt, dist, p, meta))

    if not candidates:
        raise RuntimeError(f"No panoramas on or before {target_date}")

    candidates.sort(key=lambda x: (x[1], -x[0].toordinal()))
    nearest_dist = candidates[0][1]
    close_enough = [c for c in candidates if (c[1] - nearest_dist) <= tolerance_m]
    best = max(close_enough, key=lambda x: x[0].toordinal())
    _best_dt, _best_dist, best_pano, best_meta = best
    return best_pano, best_meta

# ------------------- pano selection (wrapper) -------------------
def _find_best_panorama(coordinates: str, target_date: str, tolerance_m: float = 5.0):
    if SV_USE_JS_OUTDOOR:
        try:
            print("[SV] using JS OUTDOOR route…")
            return _find_best_panorama_via_js(coordinates, target_date, tolerance_m)
        except Exception as e:
            print("[SV] JS OUTDOOR failed:", e)
            if not SV_JS_FALLBACK_TO_CORE:
                raise
            print("[SV] falling back to core Python picker")
    else:
        print("[SV] using core Python picker")
    return _find_best_panorama_core(coordinates, target_date, tolerance_m)

# ------------------- image fetch -------------------
def _fetch_image_bytes(pano_id: str, width: int, height: int, heading: int, pitch: int, fov: int) -> bytes:
    pil_img = get_streetview(
        pano_id=pano_id,
        api_key=GOOGLE_API_KEY,
        width=width,
        height=height,
        heading=heading,
        pitch=pitch,
        fov=fov,
    )
    buf = BytesIO()
    pil_img.save(buf, format="JPEG")
    data = buf.getvalue()
    buf.close()
    return data

# ------------------- public API -------------------
def getStreetViewByDate(
    coordinates: str,
    target_date: str,
    tolerance_m: float = 5.0,
    width: int = 500,
    height: int = 250,
    fov: int = 120,
    heading: int = 0,
    pitch: int = 0,
):
    pano, meta = _find_best_panorama(coordinates, target_date, tolerance_m=tolerance_m)
    img = _fetch_image_bytes(pano.pano_id, width, height, heading, pitch, fov)

    mlat = getattr(getattr(meta, "location", SimpleNamespace()), "lat", None)
    mlng = getattr(getattr(meta, "location", SimpleNamespace()), "lng", None)

    # distance (camera pano position → requested address coords)
    try:
        addr_lat, addr_lng = map(float, coordinates.split(","))
        distance_m = haversine(addr_lat, addr_lng, float(mlat), float(mlng)) if (mlat is not None and mlng is not None) else None
    except Exception:
        distance_m = None

    metadata = {
        "pano_id": pano.pano_id,
        "date": getattr(meta, "date", None),
        "lat": mlat,
        "lng": mlng,
        "heading": heading,
        "fov": fov,
        "pitch": pitch,
        "width": width,
        "height": height,
        "size": f"{width}x{height}",
        "location": coordinates,
        "distance_m": distance_m,
    }
    return [img], [metadata]

def getPanoramaByDateTiles(
    coordinates: str,
    target_date: str,
    tolerance_m: float = 5.0,
    width: int = 500,
    height: int = 250,
    fov: int = 120,
    headings: list[int] = (0, 120, 240),
    pitch: int = 0,
):
    images, metas = [], []
    for h in headings:
        try:
            imgs, mds = getStreetViewByDate(
                coordinates,
                target_date,
                width=width,
                height=height,
                fov=fov,
                heading=h,
                pitch=pitch,
                tolerance_m=tolerance_m,
            )
            images.append(imgs[0])
            metas.append(mds[0])
        except RuntimeError:
            continue

    if not images:
        raise RuntimeError(f"No panoramas on or before {target_date} at any heading")
    return images, metas

def getStreetViewOfBuilding(
    coordinates: str,
    target_date: str,
    tolerance_m: float = 5.0,
    width: int = 500,
    height: int = 250,
    pitch: int = 0,
    fov: int = 120,
):
    building_coords = coordinates
    pano, meta = _find_best_panorama(coordinates, target_date, tolerance_m=tolerance_m)
    mlat = getattr(getattr(meta, "location", SimpleNamespace()), "lat", None)
    mlng = getattr(getattr(meta, "location", SimpleNamespace()), "lng", None)
    if mlat is None or mlng is None:
        raise RuntimeError("Panorama location missing; cannot compute bearing")

    addr_lat, addr_lng = map(float, building_coords.split(","))
    distance_m, bearing = haversine_and_bearing(mlat, mlng, addr_lat, addr_lng)

    img = _fetch_image_bytes(pano.pano_id, width, height, int(bearing), pitch, fov)
    metadata = {
        "pano_id": pano.pano_id,
        "date": getattr(meta, "date", None),
        "lat": mlat,
        "lng": mlng,
        "pitch": pitch,
        "width": width,
        "height": height,
        "heading": int(bearing),
        "fov": fov,
        "size": f"{width}x{height}",
        "location": building_coords,
        "distance_m": distance_m,
    }
    return [img], [metadata]

def getStreetView(
    coordinates: str,
    target_date: str,
    mode: str,
    tolerance_m: int,
    width: int,
    height: int,
    **kwargs
):
    if mode == PerspectiveMode.SURROUNDING.value:
        return getPanoramaByDateTiles(coordinates, target_date, tolerance_m, width, height, **kwargs)
    return getStreetViewOfBuilding(coordinates, target_date, tolerance_m, width, height, **kwargs)
