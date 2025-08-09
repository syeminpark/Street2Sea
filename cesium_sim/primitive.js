// helpers.js
import { waitForFrames } from "./waitHelpers.js";

export async function addExtrudedPolygonPrimitive(viewer, opts) {
  const {
    west, south, east, north,
    height, extrudedHeight,
    color = Cesium.Color.SKYBLUE.withAlpha(0.8),
    outlineColor = Cesium.Color.DARKBLUE.withAlpha(0.8),
    showOutline = true,
  } = opts;

  const hierarchy = new Cesium.PolygonHierarchy(
    Cesium.Cartesian3.fromDegreesArray([
      west, south,  east, south,  east, north,  west, north
    ])
  );

  const fillGeom = new Cesium.PolygonGeometry({
    polygonHierarchy: hierarchy,
    height,
    extrudedHeight,
    vertexFormat: Cesium.PerInstanceColorAppearance.VERTEX_FORMAT,
    perPositionHeight: false,
    closeTop: true,
    closeBottom: true,
  });

  const fillInstance = new Cesium.GeometryInstance({
    geometry: fillGeom,
    attributes: { color: Cesium.ColorGeometryInstanceAttribute.fromColor(color) },
  });

  const fillPrim = new Cesium.Primitive({
    geometryInstances: [fillInstance],
    appearance: new Cesium.PerInstanceColorAppearance({
      flat: true,
      translucent: color.alpha < 1.0,
    }),
    asynchronous: true,
  });

  viewer.scene.primitives.add(fillPrim);

  let outlinePrim = null;
  if (showOutline) {
    const outlineGeom = new Cesium.PolygonOutlineGeometry({ polygonHierarchy: hierarchy, height, extrudedHeight });
    const outlineInstance = new Cesium.GeometryInstance({
      geometry: outlineGeom,
      attributes: { color: Cesium.ColorGeometryInstanceAttribute.fromColor(outlineColor) },
    });
    outlinePrim = new Cesium.Primitive({
      geometryInstances: [outlineInstance],
      appearance: new Cesium.PerInstanceColorAppearance({
        flat: true,
        translucent: outlineColor.alpha < 1.0
      }),
      asynchronous: true,
    });
    viewer.scene.primitives.add(outlinePrim);
  }

  // Wait for GPU resources to be created
  await fillPrim.readyPromise;
  if (outlinePrim) await outlinePrim.readyPromise;

  // Ensure draw commands land and a frame is rendered
  await waitForFrames(viewer.scene, 2);

  return { fillPrim, outlinePrim };
}
