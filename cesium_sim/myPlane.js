/* global Cesium */
export function rectFromCenterMeters_ENU(lonDeg, latDeg, halfSizeM) {
  lonDeg = Number(lonDeg); latDeg = Number(latDeg); halfSizeM = Number(halfSizeM);
  if (!Number.isFinite(lonDeg) || !Number.isFinite(latDeg) || !Number.isFinite(halfSizeM)) {
    throw new Error(`[rectFromCenterMeters] bad inputs lon=${lonDeg} lat=${latDeg} half=${halfSizeM}`);
  }
  const phi = Cesium.Math.toRadians(latDeg);
  const metersPerDegLon = 111320 * Math.cos(phi);
  const metersPerDegLat = 110540;
  const dLon = halfSizeM / metersPerDegLon;
  const dLat = halfSizeM / metersPerDegLat;
  return {
    west:  lonDeg - dLon,
    east:  lonDeg + dLon,
    south: latDeg - dLat,
    north: latDeg + dLat,
  };
}
