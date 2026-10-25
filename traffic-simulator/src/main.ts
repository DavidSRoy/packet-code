import { World, Speed } from './sim/world.js';
import { drawRadar } from './sim/render.js';
import { TICK_S, SimConfig } from './sim/types.js';
import configData from '../config/waypoints.json';

const SPEEDS: Speed[] = [1, 5, 20];

const world = new World();
const config = configData as SimConfig;
world.waypoints = config.waypoints;

// Fleet parks at the hub; the order spawner puts them to work.
const LAYERS = [60, 80, 100, 60, 80];
for (let i = 0; i < 5; i++) {
  const drone = world.spawnDrone(`D${i + 1}`, ['hub'], LAYERS[i % LAYERS.length]!, false);
  drone.route = [];
  drone.leg = 0;
}

let selectedId: string | null = null;
const selectedEl = document.getElementById('selected')!;

const canvas = document.getElementById('radar') as HTMLCanvasElement;
canvas.addEventListener('click', (ev) => {
  const rect = canvas.getBoundingClientRect();
  const sx = canvas.width / rect.width;
  const x = (ev.clientX - rect.left) * sx;
  const y = (ev.clientY - rect.top) * sx;
  let best: string | null = null;
  let bestD = 24;
  for (const d of world.drones) {
    const dist = Math.hypot(d.x - x, d.y - y);
    if (dist < bestD) {
      bestD = dist;
      best = d.id;
    }
  }
  selectedId = best;
});
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

const cmdTarget = document.getElementById('cmd-target') as HTMLSelectElement;
for (const wp of world.waypoints) {
  const opt = document.createElement('option');
  opt.value = wp.id;
  opt.textContent = wp.name;
  cmdTarget.appendChild(opt);
}

function selectedDrone() {
  return world.drones.find((d) => d.id === selectedId) ?? null;
}

const wire = (id: string, fn: (d: NonNullable<ReturnType<typeof selectedDrone>>) => void) => {
  document.getElementById(id)!.addEventListener('click', () => {
    const d = selectedDrone();
    if (d) fn(d);
  });
};

wire('cmd-hold', (d) => world.commandHold(d));
wire('cmd-rtb', (d) => world.commandRTB(d));
wire('cmd-cancel', (d) => world.commandCancelOrder(d));
wire('cmd-60', (d) => world.commandLayer(d, 60));
wire('cmd-80', (d) => world.commandLayer(d, 80));
wire('cmd-100', (d) => world.commandLayer(d, 100));
wire('cmd-slow', (d) => world.commandSpeed(d, false));
wire('cmd-fast', (d) => world.commandSpeed(d, true));
wire('cmd-route', (d) => world.commandReroute(d, cmdTarget.value));

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

  drawRadar(ctx, world, selectedId);
  clockEl.textContent = `T+${world.simTime.toFixed(1)}s`;
    const commandsEl = document.getElementById('commands')!;
  const alertsEl = document.getElementById('alerts')!;
  const latestAlerts = world.alerts.slice(-6).reverse();
  alertsEl.innerHTML = latestAlerts
    .map((a) => `<li class="${a.critical ? 'critical' : ''}">T+${a.time.toFixed(0)}s ${a.text}</li>`)
    .join('');
  const selected = world.drones.find((d) => d.id === selectedId) ?? null;
  commandsEl.classList.toggle('hidden', selected === null);
  if (!selected) {
    if (selectedId !== null) selectedId = null;
    selectedEl.textContent = 'None';
  } else {
    const order = selected.task ? world.orders.find((o) => o.id === selected.task!.orderId) : null;
    const legs = selected.route.slice(selected.leg).map((w) => w.id).join(' → ');
    selectedEl.textContent =
      `${selected.id} · ${selected.state} · alt ${Math.round(selected.altitudeM)}m · ` +
      `layer ${selected.cruiseM}m · x${selected.speedFactor} · batt ${Math.round(selected.batteryPct)}% · ` +
      `order ${order ? `${order.id} (${order.status})` : '—'}` +
      (legs ? ` · via ${legs}` : '');
  }
  scoreEls.deliveries.textContent = String(world.score.deliveries);
  scoreEls.conflicts.textContent = String(world.score.conflicts);
  scoreEls.incidents.textContent = String(world.score.incidents);
  const avg = world.averageDeliveryTime();
  scoreEls.avg.textContent = avg === null ? '—' : `${avg.toFixed(1)}s`;

  requestAnimationFrame(frame);
}

refreshControls();
requestAnimationFrame(frame);
