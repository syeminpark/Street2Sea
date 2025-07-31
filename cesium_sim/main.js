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
    geocoder:false, homeButton:false, sceneModePicker:false,
    navigationHelpButton:false
  });

  viewer.imageryLayers.addImageryProvider(
    new Cesium.UrlTemplateImageryProvider({
      url:'/osm/{z}/{x}/{y}.png', maximumLevel:19,
      credit:'© OpenStreetMap contributors'
    })
  );
  viewer.scene.screenSpaceCameraController.enableInputs = false;

  /* ──  Initial camera  ─────────────────────────────────── */
  const lon = 139.6142023961819;
  const lat =  35.65256823531473;
  const hAGL = 2.05;

  const [pos] = await Cesium.sampleTerrainMostDetailed(
    viewer.terrainProvider,
    [Cesium.Cartographic.fromDegrees(lon, lat)]
  );
  viewer.camera.setView({
    destination : Cesium.Cartesian3.fromDegrees(lon, lat, pos.height + hAGL),
    orientation : { heading:Cesium.Math.toRadians(336), pitch:0, roll:0 }
  });
  viewer.camera.frustum.fov = Cesium.Math.toRadians(120);

  /* ──  Load tileset after first moveEnd  ───────────────── */
  let loaded = false;
  viewer.camera.moveEnd.addEventListener(async () => {
    if (loaded) return;  loaded = true;

    const ts = await Cesium.Cesium3DTileset.fromIonAssetId(2602291);
    Object.assign(ts, {
      maximumScreenSpaceError      : 128,
      dynamicScreenSpaceError      : true,
      dynamicScreenSpaceErrorDensity:2e-4,
      preloadWhenHidden:false, updateWhenHidden:false
    });
    viewer.scene.primitives.add(ts);
    await ts.readyPromise;
  });

initNodeStream(viewer, (d, v) => {

     console.log("!!!data", JSON.stringify(d, null, 2));
    

//   const dest = Cesium.Cartesian3.fromDegrees(d.lng, d.lat, 2.0); // 2 m AGL
//   v.camera.setView({
//     destination : dest,
//     orientation : {
//       heading : Cesium.Math.toRadians(d.heading ?? 0),
//       pitch   : 0,
//       roll    : 0
//     }
//   });
//   v.camera.frustum.fov = Cesium.Math.toRadians(d.fov ?? 90);

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