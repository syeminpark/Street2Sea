import json, math, os
from urllib.parse import urljoin

def load_tiles(tileset_path):
    with open(tileset_path,'r') as f:
        tileset = json.load(f)
    base = os.path.dirname(os.path.abspath(tileset_path)) + '/'
    tiles = []
    def recurse(node, parent_uri=''):
        uri = urljoin(parent_uri, node.get('content',{}).get('uri',''))
        region = node.get('boundingVolume',{}).get('region')
        if region:
            tiles.append({'region': region, 'uri': uri})
        for c in node.get('children',[]):
            recurse(c, parent_uri)
    recurse(tileset['root'], base)
    return tiles

def region_center_deg(region):
    west, south, east, north = [math.degrees(x) for x in region[:4]]
    return ((south + north)/2.0, (west + east)/2.0)

def bearing_deg(lat1, lon1, lat2, lon2):
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    Δλ = math.radians(lon2 - lon1)
    x = math.sin(Δλ)*math.cos(φ2)
    y = math.cos(φ1)*math.sin(φ2) - math.sin(φ1)*math.cos(φ2)*math.cos(Δλ)
    θ = math.degrees(math.atan2(x, y))
    return (θ + 360) % 360

def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    dφ = φ2 - φ1
    dλ = math.radians(lon2 - lon1)
    a = math.sin(dφ/2)**2 + math.cos(φ1)*math.cos(φ2)*math.sin(dλ/2)**2
    return 2 * R * math.asin(math.sqrt(a))

def tiles_in_view(tiles, cam_lat, cam_lon, look_lat, look_lon, h_fov, max_dist=None):
    cam_heading = bearing_deg(cam_lat, cam_lon, look_lat, look_lon)
    half = h_fov / 2.0
    visible = []
    for t in tiles:
        lat_t, lon_t = region_center_deg(t['region'])
        b = bearing_deg(cam_lat, cam_lon, lat_t, lon_t)
        delta = min((b - cam_heading) % 360, (cam_heading - b) % 360)
        if delta > half:
            continue
        if max_dist is not None:
            d = haversine_m(cam_lat, cam_lon, lat_t, lon_t)
            if d > max_dist:
                continue
        visible.append(t['uri'])
    return visible

