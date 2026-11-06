import { AlertEntry, BASE_SPEED_MPS, CLIMB_MPS, CONFLICT_WINDOW_S, Drone, Order, Score, SEP_ALT_M, SEP_DIST_M, TICK_S, Waypoint } from './types.js';

export type Speed = 1 | 5 | 20;

export class World {
  simTime = 0;
  speed: Speed = 1;
  paused = false;
  waypoints: Waypoint[] = [];
  drones: Drone[] = [];
  orders: Order[] = [];
  score: Score = { deliveries: 0, conflicts: 0, incidents: 0, deliveryTimes: [] };

  orderSpawnEvery = 40;
  private spawnTimer = 0;
  private orderSeq = 0;
  alerts: AlertEntry[] = [];
  private conflictUntil = new Map<string, number>();

  log(text: string, critical = false): void {
    this.alerts.push({ time: this.simTime, text, critical });
    if (this.alerts.length > 50) this.alerts.shift();
  }

  // Operator commands. Any route-changing command clears an auto-hold.
  commandReroute(drone: Drone, waypointId: string): void {
    drone.autoHold = false;
    this.assignRoute(drone, [this.droneStopId(drone), this.nearestCorridorId(this.waypointById(waypointId)!), waypointId].filter((v, i, a) => i === 0 || v !== a[i - 1]!));
    if (drone.state === 'idle') drone.state = 'in_flight';
    this.log(`${drone.id} rerouted → ${waypointId}`);
  }

  commandHold(drone: Drone): void {
    drone.autoHold = false;
    drone.route = [];
    drone.speedMps = 0;
    this.log(`${drone.id} holding`);
  }

  commandLayer(drone: Drone, layerM: number): void {
    drone.cruiseM = layerM;
    this.log(`${drone.id} layer → ${layerM}m`);
  }

  commandSpeed(drone: Drone, faster: boolean): void {
    drone.speedFactor = faster
      ? Math.min(2, drone.speedFactor + 0.5)
      : Math.max(0.5, drone.speedFactor - 0.5);
    this.log(`${drone.id} speed x${drone.speedFactor}`);
  }

  commandRTB(drone: Drone): void {
    drone.autoHold = false;
    drone.task = null;
    drone.state = 'returning';
    this.assignRoute(drone, this.routeThrough([this.droneStopId(drone), this.nearestCorridorId(this.waypointById('hub')!), 'hub']));
    this.log(`${drone.id} returning to hub`);
  }

  commandCancelOrder(drone: Drone): void {
    if (!drone.task) return;
    const order = this.orders.find((o) => o.id === drone.task!.orderId);
    if (order && order.status !== 'delivered') order.status = 'cancelled';
    drone.task = null;
    this.log(`${drone.id} order cancelled`, true);
    this.commandRTB(drone);
  }

  tick(dt: number = TICK_S): void {
    this.simTime += dt;
    this.spawnTimer += dt;
    if (this.spawnTimer >= this.orderSpawnEvery) {
      this.spawnTimer = 0;
      this.spawnOrder();
    }
    for (const drone of this.drones) {
      this.updateDrone(drone, dt);
    }
    this.assignOrders();
    this.advanceDeliveries();
    this.detectConflicts();
  }

  private detectConflicts(): void {
    const live = new Set<string>();
    for (let i = 0; i < this.drones.length; i++) {
      for (let j = i + 1; j < this.drones.length; j++) {
        const a = this.drones[i]!;
        const b = this.drones[j]!;
        // Ground traffic at the hub does not conflict; both must be airborne.
        if (a.altitudeM < 2 || b.altitudeM < 2) continue;
        const d2d = Math.hypot(a.x - b.x, a.y - b.y);
        const dAlt = Math.abs(a.altitudeM - b.altitudeM);
        if (d2d >= SEP_DIST_M || dAlt >= SEP_ALT_M) continue;
        const key = [a.id, b.id].sort().join('|');
        live.add(key);
        if (!this.conflictUntil.has(key)) {
          this.conflictUntil.set(key, this.simTime + CONFLICT_WINDOW_S);
          this.score.conflicts += 1;
          this.log(`CONFLICT ${a.id} × ${b.id} — resolve in ${CONFLICT_WINDOW_S}s`, true);
        }
        a.conflict = true;
        b.conflict = true;
      }
    }
    for (const [key, deadline] of [...this.conflictUntil]) {
      if (!live.has(key)) {
        this.conflictUntil.delete(key);
        this.log(`${key} resolved`, false);
        continue;
      }
      if (this.simTime >= deadline) {
        this.conflictUntil.delete(key);
        this.score.incidents += 1;
        const [aId, bId] = key.split('|');
        const a = this.drones.find((d) => d.id === aId)!;
        const b = this.drones.find((d) => d.id === bId)!;
        // The second drone auto-holds until separated or re-commanded.
        b.autoHold = true;
        this.log(`INCIDENT ${a.id} × ${b.id} — ${b.id} auto-holding`, true);
      }
    }
    const active = new Set<string>();
    for (const key of this.conflictUntil.keys()) {
      for (const id of key.split('|')) active.add(id);
    }
    for (const d of this.drones) {
      d.conflict = active.has(d.id);
    }
  }

