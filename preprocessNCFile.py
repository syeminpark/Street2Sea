import xarray as xr
from dotenv import load_dotenv
import os 
load_dotenv()
import xarray as xr
import os
import re
from datetime import datetime

DATA_DIR = os.getenv("TEJAPAN_DATA_DIR")

fileType = {
    "depth": "FLDDPH",
    "fraction": "FLDFRC"
}

def extract_datetime_from_filename(filename):
    # Match strings like: TE-JPN15S_MSM_H2025072310_FLDDPH.nc
    match = re.search(r"_H(\d{10})_", filename)
    if match:
        dt_str = match.group(1)  # e.g., "2025072310"
        return datetime.strptime(dt_str, "%Y%m%d%H")
    return None

def openClosestFile(fileType, target_datetime: datetime):
    # Find matching files
    files = [
        f for f in os.listdir(DATA_DIR)
        if f.endswith(".nc") and fileType in f
    ]

    if not files:
        raise FileNotFoundError(f"No matching .nc files for {fileType}")

    # Extract datetime from each file and filter those before target time
    dated_files = []
    for f in files:
        dt = extract_datetime_from_filename(f)
        if dt and dt <= target_datetime:
            dated_files.append((dt, f))

    if not dated_files:
        raise FileNotFoundError(f"No {fileType} files found before {target_datetime}")

    # Sort by datetime and select the closest past file
    dated_files.sort()
    closest_file = dated_files[-1][1]
    file_path = os.path.join(DATA_DIR, closest_file)

    print(f"✅ Opening {fileType} file closest to {target_datetime}: {closest_file}")
    return xr.open_dataset(file_path)


def getNearestValueByCoordinates(dataset, coordinates):
    data = dataset.sel(lat=coordinates["latitude"], lon=coordinates["longitude"], method="nearest").item()
    return data

def floodVolumeProxy(depth,fraction):
    effective_volume = depth * fraction
    return effective_volume
