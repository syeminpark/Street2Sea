import os
from dotenv import load_dotenv
from PIL import Image
from io import BytesIO
import requests

load_dotenv()
google_street_api_key = os.getenv("GOOGLE_STREET_VIEW_API_KEY")

image_size = '600x300'             # Width x Height
fov = 90                           # Field of view (10-120)
heading = 0                        # Compass direction (0 = North)
pitch = 0                          # Up/down tilt


def addressToCoordinates(address):
    url = f'https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={google_street_api_key}'

    response = requests.get(url)
    data = response.json()

    if data['status'] == 'OK':
        location = data['results'][0]['geometry']['location']
        lat = location['lat']
        lng = location['lng']
        print(f"Latitude: {lat}, Longitude: {lng}")
    else:
        print("Error:", data['status'])

    return f'"{lat},{lng}"'

def getStreetViewImage(coordinates, isDisplayImage=False):

        # --- BUILD REQUEST URL ---
    url = (
        f'https://maps.googleapis.com/maps/api/streetview'
        f'?size={image_size}'
        f'&location={coordinates}' # Format: "latitude,longitude")
        f'&fov={fov}'
        f'&heading={heading}'
        f'&pitch={pitch}'
        f'&key={google_street_api_key}'
    )
    # --- MAKE REQUEST ---
    response = requests.get(url)

    # --- Display Image ---
    if(isDisplayImage):
        if response.status_code == 200:
            img = Image.open(BytesIO(response.content))
            img.show()  # This opens the image in the default image viewer
        else:
            print("Error:", response.status_code, response.text)
    return response




import os, requests, datetime
from typing import List, Dict

API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")  # set this in your env

TILE_BASE = "https://tile.googleapis.com/v1/streetview"
STATIC_BASE = "https://maps.googleapis.com/maps/api/streetview"

def get_pano_ids(lat: float, lng: float, radius_m: int = 50) -> List[str]:
    """POST /streetview/panoIds to get candidate panoIds near (lat,lng)."""
    url = f"{TILE_BASE}/panoIds?key={API_KEY}"
    payload = {"locations": [{"lat": lat, "lng": lng}], "radius": radius_m}
    r = requests.post(url, json=payload, timeout=30)
    r.raise_for_status()
    return [p["panoId"] for p in r.json().get("panoIds", [])]

def get_metadata(pano_id: str) -> Dict:
    """GET /streetview/metadata for each panoId."""
    url = f"{TILE_BASE}/metadata"
    r = requests.get(url, params={"panoId": pano_id, "key": API_KEY}, timeout=30)
    r.raise_for_status()
    return r.json()

def pick_by_date(candidates: List[Dict], start: str, end: str) -> Dict:
    """Filter metadata objects by YYYY-MM range (inclusive)."""
    s = datetime.datetime.strptime(start, "%Y-%m")
    e = datetime.datetime.strptime(end, "%Y-%m")
    def parse(d):  # d like "2023-01" or "2019"
        return datetime.datetime.strptime(d, "%Y-%m" if "-" in d else "%Y")
    filtered = [m for m in candidates if "date" in m and s <= parse(m["date"]) <= e]
    return sorted(filtered, key=lambda m: m["date"])[0] if filtered else {}

def download_image(pano_id: str, out_path: str = "streetview.jpg",
                   size: str = "640x640", fov: int = 90, heading: int = 0, pitch: int = 0):
    """Fetch the actual JPEG with the Static API."""
    params = {
        "pano": pano_id,
        "size": size,
        "fov": fov,
        "heading": heading,
        "pitch": pitch,
        "key": API_KEY,
    }
    r = requests.get(STATIC_BASE, params=params, timeout=60)
    r.raise_for_status()
    with open(out_path, "wb") as f:
        f.write(r.content)
    return out_path

if __name__ == "__main__":
    lat, lng = 37.4219999, -122.0840575   # Example: Googleplex
    pano_ids = get_pano_ids(lat, lng, radius_m=100)
    metas = [get_metadata(pid) for pid in pano_ids]
    chosen = pick_by_date(metas, start="2018-01", end="2019-12")
    if not chosen:
        raise SystemExit("No pano in that date range.")
    print("Chosen pano:", chosen["panoId"], "date:", chosen["date"])
    path = download_image(chosen["panoId"])
    print("Saved:", path)