  spawnOrder(): void {
    const pickups = this.waypoints.filter((w) => w.kind === 'pickup');
    const dropoffs = this.waypoints.filter((w) => w.kind === 'dropoff');
    if (pickups.length === 0 || dropoffs.length === 0) return;
    const pickup = pickups[Math.floor(Math.random() * pickups.length)]!;
    const dropoff = dropoffs[Math.floor(Math.random() * dropoffs.length)]!;
    this.orderSeq += 1;
    this.orders.push({
      id: `o${this.orderSeq}`,
      status: 'placed',
      droneId: null,
      pickupId: pickup.id,
      dropoffId: dropoff.id,
      placedAt: this.simTime,
      deliveredAt: null,
    });
  }

  private nearestCorridorId(wp: Waypoint): string {
    let best = 'hub';
    let bestD = Infinity;
    for (const c of this.waypoints) {
      if (c.kind !== 'corridor') continue;
      const d = Math.hypot(c.x - wp.x, c.y - wp.y);
      if (d < bestD) {
        bestD = d;
        best = c.id;
      }
    }
    return best;
  }

  private routeThrough(stopIds: string[]): string[] {
    const ids: string[] = [];
    for (const id of stopIds) {
      if (ids[ids.length - 1] !== id) ids.push(id);
    }
    return ids;
  }

  assignRoute(drone: Drone, ids: string[]): void {
    const route = ids.map((rid) => {
      const wp = this.waypointById(rid);
      if (!wp) throw new Error(`unknown waypoint ${rid}`);
      return wp;
    });
    drone.route = route;
    const first = route[0]!;
    drone.leg = route.length > 1 && drone.x === first.x && drone.y === first.y ? 1 : 0;
  }

  private assignOrders(): void {
    for (const order of this.orders) {
      if (order.status !== 'placed' || order.droneId) continue;
      const drone = this.drones.find((d) => d.task === null && d.state === 'idle');
      if (!drone) continue;
      const cA = this.nearestCorridorId(this.waypointById(order.pickupId)!);
      order.status = 'accepted';
      order.droneId = drone.id;
      drone.task = { orderId: order.id, phase: 'toPickup' };
      drone.state = 'to_pickup';
      this.assignRoute(drone, this.routeThrough([this.droneStopId(drone), cA, order.pickupId]));
    }
  }

  private droneStopId(drone: Drone): string {
    let best = this.waypoints[0]!.id;
    let bestD = Infinity;
    for (const w of this.waypoints) {
      if (w.kind === 'corridor') continue;
      const d = Math.hypot(w.x - drone.x, w.y - drone.y);
      if (d < bestD) {
        bestD = d;
        best = w.id;
      }
    }
    return best;
  }

  private at(drone: Drone, id: string): boolean {
    return drone.route.length === 1 && drone.route[0]!.id === id && drone.speedMps === 0;
  }

  private advanceDeliveries(): void {
    for (const drone of this.drones) {
      if (!drone.task) continue;
      const order = this.orders.find((o) => o.id === drone.task!.orderId);
      if (!order) {
        drone.task = null;
        continue;
      }
      const pickupId = order.pickupId;
      const dropoffId = order.dropoffId;
      const cA = this.nearestCorridorId(this.waypointById(pickupId)!);
      const cB = this.nearestCorridorId(this.waypointById(dropoffId)!);
      if (drone.task.phase === 'toPickup' && this.at(drone, pickupId)) {
        if (order.status === 'accepted') {
          order.status = 'picked_up';
          drone.state = 'loading';
          drone.pauseUntil = this.simTime + 20;
        } else if (order.status === 'picked_up' && this.simTime >= drone.pauseUntil) {
          order.status = 'loaded';
          drone.task.phase = 'toDropoff';
          drone.state = 'in_flight';
          this.assignRoute(drone, this.routeThrough([pickupId, cA, 'hub', cB, dropoffId]));
        }
      } else if (drone.task.phase === 'toDropoff' && this.at(drone, dropoffId)) {
        if (order.status === 'loaded') {
          order.status = 'delivered';
          order.deliveredAt = this.simTime;
          this.score.deliveries += 1;
          this.score.deliveryTimes.push(order.deliveredAt - order.placedAt);
          drone.task.phase = 'returning';
          drone.state = 'returning';
          this.assignRoute(drone, this.routeThrough([dropoffId, cB, 'hub']));
        }
      } else if (drone.task.phase === 'returning' && this.at(drone, 'hub')) {
        drone.task = null;
        drone.state = 'idle';
      }
    }
  }

