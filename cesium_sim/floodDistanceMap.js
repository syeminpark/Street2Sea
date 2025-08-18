// floodDistanceMap.js
import { nextFrame } from './viewReady.js';

/**
 * Full‑screen postprocess that writes a planar distance (white=near, black=far)
 * for the flood plane, *without* using geometry depth. Visibility comes from
 * the mask you multiply afterwards.
 */
export async function captureFloodDistanceMapCanvas(
  viewer,
  {
    planePointWC,      // Cesium.Cartesian3 point on the plane
    planeNormalWC,     // Cesium.Cartesian3 unit normal (world)
    nearMeters = 0.0,  // white at/below this planar distance
    farMeters  = 50.0, // black at/above this planar distance
    hiResScale = 2
  }
) {
  const { scene } = viewer;
  const prevScale = viewer.resolutionScale;
  const prevReq   = scene.requestRenderMode;

  scene.requestRenderMode = false;
  if (hiResScale && hiResScale > 1) viewer.resolutionScale = hiResScale;

  const webgl2 = viewer.scene.context.webgl2;
  const VARYING = webgl2 ? 'in' : 'varying';
  const OUT     = webgl2 ? 'out_FragColor' : 'gl_FragColor';

  // IMPORTANT: do not declare out_FragColor yourself – Cesium provides it for WebGL2
  const frag = `
  uniform sampler2D colorTexture;   // required by Cesium stages
  uniform sampler2D depthTexture;   // not used here
  ${VARYING} vec2 v_textureCoordinates;

  uniform vec3  u_planePointWC;
  uniform vec3  u_planeNormalWC;
  uniform float u_nearMeters;
  uniform float u_farMeters;

  // Reconstruct WORLD-SPACE ray direction for this pixel
  vec3 rayDirWC(vec2 uv){
    vec4 clip = vec4(uv * 2.0 - 1.0, 1.0, 1.0);
    vec4 eye  = czm_inverseProjection * clip;              // eye space
    vec3 dirE = normalize(eye.xyz / eye.w);
    return normalize((czm_inverseView * vec4(dirE, 0.0)).xyz);
  }

  void main(){
    vec3 cam = czm_viewerPositionWC;
    vec3 dir = rayDirWC(v_textureCoordinates);

    float denom = dot(u_planeNormalWC, dir);
    if (abs(denom) < 1e-6) { ${OUT} = vec4(0.0); return; }      // almost parallel

    float t = dot(u_planeNormalWC, (u_planePointWC - cam)) / denom;
    if (t <= 0.0) { ${OUT} = vec4(0.0); return; }               // behind camera

    vec3 hit = cam + t * dir;
    // Planar (tangent) distance from camera to hit point
    vec3 v   = hit - cam;
    float n  = dot(v, u_planeNormalWC);
    vec3 tangent = v - n * u_planeNormalWC;
    float planar = length(tangent);

    float v01 = 1.0 - clamp((planar - u_nearMeters) / max(1e-3, (u_farMeters - u_nearMeters)), 0.0, 1.0);
    ${OUT} = vec4(vec3(v01), 1.0);
  }
  `;

  const stage = new Cesium.PostProcessStage({
    name: 'floodPlaneDistance',
    fragmentShader: frag,
    uniforms: {
      u_planePointWC: () => planePointWC,
      u_planeNormalWC: () => planeNormalWC,
      u_nearMeters:   () => nearMeters,
      u_farMeters:    () => farMeters
    }
  });

  scene.postProcessStages.add(stage);

  // Draw twice to be safe the first time a program is compiled
  scene.requestRender(); await nextFrame(viewer);
  scene.requestRender(); await nextFrame(viewer);

  const gl = scene.context._gl;
  const w = gl.drawingBufferWidth, h = gl.drawingBufferHeight;

  const out = document.createElement('canvas');
  out.width = w; out.height = h;
  out.getContext('2d', { willReadFrequently: true })
     .drawImage(viewer.canvas, 0, 0, w, h);

  scene.postProcessStages.remove(stage);
  viewer.resolutionScale = prevScale;
  scene.requestRenderMode = prevReq;
  scene.requestRender();

  return out;
}
