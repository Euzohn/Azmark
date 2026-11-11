/**
 * Run with `npm test` (Node's built-in test runner; no extra dependencies).
 *
 * These helpers guard the map's low-zoom aggregation contract: nearby stops
 * collapse into one city-level point without ever moving the cluster away from
 * its members.
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import { clusterByDistance, haversineKm } from "./geo.ts";

const beijingSouth = { id: "北京南", point: [116.372, 39.863] as [number, number] };
const beijingWest = { id: "北京西", point: [116.315, 39.894] as [number, number] };
const beijingMain = { id: "北京", point: [116.421, 39.901] as [number, number] };
const shanghai = { id: "上海虹桥", point: [121.316, 31.196] as [number, number] };

test("clusterByDistance groups nearby stops into one cluster", () => {
  const clusters = clusterByDistance([beijingSouth, beijingWest, beijingMain], 45);
  assert.equal(clusters.length, 1);
  assert.equal(clusters[0]!.members.length, 3);
});

test("clusterByDistance keeps distant stops separate", () => {
  const clusters = clusterByDistance([beijingSouth, shanghai], 45);
  assert.equal(clusters.length, 2);
  assert.ok(clusters.every((cluster) => cluster.members.length === 1));
});

test("cluster point is the mean of its members", () => {
  const clusters = clusterByDistance([beijingSouth, beijingWest], 45);
  const [lon, lat] = clusters[0]!.point;
  assert.ok(Math.abs(lon - (beijingSouth.point[0] + beijingWest.point[0]) / 2) < 1e-9);
  assert.ok(Math.abs(lat - (beijingSouth.point[1] + beijingWest.point[1]) / 2) < 1e-9);
  // The centroid must stay within the clustering radius of every member.
  for (const member of clusters[0]!.members) {
    assert.ok(haversineKm(clusters[0]!.point, member.point) <= 45);
  }
});

test("clusterByDistance is deterministic for a given input order", () => {
  const first = clusterByDistance([beijingSouth, beijingWest, shanghai], 45);
  const second = clusterByDistance([beijingSouth, beijingWest, shanghai], 45);
  assert.deepEqual(
    first.map((cluster) => cluster.members.map((member) => member.id)),
    second.map((cluster) => cluster.members.map((member) => member.id)),
  );
  // Seeds follow input order: the first stop owns the first cluster.
  assert.equal(first[0]!.members[0]!.id, "北京南");
});

test("clusterByDistance handles an empty list", () => {
  assert.deepEqual(clusterByDistance([], 45), []);
});
