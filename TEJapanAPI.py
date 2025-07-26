from ftplib import FTP, error_perm
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from constants import TEJapanDirectory, TEJapanFileType

load_dotenv()
FTP_HOST             = "ftp.eorc.jaxa.jp"
FTP_USER             = os.getenv("FTP_USER")
FTP_PASS             = os.getenv("FTP_PASS")
PRED_INTERVAL_HOURS  = 3    # interval between predictions
MAX_LEAD_HOURS       = 38   # forecast length (hours)


def connect_ftp() -> FTP:
    ftp = FTP(FTP_HOST)
    ftp.login(FTP_USER, FTP_PASS)
    print(f"✅ Connected to {FTP_HOST}")
    return ftp


def build_path_from_datetime(dt: datetime) -> str:
    """Builds folder path for a given datetime: /YYYY/MM/DD/HH"""
    return f"/{dt.year}/{dt.month:02d}/{dt.day:02d}/{dt.hour:02d}"


def _download_one(ftp: FTP, folder: str, filename: str, dest_dir: str) -> None:
    """Fetch a single file from folder and save into dest_dir."""
    os.makedirs(dest_dir, exist_ok=True)
    local_path = os.path.join(dest_dir, filename)
    print(f"⬇ Downloading: {filename}")
    ftp.cwd(folder)
    with open(local_path, "wb") as f:
        ftp.retrbinary(f"RETR {filename}", f.write)
    print(f"✅ Saved: {local_path}")


def find_and_download_flood_data(
    target_time: datetime
) -> Tuple[Optional[datetime], Optional[str]]:
    """
    Given a target datetime, selects the prediction start time on the 3-hour grid,
    then downloads the exact-lead DEPTH and FRACTION files matching the user hour.
    Returns the chosen start datetime and resolution string ("15S" or "01M").
    """
    # find the 3-hourly run that generated the forecast
    base_hour = target_time.hour - (target_time.hour % PRED_INTERVAL_HOURS)
    run_dt = target_time.replace(hour=base_hour, minute=0, second=0, microsecond=0)

    # compute lead hour (difference between target and run)
    delta = target_time - run_dt
    lead = int(delta.total_seconds() / 3600)
    if lead < 0 or lead > MAX_LEAD_HOURS:
        print(f"❌ Requested time {target_time} is {lead}h from run; out of valid range 0–{MAX_LEAD_HOURS}")
        return None, None

    ftp = connect_ftp()
    types: List[TEJapanFileType] = [
        TEJapanFileType.DEPTH,
        TEJapanFileType.FRACTION
    ]
    dest = TEJapanDirectory.DIRECTORY.value

    folder = build_path_from_datetime(run_dt)
    prefix = run_dt.strftime("H%Y%m%d%H")  # e.g. "H2025072606"
    lead_str = f"{lead:02d}"

    try:
        ftp.cwd(folder)
        all_files = ftp.nlst()
    except error_perm:
        print(f"❌ Prediction folder not found: {folder}")
        return None, None

    if not any(fn.endswith(".nc") for fn in all_files):
        print(f"❌ No .nc files in folder: {folder}")
        return None, None

    print(f"🔍 Using run at {run_dt:%Y-%m-%d %H:00}, lead={lead}h (folder={folder})")

    downloaded = []
    used_resolution = None

    # attempt exact-lead file downloads
    for var in types:
        fn15 = f"TE-JPN15S_MSM_{prefix}_{lead_str}_{var.value}.nc"
        fn01 = f"TE-JPN01M_MSM_{prefix}_{lead_str}_{var.value}.nc"

        if fn15 in all_files:
            _download_one(ftp, folder, fn15, dest)
            downloaded.append(var)
            used_resolution = "15S"
        elif fn01 in all_files:
            _download_one(ftp, folder, fn01, dest)
            downloaded.append(var)
            if used_resolution is None:
                used_resolution = "01M"
        else:
            print(f"⚠️ Missing both 15S & 01M for {var.value} at lead {lead}")
            break

    ftp.quit()

    if len(downloaded) == len(types):
        print(f"✅ Completed fetch for run {run_dt:%Y-%m-%d %H:00}, lead {lead}h via {used_resolution}")
        return run_dt, used_resolution
    else:
        print(f"⚠️ Could not fetch all files for lead {lead}")
        return run_dt, None


