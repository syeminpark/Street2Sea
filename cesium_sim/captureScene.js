// captureScene.js
import { sendCanvasAsPNG } from "./nodeCommunication.js";

/**
 * Capture the current Cesium scene as an image.
 *
 * Options:
 *  - filename: output file name
 *  - format: "png" | "jpeg"
 *  - jpegQuality: 0..1 (only when format="jpeg")
 *  - resolutionScale: >1 for supersampled image (e.g., 2 for 2x)
 *  - transparent: true to capture with transparent background (requires viewer created with alpha:true)
 *  - hideUI: true to temporarily hide credits/entities you don't want in the shot
 */
export async function captureSceneCanvas(
  viewer,
  {
    filename = "scene.png",
    format = "png",
    jpegQuality = 0.92,
    resolutionScale = 1,
    transparent = false,
    hideUI = true,
  } = {}
) {
  if (!viewer?.scene) throw new Error("bad viewer");
  const scene = viewer.scene;

  // --- Save current state
  const prev = {
    resolutionScale: viewer.resolutionScale,
    backgroundColor: scene.backgroundColor.clone(),
    skyBox: scene.skyBox,
    skyAtmosphere: scene.skyAtmosphere,
    globeShow: scene.globe.show,
    creditShow: viewer._creditContainer?.style?.display,
    entitiesShow: viewer.entities.show,
  };

  // --- Optional UI/sky hiding
  if (hideUI && viewer._creditContainer) {
    viewer._creditContainer.style.display = "none";
  }

  if (transparent) {
    // To truly get transparency, the Viewer must be created with:
    //   contextOptions: { webgl: { alpha: true, preserveDrawingBuffer: true } }
    // If alpha wasn't enabled at creation, you'll still get opaque output.
    scene.backgroundColor = Cesium.Color.TRANSPARENT;
    scene.skyBox = undefined;
    scene.skyAtmosphere = undefined;
  }

  // --- Bump resolution if requested
  viewer.resolutionScale = Math.max(0.5, resolutionScale);

  // --- Render and grab
  scene.requestRender();
  scene.render();

  // Copy framebuffer to an offscreen canvas (avoids driver quirks)
  const src = viewer.canvas;
  const out = document.createElement("canvas");
  out.width = src.width;
  out.height = src.height;
  const octx = out.getContext("2d");
  octx.drawImage(src, 0, 0);

  // --- Restore state
  viewer.resolutionScale = prev.resolutionScale;
  scene.backgroundColor = prev.backgroundColor;
  scene.skyBox = prev.skyBox;
  scene.skyAtmosphere = prev.skyAtmosphere;
  if (hideUI && viewer._creditContainer) {
    viewer._creditContainer.style.display = prev.creditShow ?? "";
  }
  scene.requestRender();

  // Return canvas (caller decides whether to send/save)
  return out;
}

export async function captureAndSendScene(
  viewer,
  {
    filename = "scene.png",
    format = "png",
    jpegQuality = 0.92,
    resolutionScale = 1,
    transparent = false,
    hideUI = true,
  } = {}
) {
  const canvas = await captureSceneCanvas(viewer, {
    filename,
    format,
    jpegQuality,
    resolutionScale,
    transparent,
    hideUI,
  });

  if (format === "png") {
    return sendCanvasAsPNG(canvas, filename);
  } else {
    // Small helper to send JPEG via your JSON endpoint
    const dataUrl = canvas.toDataURL("image/jpeg", jpegQuality);
    const resp = await fetch("/save-mask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dataUrl, filename }),
    });
    if (!resp.ok) throw new Error(`save-mask ${resp.status}`);
    return resp.json();
  }
}
