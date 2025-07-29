#!/usr/bin/env python3
"""
view_las_at_gps_with_building_target.py  
– street‑level LiDAR shot: camera 2 m above ground, looking at building mid‑height.
"""
import numpy as np
import laspy
import open3d as o3d
from pyproj import Transformer, exceptions
import matplotlib.cm as cm

# ─────────────────────────────────────────────────────────────────
# 1.  INPUT PARAMETERS (edit these!)
# ─────────────────────────────────────────────────────────────────
LAS_PATH      = "pointCloud/09LD2580.las"   # your LAS file
CAMERA_LAT    = 35.65293345953977          # camera WGS‑84 latitude
CAMERA_LON    = 139.6139378111143          # camera WGS‑84 longitude
TARGET_LAT    = 35.6527645                 # building WGS‑84 latitude
TARGET_LON    = 139.6139331                 # building WGS‑84 longitude
GROUND_OFFSET = 2.05                        # meters above ground
RADIUS        = 1.0                        # search radius [m] to find building points

WINDOW_WIDTH  = 600
WINDOW_HEIGHT = 300

# ─────────────────────────────────────────────────────────────────
# 2.  initialize Open3D GUI
# ─────────────────────────────────────────────────────────────────
app = o3d.visualization.gui.Application.instance
app.initialize()

# ─────────────────────────────────────────────────────────────────
# 3.  convert WGS‑84 → LAS CRS (EPSG:6677)
# ─────────────────────────────────────────────────────────────────
try:
    tf = Transformer.from_crs("EPSG:4326", "EPSG:6677", always_xy=True)
    cam_e, cam_n = tf.transform(CAMERA_LON, CAMERA_LAT)
    tgt_e, tgt_n = tf.transform(TARGET_LON, TARGET_LAT)
except exceptions.ProjError:
    tf = Transformer.from_crs("EPSG:4326", "EPSG:6677",
                              always_xy=True, skip_equivalent=True)
    cam_e, cam_n = tf.transform(CAMERA_LON, CAMERA_LAT)
    tgt_e, tgt_n = tf.transform(TARGET_LON, TARGET_LAT)

# ─────────────────────────────────────────────────────────────────
# 4.  load LAS and build point cloud
# ─────────────────────────────────────────────────────────────────
las = laspy.read(LAS_PATH)
pts = np.vstack((las.x, las.y, las.z)).T
pcd = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(pts))

# optional height‑based colouring
zmin, zmax = pts[:,2].min(), pts[:,2].max()
norm = (pts[:,2]-zmin)/(zmax-zmin+1e-9)
pcd.colors = o3d.utility.Vector3dVector(cm._colormaps["turbo"](norm)[:,:3])

# ─────────────────────────────────────────────────────────────────
# 5.  sample ground elevation at camera XY
# ─────────────────────────────────────────────────────────────────
d2_cam    = (las.x - cam_e)**2 + (las.y - cam_n)**2
idx_cam   = int(np.argmin(d2_cam))
ground_z  = float(las.z[idx_cam])
EYE       = np.array([cam_e, cam_n, ground_z + GROUND_OFFSET])
print(f"[INFO] Camera @ {EYE[2]:.2f} m above ellipsoid")


# ─────────────────────────────────────────────────────────────────
# 6.  sample building mid‑height at target XY
# ─────────────────────────────────────────────────────────────────
# select all points within RADIUS of the target XY
mask      = (np.hypot(las.x - tgt_e, las.y - tgt_n) < RADIUS)
if not mask.any():
    raise RuntimeError("No points found within radius around target XY!")
building_z = float(np.median(las.z[mask]))  
LOOKAT    = np.array([tgt_e, tgt_n, building_z])
print(f"[INFO] Aiming at building mid-height ≈ {building_z:.2f} m")

# ─────────────────────────────────────────────────────────────────
# 7.  create & show the viewer
# ─────────────────────────────────────────────────────────────────
vis = o3d.visualization.O3DVisualizer("LiDAR Viewer", WINDOW_WIDTH, WINDOW_HEIGHT)
vis.add_geometry("cloud", pcd)

UP = np.array([0,0,1])
vis.scene.camera.look_at(LOOKAT, EYE, UP)

app.add_window(vis)
app.run()
