import os
from dotenv import load_dotenv
from ftplib import FTP

load_dotenv()

output_dir = "TEJapn_Data"
os.makedirs(output_dir, exist_ok=True)




FTP_USER = os.getenv("FTP_USER")
FTP_PASS = os.getenv("FTP_PASS")
FTP_HOST = "ftp.eorc.jaxa.jp"


def getTEJapanData():
    ftp = FTP(FTP_HOST)
    ftp.login(FTP_USER, FTP_PASS)
    print(f"Connected to: {FTP_HOST}")

    ftp.cwd("/TE-global/JRA55/daily")
    files = ftp.nlst()
    print("Files available:")
    for f in files[:10]:  # just show the first 10 files
        print(f)

    # Download one file (example)
    filename = files[0]
    with open(filename, "wb") as f:
        ftp.retrbinary(f"RETR {filename}", f.write)
        print(f"Downloaded: {filename}")

    ftp.quit()

getTEJapanData()
