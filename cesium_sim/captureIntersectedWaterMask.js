// captureIntersectedWaterMask.js
import { sendCanvasAsPNG } from "./nodeCommunication.js";
import { nextFrame } from './viewReady.js';
import { captureFloodDistanceMapCanvas } from './floodDistanceMap.js';

/**
 * Render a big horizontal plane at `waterLevelUp` with depth test ON so it is
 * clipped by terrain and/or buildings based on the options.
 * Returns an offscreen canvas containing just the black/white mask.
 */


export async function captureIntersectedWaterMaskCanvas(
  viewer,
  {
    rect,
    waterLevelUp,
    includeBuildings = true,
    includeTerrain = true,
    planeColor = Cesium.Color.fromBytes(0, 0, 255, 255),
    hiResScale = 1
  },
) {
  const { scene } = viewer;
  const globe = scene.globe;

  // --- bump resolution (true supersampling) ---
  const prevScale = viewer.resolutionScale;
  const prevReqMode = scene.requestRenderMode;
  try {
    // Ensure we can trigger frames as needed
    scene.requestRenderMode = false;

    // Try to apply the requested scale; Cesium will clamp if needed
    if (hiResScale && hiResScale > 1) {
      viewer.resolutionScale = hiResScale;
    }

    // 0) Hide 3D tiles if needed
    const hiddenTilesets = [];
    if (!includeBuildings) {
      scene.primitives._primitives.forEach(p => {
        if (p instanceof Cesium.Cesium3DTileset && p.show) {
          p.show = false;
          hiddenTilesets.push(p);
        }
      });
    }

    // 0.5) Hide terrain if needed
    const terrainWasShown = globe.show;
    if (!includeTerrain) globe.show = false;

    // 1) First render: populate depth buffer
    scene.requestRender();
    scene.render();

    // 2) Build a large rectangle at water height
    const rectangle = Cesium.Rectangle.fromDegrees(rect.west, rect.south, rect.east, rect.north);
    const instance = new Cesium.GeometryInstance({
      geometry: new Cesium.RectangleGeometry({ rectangle, height: waterLevelUp }),
      attributes: { color: Cesium.ColorGeometryInstanceAttribute.fromColor(planeColor) }
    });

    const appearance = new Cesium.PerInstanceColorAppearance({
      flat: true, translucent: false,
      renderState: {
        depthTest: { enabled: true, func: Cesium.DepthFunction.LESS_OR_EQUAL },
        depthMask: false,
        cull: { enabled: false }
      }
    });

    const plane = new Cesium.Primitive({ geometryInstances: [instance], appearance, asynchronous: false });
    scene.primitives.add(plane);

    viewer.camera.frustum.near = 0.001;
    viewer.camera.frustum.far  = viewer.scene.globe.ellipsoid.maximumRadius * 3.0;

    // Render at the higher resolution
    scene.requestRender();
    scene.render();
    await nextFrame(viewer);

    // 4) Copy framebuffer to an offscreen canvas
    const gl = viewer.scene.context._gl;
    const srcW = gl.drawingBufferWidth;
    const srcH = gl.drawingBufferHeight;

    const out = document.createElement('canvas');
    out.width  = srcW;
    out.height = srcH;

    const octx = out.getContext('2d', { willReadFrequently: true });
    await nextFrame(viewer);
    octx.drawImage(viewer.canvas, 0, 0, srcW, srcH);

    // 5) Convert plane color → white, everything else → black
    const img = octx.getImageData(0, 0, out.width, out.height);
    const [kr, kg, kb] = [
      planeColor.red * 255,
      planeColor.green * 255,
      planeColor.blue * 255
    ];
    for (let i = 0; i < img.data.length; i += 4) {
      const r = img.data[i], g = img.data[i + 1], b = img.data[i + 2];
      const isPlane =
        Math.abs(r - kr) < 8 &&
        Math.abs(g - kg) < 8 &&
        Math.abs(b - kb) < 8;

      const v = isPlane ? 255 : 0;
      img.data[i] = img.data[i + 1] = img.data[i + 2] = v;
      img.data[i + 3] = 255;
    }
    octx.putImageData(img, 0, 0);

    // 6) Cleanup & restore scene toggles
    scene.primitives.remove(plane);
    hiddenTilesets.forEach(p => (p.show = true));
    globe.show = terrainWasShown;
    scene.requestRender();

    return out; // B/W mask at ×2 render resolution
  } finally {
    // Always restore render settings
    viewer.resolutionScale = prevScale;
    scene.requestRenderMode = prevReqMode;
    scene.requestRender();
  }
}


// --- add below your existing exports in captureIntersectedWaterMask.js ---

