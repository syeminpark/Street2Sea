import os
import requests
import datetime
import math
from dotenv import load_dotenv
from streetview import search_panoramas, get_panorama_meta, get_streetview
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_STREET_VIEW_API_KEY")

# Cache for panorama metadata to avoid duplicate requests
_meta_cache = {}

def fetch_meta(pano_id: str):
    """
    Fetch panorama metadata with caching.
    """
    if pano_id not in _meta_cache:
        _meta_cache[pano_id] = get_panorama_meta(pano_id=pano_id, api_key=GOOGLE_API_KEY)
    return _meta_cache[pano_id]


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance (meters) between two points.
    """
    R = 6371000  # Earth radius in meters
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    dφ = math.radians(lat2 - lat1)
    dλ = math.radians(lon2 - lon1)
    a = math.sin(dφ/2)**2 + math.cos(φ1) * math.cos(φ2) * math.sin(dλ/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def addressToCoordinates(address: str) -> str:
    """
    Returns "lat,lng" for the given address, or raises RuntimeError
    if the Geocoding API returns anything other than status='OK'.
    """
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    resp = requests.get(url, params={"address": address, "key": GOOGLE_API_KEY})
    data = resp.json()
    if data.get("status") != "OK":
        err = data.get("error_message", "no details")
        raise RuntimeError(f"Geocode API error {data.get('status')}: {err}")
    loc = data["results"][0]["geometry"]["location"]
    return f"{loc['lat']},{loc['lng']}"


def _fetch_streetview_bytes(
    pano_id: str,
    width: int,
    height: int,
    heading: int,
    pitch: int,
    fov: int,
) -> bytes:
    """
    Download a Street View image (PIL) and serialize to JPEG bytes.
    """
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


def getStreetViewByDate(
    coordinates: str,
    target_date: str,
    width: int = 600,
    height: int = 300,
    fov: int = 120,
    heading: int = 0,
    pitch: int = 0,
):
    """
    Fetch the Street View panorama on or before `target_date` closest to `coordinates`.

    Returns:
      images:   list of raw JPEG bytes (length=1)
      metadata: list of dicts (length=1)
    """
    # Parse the target date
    user_dt = datetime.date.fromisoformat(target_date)

    # Split coordinates
    lat, lon = map(float, coordinates.split(","))

    # 1) List available panoramas via streetview JS-scrape
    panos = search_panoramas(lat=lat, lon=lon)

    # 2) Phase 1: Filter by date only (no HTTP except fallback)
    parsed = []
    for pano in panos:
        # Get date string from JS result or fallback to metadata
        if pano.date:
            date_str = pano.date
        else:
            date_str = fetch_meta(pano.pano_id).date

        # Parse date_str in formats: YYYY-MM, YYYY, Month YYYY
        dt = None
        for fmt in ("%Y-%m", "%Y", "%B %Y"):
            try:
                parsed_dt = datetime.datetime.strptime(date_str, fmt)
                dt = parsed_dt.date().replace(day=1)
                break
            except ValueError:
                continue
        if dt and dt <= user_dt:
            parsed.append((dt, pano))

    if not parsed:
        raise RuntimeError(f"No panoramas on/before {target_date}")

    # Find the most recent date
    best_date = max(dt for dt, _ in parsed)
    candidates = [p for dt, p in parsed if dt == best_date]

    # 3) Phase 2: Among candidates, compute distance (min HTTP via cache + parallel)
    with ThreadPoolExecutor(max_workers=min(4, len(candidates))) as exe:
        metas = list(exe.map(lambda p: fetch_meta(p.pano_id), candidates))

    dists = [haversine(lat, lon, m.location.lat, m.location.lng) for m in metas]
    best_idx = dists.index(min(dists))
    best_pano = candidates[best_idx]
    best_meta = metas[best_idx]

    # 4) Download the exact image bytes
    img_bytes = _fetch_streetview_bytes(
        pano_id=best_pano.pano_id,
        width=width,
        height=height,
        heading=heading,
        pitch=pitch,
        fov=fov,
    )

    metadata = {
        "pano_id": best_pano.pano_id,
        "date": best_meta.date,
        "lat": best_meta.location.lat,
        "lng": best_meta.location.lng,
        "heading": heading,
        "fov": fov,
        "size": f"{width}x{height}",
        "location": coordinates,
    }

    return [img_bytes], [metadata]


def getPanoramaByDateTiles(
    coordinates: str,
    target_date: str,
    width: int = 600,
    height: int = 300,
    fov: int = 120,
    headings: list[int] = (0, 120, 240),
    pitch: int = 0,
):
    """
    Fetch up to three images (for each heading) on or before `target_date`.

    Returns:
      images:   list of raw JPEG bytes
      metadata: list of dicts
    """
    all_images, all_meta = [], []

    for h in headings:
        try:
            imgs, metas = getStreetViewByDate(
                coordinates=coordinates,
                target_date=target_date,
                width=width,
                height=height,
                fov=fov,
                heading=h,
                pitch=pitch,
            )
            all_images.append(imgs[0])
            all_meta.append(metas[0])
        except RuntimeError:
            continue

    if not all_images:
        raise RuntimeError(
            f"No panoramas on/before {target_date} at any heading"
        )

    return all_images, all_meta
