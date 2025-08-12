let moveToken = 0;

function pumpRenderUntilTerrainReady(scene, timeoutMs = 6000) {
  return new Promise((resolve, reject) => {
    let done = false;
    const start = performance.now();

    // Kick renders while tiles are outstanding
    const off = scene.globe.tileLoadProgressEvent.addEventListener((remaining) => {
      scene.requestRender();
      if (remaining === 0 && scene.globe.tilesLoaded && !done) {
        done = true; off(); resolve();
      }
    });

    function step() {
      if (done) return;
      scene.requestRender();
      if (scene.globe.tilesLoaded) { done = true; off(); resolve(); return; }
      if (performance.now() - start > timeoutMs) { done = true; off(); reject(new Error('terrain timeout')); return; }
      requestAnimationFrame(step);
    }
    step();
  });
}


export async function moveCameraTo(viewer, meta) {
  const scene = viewer.scene;
  const token = ++moveToken;

  // Provisional move (ellipsoid height so we see *something* right away)
  const provisionalAlt = 30.0;
  viewer.camera.setView({
    destination: Cesium.Cartesian3.fromDegrees(meta.lng, meta.lat, provisionalAlt),
    orientation: {
      heading: Cesium.Math.toRadians(meta.heading ?? 0),
      pitch:   Cesium.Math.toRadians(meta.pitch ?? 0),
      roll: 0
    }
  });

  // H-FOV: Cesium uses horizontal FOV in landscape
  const aspect = scene.canvas.clientWidth / scene.canvas.clientHeight;
  const fr = viewer.camera.frustum;
  fr.fov  = (aspect >= 1)
    ? Cesium.Math.toRadians(meta.fov ?? 90)
    : 2 * Math.atan(Math.tan(Cesium.Math.toRadians(meta.fov ?? 90)/2) / aspect);
  fr.aspectRatio = aspect;
  fr.near = 0.1;
  fr.far  = viewer.scene.globe.ellipsoid.maximumRadius * 3.0;

  // Start rendering so terrain requests fire
  pumpRenderUntilTerrainReady(scene).catch(()=>{});

  // Now refine height from terrain asynchronously
  try {
    const [s] = await Cesium.sampleTerrainMostDetailed(
      viewer.terrainProvider,
      [Cesium.Cartographic.fromDegrees(meta.lng, meta.lat)]
    );
    if (token !== moveToken) return; // a newer move happened
    const h = (s?.height ?? 0) + 2.5;
    viewer.camera.setView({ destination: Cesium.Cartesian3.fromDegrees(meta.lng, meta.lat, h) });
    scene.requestRender();
  } catch {}
}
