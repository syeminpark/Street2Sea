import os
import requests
import datetime
import math
from dotenv import load_dotenv
from streetview import search_panoramas, get_panorama_meta, get_streetview
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor
from constants import PerspectiveMode

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_STREET_VIEW_API_KEY")

# Cache for panorama metadata
_meta_cache = {}

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


def fetch_meta(pano_id: str):
    """
    Fetch panorama metadata with caching to avoid duplicate network calls.
    """
    if pano_id not in _meta_cache:
        _meta_cache[pano_id] = get_panorama_meta(pano_id=pano_id, api_key=GOOGLE_API_KEY)
    return _meta_cache[pano_id]


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate great-circle distance in meters between two coordinates.
    """
    R = 6371000  # earth radius in meters
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    dφ = math.radians(lat2 - lat1)
    dλ = math.radians(lon2 - lon1)
    a = math.sin(dφ/2)**2 + math.cos(φ1)*math.cos(φ2)*math.sin(dλ/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def haversine_and_bearing(lat1: float, lon1: float, lat2: float, lon2: float):
    """
    Returns (distance_meters, bearing_degrees) from point1 to point2.
    """
    dist = haversine(lat1, lon1, lat2, lon2)
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    Δλ = math.radians(lon2 - lon1)
    y = math.sin(Δλ) * math.cos(φ2)
    x = math.cos(φ1)*math.sin(φ2) - math.sin(φ1)*math.cos(φ2)*math.cos(Δλ)
    bearing = (math.degrees(math.atan2(y, x)) + 360) % 360
    return dist, bearing


def _find_best_panorama(coordinates: str, target_date: str):
    """
    Find the panorama ID and metadata nearest to coordinates and on or before target_date.
    """
    user_dt = datetime.date.fromisoformat(target_date)
    lat, lon = map(float, coordinates.split(","))
    panos = search_panoramas(lat=lat, lon=lon)

    candidates = []
    for p in panos:
        ds = p.date or fetch_meta(p.pano_id).date
        dt = None
        for fmt in ("%Y-%m", "%Y", "%B %Y"):
            try:
                parsed = datetime.datetime.strptime(ds, fmt)
                dt = parsed.date().replace(day=1)
                break
            except ValueError:
                continue
        if not dt or dt > user_dt:
            continue
        meta = fetch_meta(p.pano_id)
        dist = haversine(lat, lon, meta.location.lat, meta.location.lng)
        candidates.append((dt, dist, p, meta))

    if not candidates:
        raise RuntimeError(f"No panoramas on or before {target_date}")

    # sort by date (newest first), then proximity (nearest)
    _, _, best_pano, best_meta = sorted(
        candidates,
        key=lambda x: (x[0].toordinal(), -x[1])
    )[-1]
    return best_pano, best_meta


def _fetch_image_bytes(pano_id: str, width: int, height: int, heading: int, pitch: int, fov: int) -> bytes:
    """
    Download a Street View image via robolyst/streetview and return raw JPEG bytes.
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
    pitch: int = 0
):
    """
    Single‐tile Street‑View for best panorama on or before target_date.
    Returns ([bytes], [metadata]).
    """
    pano, meta = _find_best_panorama(coordinates, target_date)
    img = _fetch_image_bytes(pano.pano_id, width, height, heading, pitch, fov)
    metadata = {
        "pano_id": pano.pano_id,
        "date": meta.date,
        "lat": meta.location.lat,
        "lng": meta.location.lng,
        "heading": heading,
        "fov": fov,
        "size": f"{width}x{height}",
        "location": coordinates,
    }
    return [img], [metadata]


def getPanoramaByDateTiles(
    coordinates: str,
    target_date: str,
    width: int = 600,
    height: int = 300,
    fov: int = 120,
    headings: list[int] = (0, 120, 240),
    pitch: int = 0
):
    """
    Surrounding‐view mode: fetch multiple headings via getStreetViewByDate.
    Returns (list[bytes], list[metadata]).
    """
    images, metas = [], []
    for h in headings:
        try:
            imgs, mds = getStreetViewByDate(
                coordinates, target_date,
                width=width, height=height,
                fov=fov, heading=h, pitch=pitch
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
    width: int = 600,
    height: int = 300,
    pitch: int = 0,
    fov: int = 120
):
    """
    Building‐centered view: compute bearing to building_coords and fetch single tile.
    Returns ([bytes], [metadata]).
    """
   
    building_coords = coordinates
    pano, meta = _find_best_panorama(coordinates, target_date)
    dist, bearing = haversine_and_bearing(
        meta.location.lat, meta.location.lng,
        *map(float, building_coords.split(","))
    )
    img = _fetch_image_bytes(pano.pano_id, width, height, int(bearing), pitch, fov)
    metadata = {
        "pano_id": pano.pano_id,
        "date": meta.date,
        "lat": meta.location.lat,
        "lng": meta.location.lng,
        "heading": int(bearing),
        "fov": fov,
        "size": f"{width}x{height}",
        "location": building_coords 
    }
    return [img], [metadata]


def getStreetView(
    coordinates: str,
    target_date: str,
    mode: str,
    **kwargs
):
    """
    Unified entry: use mode="building" or "surrounding" to dispatch.
    """
    if mode == PerspectiveMode.SURROUNDING.value:
        return getPanoramaByDateTiles(coordinates, target_date, **kwargs)
    return getStreetViewOfBuilding(coordinates, target_date, **kwargs)