import xarray as xr
import os
import re
from datetime import datetime
from constants import TEJapanDirectory, TEJapanFileType
import pandas as pd


def extract_datetime_from_filename(filename):
    # Match strings like: TE-JPN15S_MSM_H2025072310_FLDDPH.nc
    match = re.search(r"_H(\d{10})_", filename)
    if match:
        dt_str = match.group(1)  # e.g., "2025072310"
        return datetime.strptime(dt_str, "%Y%m%d%H")
    return None

def openClosestFile(fileType, target_datetime: datetime):
    # normalize fileType into an iterable of strings
    if hasattr(fileType, "value"):
        ft = fileType.value
    else:
        ft = fileType

    if isinstance(ft, tuple):
        terms = ft             # e.g. ("FLDDPH","depth")
    else:
        terms = (ft,)          # single‐element tuple

    # now filter filenames by any of those terms
    dirpath = TEJapanDirectory.DIRECTORY.value
    files = [
        f for f in os.listdir(dirpath)
        if f.endswith(".nc")
           and any(term in f for term in terms)
    ]
    if not files:
        raise FileNotFoundError(f"No matching .nc files for {fileType}")

    # the rest is unchanged
    dated = []
    for f in files:
        dt = extract_datetime_from_filename(f)
        if dt and dt <= target_datetime:
            dated.append((dt, f))
    if not dated:
        raise FileNotFoundError(
            f"No {fileType} files found before {target_datetime}"
        )
    dated.sort()
    chosen = dated[-1][1]
    path = os.path.join(dirpath, chosen)
    print(f"✅ Opening {fileType} file closest to {target_datetime}: {chosen}")
    return xr.open_dataset(path)


def getNearestValueByCoordinates(dataset, coordinates, target_time):
    # Parse coordinates
    if isinstance(coordinates, str):
        lat, lon = map(float, coordinates.split(","))
    else:
        lat = coordinates["latitude"]
        lon = coordinates["longitude"]

    # Select the first variable (e.g., FLDDPH)
    da = dataset[list(dataset.data_vars)[0]]

    # Convert all time values to pandas Timestamps
    times = pd.to_datetime(da.coords["time"].values)

    # Filter to past or equal times (relative to target_time)
    past_times = [t for t in times if t <= target_time]
    if not past_times:
        raise ValueError(f"No forecast times at or before {target_time} in dataset")
    nearest_time = max(past_times)

    # Select nearest value at that time and coordinates
    value = da.sel(time=nearest_time, lat=lat, lon=lon, method="nearest").item()
    print("nearest_time",nearest_time)

    return value, nearest_time

def floodVolumeProxy(depth,fraction):
    effective_volume = depth * fraction
    return effective_volume
