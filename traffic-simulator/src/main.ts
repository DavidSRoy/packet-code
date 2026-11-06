import { World, Speed } from './sim/world.js';
import { drawRadar } from './sim/render.js';
import { TICK_S, SimConfig } from './sim/types.js';
import configData from '../config/waypoints.json';

const SPEEDS: Speed[] = [1, 5, 20];

const world = new World();
const config = configData as SimConfig;
world.waypoints = config.waypoints;

// Throwaway demo traffic until orders arrive in PR 3: two drones looping at
// different cruise layers so their paths cross safely.
world.spawnDrone('D1', ['hub', 'c-25th', 'bowls', 'c-east', 'bryant', 'c-north', 'hub'], 80, true);
world.spawnDrone('D2', ['hub', 'c-west', 'ave', 'c-west', 'mercer', 'c-45th', 'hub'], 60, true);
const canvas = document.getElementById('radar') as HTMLCanvasElement;
const ctx = canvas.getContext('2d')!;

const clockEl = document.getElementById('clock')!;
const btnPause = document.getElementById('btn-pause') as HTMLButtonElement;
const btnSpeed = document.getElementById('btn-speed') as HTMLButtonElement;
const btnReset = document.getElementById('btn-reset') as HTMLButtonElement;
const scoreEls = {
  deliveries: document.getElementById('score-deliveries')!,
  conflicts: document.getElementById('score-conflicts')!,
  incidents: document.getElementById('score-incidents')!,
  avg: document.getElementById('score-avg')!,
};

function refreshControls(): void {
  btnPause.textContent = world.paused ? 'Resume' : 'Pause';
  btnPause.classList.toggle('active', world.paused);
  btnSpeed.textContent = `${world.speed}x`;
}

btnPause.addEventListener('click', () => {
  world.togglePause();
  refreshControls();
});

btnSpeed.addEventListener('click', () => {
  const next = SPEEDS[(SPEEDS.indexOf(world.speed) + 1) % SPEEDS.length]!;
  world.setSpeed(next);
  refreshControls();
});

btnReset.addEventListener('click', () => {
  world.reset();
  refreshControls();
});

let accumulator = 0;
let last = performance.now();

function frame(now: number): void {
  const realDt = Math.min((now - last) / 1000, 0.5);
  last = now;

  if (!world.paused) {
    accumulator += realDt * world.speed;
    let guard = 0;
    while (accumulator >= TICK_S && guard++ < 400) {
      world.tick(TICK_S);
      accumulator -= TICK_S;
    }
  } else {
    accumulator = 0;
  }

  drawRadar(ctx, world);
  clockEl.textContent = `T+${world.simTime.toFixed(1)}s`;
  scoreEls.deliveries.textContent = String(world.score.deliveries);
  scoreEls.conflicts.textContent = String(world.score.conflicts);
  scoreEls.incidents.textContent = String(world.score.incidents);
  const avg = world.averageDeliveryTime();
  scoreEls.avg.textContent = avg === null ? '—' : `${avg.toFixed(1)}s`;

  requestAnimationFrame(frame);
}

refreshControls();
requestAnimationFrame(frame);
