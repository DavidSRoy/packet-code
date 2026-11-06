// Shared world model for the Packet traffic simulator.
// Units: meters, seconds. x grows east, y grows south (canvas space).

export type OrderStatus =
  | 'placed'
  | 'accepted'
  | 'picked_up'
  | 'loaded'
  | 'in_flight'
  | 'delivered'
  | 'failed'
  | 'cancelled';

export type DroneState =
  | 'idle'
  | 'to_pickup'
  | 'loading'
  | 'in_flight'
  | 'returning'
  | 'charging'
  | 'fault';

export interface Waypoint {
  id: string;
  name: string;
  kind: 'hub' | 'pickup' | 'dropoff' | 'corridor';
  x: number;
  y: number;
}

export interface TrailPoint {
  x: number;
  y: number;
}

export interface Drone {
  id: string;
  x: number;
  y: number;
  altitudeM: number;
  speedMps: number;
  headingDeg: number;
  batteryPct: number;
  state: DroneState;
  trail: TrailPoint[];
  // Flight plan: resolved waypoints, index of the current target leg.
  route: Waypoint[];
  leg: number;
  loop: boolean;
  cruiseM: number;
  speedBaseMps: number;
  speedFactor: number;
  // Sim time until which the drone sits grounded (turnaround at stops).
  pauseUntil: number;
  lastTrailAt: number;
}

export interface SimConfig {
  origin: { lat: number; lng: number };
  layers: number[];
  waypoints: Waypoint[];
}

export const CRUISE_LAYERS = [60, 80, 100];
export const CLIMB_MPS = 6;
export const BASE_SPEED_MPS = 12;

export interface Order {
  id: string;
  status: OrderStatus;
  droneId: string | null;
  placedAt: number;
  deliveredAt: number | null;
}

export interface Score {
  deliveries: number;
  conflicts: number;
  incidents: number;
  deliveryTimes: number[];
}

export const WORLD_W = 1800;
export const WORLD_H = 1200;
export const TICK_S = 0.1;