  waypointById(id: string): Waypoint | undefined {
    return this.waypoints.find((w) => w.id === id);
  }

  spawnDrone(id: string, routeIds: string[], cruiseM: number, loop = false): Drone {
    const route = routeIds.map((rid) => {
      const wp = this.waypointById(rid);
      if (!wp) throw new Error(`unknown waypoint ${rid}`);
      return wp;
    });
    const start = route[0]!;
    const drone: Drone = {
      id,
      x: start.x,
      y: start.y,
      altitudeM: 0,
      speedMps: 0,
      headingDeg: 0,
      batteryPct: 100,
      state: 'idle',
      trail: [],
      route,
      leg: 1 % route.length,
      loop,
      cruiseM,
      speedBaseMps: BASE_SPEED_MPS,
      speedFactor: 1,
      pauseUntil: 0,
      lastTrailAt: -1,
      task: null,
      conflict: false,
      autoHold: false,
    };
    this.drones.push(drone);
    return drone;
  }

  protected updateDrone(drone: Drone, dt: number): void {
    if (drone.autoHold) {
      drone.speedMps = 0;
      this.settleAltitude(drone, drone.cruiseM, dt);
      return;
    }
    if (drone.route.length === 0) return;
    if (this.simTime < drone.pauseUntil) {
      drone.speedMps = 0;
      this.settleAltitude(drone, 0, dt);
      return;
    }
    const target = drone.route[drone.leg]!;
    const dx = target.x - drone.x;
    const dy = target.y - drone.y;
    const dist = Math.hypot(dx, dy);
    if (dist < 0.01) {
      // Parked at the only remaining waypoint. Settle altitude and wait;
      // arrival already fired when the drone got here.
      drone.speedMps = 0;
      this.settleAltitude(drone, target.kind === 'corridor' ? drone.cruiseM : 0, dt);
      return;
    }
    const speed = drone.speedBaseMps * drone.speedFactor;
    if (dist <= Math.max(speed * dt, 0.5)) {
      drone.x = target.x;
      drone.y = target.y;
      this.arrive(drone, target);
    } else {
      drone.x += (dx / dist) * speed * dt;
      drone.y += (dy / dist) * speed * dt;
      drone.headingDeg = (Math.atan2(dx, -dy) * 180) / Math.PI;
      drone.speedMps = speed;
      this.settleAltitude(drone, drone.cruiseM, dt);
      if (drone.state === 'idle' || drone.state === 'returning') drone.state = 'in_flight';
    }
    drone.batteryPct = Math.max(0, drone.batteryPct - dt * 0.05);
    if (this.simTime - drone.lastTrailAt >= 0.5) {
      drone.trail.push({ x: drone.x, y: drone.y });
      if (drone.trail.length > 40) drone.trail.shift();
      drone.lastTrailAt = this.simTime;
    }
  }

  private arrive(drone: Drone, target: Waypoint): void {
    drone.speedMps = 0;
    // Arm the ground pause once. A drone already sitting at a stop is
    // re-arrived at every tick; re-arming the pause here would freeze it.
    const armPause = () => {
      if (target.kind !== 'corridor' && drone.pauseUntil <= this.simTime) {
        drone.pauseUntil = this.simTime + 3;
      }
    };
    if (drone.loop) {
      armPause();
      drone.leg = (drone.leg + 1) % drone.route.length;
      return;
    }
    if (drone.leg + 1 < drone.route.length) {
      armPause();
      drone.leg += 1;
      return;
    }
    // Terminal arrival: stay here. Stops ground the drone (it descends
    // during the pause); a bare corridor endpoint hovers at cruise.
    armPause();
    drone.route = [target];
    drone.leg = 0;
    drone.state = 'idle';
  }

  private settleAltitude(drone: Drone, target: number, dt: number): void {
    const d = target - drone.altitudeM;
    const step = CLIMB_MPS * dt;
    drone.altitudeM += Math.abs(d) <= step ? d : Math.sign(d) * step;
  }

  setSpeed(speed: Speed): void {
    this.speed = speed;
  }

  togglePause(): void {
    this.paused = !this.paused;
  }

  reset(): void {
    this.simTime = 0;
    this.drones = [];
    this.orders = [];
    this.alerts = [];
    this.conflictUntil.clear();
    this.score = { deliveries: 0, conflicts: 0, incidents: 0, deliveryTimes: [] };
  }

  averageDeliveryTime(): number | null {
    const times = this.score.deliveryTimes;
    if (times.length === 0) return null;
    return times.reduce((a, b) => a + b, 0) / times.length;
  }
}
