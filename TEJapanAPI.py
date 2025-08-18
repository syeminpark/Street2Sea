from ftplib import FTP, error_perm
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from constants import TEJapanDirectory, TEJapanFileType


# Load environment variables
load_dotenv()
FTP_HOST = "ftp.eorc.jaxa.jp"
FTP_USER = os.getenv("FTP_USER")
FTP_PASS = os.getenv("FTP_PASS")
PRED_INTERVAL_HOURS = 3    # interval between predictions
MAX_LEAD_HOURS = 38        # forecast length (hours)
MAX_DAYS_BACK = 7          # how many days back to search for available data


def connect_ftp() -> FTP:
    ftp = FTP(FTP_HOST)
    ftp.login(FTP_USER, FTP_PASS)
    print(f"✅ Connected to {FTP_HOST}")
    return ftp


def list_files_for_date(ftp: FTP, date: datetime) -> None:
    """
    Prints all files in all hourly subfolders of the given date folder (/YYYY/MM/DD).
    """
    date_path = f"/{date.year}/{date.month:02d}"
    try:
        ftp.cwd(date_path)
        print(ftp.nlst())

    except:
        pass



def find_most_recent_valid_folder(
    ftp: FTP,
    target_time: datetime,
    max_days_back: int = MAX_DAYS_BACK
) -> Optional[datetime]:
    for day_offset in range(max_days_back):
        check_date = target_time - timedelta(days=day_offset)
        date_path = f"/{check_date.year}/{check_date.month:02d}/{check_date.day:02d}"
        try:
            ftp.cwd(date_path)
            entries = ftp.nlst()
        except error_perm:
            continue

        hours = sorted([int(e) for e in entries if e.isdigit() and len(e) == 2], reverse=True)
        for hr in hours:
            if day_offset == 0 and hr > target_time.hour:
                continue
            folder_path = f"{date_path}/{hr:02d}"
            try:
                ftp.cwd(folder_path)
                return check_date.replace(hour=hr, minute=0, second=0, microsecond=0)
            except error_perm:
                continue
    return None


def _download_one(ftp: FTP, folder: str, filename: str, dest_dir: str) -> str:
    os.makedirs(dest_dir, exist_ok=True)
    local_path = os.path.join(dest_dir, filename)
    if os.path.exists(local_path):
        print(f"ℹ️  Skipping download; file already exists: {local_path}")
        return local_path
    print(f"⬇ Downloading: {filename}")
    ftp.cwd(folder)
    with open(local_path, "wb") as f:
        ftp.retrbinary(f"RETR {filename}", f.write)
    print(f"✅ Saved: {local_path}")
    return local_path

def find_and_download_flood_data(target_time: datetime) -> Tuple[Optional[datetime], Optional[str]]:
    ftp = connect_ftp()

    run_dt = find_most_recent_valid_folder(ftp, target_time)
    if run_dt is None:
        print(f"❌ No available forecast folder within {MAX_DAYS_BACK} days of {target_time}")
        ftp.quit()
        return None, None

    lead = int((target_time - run_dt).total_seconds() / 3600)
    if lead < 0 or lead > MAX_LEAD_HOURS:
        print(f"❌ Target {target_time} outside valid lead range (0–{MAX_LEAD_HOURS}) from run {run_dt}")
        ftp.quit()
        return None, None

    folder = f"/{run_dt.year}/{run_dt.month:02d}/{run_dt.day:02d}/{run_dt.hour:02d}"
    prefix = target_time.strftime("H%Y%m%d%H")

    try:
        ftp.cwd(folder)
        all_files = ftp.nlst()
    except error_perm:
        print(f"❌ Unable to access folder: {folder}")
        ftp.quit()
        return None, None

    print(f"🔍 Using run at {run_dt:%Y-%m-%d %H:00}, lead={lead}h (folder={folder})")

    dest = TEJapanDirectory.DIRECTORY.value
    types: List[TEJapanFileType] = [TEJapanFileType.DEPTH, TEJapanFileType.FRACTION]

    used_resolution = None
    downloaded_locals = []  # keep local paths for cleanup if partial

    for var in types:
        fn15 = f"TE-JPN15S_MSM_{prefix}_{var.value}.nc"
        fn01 = f"TE-JPN01M_MSM_{prefix}_{var.value}.nc"

        if fn15 in all_files:
            downloaded_locals.append(_download_one(ftp, folder, fn15, dest))
            used_resolution = used_resolution or "15S"
        elif fn01 in all_files:
            downloaded_locals.append(_download_one(ftp, folder, fn01, dest))
            used_resolution = used_resolution or "01M"
        else:
            print(f"❌ No forecast file for {var.value} at {prefix} (checked {fn15} and {fn01})")
            # cleanup any partials we downloaded so we don't leave stale files
            for p in downloaded_locals:
                try: os.remove(p)
                except Exception: pass
            ftp.quit()
            return None, None

    ftp.quit()
    print(f"✅ Completed fetch: run {run_dt:%Y-%m-%d %H:00}, lead {lead}h via {used_resolution}")
    return run_dt, used_resolution


if __name__ == "__main__":
    now = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    find_and_download_flood_data(now)
