// Vehicle attitude view: the X650 model posed by the drone's own attitude estimate (EKF).
// Model axes: +X front (GPS mast end), +Y up, +Z right = ArduPilot body FRD as (x, -z, y).
// World axes: +X north, +Y up, +Z east. So body->NED rotation R maps to three.js as M R M^T.
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

const DEG = Math.PI / 180;
const P = [0, 2, 1], S = [1, -1, 1];   // three axis i <- NED axis P[i] with sign S[i]

function bodyToThree(rollDeg, pitchDeg, yawDeg) {
  const r = rollDeg * DEG, p = pitchDeg * DEG, y = yawDeg * DEG;
  const cr = Math.cos(r), sr = Math.sin(r), cp = Math.cos(p), sp = Math.sin(p), cy = Math.cos(y), sy = Math.sin(y);
  const R = [  // ZYX: body -> NED
    [cp * cy, sr * sp * cy - cr * sy, cr * sp * cy + sr * sy],
    [cp * sy, sr * sp * sy + cr * cy, cr * sp * sy - sr * cy],
    [-sp, sr * cp, cr * cp],
  ];
  const m = new THREE.Matrix4();
  const e = [];
  for (let i = 0; i < 3; i++) for (let j = 0; j < 3; j++) e[i * 3 + j] = S[i] * S[j] * R[P[i]][P[j]];
  m.set(e[0], e[1], e[2], 0, e[3], e[4], e[5], 0, e[6], e[7], e[8], 0, 0, 0, 0, 1);
  return new THREE.Quaternion().setFromRotationMatrix(m);
}

function labelSprite(text, size, opacity) {
  const c = document.createElement("canvas");
  c.width = 128; c.height = 64;
  const g = c.getContext("2d");
  g.font = `500 ${size}px -apple-system, "Helvetica Neue", sans-serif`;
  g.fillStyle = `rgba(255,255,255,${opacity})`;
  g.textAlign = "center"; g.textBaseline = "middle";
  g.fillText(text, 64, 32);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: t, transparent: true, depthWrite: false }));
  s.scale.set(0.16, 0.08, 1);
  return s;
}

export class AttitudeView {
  constructor(canvas) {
    this.canvas = canvas;
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(32, 1, 0.01, 50);
    this.chase = true;
    this.target = new THREE.Quaternion();
    this.yawTarget = 0; this.camYaw = 0;
    this.armed = false;
    this.buildWorld();
    this.loadModel();
    new ResizeObserver(() => this.resize()).observe(canvas);
    this.resize();
    this.clock = new THREE.Clock();
    this.renderer.setAnimationLoop(() => this.frame());
  }

