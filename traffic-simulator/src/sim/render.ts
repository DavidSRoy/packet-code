import { WORLD_H, WORLD_W } from './types.js';
import { World } from './world.js';

const GRID_M = 100;

export function drawRadar(ctx: CanvasRenderingContext2D, world: World): void {
  ctx.fillStyle = '#0c0c0c';
  ctx.fillRect(0, 0, WORLD_W, WORLD_H);

  ctx.strokeStyle = '#1e1e1e';
  ctx.lineWidth = 1;
  ctx.beginPath();
  for (let x = 0; x <= WORLD_W; x += GRID_M) {
    ctx.moveTo(x + 0.5, 0);
    ctx.lineTo(x + 0.5, WORLD_H);
  }
  for (let y = 0; y <= WORLD_H; y += GRID_M) {
    ctx.moveTo(0, y + 0.5);
    ctx.lineTo(WORLD_W, y + 0.5);
  }
  ctx.stroke();

  ctx.strokeStyle = '#3a3a3a';
  ctx.lineWidth = 2;
  ctx.strokeRect(1, 1, WORLD_W - 2, WORLD_H - 2);

  // Waypoint and drone layers arrive in later PRs.
  void world;
}
