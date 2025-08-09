// waitHelpers.js
export function waitForNextRender(input) {
  const scene = input?.scene ? input.scene : input;
  if (!scene?.postRender?.addEventListener) {
    throw new Error("waitForNextRender: invalid Scene or postRender");
  }
  return new Promise((resolve) => {
    const off = scene.postRender.addEventListener(() => { off(); resolve(); });
    scene.requestRender();
  });
}

export async function waitForFrames(input, n = 2) {
  const scene = input?.scene ? input.scene : input;
  for (let i = 0; i < n; i++) await waitForNextRender(scene);
}

/**
 * Wait until:
 *  - every Cesium3DTileset in `tilesets` reports idle (via loadProgress or allTilesLoaded)
 *  - the globe (terrain/imagery) is idle (tileLoadProgressEvent==0 OR globe.tilesLoaded)
 * Then render one more frame.
 */
export function waitForTilesetsIdle(viewer, tilesets = []) {
  if (!viewer?.scene) throw new Error("waitForTilesetsIdle: bad viewer");
  const { scene } = viewer;

  return new Promise((resolve) => {
    // Track tileset states
    const tsDone = new Map();
    const unsubTiles = [];

    // Prefer tileset.loadProgress; fall back to allTilesLoaded
    for (const t of tilesets) {
      tsDone.set(t, false);

      if (t?.loadProgress?.addEventListener) {
        const rm = t.loadProgress.addEventListener((pending, processing) => {
          tsDone.set(t, pending === 0 && processing === 0);
        });
        unsubTiles.push(rm);
      } else if (t?.allTilesLoaded?.addEventListener) {
        const rm = t.allTilesLoaded.addEventListener(() => {
          tsDone.set(t, true);
        });
        unsubTiles.push(rm);
      } else {
        // Unknown object; don't block on it
        tsDone.set(t, true);
        console.warn("Tileset lacks loadProgress/allTilesLoaded", t);
      }
    }

    // Track globe (terrain/imagery) load progress
    let globeIdle = !!scene.globe?.tilesLoaded;
    let offGlobe = null;
    if (scene.globe?.tileLoadProgressEvent?.addEventListener) {
      offGlobe = scene.globe.tileLoadProgressEvent.addEventListener((q) => {
        globeIdle = (q === 0);
      });
    }

    const off = scene.postRender.addEventListener(async () => {
      const tilesetsIdle = [...tsDone.values()].every(Boolean);
      const globeOk = globeIdle || !!scene.globe?.tilesLoaded;

      if (tilesetsIdle && globeOk) {
        off();
        unsubTiles.forEach((fn) => fn && fn());
        if (offGlobe) offGlobe();
        // one more frame to ensure draw commands for the idle state were submitted
        await waitForNextRender(scene);
        resolve();
      }
    });

    scene.requestRender();
  });
}
