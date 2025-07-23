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


def adressToCoordinates(address):
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
