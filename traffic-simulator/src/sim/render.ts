import { WORLD_H, WORLD_W } from './types.js';
import { World } from './world.js';

const GRID_M = 100;

function fitCanvas(ctx: CanvasRenderingContext2D): number {
  const s = Math.min(ctx.canvas.width / WORLD_W, ctx.canvas.height / WORLD_H);
  ctx.setTransform(s, 0, 0, s, 0, 0);
  return s;
}

export function drawRadar(ctx: CanvasRenderingContext2D, world: World): void {
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.fillStyle = '#0c0c0c';
  ctx.fillRect(0, 0, ctx.canvas.width, ctx.canvas.height);
  const s = fitCanvas(ctx);
  ctx.lineWidth = 1 / s;

  ctx.strokeStyle = '#1e1e1e';
  ctx.beginPath();
  for (let x = 0; x <= WORLD_W; x += GRID_M) {
    ctx.moveTo(x, 0);
    ctx.lineTo(x, WORLD_H);
  }
  for (let y = 0; y <= WORLD_H; y += GRID_M) {
    ctx.moveTo(0, y);
    ctx.lineTo(WORLD_W, y);
  }
  ctx.stroke();

  ctx.strokeStyle = '#3a3a3a';
  ctx.lineWidth = 2 / s;
  ctx.strokeRect(0, 0, WORLD_W, WORLD_H);

  drawNetwork(ctx, world);
  drawDrones(ctx, world);
}

function drawNetwork(ctx: CanvasRenderingContext2D, world: World): void {
  const s = ctx.canvas.width / WORLD_W;
  const corridors = world.waypoints.filter((w) => w.kind === 'corridor');
  const hub = world.waypoints.find((w) => w.kind === 'hub');

  ctx.strokeStyle = '#2f2f2f';
  ctx.lineWidth = 1.5 / s;
  ctx.beginPath();
  if (hub) {
    for (const c of corridors) {
      ctx.moveTo(hub.x, hub.y);
      ctx.lineTo(c.x, c.y);
    }
  }
  // Each stop links to its nearest corridor.
  for (const w of world.waypoints) {
    if (w.kind === 'pickup' || w.kind === 'dropoff') {
      let best: typeof w | null = null;
      let bestD = Infinity;
      for (const c of corridors) {
        const d = Math.hypot(c.x - w.x, c.y - w.y);
        if (d < bestD) {
          bestD = d;
          best = c;
        }
      }
      if (best) {
        ctx.moveTo(w.x, w.y);
        ctx.lineTo(best.x, best.y);
      }
    }
  }
  ctx.stroke();

  for (const w of world.waypoints) {
    if (w.kind === 'hub') {
      ctx.fillStyle = '#b4432f';
      ctx.fillRect(w.x - 6, w.y - 6, 12, 12);
    } else if (w.kind === 'pickup') {
      ctx.fillStyle = '#d3a13f';
      ctx.fillRect(w.x - 4, w.y - 4, 8, 8);
    } else if (w.kind === 'dropoff') {
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(w.x - 4, w.y - 4, 8, 8);
    } else {
      ctx.fillStyle = '#6a6a6a';
      ctx.beginPath();
      ctx.arc(w.x, w.y, 3, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.fillStyle = '#9a9a9a';
    ctx.font = `${11 / s}px sans-serif`;
    ctx.fillText(w.name, w.x + 8, w.y - 8);
  }
}

function drawDrones(ctx: CanvasRenderingContext2D, world: World): void {
  const s = ctx.canvas.width / WORLD_W;
  for (const d of world.drones) {
    if (d.trail.length > 1) {
      ctx.strokeStyle = 'rgba(255,255,255,0.35)';
      ctx.lineWidth = 1.5 / s;
      ctx.beginPath();
      ctx.moveTo(d.trail[0]!.x, d.trail[0]!.y);
      for (const p of d.trail) ctx.lineTo(p.x, p.y);
      ctx.lineTo(d.x, d.y);
      ctx.stroke();
    }
    ctx.fillStyle = '#ffffff';
    ctx.beginPath();
    ctx.arc(d.x, d.y, 5, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = '#ffffff';
    ctx.font = `${12 / s}px sans-serif`;
    ctx.fillText(`${d.id} ${Math.round(d.altitudeM)}m`, d.x + 9, d.y + 4);
  }
}
