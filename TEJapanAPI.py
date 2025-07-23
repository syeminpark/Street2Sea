from ftplib import FTP, error_perm
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Load credentials and set default paths
load_dotenv()
FTP_HOST = "ftp.eorc.jaxa.jp"
FTP_USER = os.getenv("FTP_USER")
FTP_PASS = os.getenv("FTP_PASS")
BASE_DIR = "/TE-japan/MSM/hourly"
OUTPUT_DIR = os.getenv("TEJAPAN_DATA_DIR")
MAX_LOOKBACK_HOURS = 24


def connect_ftp():
    ftp = FTP(FTP_HOST)
    ftp.login(FTP_USER, FTP_PASS)
    print(f"✅ Connected to: {FTP_HOST}")
    return ftp


def build_path_from_datetime(dt: datetime) -> str:
    return f"{BASE_DIR}/{dt.year}/{dt.month:02d}/{dt.day:02d}/{dt.hour:02d}"


def get_flood_files(ftp: FTP, full_path: str):
    try:
        ftp.cwd(full_path)
        files = ftp.nlst()
        return [
            f for f in files
            if "15S" in f and ("FLDFRC" in f or "FLDDPH" in f)
        ]
    except error_perm:
        return []


def download_files(ftp: FTP, files, destination_dir):
    os.makedirs(destination_dir, exist_ok=True)
    for filename in files:
        print(f"⬇️  Downloading: {filename}")
        local_path = os.path.join(destination_dir, filename)
        with open(local_path, "wb") as f:
            ftp.retrbinary(f"RETR " + filename, f.write)
        print(f"✅ Saved to: {local_path}")


def find_and_download_flood_data(start_time: datetime):
    ftp = connect_ftp()
    for hour_back in range(MAX_LOOKBACK_HOURS):
        dt = start_time - timedelta(hours=hour_back)
        path = build_path_from_datetime(dt)
        print(f"🔍 Checking: {path}")
        files = get_flood_files(ftp, path)
        if files:
            print(f"✅ Found {len(files)} matching file(s) at {path}")
            download_files(ftp, files, OUTPUT_DIR)
            ftp.quit()
            return dt  # return the matched datetime
    ftp.quit()
    print("⚠️ No matching flood data found within lookback window.")
    return None
