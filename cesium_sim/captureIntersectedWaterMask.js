// captureIntersectedWaterMask.js
import { sendCanvasAsPNG } from "./nodeCommunication.js";

/**
 * Render a big horizontal plane at `waterLevelUp` with depth test ON so it is
 * clipped by terrain and/or buildings based on the options.
 * Returns an offscreen canvas containing just the black/white mask.
 */
export async function captureIntersectedWaterMaskCanvas(
  viewer,
  {
    centerLon,
    centerLat,
    sizeMeters = 1500,
    waterLevelUp,
    includeBuildings = true,       // false => hide 3D Tilesets
    includeTerrain = true,         // false => hide terrain
    planeColor = Cesium.Color.fromBytes(0, 0, 255, 255), // key color
  }
) {
  const { scene } = viewer;
  const globe = scene.globe;

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
  if (!includeTerrain) {
    globe.show = false;
  }

  // 1) First render: populate depth buffer
  scene.requestRender();
  scene.render();

  // 2) Build a large rectangle at water height
  const dLon = sizeMeters / 111320;
  const dLat = sizeMeters / 110540;
  const rect = Cesium.Rectangle.fromDegrees(
    centerLon - dLon / 2, centerLat - dLat / 2,
    centerLon + dLon / 2, centerLat + dLat / 2
  );

  const instance = new Cesium.GeometryInstance({
    geometry: new Cesium.RectangleGeometry({
      rectangle: rect,
      height: waterLevelUp
    }),
    attributes: {
      color: Cesium.ColorGeometryInstanceAttribute.fromColor(planeColor)
    }
  });

  const appearance = new Cesium.PerInstanceColorAppearance({
    flat: true,
    translucent: false,
    renderState: {
      depthTest: { enabled: true, func: Cesium.DepthFunction.LESS_OR_EQUAL },
      depthMask: false,
      cull: { enabled: false }
    }
  });

  const plane = new Cesium.Primitive({
    geometryInstances: [instance],
    appearance,
    asynchronous: false
  });

  scene.primitives.add(plane);

  // 3) Render plane with depth clipping
  scene.requestRender();
  scene.render();

  // 4) Copy framebuffer to an offscreen canvas
  const src = viewer.canvas;
  const out = document.createElement("canvas");
  out.width = src.width;
  out.height = src.height;
  const octx = out.getContext("2d");
  octx.drawImage(src, 0, 0);

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

  // 6) Cleanup & restore
  scene.primitives.remove(plane);
  hiddenTilesets.forEach(p => (p.show = true));
  globe.show = terrainWasShown;
  scene.requestRender();

  return out; // mask canvas (B/W)
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


