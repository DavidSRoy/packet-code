// Headless regression checks for the sim core. Runs against compiled JS:
//   npm test  (compiles src/sim, runs this file, cleans up)
import assert from 'node:assert';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import worldModule from '../.test-out/world.js';
const { World } = worldModule;

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const config = JSON.parse(readFileSync(join(root, 'config/waypoints.json'), 'utf8'));

function freshWorld() {
  const w = new World();
  w.waypoints = config.waypoints;
  return w;
}

// Regression: a route ending at a stop must land (state idle, altitude 0),
// not hover at cruise forever.
{
  const w = freshWorld();
  w.orderSpawnEvery = 1e9; // isolate from the order spawner
  const d = w.spawnDrone('T1', ['hub', 'c-25th', 'bowls'], 80, false);
  for (let i = 0; i < 3000; i++) w.tick(0.1);
  assert.strictEqual(d.state, 'idle');
  assert.strictEqual(d.altitudeM, 0);
  console.log('landing: ok');
}

// Delivery loop: orders flow placed -> delivered, score follows.
{
  const w = freshWorld();
  const layers = [60, 80, 100, 60, 80];
  for (let i = 0; i < 5; i++) {
    const drone = w.spawnDrone(`D${i + 1}`, ['hub'], layers[i], false);
    drone.route = [];
  }
  for (let i = 0; i < 20000; i++) w.tick(0.1);
  const delivered = w.orders.filter((o) => o.status === 'delivered');
  assert.ok(delivered.length >= 1, `expected deliveries, got ${delivered.length}`);
  assert.strictEqual(w.score.deliveries, delivered.length);
  assert.ok((w.averageDeliveryTime() ?? 0) > 0);
  for (const o of w.orders) {
    assert.ok(
      ['placed', 'accepted', 'picked_up', 'loaded', 'in_flight', 'delivered', 'failed', 'cancelled'].includes(o.status),
      `bad status ${o.status}`,
    );
  }
  console.log(`delivery: ok (${delivered.length} delivered)`);
}

// Cruise layers: a drone on a long leg reaches its assigned layer.
{
  const w = freshWorld();
  const d = w.spawnDrone('T2', ['hub', 'c-east', 'bryant'], 100, false);
  for (let i = 0; i < 200; i++) w.tick(0.1);
  assert.ok(d.altitudeM >= 95, `cruise layer, alt=${d.altitudeM}`);
  console.log('cruise: ok');
}
