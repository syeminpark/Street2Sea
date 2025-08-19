// main.js
import { initNodeStream } from './nodeCommunication.js';
import { attachViewLoadHUD, nextFrame } from './viewReady.js';
import {
  captureAndSendIntersectedWaterMask,
  captureAndSendSubmergedInpaintMask,
} from './captureIntersectedWaterMask.js';
import { captureAndSendScene } from './captureScene.js';
import {withOverlayHidden} from './viewReady.js'
import { rectFromCenterMeters_ENU } from './myPlane.js';

Cesium.Ion.defaultAccessToken = window.CESIUM_ION_TOKEN;
let UUID = "";

// ---- scene/overlay behavior knobs ---------------------------------
const SHOW_WATER_IN_SCENE  = true;   // water plane visible in final screenshot
const SHOW_MARKER_IN_SCENE = false;   // depth label visible in final screenshot
const WATER_EPS_M          = 0.25;   // deadband: skip masks if depth <= this
const HALF_SIZE_METERS     = 100;    // half-width of the local water box
// -------------------------------------------------------------------

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
      infoBox: false,    
       selectionIndicator: false,   // ⬅️ disable green selection target
    navigationHelpButton: false,
    contextOptions: { webgl: { preserveDrawingBuffer: true } }
  });
  window.cesiumViewer = viewer;

  viewer.scene.screenSpaceCameraController.enableInputs = false;
  viewer.scene.globe.depthTestAgainstTerrain = true;
  viewer.scene.fxaa = false;
  viewer.scene.pickTranslucentDepth = true;
  viewer.scene.useDepthPicking = true;
  viewer.screenSpaceEventHandler.removeInputAction(Cesium.ScreenSpaceEventType.LEFT_CLICK);
