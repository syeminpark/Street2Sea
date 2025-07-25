# googleAPI.py
import os
import requests
import datetime
from dotenv import load_dotenv
from streetview import search_panoramas, get_panorama_meta, get_streetview
from io import BytesIO
import math

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_STREET_VIEW_API_KEY")

def haversine(lat1, lon1, lat2, lon2):
    # returns distance in meters
        R = 6371000
        φ1, φ2 = math.radians(lat1), math.radians(lat2)
        dφ = math.radians(lat2 - lat1)
        dλ = math.radians(lon2 - lon1)
        a = math.sin(dφ/2)**2 + math.cos(φ1)*math.cos(φ2)*math.sin(dλ/2)**2
        c = 2*math.atan2(math.sqrt(a), math.sqrt(1-a))
        return R * c


def addressToCoordinates(address: str) -> str:
    """
    Returns “lat,lng” for the given address, or raises RuntimeError
    if the Geocoding API returns anything other than status='OK'.
    """
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    resp = requests.get(url, params={"address": address, "key": GOOGLE_API_KEY})
    data = resp.json()
    status = data.get("status")
    if status != "OK":
        err = data.get("error_message", "no details")
        raise RuntimeError(f"Geocode API error {status}: {err}")
    loc = data["results"][0]["geometry"]["location"]
    return f"{loc['lat']},{loc['lng']}"


def getStreetViewByDate(
    coordinates: str,
    target_date: str,
    width: int   = 600,
    height: int    = 300,
    fov: int     = 120,
    heading: int = 0,
    pitch: int   = 0
):
    user_dt = datetime.date.fromisoformat(target_date)

    # 2) split coords
    lat, lon = map(float, coordinates.split(","))

    # 3) list panoramas
    panos = search_panoramas(lat=lat, lon=lon)

    # 4) filter + distance
    valid = []
    for pano in panos:
        date_str = pano.date or get_panorama_meta(pano.pano_id, api_key=GOOGLE_API_KEY).date
        dt = None
        for fmt in ("%Y-%m", "%Y", "%B %Y"):
            try:
                dt = datetime.datetime.strptime(date_str, fmt).date().replace(day=1)
                break
            except ValueError:
                pass
        if not dt or dt > user_dt:
            continue

        meta = get_panorama_meta(pano_id=pano.pano_id, api_key=GOOGLE_API_KEY)
        dist = haversine(lat, lon, meta.location.lat, meta.location.lng)
        valid.append((dt, pano, dist))

    if not valid:
        raise RuntimeError(f"No panoramas on/before {target_date}")

    # pick newest date, then nearest
    _, best, _ = sorted(valid, key=lambda x: (-x[0].toordinal(), x[2]))[0]

        


    # 6) fetch metadata for that pano
    meta = get_panorama_meta(pano_id=best.pano_id, api_key=GOOGLE_API_KEY)

    # 7) download the exact historic image
    image = get_streetview(
        pano_id=best.pano_id,
        api_key=GOOGLE_API_KEY,
        width=width,
        height=height,
        heading=heading,
        pitch=pitch,
        fov=fov
    )

    # 8) return as before
    metadata = {
        "pano_id":   best.pano_id,
        "date":      meta.date,
        "heading":   heading,
        "fov":       fov,
        "size":      f"{width}x{height}",
        "location":  coordinates,
        "lat":       meta.location.lat,
        "lng":       meta.location.lng,
    }
    return [image], [metadata]


def getPanoramaByDateTiles(
    coordinates: str,
    target_date: str,
    width: int   = 600,
    height: int    = 300,
    fov: int          = 120,
    headings: list[int] = (0, 120, 240),
    pitch: int        = 0
):
    """
    Calls getStreetViewByDate() for each heading in `headings`,
    collecting up to three images + metadata.

    Returns:
      images:   list of image-bytes
      metadata: list of dicts (same length as images)

    Skips any heading whose capture is newer than target_date.
    Raises if none succeed.
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
                pitch=pitch
            )
            # unpack the single-item lists
            all_images.append(imgs[0])
            all_meta.append(metas[0])
        except RuntimeError:
            # skip headings with no valid panorama
            continue

    if not all_images:
        raise RuntimeError(f"No panoramas on/before {target_date} at any heading")

    return all_images, all_meta