/**
 * Turn a B/W surface mask canvas (white = water plane visible) into a
 * soft inpainting mask: white on surface, mid-gray on everything else.
 * @param {HTMLCanvasElement} surfaceCanvas - output of captureIntersectedWaterMaskCanvas
 * @param {Object} opts
 * @param {number} opts.solidsStrength - 0..1 gray for submerged solids (0.42 ≈ 107)
 * @param {number} opts.blurPx - feather amount in px at the boundary
 * @returns {HTMLCanvasElement} mask canvas ready for SD inpainting
 */
export function makeSubmergedInpaintMask(surfaceCanvas, {
  solidsStrength = 0.42,
  blurPx = 2
} = {}) {
  const w = surfaceCanvas.width, h = surfaceCanvas.height;
  const sctx = surfaceCanvas.getContext('2d', { willReadFrequently: true });
  const src = sctx.getImageData(0, 0, w, h);

  const out = new ImageData(w, h);
  const solidGray = Math.round(255 * solidsStrength);

  // surfaceCanvas is B/W (255 on surface, 0 elsewhere)
  for (let i = 0; i < src.data.length; i += 4) {
    const r = src.data[i]; // r=g=b in your B/W canvas
    const isSurface = r > 250; // robust threshold for "white"
    const v = isSurface ? 255 : solidGray;
    out.data[i] = out.data[i + 1] = out.data[i + 2] = v;
    out.data[i + 3] = 255;
  }

  // Draw to an intermediate canvas
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  const ctx = c.getContext('2d');
  ctx.putImageData(out, 0, 0);

  // Feather the edge a touch to avoid seams in SD
  if (blurPx > 0) {
    const dst = document.createElement('canvas');
    dst.width = w; dst.height = h;
    const dctx = dst.getContext('2d');
    // canvas filters are widely supported; skip if not available
    if ('filter' in dctx) {
      dctx.filter = `blur(${blurPx}px)`;
      dctx.drawImage(c, 0, 0);
      return dst;
    }
  }
  return c;
}

/** Convenience: capture surface mask → convert → return canvas */
export async function captureSubmergedInpaintMaskCanvas(
  viewer,
  opts,
  maskOpts = { solidsStrength: 0.42, blurPx: 2 }
) {
  const surface = await captureIntersectedWaterMaskCanvas(viewer, opts);
  return makeSubmergedInpaintMask(surface, maskOpts);
}

/** Convenience: capture + convert + send PNG */
export async function captureAndSendSubmergedInpaintMask(
  viewer,
  opts,
  filename = "water_inpaint_mask.png",
  maskOpts = { solidsStrength: 0.42, blurPx: 2 }
) {
  const canvas = await captureSubmergedInpaintMaskCanvas(viewer, opts, maskOpts);
  return sendCanvasAsPNG(canvas, filename);
}


/** Convenience wrapper: capture and send */
export async function captureAndSendIntersectedWaterMask(
  viewer,
  opts,
  filename = "water_mask.png"
) {
  const canvas = await captureIntersectedWaterMaskCanvas(viewer, opts);
  return sendCanvasAsPNG(canvas, filename);
}

// Add this helper near the top of captureIntersectedWaterMask.js
function estimateVisiblePlanarFar(viewer, planePointWC, planeNormalWC) {
  const n    = Cesium.Cartesian3.normalize(planeNormalWC, new Cesium.Cartesian3());
  const cam  = viewer.camera.positionWC;
  const pln  = Cesium.Plane.fromPointNormal(planePointWC, n);

  // perpendicular distance cam → plane, used for a fallback guess
  const dPerp = Math.abs(Cesium.Cartesian3.dot(
    n,
    Cesium.Cartesian3.subtract(planePointWC, cam, new Cesium.Cartesian3())
  ));

  // sample a few window positions
  const w = viewer.canvas.width, h = viewer.canvas.height;
  const pts = [
    new Cesium.Cartesian2(0, 0),
    new Cesium.Cartesian2(w-1, 0),
    new Cesium.Cartesian2(0, h-1),
    new Cesium.Cartesian2(w-1, h-1),
    new Cesium.Cartesian2(w*0.5, h*0.5),
    new Cesium.Cartesian2(w*0.5, 0),
    new Cesium.Cartesian2(w*0.5, h-1),
    new Cesium.Cartesian2(0, h*0.5),
    new Cesium.Cartesian2(w-1, h*0.5),
  ];

  let far = 0.0;
  for (const p of pts) {
    const ray = viewer.scene.camera.getPickRay(p, new Cesium.Ray());
    if (!ray) continue;
    const hit = Cesium.IntersectionTests.rayPlane(ray, pln);
    if (!hit) continue;
    // planar component of (hit - cam)
    const v = Cesium.Cartesian3.subtract(hit, cam, new Cesium.Cartesian3());
    const along = Cesium.Cartesian3.subtract(
      v,
      Cesium.Cartesian3.multiplyByScalar(n, Cesium.Cartesian3.dot(v, n), new Cesium.Cartesian3()),
      new Cesium.Cartesian3()
    );
    far = Math.max(far, Cesium.Cartesian3.magnitude(along));
  }

  if (far <= 0.0 || !Number.isFinite(far)) {
    // Fallback: visible extent ~ perpendicular distance * tan(FOV/2) (times a margin)
    const fov = viewer.camera.frustum.fov; // Cesium uses vertical FOV
    far = Math.max(20, dPerp * Math.tan(fov * 0.5) * 1.6);
  }
  return far * 1.05; // small safety headroom
}


