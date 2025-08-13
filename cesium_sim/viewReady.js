// viewReady.js

/** Tiny helper: resolve on the next rendered frame. */
export function nextFrame(viewer) {
  return new Promise((resolve) => {
    const once = () => {
      viewer.scene.postRender.removeEventListener(once);
      resolve();
    };
    viewer.scene.postRender.addEventListener(once);
    viewer.scene.requestRender();
  });
}

/**
 * Show a small loading HUD and resolve when terrain + all provided tilesets are loaded.
 * Uses ground-truth booleans (tilesLoaded) instead of progress counters so it won’t get stuck.
 *
 * @param {Cesium.Viewer} viewer
 * @param {Cesium.Cesium3DTileset|Cesium.Cesium3DTileset[]} tilesets
 * @returns {{readyPromise: Promise<void>, dispose: () => void}}
 */
export function attachViewLoadHUD(viewer, tilesets = []) {
  const div = document.createElement('div');
  Object.assign(div.style, {
    position: 'absolute',
    right: '10px',
    top: '10px',
    padding: '6px 10px',
    color: '#fff',
    font: '12px/1.2 sans-serif',
    borderRadius: '6px',
    zIndex: 9999,
    pointerEvents: 'none',
    background: 'rgba(255,165,0,.85)', // orange = loading
  });
  viewer.container.appendChild(div);

  // progress counts purely for display; not used for readiness
  let terr = 1;
  let tiles = 0;

  // require a couple consecutive "ready" frames to be safe
  let stable = 0;
  const needStable = 2;

  // safety valve: never wait forever
  const start = performance.now();
  const TIMEOUT_MS = 6000;

  // Normalize tilesets input
  const tsList = (Array.isArray(tilesets) ? tilesets : [tilesets]).filter(Boolean);

  // Terrain progress (display only)
  const onTerr = (n) => {
    terr = n;
  };
  viewer.scene.globe.tileLoadProgressEvent.addEventListener(onTerr);

  // 3D Tiles progress (display only)
  const tsHandlers = [];
  tsList.forEach((ts) => {
    const h = (n) => {
      tiles = n;
    };
    ts.tileLoadProgressEvent?.addEventListener?.(h);
    tsHandlers.push([ts, h]);
  });

  // HUD update on every frame
  const onPost = () => {
    const terrainLoaded = viewer.scene.globe.tilesLoaded;
    const tilesLoaded = tsList.length ? tsList.every((t) => t.tilesLoaded) : true;
    const loading = !(terrainLoaded && tilesLoaded);

    stable = loading ? 0 : stable + 1;

    div.textContent = loading
      ? `Loading… terrain:${terr} tiles:${tiles}`
      : `Ready`;
    div.style.background = loading
      ? 'rgba(255,165,0,.85)'
      : 'rgba(46,125,50,.85)'; // green = ready
  };
  viewer.scene.postRender.addEventListener(onPost);

  // Promise that resolves when ready (or timeout)
  const readyPromise = new Promise((resolve) => {
    const check = () => {
      const terrainLoaded = viewer.scene.globe.tilesLoaded;
      const tilesLoaded = tsList.length ? tsList.every((t) => t.tilesLoaded) : true;
      const loading = !(terrainLoaded && tilesLoaded);

      if (!loading && stable >= needStable) {
        cleanup();
        resolve();
      } else if (performance.now() - start > TIMEOUT_MS) {
        // Safety: proceed even if counters bug out
        console.warn('[HUD] timeout; proceeding');
        cleanup();
        resolve();
      } else {
        viewer.scene.requestRender();
        requestAnimationFrame(check);
      }
    };
    requestAnimationFrame(check);
  });

  function cleanup() {
    viewer.scene.globe.tileLoadProgressEvent.removeEventListener(onTerr);
    tsHandlers.forEach(([ts, h]) => ts.tileLoadProgressEvent?.removeEventListener?.(h));
    viewer.scene.postRender.removeEventListener(onPost);
    div.remove();
  }

  return { readyPromise, dispose: cleanup };
}

/**
 * Temporarily hide overlay entities and adjust the near plane while running an async task,
 * then restore previous state (used to avoid the overlay “painting” into masks).
 *
 * @param {Cesium.Viewer} viewer
 * @param {Cesium.Entity|null} waterEntity
 * @param {Cesium.Entity|null} markerEntity
 * @param {() => (Promise<any>|any)} run
 */
export async function withOverlayHidden(viewer, waterEntity, markerEntity, run) {
  const prev = {
    near: viewer.camera.frustum.near,
    water: waterEntity?.show ?? null,
    marker: markerEntity?.show ?? null,
  };

  // hide entities that might affect mask pixels
  if (waterEntity) waterEntity.show = false;
  if (markerEntity) markerEntity.show = false;

  // tighten near plane to reduce depth noise during mask capture
  viewer.camera.frustum.near = Math.max(prev.near, 0.5);

  viewer.scene.requestRender();
  await nextFrame(viewer);

  try {
    return await run();
  } finally {
    if (waterEntity && prev.water !== null) waterEntity.show = prev.water;
    if (markerEntity && prev.marker !== null) markerEntity.show = prev.marker;
    viewer.camera.frustum.near = prev.near;

    viewer.scene.requestRender();
    await nextFrame(viewer);
  }
}
