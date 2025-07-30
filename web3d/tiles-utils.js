/* Utilities for loading and filtering 3D tiles in JavaScript (browser-friendly) */

/**
 * Load a Cesium-style tileset JSON and collect all tile URIs with region volumes.
 * @param {string} tilesetUrl - URL to the tileset JSON file (can be relative)
 * @returns {Promise<Array<{ region: number[], uri: string }>>}
 */
export async function loadTiles(tilesetUrl) {
  // Resolve the tileset URL against the current page location
  const tilesetAbsoluteUrl = new URL(tilesetUrl, window.location.href).href;
  const response = await fetch(tilesetAbsoluteUrl);
  if (!response.ok) {
    throw new Error(`Failed to load tileset: ${response.status} ${response.statusText}`);
  }
  const tileset = await response.json();

  // Compute a valid base URL (ensures trailing slash) for resolving relative URIs
  const base = new URL('.', tilesetAbsoluteUrl).href;
  const tiles = [];

  function recurse(node) {
    const contentUri = node.content && node.content.uri;
    const uri = contentUri
      ? new URL(contentUri, base).href
      : null;

    const region = node.boundingVolume && node.boundingVolume.region;
    if (region && uri) {
      tiles.push({ region, uri });
    }

    if (Array.isArray(node.children)) {
      node.children.forEach(recurse);
    }
  }

  recurse(tileset.root);
  return tiles;
}

/**
 * Compute the center latitude/longitude (in degrees) of a region array.
 */
export function regionCenterDeg(region) {
  const [west, south, east, north] = region;
  const lat = ((south + north) / 2) * (180 / Math.PI);
  const lon = ((west + east) / 2) * (180 / Math.PI);
  return [lat, lon];
}

/**
 * Compute initial bearing (degrees) from (lat1, lon1) to (lat2, lon2).
 */
export function bearingDeg(lat1, lon1, lat2, lon2) {
  const φ1 = lat1 * Math.PI / 180;
  const φ2 = lat2 * Math.PI / 180;
  const Δλ = (lon2 - lon1) * Math.PI / 180;
  const x = Math.sin(Δλ) * Math.cos(φ2);
  const y = Math.cos(φ1) * Math.sin(φ2)
          - Math.sin(φ1) * Math.cos(φ2) * Math.cos(Δλ);
  const θ = Math.atan2(x, y) * 180 / Math.PI;
  return (θ + 360) % 360;
}

/**
 * Haversine distance between two points (meters).
 */
export function haversineM(lat1, lon1, lat2, lon2) {
  const R = 6371000;
  const φ1 = lat1 * Math.PI / 180;
  const φ2 = lat2 * Math.PI / 180;
  const dφ = (lat2 - lat1) * Math.PI / 180;
  const dλ = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dφ / 2) ** 2
          + Math.cos(φ1) * Math.cos(φ2) * Math.sin(dλ / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

/**
 * Filter tiles by horizontal field of view and optional max distance.
 */
export function tilesInView(tiles, camLat, camLon, lookLat, lookLon, hFov, maxDist) {
  const camHeading = bearingDeg(camLat, camLon, lookLat, lookLon);
  const half = hFov / 2;
  const visible = [];

  for (const t of tiles) {
    const [latT, lonT] = regionCenterDeg(t.region);
    const b = bearingDeg(camLat, camLon, latT, lonT);
    const delta = Math.min((b - camHeading + 360) % 360, (camHeading - b + 360) % 360);
    if (delta > half) continue;
    if (maxDist != null) {
      const d = haversineM(camLat, camLon, latT, lonT);
      if (d > maxDist) continue;
    }
    visible.push(t.uri);
  }
  return visible;
}