// --- util: multiply two canvases in-place (grayscale × B/W mask) ---
function multiplyCanvases(dstCanvas, maskCanvas) {
  const w = dstCanvas.width, h = dstCanvas.height;
  const dctx = dstCanvas.getContext('2d', { willReadFrequently: true });
  const mctx = maskCanvas.getContext('2d', { willReadFrequently: true });
  const d = dctx.getImageData(0, 0, w, h);
  const m = mctx.getImageData(0, 0, w, h);
  for (let i = 0; i < d.data.length; i += 4) {
    const mask = m.data[i]; // R=G=B in B/W mask
    d.data[i]   = (d.data[i]   * mask) >> 8;
    d.data[i+1] = (d.data[i+1] * mask) >> 8;
    d.data[i+2] = (d.data[i+2] * mask) >> 8;
    d.data[i+3] = 255;
  }
  dctx.putImageData(d, 0, 0);
  return dstCanvas;
}

/**
 * Perspective flood depth map (white=near, black=far) gated by visibility.
 * Saves a PNG via sendCanvasAsPNG and returns the canvas.
 *
 * @param {Cesium.Viewer} viewer
 * @param {Object} opts
 * @param {Object} opts.rect - {west,east,south,north} in degrees
 * @param {number} opts.floodHeight - water level (meters MSL)
 * @param {string} opts.filename - output filename
 * @param {number} [opts.hiResScale=2] - supersampling scale
 * @param {boolean} [opts.includeBuildings=true] - for visibility mask
 * @param {boolean} [opts.includeTerrain=true]   - for visibility mask
 * @param {number|null} [opts.nearMeters=null]   - override near (m)
 * @param {number|null} [opts.farMeters=null]    - override far (m)
 * @param {number} [opts.farHintMeters=300]      - used if farMeters not set
 */

export async function captureAndSendFloodDepthMap(
  viewer,
  {
    rect,
    floodHeight,
    filename = "flood_depthmap.png",
    hiResScale = 2,
    includeBuildings = true,
    includeTerrain = true,
    nearMeters = null,
    farMeters = null
  }
) {
  // 1) plane point & normal
  const centerLon = (rect.west + rect.east) * 0.5;
  const centerLat = (rect.south + rect.north) * 0.5;
  const planePointWC  = Cesium.Cartesian3.fromDegrees(centerLon, centerLat, floodHeight);
  const planeNormalWC = Cesium.Ellipsoid.WGS84.geodeticSurfaceNormal(planePointWC);

  // 2) auto near/far based on what's visible
  if (nearMeters == null) nearMeters = 0.0;
  if (farMeters  == null) {
    farMeters = estimateVisiblePlanarFar(viewer, planePointWC, planeNormalWC);
  }

  // 3) render the planar distance field
  const planeDist = await captureFloodDistanceMapCanvas(viewer, {
    planePointWC, planeNormalWC, nearMeters, farMeters, hiResScale
  });

  // 4) mask by actual visibility (terrain + buildings)
  const bwMask = await captureIntersectedWaterMaskCanvas(viewer, {
    rect,
    waterLevelUp: floodHeight,
    includeBuildings,
    includeTerrain,
    hiResScale
  });
  multiplyCanvases(planeDist, bwMask);

  // 5) save
  await sendCanvasAsPNG(planeDist, filename);
  return planeDist;
}


export function withSolidWaterForCapture(viewer, waterEntity, fn) {
  if (!waterEntity) return fn();

  // stash current props
  const prev = {
    show: waterEntity.show,
    material: waterEntity.polygon?.material,
    outlineColor: waterEntity.polygon?.outlineColor
  };

  // make it opaque for capture
  waterEntity.show = true;
  waterEntity.polygon.material     = Cesium.Color.SKYBLUE;          // alpha = 1
  waterEntity.polygon.outlineColor = Cesium.Color.DARKBLUE;         // alpha = 1
  viewer.scene.requestRender();

  const done = async () => {
    // restore after capture
    waterEntity.polygon.material     = prev.material;
    waterEntity.polygon.outlineColor = prev.outlineColor;
    waterEntity.show = prev.show;
    viewer.scene.requestRender();
  };

  return Promise.resolve(fn()).finally(done);
}
