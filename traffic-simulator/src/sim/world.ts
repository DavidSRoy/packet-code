import { Drone, Order, Score, TICK_S, Waypoint } from './types.js';

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

  // Overridden by later flight logic; PR 1 keeps drones parked.
  protected updateDrone(_drone: Drone, _dt: number): void {}

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
