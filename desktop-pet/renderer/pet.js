// 桌面小柴 —— 渲染层
// 3D 模型直接复用 training/companion-preview/dog/3d/model.js（程序化几何，不依赖外部贴图）

import * as T from '../../training/companion-preview/dog/3d/vendor/three.module.js';
import { makeDog } from '../../training/companion-preview/dog/3d/model.js';

const stage = document.getElementById('stage');
const bubble = document.getElementById('bubble');
const menu = document.getElementById('menu');
const askBox = document.getElementById('ask');
const askInput = document.getElementById('ask-input');

const reduced = matchMedia('(prefers-reduced-motion: reduce)');
const clamp = T.MathUtils.clamp;
const random = (a, b) => a + Math.random() * (b - a);

const patLines = [
  '唔……再摸一下。',
  '在呢，我在。',
  '你忙你的，我陪着。',
  '肚子可以摸哦。',
  '今天也一起加油吧。',
  '呼——被你摸得很舒服。'
];

let rig = null, scene = null, camera = null, renderer = null;
const raycaster = new T.Raycaster();
const ndc = new T.Vector2();
const q = new T.Quaternion();
const euler = new T.Euler();

let pointer = { x: 0, y: 0 };
let pointerAt = -1e9;      // 最后一次鼠标移动（秒）
let action = null, actionStart = 0, nextIdle = 0;
let nextBlink = 0, blinkStart = -1e9;
let frame = 0, lastTime = 0;

let dragState = null;      // { x, y, time }
let dragMoved = false;
let lastHitCheck = 0;
let lastHit = null;
let bubbleTimer = 0;

// ---------- 气泡 ----------
function say(text, holdMs = 5000) {
  clearTimeout(bubbleTimer);
  bubble.textContent = text;
  bubble.hidden = false;
  if (holdMs > 0) bubbleTimer = setTimeout(() => { bubble.hidden = true; }, holdMs);
}

// ---------- 场景 ----------
function resize() {
  if (!renderer || !camera) return;
  const w = window.innerWidth, h = window.innerHeight;
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  renderer.setSize(w, h, false);
  renderer.render(scene, camera);
}

function rotate(bone, x, y, z, smoothing) {
  q.setFromEuler(euler.set(x, y, z));
  bone.quaternion.slerp(q, smoothing);
}

function hitTest(clientX, clientY) {
  if (!rig) return true;
  ndc.x = (clientX / window.innerWidth) * 2 - 1;
  ndc.y = -(clientY / window.innerHeight) * 2 + 1;
  raycaster.setFromCamera(ndc, camera);
  return raycaster.intersectObject(rig.dog, true).length > 0;
}

// ---------- 动画 ----------
function draw(nowMs) {
  frame = 0;
  if (!rig) return;

  const now = nowMs / 1000;
  const dt = lastTime ? Math.min(now - lastTime, 0.05) : 1 / 60;
  lastTime = now;

  const quiet = now > pointerAt / 1000 + 3.5;
  const motion = !reduced.matches;

  if (motion && !action && quiet && now > nextIdle) {
    action = ['look', 'sniff', 'stretch', 'wag'][Math.floor(Math.random() * 4)];
    actionStart = now;
  }

  let yaw = quiet ? 0 : clamp(pointer.x, -1, 1) * 0.40;
  let pitch = quiet ? 0 : clamp(pointer.y, -1, 1) * 0.18;
  let tilt = 0, wag = 0, lean = 0;
  const breath = motion ? Math.sin(now * 1.65) : 0;

  if (action && motion) {
    const t = now - actionStart;
    const duration = action === 'pat' ? 3 : 4;
    if (t > duration) {
      action = null;
      nextIdle = now + random(5, 10);
    } else {
      const env = Math.sin((Math.PI * t) / duration) ** 2;
      if (action === 'pat') { tilt = Math.sin(t * 2) * 0.12 * env; wag = Math.sin(t * 9) * 0.23 * env; pitch = -0.08 * env; }
      if (action === 'look') { yaw = 0.30 * Math.sin(t * 1.2) * env; tilt = 0.12 * env; }
      if (action === 'sniff') { pitch = 0.18 * env; lean = 0.035 * env; }
      if (action === 'stretch') { pitch = -0.14 * env; lean = -0.035 * env; }
      if (action === 'wag') { wag = Math.sin(t * 6) * 0.2 * env; }
    }
  }

  if (!motion) { yaw = 0; pitch = 0; tilt = 0; wag = 0; lean = 0; action = null; }

  const a = 1 - Math.exp(-dt / 0.16);
  rotate(rig.spine, lean + breath * 0.003, yaw * 0.10, 0, a * 0.6);
  rotate(rig.neck, pitch * 0.35, yaw * 0.30, tilt * 0.30, a);
  rotate(rig.head, pitch * 0.65, yaw * 0.60, tilt * 0.70, a);

  for (let i = 0; i < rig.tailBones.length; i++) {
    rig.tailBones[i].rotation.y = (wag + (motion ? Math.sin(now * 1.1) * 0.012 : 0)) * (1 - i * 0.14);
  }

  if (motion && now > nextBlink) { blinkStart = now; nextBlink = now + random(3.5, 6.5); }
  const bt = now - blinkStart;
  const blink = motion && bt >= 0 && bt < 0.2 ? Math.sin((Math.PI * bt) / 0.2) ** 2 : 0;
  rig.eyes.forEach((eye) => { eye.scale.y = rig.eyeHeight * (1 - 0.94 * blink); });

  renderer.render(scene, camera);
  if (motion) frame = requestAnimationFrame(draw);
}

function start() {
  if (frame || !rig) return;
  lastTime = 0;
  frame = requestAnimationFrame(draw);
}

