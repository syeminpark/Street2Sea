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
      const buildingLon = Number(lonStr);

      const { depth: data, stepDeg, lon0, lat0 } = grid;
      const numRows = data.length;
      const numCols = data[0].length;

      const alignedCol = Math.round((buildingLon - lon0) / stepDeg);
      const alignedRow = Math.round((buildingLat - lat0) / stepDeg);
      const alignedLon = lon0 + alignedCol * stepDeg;
      const alignedLat = lat0 + alignedRow * stepDeg;

      const [terrainSample] = await Cesium.sampleTerrainMostDetailed(
  viewer.terrainProvider,
  [Cesium.Cartographic.fromDegrees(buildingLon, buildingLat)]
);
      const baseHeight = terrainSample.height;
     

      const halfWidthDeg = (numCols * stepDeg) / 2;
      const halfHeightDeg = (numRows * stepDeg) / 2;
      const west = alignedLon - halfWidthDeg;
      const south = alignedLat - halfHeightDeg;

      function getColor(d) {
        const t = Math.min(Math.max(d / 5, 0), 1); // scale for visualization
        return Cesium.Color.fromHsl(0.6 - 0.6 * t, 1.0, 0.5).withAlpha(0.6);
      }
      for (let r = 0; r < data.length; r++) {
  for (let c = 0; c < data[r].length; c++) {
    const d = data[r][c];
     console.log('height:',d)
    if (!Number.isFinite(d) || d <= 0) continue;

    const cellWest = west + c * stepDeg;
    const cellSouth = south + r * stepDeg;
    const cellEast = cellWest + stepDeg;
    const cellNorth = cellSouth + stepDeg;

    const centerLon = (cellWest + cellEast) / 2;
    const centerLat = (cellSouth + cellNorth) / 2;

    const [terrain] = await Cesium.sampleTerrainMostDetailed(
  viewer.terrainProvider,
  [Cesium.Cartographic.fromDegrees(buildingLon, buildingLat)]
);
    const baseHeight = terrain.height;

    viewer.entities.add({
      polygon: {
        hierarchy: Cesium.Cartesian3.fromDegreesArray([
          cellWest, cellSouth,
          cellEast, cellSouth,
          cellEast, cellNorth,
          cellWest, cellNorth
        ]),
        height: baseHeight,
        extrudedHeight: baseHeight + d,
        material: getColor(d),
        outline: true,
        outlineColor: Cesium.Color.BLACK.withAlpha(0.1)
        
      }
    });
  }
}

 
      // const maxHalfDeg = Math.max(halfWidthDeg, halfHeightDeg);
      // const range = maxHalfDeg * 111000 * 1.2;
      // viewer.camera.flyTo({
      //   destination: Cesium.Cartesian3.fromDegrees(alignedLon, alignedLat, range),
      //   orientation: { heading: 0, pitch: Cesium.Math.toRadians(-60) },
      //   duration: 2
      // });

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