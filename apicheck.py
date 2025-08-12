# apicheck.py
import os
from dotenv import load_dotenv, find_dotenv
import requests

# load .env from the current working dir or parents
load_dotenv(find_dotenv(usecwd=True))

GOOGLE_API_KEY = os.getenv("GOOGLE_STREET_VIEW_API_KEY")



def get_pano_source(pano_id: str):
    url = "https://maps.googleapis.com/maps/api/streetview/metadata"
    resp = requests.get(url, params={"pano": pano_id, "key": GOOGLE_API_KEY}, timeout=10)
    data = resp.json()
    return data.get("source"), data

# Example usage
pano_id = "Tf-DmvKTM50lwwxaq6EHfw"  # your April 2011 street pano
source, full_meta = get_pano_source(pano_id)
print("Source:", source)
print("Full metadata:", full_meta)