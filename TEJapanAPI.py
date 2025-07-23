from ftplib import FTP, error_perm
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Load FTP credentials from .env
load_dotenv()

FTP_HOST = "ftp.eorc.jaxa.jp"
FTP_USER = os.getenv("FTP_USER")
FTP_PASS = os.getenv("FTP_PASS")
BASE_DIR = "/TE-japan/MSM/hourly"
OUTPUT_DIR = os.getenv("TEJAPAN_DATA_DIR")
MAX_LOOKBACK_HOURS = 24

# Create output directory
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Connect to FTP
ftp = FTP(FTP_HOST)
ftp.login(FTP_USER, FTP_PASS)
print(f"Connected to: {FTP_HOST}")

# Try to find data for up to 24 previous hours
success = False
for attempt in range(MAX_LOOKBACK_HOURS):
    target_time = datetime.now() - timedelta(hours=attempt)
    year = str(target_time.year)
    month = f"{target_time.month:02d}"
    day = f"{target_time.day:02d}"
    hour = f"{target_time.hour:02d}"
    
    full_path = f"{BASE_DIR}/{year}/{month}/{day}/{hour}"
    print(f"Trying: {full_path}")
    
    try:
        ftp.cwd(full_path)
        items = ftp.nlst()

        # Filter only 15S files for FLDFRC and FLDDPH
        files_15s_flood = [
            item for item in items
            if "15S" in item and ("FLDFRC" in item or "FLDDPH" in item)
        ]

        if not files_15s_flood:
            print(f"⚠️ No matching 15S flood files in {full_path}")
            continue

        print(f"\n✅ Found {len(files_15s_flood)} flood-related 15S file(s):")
        for item in files_15s_flood:
            print(f"Downloading: {item}")
            local_path = os.path.join(OUTPUT_DIR, item)
            with open(local_path, "wb") as f:
                ftp.retrbinary(f"RETR {item}", f.write)
            print(f"✅ Downloaded to: {local_path}")
        
        success = True
        break  # Exit loop if download is successful

    except error_perm as e:
        print(f"⛔ Directory not found or no access: {e}")
        continue

ftp.quit()
print("FTP connection closed.")

if not success:
    print("\n⚠️ No flood-related 15S data found in the last 24 hours.")
