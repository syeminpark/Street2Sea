import xarray as xr
from dotenv import load_dotenv
import os 
load_dotenv()

DATA_DIR = os.getenv("TEJAPAN_DATA_DIR")

def openRecentFile(fileType):
    # Find the most recent FLDDPH file in the folder
    flood_files = [
        f for f in os.listdir(DATA_DIR)
        if f.endswith(".nc") and fileType in f
    ]

    if not flood_files:
        raise FileNotFoundError("No FLDDPH .nc files found in the folder.")

    # Optionally, sort and take the most recent (alphabetical sorting often works for timestamped names)
    flood_files.sort()
    latest_file = flood_files[-1]  # the most recent


    # Full path
    file_path = os.path.join(DATA_DIR, latest_file)

    # Load the dataset
    ds = xr.open_dataset(file_path)

    # Print dataset info
    print(f"✅ Opened: {latest_file}")
    print(ds)

openRecentFile("FLDDPH")

