# te_japan_downloader.py

from ftplib import FTP, error_perm
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
from typing import List

from constants import TEJapanDirectory, TEJapanFileType

# —————————————————————————————————————————————————————
# Load FTP credentials

load_dotenv()
FTP_HOST           = "ftp.eorc.jaxa.jp"
FTP_USER           = os.getenv("FTP_USER")
FTP_PASS           = os.getenv("FTP_PASS")
MAX_LOOKBACK_HOURS = 24


def connect_ftp() -> FTP:
    ftp = FTP(FTP_HOST)
    ftp.login(FTP_USER, FTP_PASS)
    print(f"✅ Connected to {FTP_HOST}")
    return ftp


def build_path_from_datetime(dt: datetime) -> str:
    """Build folder path for a given datetime: /YYYY/MM/DD/HH"""
    return f"/{dt.year}/{dt.month:02d}/{dt.day:02d}/{dt.hour:02d}"


def _download_one(ftp: FTP, folder: str, filename: str, dest_dir: str):
    """Helper to fetch a single file from `folder` and save into `dest_dir`."""
    os.makedirs(dest_dir, exist_ok=True)
    local_path = os.path.join(dest_dir, filename)
    print(f"⬇ Downloading: {filename}")
    ftp.cwd(folder)
    print("Remote files in", folder)
    for fn in ftp.nlst():
        if fn.endswith(".nc"):
            print("  •", fn)
    with open(local_path, "wb") as f:
        ftp.retrbinary(f"RETR {filename}", f.write)
    print(f"✅ Saved: {local_path}")


def find_and_download_flood_data(start_time: datetime):
    """
    Scans backward up to MAX_LOOKBACK_HOURS:
      • In each hour-folder, first try to download
        TE-JPN15S_MSM_HYYYYMMDDHH_FLDDPH.nc and
        TE-JPN15S_MSM_HYYYYMMDDHH_FLDFRC.nc.
      • If either is missing, fall back for each missing variable
        to TE-JPN01M_MSM_HYYYYMMDDHH_<VAR>.nc.
    Stops after fetching both DEPTH and FRACTION files for the first hour found.
    """
    ftp = connect_ftp()
    types: List[TEJapanFileType] = [
        TEJapanFileType.DEPTH,
        TEJapanFileType.FRACTION
    ]
    dest = TEJapanDirectory.DIRECTORY.value

    for h in range(MAX_LOOKBACK_HOURS):
        dt = start_time - timedelta(hours=h)
        folder = build_path_from_datetime(dt)
        prefix = dt.strftime("H%Y%m%d%H")  # e.g. "H2025072606"

        try:
            ftp.cwd(folder)
            all_files = ftp.nlst()
        except error_perm:
            continue  # folder doesn't exist, try previous hour

        # If no .nc at all, skip
        if not any(fn.endswith(".nc") for fn in all_files):
            continue

        print(f"🔍 Found files in {folder}; attempting per-variable resolution fallback")

        downloaded = []

        # For each variable type, try 15S first, else 01M
        for var in types:
            fname_15 = f"TE-JPN15S_MSM_{prefix}_{var.value}.nc"
            fname_01 = f"TE-JPN01M_MSM_{prefix}_{var.value}.nc"

            if fname_15 in all_files:
                _download_one(ftp, folder, fname_15, dest)
                downloaded.append((var, "15S"))
            elif fname_01 in all_files:
                _download_one(ftp, folder, fname_01, dest)
                downloaded.append((var, "01M"))
            else:
                print(f"⚠️ Neither 15S nor 01M found for {var.value} at {prefix}")
                break  # missing this variable, cannot complete pair

        # If we downloaded both variables, we’re done
        if len(downloaded) == len(types):
            ftp.quit()
            print("✅ Completed fetch for hour:", dt.strftime("%Y-%m-%d %H:00"))
            for var, res in downloaded:
                print(f"   • {var.name} via {res}")
            return dt

    ftp.quit()
    print("⚠️ No complete flood-depth+fraction pair found in last 24 h.")
    return None

