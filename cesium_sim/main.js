// main.js
import { initNodeStream,
} from './nodeCommunication.js';
import { attachViewLoadHUD, nextFrame} from './viewReady.js';
import { captureAndSendIntersectedWaterMask } from "./captureIntersectedWaterMask.js";
import { captureAndSendScene } from "./captureScene.js";

Cesium.Ion.defaultAccessToken = window.CESIUM_ION_TOKEN;
let UUID="";


(async () => {
  const viewer = new Cesium.Viewer('cesiumContainer', {
    terrainProvider: await Cesium.CesiumTerrainProvider.fromIonAssetId(2767062),
    baseLayerPicker: false,
    timeline: false,
    animation: false,
    requestRenderMode: true,
    geocoder: false,
    homeButton: false,
    sceneModePicker: false,
    navigationHelpButton: false,
      contextOptions: { webgl: { preserveDrawingBuffer: true } }
  });
  window.cesiumViewer = viewer;
  
  viewer.scene.screenSpaceCameraController.enableInputs = true
  viewer.scene.globe.depthTestAgainstTerrain = true;
viewer.scene.fxaa = false
viewer.scene.pickTranslucentDepth = true;
viewer.scene.useDepthPicking = true;    


  const ctx = viewer.scene.context;
console.log('depthTexture support:', !!ctx.depthTexture); // must be true
console.log('webgl2:', ctx.webgl2, 'floatTex:', !!ctx.textureFloat);

  viewer.imageryLayers.addImageryProvider(
    new Cesium.UrlTemplateImageryProvider({
      url: '/osm/{z}/{x}/{y}.png', maximumLevel: 19, credit: '© OpenStreetMap contributors'
    })
  );


  const initialLon = 139.6142023961819;
  const initialLat = 35.65256823531473;
  const hAGL = 2.05;
  const [initSample] = await Cesium.sampleTerrainMostDetailed(
    viewer.terrainProvider,
    [Cesium.Cartographic.fromDegrees(initialLon, initialLat)]
  );
  viewer.camera.setView({
    destination: Cesium.Cartesian3.fromDegrees(initialLon, initialLat, initSample.height + hAGL),
    orientation: { heading: Cesium.Math.toRadians(336), pitch: 0, roll: 0 }
  });
  viewer.camera.frustum.fov = Cesium.Math.toRadians(120);

  const tileset = await Cesium.Cesium3DTileset.fromIonAssetId(2602291);
  Object.assign(tileset, {
    maximumScreenSpaceError: 128,
    dynamicScreenSpaceError: true,
    dynamicScreenSpaceErrorDensity: 2e-4,
    preloadWhenHidden: true,
    updateWhenHidden: true,
    throttleRequests: false
  });
  viewer.scene.primitives.add(tileset);


  initNodeStream(viewer, async (payload) => {
    if (payload.type === 'depth') {
      const {  location,lng,lat} = payload;
      const cameraLng=lng
      const cameraLat= lat

      const value=1.8
      const [latStr, lonStr] = location.split(',');
      const buildingLat = Number(latStr);
      const buildingLon = Number(lonStr);

      // 1. Sample terrain height at the building's center
const centerCartographic = Cesium.Cartographic.fromDegrees(buildingLon, buildingLat);
const [centerSample] = await Cesium.sampleTerrainMostDetailed(viewer.terrainProvider, [centerCartographic]);

const baseHeight = centerSample.height;
const floodHeight = baseHeight + value;


const [cameraPos] = await Cesium.sampleTerrainMostDetailed(
        viewer.terrainProvider,
        [Cesium.Cartographic.fromDegrees(cameraLng, cameraLat)]
      );

// console.log('camera base height:', cameraPos.height);
// console.log('building base height:', baseHeight);
// console.log('flood ellipsoid Final height:', floodHeight);
// console.log('camera Final height:', viewer.camera.positionCartographic.height);
// console.log('is water above camera?', floodHeight > viewer.camera.positionCartographic.height);

// 2. Define square size (e.g., 20 meters per side)
const halfSizeMeters = 100; // half of 20m
const halfSizeDeg = halfSizeMeters / 111000; // convert to approx. degrees

const west = buildingLon - halfSizeDeg;
const east = buildingLon + halfSizeDeg;
const south = buildingLat - halfSizeDeg;
const north = buildingLat + halfSizeDeg;



const poly =viewer.entities.add({
  polygon: {
    hierarchy: Cesium.Cartesian3.fromDegreesArray([
      west, south,
      east, south,
      east, north,
      west, north
    ]),
    height: baseHeight,
    extrudedHeight: floodHeight,
    material: Cesium.Color.SKYBLUE.withAlpha(0.8),
    outline: true,
    outlineColor: Cesium.Color.DARKBLUE.withAlpha(0.8)
  }
});
poly.show = false; // hide the polygon

// after you add your tileset(s) and await tileset.readyPromise:
await tileset.readyPromise;
const hud = attachViewLoadHUD(viewer, [tileset]);
await hud.readyPromise;  

await captureAndSendIntersectedWaterMask(viewer, {
  centerLon: buildingLon,
  centerLat: buildingLat,
  sizeMeters: 1500,        // or compute from camera as shown earlier
  waterLevelUp: floodHeight,
  includeBuildings: true,  // set false for terrain-only
   includeTerrain:true
}, UUID+"_mask.png");


await captureAndSendIntersectedWaterMask(viewer, {
  centerLon: buildingLon,
  centerLat: buildingLat,
  sizeMeters: 1500,        // or compute from camera as shown earlier
  waterLevelUp: floodHeight,
  includeBuildings: false,  // set false for terrain-only
   includeTerrain:true,
}, UUID+"_navive_mask.png");


hud.dispose();
poly.show=true

 viewer.scene.requestRender(); // ensure a fresh frame
await nextFrame(viewer);        

await captureAndSendScene(viewer, {
  filename: UUID+"_scene.png",
  resolutionScale: 2,   // 2x supersample for sharper output
  transparent: false,   // set true if you created Viewer with webgl.alpha=true
  hideUI: true,         // hides Cesium credit + your entities during capture
});


      const [markerSample] = await Cesium.sampleTerrainMostDetailed(
        viewer.terrainProvider,
        [Cesium.Cartographic.fromDegrees(buildingLon, buildingLat)]
      );
      viewer.entities.add({
        position: Cesium.Cartesian3.fromDegrees(
          buildingLon, buildingLat, markerSample.height + 1.5
        ),
        point: { pixelSize: 15, color: Cesium.Color.RED, disableDepthTestDistance: Infinity },
        label: {
          text: `Depth: ${value.toFixed(2)} m`,
          font: '24px sans-serif',
          fillColor: Cesium.Color.BLUE,
          showBackground: true,
          horizontalOrigin: Cesium.HorizontalOrigin.CENTER,
          verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
          disableDepthTestDistance: Infinity
        }
      });
      viewer.scene.requestRender(); // ensure a fresh frame

    }

     else if (Array.isArray(payload)) {
      const {lat,lng, heading, fov,uuid } = payload[0];
      UUID=uuid
      const cameraLng=lng
      const cameraLat= lat

      const [pos2] = await Cesium.sampleTerrainMostDetailed(
        viewer.terrainProvider,
        [Cesium.Cartographic.fromDegrees(cameraLng, cameraLat)]
      );
      viewer.camera.setView({
        destination: Cesium.Cartesian3.fromDegrees(cameraLng, cameraLat, pos2.height + 2.05),
        orientation: { heading: Cesium.Math.toRadians(heading), pitch: 0, roll: 0 }
      });
      viewer.camera.frustum.fov = Cesium.Math.toRadians(fov);
      viewer.camera.frustum.near = 0.001; // in meters
       viewer.camera.frustum.far  = viewer.scene.globe.ellipsoid.maximumRadius * 3.0;
      viewer.scene.requestRender();
    }
  });
})()