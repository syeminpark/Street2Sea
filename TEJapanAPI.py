# te_japan_downloader.py

from ftplib import FTP, error_perm
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
from typing import List

from constants import TEJapanDirectory, TEJapanFileType

# —————————————————————————————————————————————————————
# Load FTP credentials and constants

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
    """“/YYYY/MM/DD/HH”"""
    return f"/{dt.year}/{dt.month:02d}/{dt.day:02d}/{dt.hour:02d}"


def get_flood_files(
    ftp: FTP,
    folder: str,
    types: List[TEJapanFileType],
    resolution: str,
    hour_prefix: str
) -> List[str]:
    """
    In `folder`, return only files that:
      • end with .nc  
      • contain HYYYYMMDDHH  
      • contain “15S” or “01M” as specified  
      • contain one of the type keywords (FLDDPH or FLDFRC)
    """
    try:
        ftp.cwd(folder)
        all_files = ftp.nlst()
    except error_perm:
        return []

    keywords = [t.value for t in types]
    return [
        fn for fn in all_files
        if fn.endswith(".nc")
        and resolution  in fn
        and hour_prefix in fn
        and any(k in fn for k in keywords)
    ]


def download_files(ftp: FTP, files: List[str], dest_dir: str):
    os.makedirs(dest_dir, exist_ok=True)
    for fn in files:
        local = os.path.join(dest_dir, fn)
        try:
            rsize = ftp.size(fn)
        except:
            rsize = None

        if rsize is not None and os.path.exists(local) and os.path.getsize(local) == rsize:
            print(f"⏭ Skipping existing: {fn}")
            continue

        print(f"⬇ Downloading: {fn}")
        with open(local, "wb") as f:
            ftp.retrbinary(f"RETR {fn}", f.write)
        print(f"✅ Saved {local}")


def find_and_download_flood_data(start_time: datetime):
    ftp   = connect_ftp()
    types = [TEJapanFileType.DEPTH, TEJapanFileType.FRACTION]

    for h in range(MAX_LOOKBACK_HOURS):
        dt     = start_time - timedelta(hours=h)
        folder = build_path_from_datetime(dt)
        prefix = dt.strftime("H%Y%m%d%H")  # e.g. "H2025072606"

        # 1) Try 15 s, but only accept if *both* depth+fraction are present
        files_15 = get_flood_files(ftp, folder, types, resolution="15S", hour_prefix=prefix)
        # extract which types we actually found:
        found_keys_15 = { t.value for t in types if any(t.value in fn for fn in files_15) }
        if found_keys_15 == { TEJapanFileType.DEPTH.value, TEJapanFileType.FRACTION.value }:
            print(f"✅ 15S depth+frac both present for {prefix}: {files_15}")
            download_files(ftp, files_15, TEJapanDirectory.DIRECTORY.value)
            ftp.quit()
            return dt, "15S"
        else:
            # drop the partial 15 s results so we can fallback
            if files_15:
                print(f"⚠️ Only partial 15S data for {prefix} ({found_keys_15}); falling back")
            files_15 = []

        # 2) Fallback to 01 m (and here we know both must exist, since ftp always has both)
        files_01 = get_flood_files(ftp, folder, types, resolution="01M", hour_prefix=prefix)
        found_keys_01 = { t.value for t in types if any(t.value in fn for fn in files_01) }
        if found_keys_01 == { TEJapanFileType.DEPTH.value, TEJapanFileType.FRACTION.value }:
            print(f"🔁 01M depth+frac for {prefix}: {files_01}")
            download_files(ftp, files_01, TEJapanDirectory.DIRECTORY.value)
            ftp.quit()
            return dt, "01M"

    ftp.quit()
    print("⚠️ No flood depth+fraction found in the last 24 h.")
    return None, None

if __name__ == "__main__":
    now = datetime.utcnow()
    dt, res = find_and_download_flood_data(now)      # ← make sure this is the call you use
    if dt:
        print(f"Finished: downloaded {res} data for hour {dt.strftime('%Y-%m-%d %H:00')}")
    else:
        print("No files downloaded.")