import { BASE_SPEED_MPS, CLIMB_MPS, Drone, Order, Score, TICK_S, Waypoint } from './types.js';

export type Speed = 1 | 5 | 20;

export class World {
  simTime = 0;
  speed: Speed = 1;
  paused = false;
  waypoints: Waypoint[] = [];
  drones: Drone[] = [];
  orders: Order[] = [];
  score: Score = { deliveries: 0, conflicts: 0, incidents: 0, deliveryTimes: [] };

  tick(dt: number = TICK_S): void {
    this.simTime += dt;
    for (const drone of this.drones) {
      this.updateDrone(drone, dt);
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
    };
    this.drones.push(drone);
    return drone;
  }

  protected updateDrone(drone: Drone, dt: number): void {
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
    if (drone.loop) {
      if (target.kind !== 'corridor') drone.pauseUntil = this.simTime + 3;
      drone.leg = (drone.leg + 1) % drone.route.length;
      return;
    }
    if (drone.leg + 1 < drone.route.length) {
      if (target.kind !== 'corridor') drone.pauseUntil = this.simTime + 3;
      drone.leg += 1;
      return;
    }
    // Terminal arrival: stay here. Stops ground the drone (it descends
    // during the pause); a bare corridor endpoint hovers at cruise.
    if (target.kind !== 'corridor') drone.pauseUntil = this.simTime + 3;
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
    this.score = { deliveries: 0, conflicts: 0, incidents: 0, deliveryTimes: [] };
  }

  averageDeliveryTime(): number | null {
    const times = this.score.deliveryTimes;
    if (times.length === 0) return null;
    return times.reduce((a, b) => a + b, 0) / times.length;
  }
}
