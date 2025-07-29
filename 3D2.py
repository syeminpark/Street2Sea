import os, struct
import open3d as o3d


# ─── 1) CONFIGURE HERE ─────────────────────────────────────────────────────────
TILESET_PATH = 'setagaya_no_texture/tileset.json'

# Camera position:
CAM_LAT, CAM_LON     = 35.65293345953977, 139.6139378111143

# Where the camera is looking:
LOOK_LAT, LOOK_LON   = 35.6527645, 139.6139331

# Horizontal field‑of‑view (degrees):
H_FOV_DEG            = 120

# (Optional) maximum distance to consider (meters). Set to None to disable:
MAX_DISTANCE_METERS  = 500
# ───────────────────────────────────────────────────────────────────────────────



if __name__ == '__main__':
    tiles = load_tiles(TILESET_PATH)
    visible = tiles_in_view(
        tiles,
        CAM_LAT,    CAM_LON,
        LOOK_LAT,   LOOK_LON,
        H_FOV_DEG,
        max_dist=MAX_DISTANCE_METERS
    )

    print(f"{len(visible)} tiles likely in view:\n")
    for uri in visible:
        print("  ", uri)
