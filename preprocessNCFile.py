import xarray as xr
import os
import re
from datetime import datetime
from constants import TEJapanDirectory, TEJapanFileType
import pandas as pd
import numpy as np


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

    ds = xr.open_dataset(path)

    # --- figure out the resolution --------------------------------------
    if "grid_interval" in ds.attrs:              # best-case: file tells us
        step_deg = float(ds.attrs["grid_interval"])
    else:                                        # fallback: look at coords
        step_deg = float(ds.lon.diff("lon")[0])

    # Convert degrees to an easy label
    #  0.0166667°  ≃ 1-minute  → “1m”
    #  0.0041667°  ≃ 15-second → “15s”
    if abs(step_deg - 0.0166667) < 1e-4:
        resolution = "1m"
    elif abs(step_deg - 0.0041667) < 1e-4:
        resolution = "15s"
    else:
        resolution = f"{step_deg:.6f}°"          # give the raw spacing

    ds.attrs["resolution"] = resolution          # stash it in the Dataset
    return ds



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



def buildDepthPatch(da, coords, filetype, radius_m=60,):
    grid_step=0

    if filetype.lower() in {"1m", "1min"}:
        grid_step = 1850
    elif filetype.lower() in {"15s", "15sec"}:
        grid_step = 500
    else:
        raise ValueError("filetype must be '1m' or '15s'")


    if isinstance(coords, str):
        lat0, lon0 = map(float, coords.split(","))
    else:
        lat0 = coords["lat"] if "lat" in coords else coords["latitude"]
        lon0 = coords["lng"] if "lng" in coords else coords["longitude"]

    # How many cells from centre → edge?
    half_cells = int(np.ceil(radius_m / grid_step))

    # Index of nearest grid point
    j = int(abs(lat0 - da.lat[0].values) / da.lat.diff('lat')[0].values)
    i = int(abs(lon0 - da.lon[0].values) / da.lon.diff('lon')[0].values)

    # Slice row/col ranges (clamp to dataset bounds)
    j0 = max(j - half_cells, 0)
    j1 = min(j + half_cells, da.sizes["lat"] - 1)
    i0 = max(i - half_cells, 0)
    i1 = min(i + half_cells, da.sizes["lon"] - 1)

    sub = da.isel(lat=slice(j0, j1 + 1), lon=slice(i0, i1 + 1))
    sub = sub.where(sub < 1e19, 0)          # use *sub* on both sides

    print("Depth patch shape:", sub.shape)
    print("Min/max:", np.nanmin(sub), np.nanmax(sub))
    print("Unique values:", np.unique(sub))


    return dict(
    depth = sub.squeeze().values.tolist(),
    lon0    = float(sub.lon[0].values),
    lat0    = float(sub.lat[0].values),
    stepDeg = float(sub.lon.diff('lon')[0].values)
)