  buildWorld() {
    const sc = this.scene;
    sc.add(new THREE.HemisphereLight(0xe6eef6, 0x10141a, 1.6));
    const key = new THREE.DirectionalLight(0xffffff, 2.2); key.position.set(1.2, 2.5, 0.8); sc.add(key);
    const rim = new THREE.DirectionalLight(0x8fd8ff, 1.2); rim.position.set(-2, 0.6, -1.5); sc.add(rim);

    // world-fixed horizon: faint disc, compass ring with 10 degree ticks, cardinal letters
    const R = 0.62;
    const disc = new THREE.Mesh(new THREE.CircleGeometry(R, 96),
      new THREE.MeshBasicMaterial({ color: 0x9ab4c8, transparent: true, opacity: 0.045, side: THREE.DoubleSide, depthWrite: false }));
    disc.rotation.x = -Math.PI / 2; sc.add(disc);
    const ring = new THREE.Mesh(new THREE.RingGeometry(R - 0.002, R + 0.002, 192),
      new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.5, side: THREE.DoubleSide }));
    ring.rotation.x = -Math.PI / 2; sc.add(ring);
    const pts = [];
    for (let d = 0; d < 360; d += 10) {
      const a = d * DEG, len = d % 90 === 0 ? 0.07 : d % 30 === 0 ? 0.045 : 0.022;
      const n = Math.cos(a), e = Math.sin(a);
      pts.push(new THREE.Vector3(n * R, 0, e * R), new THREE.Vector3(n * (R - len), 0, e * (R - len)));
    }
    sc.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(pts),
      new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.55 })));
    const card = { N: 0, E: 90, S: 180, W: 270 };
    for (const [k, d] of Object.entries(card)) {
      const s = labelSprite(k, 34, k === "N" ? 0.95 : 0.6);
      s.position.set(Math.cos(d * DEG) * (R + 0.075), 0.012, Math.sin(d * DEG) * (R + 0.075));
      sc.add(s);
    }
    for (let d = 30; d < 360; d += 30) {
      if (d % 90 === 0) continue;
      const s = labelSprite(String(d / 10).padStart(2, "0"), 24, 0.35);
      s.position.set(Math.cos(d * DEG) * (R + 0.07), 0.01, Math.sin(d * DEG) * (R + 0.07));
      sc.add(s);
    }
    // vertical reference: gravity line under the drone
    const g = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, -0.28, 0)]);
    const gl = new THREE.Line(g, new THREE.LineDashedMaterial({ color: 0xffffff, dashSize: 0.012, gapSize: 0.01, transparent: true, opacity: 0.35 }));
    gl.computeLineDistances(); sc.add(gl);

    // the drone: pose group (attitude) -> centre offset -> model
    this.pose = new THREE.Group(); sc.add(this.pose);
    this.center = new THREE.Group(); this.pose.add(this.center);
    // body axes: nose (cyan), right (white, faint), so the attitude reads even before the model loads
    const axis = (dir, color, len, op) => {
      const geo = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), dir.clone().multiplyScalar(len)]);
      return new THREE.Line(geo, new THREE.LineBasicMaterial({ color, transparent: true, opacity: op }));
    };
    this.pose.add(axis(new THREE.Vector3(1, 0, 0), 0x5ad1ff, 0.5, 0.95));
    this.pose.add(axis(new THREE.Vector3(0, 0, 1), 0xffffff, 0.3, 0.35));
    const tip = new THREE.Mesh(new THREE.ConeGeometry(0.014, 0.045, 16), new THREE.MeshBasicMaterial({ color: 0x5ad1ff }));
    tip.rotation.z = -Math.PI / 2; tip.position.set(0.5, 0, 0); this.pose.add(tip);
  }

  loadModel() {
    const clay = new THREE.MeshStandardMaterial({ color: 0xd3d8de, roughness: 0.62, metalness: 0.05 });
    const dark = new THREE.MeshStandardMaterial({ color: 0x5b6470, roughness: 0.5, metalness: 0.2 });
    const loader = new GLTFLoader();
    const parts = ["/static/models/x650_frame.glb", "/static/models/x650_propulsion.glb"];
    Promise.all(parts.map(u => loader.loadAsync(u))).then(([frame, prop]) => {
      const model = new THREE.Group();
      frame.scene.traverse(o => { if (o.isMesh) o.material = clay; });
      prop.scene.traverse(o => { if (o.isMesh) o.material = dark; });
      model.add(frame.scene, prop.scene);
      // props: one disc per motor (15 in = 0.381 m), found from the propulsion model
      const box = new THREE.Box3().setFromObject(prop.scene);
      const motors = [];
      prop.scene.updateMatrixWorld(true);
      prop.scene.traverse(o => {
        if (!o.isMesh) return;
        const b = new THREE.Box3().setFromObject(o), c = b.getCenter(new THREE.Vector3());
        const q = (c.x > 0 ? 1 : 0) + (c.z > 0 ? 2 : 0);
        (motors[q] ??= new THREE.Box3()).union(b);
      });
      this.props = [];
      for (const b of motors.filter(Boolean)) {
        const c = b.getCenter(new THREE.Vector3());
        const disc = new THREE.Mesh(new THREE.CircleGeometry(0.19, 64),
          new THREE.MeshBasicMaterial({ color: 0xbfe9ff, transparent: true, opacity: 0.07, side: THREE.DoubleSide, depthWrite: false }));
        disc.rotation.x = -Math.PI / 2;
        disc.position.set(c.x, box.max.y + 0.012, c.z);
        model.add(disc); this.props.push(disc);
      }
      const all = new THREE.Box3().setFromObject(model);
      const mid = all.getCenter(new THREE.Vector3());
      model.position.sub(mid);  // rotate about the middle of the drone
      this.center.add(model);
    }).catch(err => console.warn("X650 model not loaded:", err));
  }

  resize() {
    const w = this.canvas.clientWidth, h = this.canvas.clientHeight;
    if (!w || !h) return;
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
  }

  update(s) {
    if (s.roll == null) return;
    const yaw = s.yaw ?? s.hdg ?? 0;
    this.target = bodyToThree(s.roll, s.pitch, yaw);
    this.yawTarget = yaw * DEG;
    this.armed = !!s.armed;
  }

  frame() {
    const dt = Math.min(this.clock.getDelta(), 0.1);
    const k = 1 - Math.exp(-dt * 14);
    this.pose.quaternion.slerp(this.target, k);
    // camera: behind the nose (chase) or fixed with north up the screen
    let d = this.yawTarget - this.camYaw;
    d = Math.atan2(Math.sin(d), Math.cos(d));
    this.camYaw += d * (1 - Math.exp(-dt * 3));
    const yaw = this.chase ? this.camYaw : 0;
    const dist = 1.75, elev = 24 * DEG;
    if (this.chase) {
      this.camera.position.set(-Math.cos(yaw) * dist * Math.cos(elev), dist * Math.sin(elev), -Math.sin(yaw) * dist * Math.cos(elev));
    } else {  // north-up: look down from the south
      this.camera.position.set(-dist * Math.cos(elev) * 0.35, dist * 1.05, 0.0001);
    }
    this.camera.lookAt(0, -0.02, 0);
    if (this.props) for (const p of this.props) p.material.opacity += ((this.armed ? 0.2 : 0.07) - p.material.opacity) * k;
    this.renderer.render(this.scene, this.camera);
  }
}

/* SpaceX-webcast style ring gauge (SVG). */
export function ringGauge(el, { label, unit, max }) {
  const R = 30, C = 2 * Math.PI * R, SWEEP = 0.75;
  el.innerHTML = `
    <svg viewBox="0 0 80 80">
      <circle cx="40" cy="40" r="${R}" fill="none" stroke="rgba(255,255,255,.14)" stroke-width="3"
        stroke-dasharray="${C * SWEEP} ${C}" transform="rotate(135 40 40)" stroke-linecap="round"/>
      <circle class="val" cx="40" cy="40" r="${R}" fill="none" stroke="#fff" stroke-width="3"
        stroke-dasharray="0 ${C}" transform="rotate(135 40 40)" stroke-linecap="round"/>
      <text class="num" x="40" y="42" text-anchor="middle">—</text>
      <text class="unit" x="40" y="54" text-anchor="middle">${unit}</text>
      <text class="unit" x="40" y="76" text-anchor="middle">${label}</text>
    </svg>`;
  const arc = el.querySelector(".val"), num = el.querySelector(".num");
  return v => {
    const f = v == null ? 0 : Math.max(0, Math.min(1, v / max));
    arc.setAttribute("stroke-dasharray", `${C * SWEEP * f} ${C}`);
    num.textContent = v == null ? "—" : Math.abs(v) < 10 ? v.toFixed(1) : Math.round(v);
  };
}
