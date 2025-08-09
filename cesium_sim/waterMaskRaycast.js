// waterMaskRaycast.js
export async function makeWaterMaskForView(
  viewer,
  {
    waterLevelUp,
    downsample = 4,
    underRange = 5.0,
    overRange  = 10.0,
    includeBuildings = false   // <-- new
  }
) {
  const scene = viewer.scene, globe = scene.globe, cam = scene.camera;
  scene.render();

  const W = Math.max(1, Math.floor(scene.canvas.width  / downsample));
  const H = Math.max(1, Math.floor(scene.canvas.height / downsample));

  const canvas = document.createElement('canvas');
  canvas.width = W; canvas.height = H;
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  const img = ctx.createImageData(W, H);

  const pickPos = new Cesium.Cartesian2();
  const tmpCarto = new Cesium.Cartographic();
  const dirLen = 1.0; // Cesium ray direction is normalized

  let idx = 0;
  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++, idx++) {
      pickPos.x = (x + 0.5) * downsample;
      pickPos.y = (y + 0.5) * downsample;

      const ray = cam.getPickRay(pickPos);

      // Terrain hit
      const gHit = globe.pick(ray, scene);
      let nearestPos = gHit;
      let nearestT = Number.POSITIVE_INFINITY;
      if (Cesium.defined(gHit)) {
        nearestT = Cesium.Cartesian3.distance(ray.origin, gHit) / dirLen;
      }

      // Optional: 3D Tiles / scene geometry hit (synchronous pick)
      if (includeBuildings) {
        const sRes = scene.pickFromRay(ray); // closest non-terrain primitive
        if (sRes && sRes.position) {
          const t = Cesium.Cartesian3.distance(ray.origin, sRes.position) / dirLen;
          if (t < nearestT) {
            nearestT = t;
            nearestPos = sRes.position;
          }
        }
      }

      let R = 0, G = 0, B = 0;
      if (Cesium.defined(nearestPos)) {
        const carto = Cesium.Cartographic.fromCartesian(nearestPos, globe.ellipsoid, tmpCarto);
        const up = carto.height;

        const dUnder = Math.max(0, waterLevelUp - up);
        const dOver  = Math.max(0, up - waterLevelUp);

        R = Math.min(255, Math.round(255 * (dUnder / Math.max(underRange, 1e-6))));
        G = Math.min(255, Math.round(255 * (dOver  / Math.max(overRange,  1e-6))));
        B = dUnder > 0 ? 255 : 0;
      }

      const p = 4 * idx;
      img.data[p+0] = R; img.data[p+1] = G; img.data[p+2] = B; img.data[p+3] = 255;
    }
  }

  ctx.putImageData(img, 0, 0);

  // Upscale to viewport size (nearest-neighbor)
  const up = document.createElement('canvas');
  up.width = scene.canvas.width; up.height = scene.canvas.height;
  const upctx = up.getContext('2d'); upctx.imageSmoothingEnabled = false;
  upctx.drawImage(canvas, 0, 0, up.width, up.height);

  return { lowRes: canvas, mask: up };
}
