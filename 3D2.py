import os, struct
import open3d as o3d
from dynamicModelSelection import load_tiles, tiles_in_view


# ─── 1) CONFIGURE HERE ─────────────────────────────────────────────────────────
TILESET_PATH = 'setagaya_no_texture/tileset.json'
DATA_DIR = 'setagaya_no_texture/data'

# Camera position:
CAM_LAT, CAM_LON     = 35.65293345953977, 139.6139378111143

# Where the camera is looking:
LOOK_LAT, LOOK_LON   = 35.6527645, 139.6139331

# Horizontal field‑of‑view (degrees):
H_FOV_DEG            = 120

# (Optional) maximum distance to consider (meters). Set to None to disable:
MAX_DISTANCE_METERS  = 500
# ───────────────────────────────────────────────────────────────────────────────

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

visible_tiles = visible  # from your tiles_in_view(...) call

def extract_glb_bytes(b3dm_path):
    with open(b3dm_path, 'rb') as f:
        header = f.read(28)
        magic,ver,blen,ftj,ftb,btj,btb = struct.unpack('<4sIIIIII', header)
        assert magic == b'b3dm'
        f.read(ftj + ftb + btj + btb)
        return f.read()

# 2) Loop through your visible tiles, extract the GLB, load it into Open3D:
meshes = []
for uri in visible_tiles:
    # uri is something like ".../data123.b3dm"
    b3dm_path = uri
    glb_bytes = extract_glb_bytes(b3dm_path)
    # write a temp file (Open3D currently reads from disk)
    tmp_glb = '/tmp/tmp_tile.glb'
    with open(tmp_glb, 'wb') as g:
        g.write(glb_bytes)

    # Try to read it directly as a mesh:
    mesh = o3d.io.read_triangle_mesh(tmp_glb)
    if not mesh.is_empty():
        mesh.compute_vertex_normals()
        meshes.append(mesh)

# 3) Visualize all at once
if meshes:
    o3d.visualization.draw_geometries(meshes)
else:
    print("No meshes loaded—check that your GLB extraction worked!")
