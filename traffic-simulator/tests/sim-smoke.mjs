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

// Conflicts: a close trail at one layer breaches; ignoring it records an incident.
{
  const w = freshWorld();
  w.orderSpawnEvery = 1e9;
  const a = w.spawnDrone('CA', ['hub', 'c-east', 'bryant'], 80, false);
  const b = w.spawnDrone('CB', ['hub', 'c-east', 'bryant'], 80, false);
  b.pauseUntil = 1; // 1 s staggered takeoff -> ~12 m trail, ~6 m apart in alt
  let sawConflict = false;
  for (let i = 0; i < 2000 && w.score.incidents === 0; i++) {
    w.tick(0.1);
    if (w.score.conflicts > 0) sawConflict = true;
  }
  assert.ok(sawConflict, 'expected a separation breach');
  assert.ok(w.score.incidents >= 1, 'expected an incident after the countdown');
  assert.ok(a.autoHold || b.autoHold, 'one drone auto-holds');
  console.log('conflict: ok');
}

// Conflict save: changing layer during the countdown separates the pair.
{
  const w = freshWorld();
  w.orderSpawnEvery = 1e9;
  w.spawnDrone('SA', ['hub', 'c-east', 'bryant'], 80, false);
  w.spawnDrone('SB', ['hub', 'c-east', 'bryant'], 80, false).pauseUntil = 1;
  let intervened = false;
  for (let i = 0; i < 2000 && !intervened; i++) {
    w.tick(0.1);
    if (w.score.conflicts > 0) {
      intervened = true;
    }
  }
  assert.ok(intervened, 'conflict happened');
  // Hold the trailer: the leader pulls away and the pair separates.
  // (A layer change would not help here: both are still climbing in lockstep.)
  const sb = w.drones.find((d) => d.id === 'SB');
  w.commandHold(sb);
  // The pair must separate before the 10 s countdown ends.
  let separated = false;
  for (let i = 0; i < 100; i++) {
    w.tick(0.1);
    const sa = w.drones.find((d) => d.id === 'SA');
    const sb = w.drones.find((d) => d.id === 'SB');
    if (!sa.conflict && !sb.conflict) {
      separated = true;
      break;
    }
  }
  assert.ok(separated, 'pair separated after layer change');
  assert.strictEqual(w.score.incidents, 0, 'save, no incident');
  console.log('conflict-save: ok');
}
