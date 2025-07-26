# pull_matsudo_timeseries.py

import os, re
from ftplib import FTP, error_perm
from datetime import datetime
import xarray as xr
import pandas as pd

from constants import TEJapanDirectory, TEJapanFileType

# — replace these or load from your .env —
FTP_HOST = "ftp.eorc.jaxa.jp"
FTP_USER = os.getenv("FTP_USER")
FTP_PASS = os.getenv("FTP_PASS")


def connect_ftp() -> FTP:
    ftp = FTP(FTP_HOST)
    ftp.login(FTP_USER, FTP_PASS)
    return ftp

def list_init_files(ftp: FTP, init_dt: datetime) -> list[str]:
    """
    Returns all filenames in the /YYYY/MM/DD/HH folder for that init.
    """
    path = f"/TE‑japan/MSM/hourly/{init_dt.year}/{init_dt.month:02d}/{init_dt.day:02d}/{init_dt.hour:02d}"
    try:
        ftp.cwd(path)
    except error_perm:
        raise FileNotFoundError(f"No remote folder for init {init_dt:%Y‑%m‑%d %H}: {path}")
    return ftp.nlst()

def download_one(ftp: FTP, remote_dir: str, fn: str, local_dir: str):
    """
    Download a single file if not already present locally.
    """
    os.makedirs(local_dir, exist_ok=True)
    local_path = os.path.join(local_dir, fn)
    if os.path.exists(local_path):
        return local_path
    ftp.cwd(remote_dir)
    with open(local_path, "wb") as f:
        ftp.retrbinary(f"RETR {fn}", f.write)
    return local_path

def extract_datetime_from_filename(fn: str) -> datetime:
    """
    Pulls out the HYYYYMMDDHH stamp from the filename.
    """
    m = re.search(r"_H(\d{10})_", fn)
    if not m:
        raise ValueError(f"Cannot parse timestamp from {fn}")
    return datetime.strptime(m.group(1), "%Y%m%d%H")

def build_timeseries(init_dt: datetime, coords: str):
    ftp = connect_ftp()
    files = list_init_files(ftp, init_dt)

    # split into depth & fraction lists
    depth_fns = [f for f in files if TEJapanFileType.DEPTH.value in f]
    frac_fns  = [f for f in files if TEJapanFileType.FRACTION.value in f]

    results = []

    # local storage directory
    local_dir = TEJapanDirectory.DIRECTORY.value

    for fn_list, product in ((depth_fns, "DEPTH"), (frac_fns, "FRACTION")):
        series = []
        for fn in sorted(fn_list, key=lambda x: extract_datetime_from_filename(x)):
            file_init = extract_datetime_from_filename(fn)
            # download
            path = download_one(ftp,
                                f"/TE‑japan/MSM/hourly/{init_dt.year}/{init_dt.month:02d}/"
                                f"{init_dt.day:02d}/{init_dt.hour:02d}",
                                fn,
                                local_dir)

            # open & sample
            ds = xr.open_dataset(path)
            da = ds[list(ds.data_vars)[0]]

            # the only time in the file:
            t0 = pd.to_datetime(da.coords["time"].values[0])
            lat, lon = map(float, coords.split(","))
            val = da.sel(time=t0, lat=lat, lon=lon, method="nearest").item()

            series.append((t0, val))

        df = pd.DataFrame(series, columns=["forecast_time", product])\
               .set_index("forecast_time")
        results.append(df)

    ftp.quit()
    # merge depth & fraction & compute proxy
    df_all = pd.concat(results, axis=1)
    df_all["VOLUME_PROXY"] = df_all["DEPTH"] * df_all["FRACTION"]
    return df_all

if __name__ == "__main__":
    # 1) Set your init datetime & Matsudo coords
    init_datetime = datetime(2025, 7, 27, 9)
    matsudo_coords = "35.78464365616577,139.9060932646005"

    # 2) Pull the 39‑hour time series
    df = build_timeseries(init_datetime, matsudo_coords)

    # 3) Inspect or save
    print(df)
    df.to_csv("matsudo_20250727_09_timeseries.csv")
    print("Saved to matsudo_20250727_09_timeseries.csv")
