export function drawDepthDots(viewer, grid, lon0, lat0, stepDeg) {
  const rows     = grid.length;
  const cols     = grid[0].length;
  const halfCols = (cols - 1) / 2;
  const halfRows = (rows - 1) / 2;

  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const d = grid[r][c];
      if (!d) continue;

      const lon = lon0 + (c - halfCols) * stepDeg;
      const lat = lat0 + (r - halfRows) * stepDeg;

      viewer.entities.add({
        position: Cesium.Cartesian3.fromDegrees(lon, lat, d),
        point: {
          pixelSize: 6,
          color: Cesium.Color.fromBytes(0, 0, 255).withAlpha(
            Cesium.Math.clamp(d / 3, 0.2, 0.8)
          )
        }
      });
    }
  }
  viewer.scene.requestRender();
}