// ---------- 初始化 ----------
function init() {
  renderer = new T.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'default' });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.setClearAlpha(0);
  renderer.outputColorSpace = T.SRGBColorSpace;
  renderer.toneMapping = T.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = T.PCFSoftShadowMap;
  stage.append(renderer.domElement);

  scene = new T.Scene();
  camera = new T.PerspectiveCamera(32, 1, 0.1, 50);
  camera.position.set(0, 1.30, 4.8);
  camera.lookAt(0, 1.20, 0);

  scene.add(new T.HemisphereLight('#fff9f1', '#9c948b', 2.0));

  const key = new T.DirectionalLight('#fff4e5', 2.5);
  key.position.set(-3, 6, 5);
  key.castShadow = true;
  key.shadow.mapSize.set(1024, 1024);
  key.shadow.radius = 4;
  key.shadow.camera.left = -2;
  key.shadow.camera.right = 2;
  key.shadow.camera.top = 4;
  key.shadow.camera.bottom = -1;
  key.shadow.normalBias = 0.03;
  key.shadow.bias = -0.0001;
  scene.add(key);

  const fill = new T.DirectionalLight('#e5edff', 1.4);
  fill.position.set(4, 3, -3);
  scene.add(fill);

  // 只有影子、没有地板的接影平面，让宠物像真的站在桌面上
  const shadowPlane = new T.Mesh(
    new T.PlaneGeometry(4, 4),
    new T.ShadowMaterial({ opacity: 0.16 })
  );
  shadowPlane.rotation.x = -Math.PI / 2;
  shadowPlane.position.y = 0.005;
  shadowPlane.receiveShadow = true;
  scene.add(shadowPlane);

  rig = makeDog();
  rig.dog.traverse((object) => {
    if (!object.isMesh) return;
    object.castShadow = true;
    object.receiveShadow = true;
  });
  scene.add(rig.dog);

  resize();
  window.addEventListener('resize', resize);
  start();
}

// ---------- 交互 ----------
function pat() {
  action = 'pat';
  actionStart = performance.now() / 1000;
  say(patLines[Math.floor(Math.random() * patLines.length)], 4200);
  start();
}

function showMenu() {
  menu.hidden = false;
}

function hideMenu() {
  menu.hidden = true;
}

function openAsk() {
  hideMenu();
  askBox.hidden = false;
  askInput.value = '';
  askInput.focus();
}

function hideAsk() {
  askBox.hidden = true;
  askInput.blur();
}

async function send(text) {
  const message = String(text || '').trim();
  if (!message) return;
  hideAsk();
  say('……', 0);
  try {
    const reply = await window.pet.ask(message);
    say(reply || '（这次它没说话）', 10000);
    action = 'wag';
    actionStart = performance.now() / 1000;
    start();
  } catch (err) {
    const detail = err && err.message ? err.message : String(err);
    say(`连不上聊天服务：${detail}\n先把 Orvyth 跑起来（training/chat_web.cmd）。`, 14000);
  }
}

function wireEvents() {
  window.addEventListener('pointermove', (event) => {
    pointerAt = performance.now() / 1000;
    pointer.x = (event.clientX / window.innerWidth) * 2 - 1;
    pointer.y = (event.clientY / window.innerHeight) * 2 - 1;

    if (dragState && !dragMoved) {
      const dist = Math.hypot(event.screenX - dragState.x, event.screenY - dragState.y);
      if (dist > 4) {
        dragMoved = true;
        window.pet.dragStart();
      }
    }

    // 空白处点击穿透：鼠标不在小柴身上时，让下面的窗口收到点击
    const now = performance.now();
    if (!dragState && now - lastHitCheck > 60) {
      lastHitCheck = now;
      const hit = hitTest(event.clientX, event.clientY);
      if (hit !== lastHit) {
        lastHit = hit;
        window.pet.setIgnore(!hit);
      }
    }
  });

  window.addEventListener('pointerdown', (event) => {
    hideMenu();
    if (event.button !== 0) return;
    if (event.target.closest('.menu, .ask')) return;
    dragState = { x: event.screenX, y: event.screenY, time: performance.now() };
    dragMoved = false;
    window.pet.setIgnore(false); // 拖动和点击时必须可交互
  });

  window.addEventListener('pointerup', () => {
    if (!dragState) return;
    const wasMoving = dragMoved;
    const quick = performance.now() - dragState.time < 600;
    dragState = null;
    dragMoved = false;
    if (wasMoving) {
      window.pet.dragEnd();
    } else if (quick && rig) {
      pat();
    }
  });

  window.addEventListener('pointercancel', () => {
    if (!dragState) return;
    if (dragMoved) window.pet.dragEnd();
    dragState = null;
    dragMoved = false;
  });

  window.addEventListener('dblclick', (event) => {
    if (event.target.closest('.menu, .ask')) return;
    window.pet.openChat();
  });

  window.addEventListener('contextmenu', (event) => {
    event.preventDefault();
    showMenu();
  });

  window.addEventListener('blur', () => {
    if (!dragState) return;
    if (dragMoved) window.pet.dragEnd();
    dragState = null;
    dragMoved = false;
  });

  menu.addEventListener('click', (event) => {
    const button = event.target.closest('button');
    if (!button) return;
    const act = button.dataset.act;
    if (act === 'talk') openAsk();
    if (act === 'chat') { hideMenu(); window.pet.openChat(); }
    if (act === 'quit') window.pet.quit();
  });

  askInput.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') { event.preventDefault(); send(askInput.value); }
    if (event.key === 'Escape') hideAsk();
  });

  window.pet.onDelta((text) => say(text, 0));
}

// ---------- 启动 ----------
try {
  init();
  wireEvents();
} catch (err) {
  say(`桌宠启动失败：${err && err.message ? err.message : err}`, 0);
  console.error(err);
}
