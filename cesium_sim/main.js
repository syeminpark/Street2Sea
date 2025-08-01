import { initNodeStream } from './receiveFromNode.js';
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

initNodeStream(viewer, async (d, v) => {

    console.log("data", JSON.stringify(d, null, 2));

    const { lng, lat, heading,fov, size} = d[0];
    const [pos] = await Cesium.sampleTerrainMostDetailed(
    viewer.terrainProvider,
    [Cesium.Cartographic.fromDegrees(lng, lat)]
  );

  const dest = Cesium.Cartesian3.fromDegrees(lng, lat, pos.height + hAGL); 
  v.camera.setView({
    destination : dest,
    orientation : {
      heading : Cesium.Math.toRadians(heading),
      pitch   : 0,
      roll    : 0
    }
  });
  viewer.camera.frustum.fov = Cesium.Math.toRadians(fov);

  // 2) Optionally drop a marker
//   const id = `pano-${d.pano_id}`;
//   let ent  = v.entities.getById(id);
//   if (!ent) ent = v.entities.add({
//     id,
//     point: { pixelSize: 12, color: Cesium.Color.CYAN }
//   });
//   ent.position = dest;

  console.log('Updated scene from payload', d);
});
})()