const EARTH_RADIUS_KM = 6371;

const toRad = (deg: number) => (deg * Math.PI) / 180;
const toDeg = (rad: number) => (rad * 180) / Math.PI;

export type LonLat = [number, number];

export function haversineKm(a: LonLat, b: LonLat): number {
  const [lon1, lat1] = a.map(toRad) as [number, number];
  const [lon2, lat2] = b.map(toRad) as [number, number];
  const h =
    Math.sin((lat2 - lat1) / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin((lon2 - lon1) / 2) ** 2;
  return 2 * EARTH_RADIUS_KM * Math.asin(Math.min(1, Math.sqrt(h)));
}

/**
 * Interpolate `steps + 1` points along the great circle between two
 * `[lon, lat]` points. Longitudes are "unwrapped" so successive points never
 * jump more than 180°, letting MapLibre draw a continuous line across the
 * antimeridian instead of taking the long way around.
 */
export function greatCircle(a: LonLat, b: LonLat, steps = 64): LonLat[] {
  const [lon1, lat1] = a;
  const [lon2, lat2] = b;
  const φ1 = toRad(lat1);
  const λ1 = toRad(lon1);
  const φ2 = toRad(lat2);
  let λ2 = toRad(lon2);

  // unwrap longitude so the interpolation takes the short way
  let dλ = λ2 - λ1;
  if (dλ > Math.PI) dλ -= 2 * Math.PI;
  if (dλ < -Math.PI) dλ += 2 * Math.PI;
  λ2 = λ1 + dλ;

  const d = 2 * Math.asin(
    Math.min(
      1,
      Math.sqrt(
        Math.sin((φ2 - φ1) / 2) ** 2 +
          Math.cos(φ1) * Math.cos(φ2) * Math.sin(dλ / 2) ** 2,
      ),
    ),
  );

  if (d === 0) return [a, b];

  const points: LonLat[] = [];
  for (let i = 0; i <= steps; i += 1) {
    const f = i / steps;
    const A = Math.sin((1 - f) * d) / Math.sin(d);
    const B = Math.sin(f * d) / Math.sin(d);
    const x = A * Math.cos(φ1) * Math.cos(λ1) + B * Math.cos(φ2) * Math.cos(λ2);
    const y = A * Math.cos(φ1) * Math.sin(λ1) + B * Math.cos(φ2) * Math.sin(λ2);
    const z = A * Math.sin(φ1) + B * Math.sin(φ2);
    points.push([
      toDeg(Math.atan2(y, x)),
      toDeg(Math.atan2(z, Math.sqrt(x * x + y * y))),
    ]);
  }
  return points;
}
