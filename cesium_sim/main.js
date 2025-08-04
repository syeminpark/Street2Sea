import { initNodeStream } from './receiveFromNode.js'
Cesium.Ion.defaultAccessToken = window.CESIUM_ION_TOKEN;

(async () => {
  /* ──  Viewer  ─────────────────────────────────────────── */
  const viewer = new Cesium.Viewer('cesiumContainer', {
    terrainProvider : await Cesium.CesiumTerrainProvider.fromIonAssetId(2767062),
    baseLayerPicker : false,
    timeline        : false,
    animation       : false,
    requestRenderMode: true,
    geocoder        : false,
    homeButton      : false,
    sceneModePicker : false,
    navigationHelpButton: false
  });

  // add OSM imagery
  viewer.imageryLayers.addImageryProvider(
    new Cesium.UrlTemplateImageryProvider({
      url: '/osm/{z}/{x}/{y}.png',
      maximumLevel: 19,
      credit: '© OpenStreetMap contributors'
    })
  );

  // lock user inputs
  viewer.scene.screenSpaceCameraController.enableInputs = false;

  /* ──  Initial camera  ─────────────────────────────────── */
  const initialLon = 139.6142023961819;
  const initialLat = 35.65256823531473;
  const hAGL        = 2.05; // meters above ground

  // sample terrain for the initial view
  const [initialPos] = await Cesium.sampleTerrainMostDetailed(
    viewer.terrainProvider,
    [ Cesium.Cartographic.fromDegrees(initialLon, initialLat) ]
  );

  viewer.camera.setView({
    destination : Cesium.Cartesian3.fromDegrees(
      initialLon,
      initialLat,
      initialPos.height + hAGL
    ),
    orientation : {
      heading: Cesium.Math.toRadians(336),
      pitch:   0,
      roll:    0
    }
  });
  viewer.camera.frustum.fov = Cesium.Math.toRadians(120);

  /* ──  Eagerly load 3D Tileset  ────────────────────────── */
  const tileset = await Cesium.Cesium3DTileset.fromIonAssetId(2602291);
  Object.assign(tileset, {
    maximumScreenSpaceError:        128,
    dynamicScreenSpaceError:        true,
    dynamicScreenSpaceErrorDensity: 2e-4,
   preloadWhenHidden:              true,
  updateWhenHidden:               true,
   throttleRequests:               false,  // default true; false → unlimited concurrent fetches
  });
  viewer.scene.primitives.add(tileset);
  console.log('loading tileset')
  // optional: wait until root tile is ready
  await tileset.readyPromise;

initNodeStream(viewer, async (payload, v) => {
  console.log("data received:", JSON.stringify(payload, null, 2));

  if (payload.type === "depth") {
  const { value, location, lat:cameraLat, lng:cameraLng } = payload;

  // 1. Correct order: lon first, then lat
  const [buildingLat,buildingLon] = location.split(',').map(Number);
  console.log(buildingLat,cameraLat,buildingLon,cameraLng)

  // 2. Terrain height at that spot
  const [pos] = await Cesium.sampleTerrainMostDetailed(
    viewer.terrainProvider,
    [Cesium.Cartographic.fromDegrees(buildingLon,buildingLat)]
  );

  const position = Cesium.Cartesian3.fromDegrees(
    buildingLon,buildingLat, pos.height + 1.5
  );

  const alwaysOnTop = Number.POSITIVE_INFINITY;   // or 500 m if you prefer

  // 4. Add entity
 const entity= viewer.entities.add({
    position,
    point: {
      pixelSize: 15,
      color: Cesium.Color.RED,
      disableDepthTestDistance: alwaysOnTop      // ← NEW
    },
    label: {
      text: `Depth: ${value.toFixed(2)} m`, // ← use depthValue
      font: '24px sans-serif',
      fillColor: Cesium.Color.BLUE,
      showBackground: true,
      horizontalOrigin: Cesium.HorizontalOrigin.CENTER,
      verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
      disableDepthTestDistance: alwaysOnTop
    }
  });
  // 5. Force redraw
  viewer.scene.requestRender();


  } 
  else {
    const { lng:cameraLng, lat:cameraLat, heading, fov,location } = payload[0];
    const [buildingLat, buildingLon] = location.split(',').map(Number);

    const [pos] = await Cesium.sampleTerrainMostDetailed(
      viewer.terrainProvider,
      [Cesium.Cartographic.fromDegrees(cameraLng, cameraLat)]
    );
    
  
    const dest = Cesium.Cartesian3.fromDegrees(cameraLng, cameraLat, pos.height + hAGL);
    viewer.camera.setView({
      destination: dest,
      orientation: {
        heading: Cesium.Math.toRadians(heading),
        pitch: 0,
        roll: 0
      }
    });

    viewer.camera.frustum.fov = Cesium.Math.toRadians(fov);
viewer.scene.requestRender();          // draw current view once

  }
});

})()