// main.js
import { initNodeStream } from './receiveFromNode.js';
Cesium.Ion.defaultAccessToken = window.CESIUM_ION_TOKEN;

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
    navigationHelpButton: false
  });

  viewer.imageryLayers.addImageryProvider(
    new Cesium.UrlTemplateImageryProvider({
      url: '/osm/{z}/{x}/{y}.png', maximumLevel: 19, credit: '© OpenStreetMap contributors'
    })
  );
  // viewer.scene.screenSpaceCameraController.enableInputs = false;

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
  await tileset.readyPromise;

  initNodeStream(viewer, async (payload) => {
    if (payload.type === 'depth') {
      const { value, location, grid,lng,lat } = payload;
      const [latStr, lonStr] = location.split(',');
      const buildingLat = Number(latStr);
      const buildingLon = Number(lonStr);ㄴ

      // 1. Sample terrain height at the building's center
const centerCartographic = Cesium.Cartographic.fromDegrees(buildingLon, buildingLat);
const [centerSample] = await Cesium.sampleTerrainMostDetailed(viewer.terrainProvider, [centerCartographic]);
const baseHeight = centerSample.height;
const floodHeight = baseHeight + value;

// 2. Define square size (e.g., 20 meters per side)
const halfSizeMeters = 100; // half of 20m
const halfSizeDeg = halfSizeMeters / 111000; // convert to approx. degrees

const west = buildingLon - halfSizeDeg;
const east = buildingLon + halfSizeDeg;
const south = buildingLat - halfSizeDeg;
const north = buildingLat + halfSizeDeg;

// 3. Add the polygon
viewer.entities.add({
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

      viewer.scene.requestRender();
    } else if (Array.isArray(payload)) {
      const { lng, lat, heading, fov } = payload[0];
      const [pos2] = await Cesium.sampleTerrainMostDetailed(
        viewer.terrainProvider,
        [Cesium.Cartographic.fromDegrees(lng, lat)]
      );
      viewer.camera.setView({
        destination: Cesium.Cartesian3.fromDegrees(lng, lat, pos2.height + 2.05),
        orientation: { heading: Cesium.Math.toRadians(heading), pitch: 0, roll: 0 }
      });
      viewer.camera.frustum.fov = Cesium.Math.toRadians(fov);
      viewer.camera.frustum.near = 0.001; // in meters
      viewer.scene.requestRender();
    }
  });
})();