viewer.screenSpaceEventHandler.removeInputAction(Cesium.ScreenSpaceEventType.LEFT_DOUBLE_CLICK);

  const ctx = viewer.scene.context;
  console.log('depthTexture support:', !!ctx.depthTexture);
  console.log('webgl2:', ctx.webgl2, 'floatTex:', !!ctx.textureFloat);

  viewer.imageryLayers.addImageryProvider(
    new Cesium.UrlTemplateImageryProvider({
      url: '/osm/{z}/{x}/{y}.png',
      maximumLevel: 19,
      credit: '© OpenStreetMap contributors'
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

  // ---------- Single overlay & reusable entities ----------
  const overlay = new Cesium.CustomDataSource('overlay');
  await viewer.dataSources.add(overlay);

  let waterEntity = null;   // polygon reused in-place
  let markerEntity = null;  // point+label reused in-place


  function upsertWaterBox({ west, east, south, north, baseHeight, floodHeight }) {
    const hierarchy = Cesium.Cartesian3.fromDegreesArray([
      west, south,
      east, south,
      east, north,
      west, north
    ]);

    if (!waterEntity) {
      waterEntity = overlay.entities.add({
        polygon: {
          hierarchy,
          height: baseHeight,
          extrudedHeight: floodHeight,
          material: Cesium.Color.SKYBLUE.withAlpha(0.8),
          outline: true,
          outlineColor: Cesium.Color.DARKBLUE.withAlpha(0.8)
        },
        show: false // keep hidden during mask capture; shown for scene per flags
      });
    } else {
      waterEntity.polygon.hierarchy = hierarchy;
      waterEntity.polygon.height = baseHeight;
      waterEntity.polygon.extrudedHeight = floodHeight;
    }
    viewer.scene.requestRender();
    return waterEntity;
  }

  function upsertMarker({ lon, lat, height, depthValue }) {
  const pos = Cesium.Cartesian3.fromDegrees(lon, lat, height + 1.5);
  const text = `Depth: ${Number(depthValue || 0).toFixed(2)} m`;
  console.log(depthValue)
  if (!markerEntity) {
    markerEntity = overlay.entities.add({
      position: pos,
      point: { pixelSize: 15, color: Cesium.Color.RED, disableDepthTestDistance: Infinity },
      label: {
        text: new Cesium.ConstantProperty(text),   // <-- make it a Property on create
        font: '24px sans-serif',
        fillColor: Cesium.Color.BLUE,
        showBackground: true,
        horizontalOrigin: Cesium.HorizontalOrigin.CENTER,
        verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
        disableDepthTestDistance: Infinity
      }
    });
  } else {
    markerEntity.position = pos;
    // ⚠️ update the Property, not just the string:
    if (markerEntity.label && markerEntity.label.text && markerEntity.label.text.setValue) {
      markerEntity.label.text.setValue(text);
    } else {
      markerEntity.label.text = new Cesium.ConstantProperty(text);
    }
  }
  viewer.scene.requestRender();
  return markerEntity;
}


  initNodeStream(viewer, async (payload) => {
    // DEPTH PAYLOAD
    if (payload && payload.type === 'depth') {
      const { location, lng, lat,size,value} = payload;

      const depth = Number(value || 0);

      // coords in "lat,lng" order (from your Python)
      const [latStr, lonStr] = String(location).split(',');
      const buildingLat = Number(latStr);
      const buildingLon = Number(lonStr);
    

      // 1) terrain height at building center
      const centerCarto = Cesium.Cartographic.fromDegrees(buildingLon, buildingLat);
      const [centerSample] = await Cesium.sampleTerrainMostDetailed(
        viewer.terrainProvider, [centerCarto]
      );

      const baseHeight   = centerSample.height;
      const floodHeight  = baseHeight + depth;     // geometric water level used for masks/box
      

// Sanity log

const rect = rectFromCenterMeters_ENU(buildingLon, buildingLat, HALF_SIZE_METERS, 0);

  

      // update (or create) the reusable water polygon
      upsertWaterBox({ west: rect.west, east: rect.east, south: rect.south, north: rect.north,
                 baseHeight, floodHeight });

      // 3) wait for tileset & HUD to settle
      await tileset.readyPromise;
      const hud = attachViewLoadHUD(viewer, [tileset]);
      await hud.readyPromise;

      // 4) generate masks with overlay hidden (and skip if near-zero depth)
      const needMask = Math.abs(depth) > WATER_EPS_M;
      
      if (needMask) {
        await withOverlayHidden(viewer,waterEntity,markerEntity, async () => {
          if (floodHeight > viewer.camera.positionCartographic.height ) {
            await captureAndSendSubmergedInpaintMask(viewer, {
               rect,
               waterLevelUp: floodHeight,
              includeBuildings: true,
              includeTerrain: true,
            }, `${UUID}_underwater_mask.png`, {
              solidsStrength: 0.42,
              blurPx: 0
            });
          } else {
            await captureAndSendIntersectedWaterMask(viewer, {
               rect,
              waterLevelUp: floodHeight,
              includeBuildings: true,
              includeTerrain: true,
            }, `${UUID}_overwater_mask.png`);

            await captureAndSendIntersectedWaterMask(viewer, {
              rect,
              waterLevelUp: floodHeight,
              includeBuildings: false,
              includeTerrain: true,
            }, `${UUID}_naive_overwater_mask.png`);
          }
// 
          });
      }
      hud.dispose();

      // 5) show what you want visible for the pretty scene export
      const prevShows = {
        water: waterEntity?.show ?? null,
        marker: markerEntity?.show ?? null
      };
      
      if (waterEntity)  waterEntity.show  = !!SHOW_WATER_IN_SCENE;
      if (markerEntity) markerEntity.show = !!SHOW_MARKER_IN_SCENE;

      viewer.scene.requestRender();
      viewer.camera.frustum.near = 0.001;
      
      await nextFrame(viewer)
      await captureAndSendScene(viewer, {
        filename: `${UUID}_scene.png`,
        resolutionScale: 2,
        transparent: false,
        hideUI: true
      });

      // restore previous visibility
      if (markerEntity && prevShows.marker !== null) markerEntity.show = prevShows.marker;

      // 6) update / place the single marker
      const [markerSample] = await Cesium.sampleTerrainMostDetailed(
        viewer.terrainProvider,
        [Cesium.Cartographic.fromDegrees(buildingLon, buildingLat)]
      );
      upsertMarker({
        lon: buildingLon,
        lat: buildingLat,
        height: markerSample.height,
        depthValue: depth
      });
      
      await nextFrame(viewer)
      viewer.scene.requestRender();
    }

    // CAMERA (array from metas)
    else if (Array.isArray(payload)) {
      const { lat, lng, heading, fov, uuid } = payload[0];
      if (uuid) UUID = uuid; // remember for filenames

      const [pos2] = await Cesium.sampleTerrainMostDetailed(
        viewer.terrainProvider,
        [Cesium.Cartographic.fromDegrees(lng, lat)]
      );
      viewer.camera.setView({
        destination: Cesium.Cartesian3.fromDegrees(lng, lat, pos2.height + 2.05),
        orientation: { heading: Cesium.Math.toRadians(heading || 0), pitch: 0, roll: 0 }
      });
      viewer.camera.frustum.fov  = Cesium.Math.toRadians(fov || 120);
      viewer.camera.frustum.near = 0.001;
      viewer.camera.frustum.far  = viewer.scene.globe.ellipsoid.maximumRadius * 3.0;

      viewer.scene.requestRender();
    }
  });
})();
