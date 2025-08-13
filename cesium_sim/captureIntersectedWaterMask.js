// captureIntersectedWaterMask.js
import { sendCanvasAsPNG } from "./nodeCommunication.js";
import { nextFrame } from './viewReady.js';
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


