// viewReady.js
export function attachViewLoadHUD(viewer, tilesets = []) {
  const div = document.createElement('div');
  Object.assign(div.style, {
    position: 'absolute', right: '10px', top: '10px',
    padding: '6px 10px', color: '#fff', font: '12px/1.2 sans-serif',
    borderRadius: '6px', zIndex: 9999, pointerEvents: 'none',
    background: 'rgba(255,165,0,.85)' // orange = loading
  });
  viewer.container.appendChild(div);

  let terr = 1;               // terrain tiles in progress
  let tiles = 0;              // 3D tiles in progress (visible set)
  let stable = 0;             // consecutive frames at zero
  const needStable = 2;       // be a bit conservative

  // Terrain progress
  const onTerr = (n) => { terr = n; };
  viewer.scene.globe.tileLoadProgressEvent.addEventListener(onTerr);

  // 3D Tiles progress
  const tsHandlers = [];
  (Array.isArray(tilesets) ? tilesets : [tilesets])
    .filter(Boolean)
    .forEach(ts => {
      const h = (n) => { tiles = n; };
      if (ts.tileLoadProgressEvent?.addEventListener) {
        ts.tileLoadProgressEvent.addEventListener(h);
        tsHandlers.push([ts, h]);
      }
    });

  // HUD update each frame
  const onPost = () => {
    const loading = (terr > 0 || tiles > 0);
    if (loading) stable = 0; else stable++;
    div.textContent = loading
      ? `Loading… terrain:${terr} tiles:${tiles}`
      : `Ready`;
    div.style.background = loading
      ? 'rgba(255,165,0,.85)'
      : 'rgba(46,125,50,.85)';  // green = ready
  };
  viewer.scene.postRender.addEventListener(onPost);

  // return a disposer + a promise you can await
  const readyPromise = new Promise((resolve) => {
    const check = () => {
      if (terr === 0 && tiles === 0 && stable >= needStable) {
        cleanup(); resolve();
      } else {
        viewer.scene.requestRender();
        requestAnimationFrame(check);
      }
    };
    requestAnimationFrame(check);
  });

  function cleanup() {
    viewer.scene.globe.tileLoadProgressEvent.removeEventListener(onTerr);
    tsHandlers.forEach(([ts, h]) => ts.tileLoadProgressEvent.removeEventListener(h));
    viewer.scene.postRender.removeEventListener(onPost);
    div.remove();
  }

  return { readyPromise, dispose: cleanup };
}




export function nextFrame(viewer) {
  return new Promise(resolve => {
    const once = () => { viewer.scene.postRender.removeEventListener(once); resolve(); };
    viewer.scene.postRender.addEventListener(once);
    viewer.scene.requestRender();
  });
}