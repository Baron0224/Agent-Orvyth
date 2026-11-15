'use strict';
// Orvyth 桌面小柴 —— Electron 主进程
// 透明无边框悬浮窗 + 复用仓库里的 3D 模型 + 可选的聊天（连本机 chat_web.py）

const { app, BrowserWindow, ipcMain, protocol, screen, shell, globalShortcut, safeStorage, dialog } = require('electron');
const path = require('node:path');
const fs = require('node:fs/promises');
const http = require('node:http');

const APP_DIR = __dirname;
const REPO_ROOT = path.resolve(APP_DIR, '..');      // D:\Codex\Orvyth
const PORT = Number(process.env.ORVYTH_PORT || 8775); // chat_web.py 默认端口
const BASE = `http://127.0.0.1:${PORT}`;

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.txt': 'text/plain; charset=utf-8'
};

// 自定义协议：pet://local/<相对仓库根目录的路径>
// 这样渲染层可以直接 import ../training/companion-preview/dog/3d/model.js，
// 不用复制模型代码，改动 companion-preview 后会同步生效。
protocol.registerSchemesAsPrivileged([{
  scheme: 'pet',
  privileges: { standard: true, secure: true, supportFetchAPI: true, corsEnabled: true, stream: true }
}]);

let win = null;
let dragTimer = null;

function createWindow() {
  const area = screen.getPrimaryDisplay().workArea;
  const size = 320;

  win = new BrowserWindow({
    width: size,
    height: size,
    x: area.x + area.width - size - 24,
    y: area.y + area.height - size - 24,
    frame: false,
    transparent: true,
    backgroundColor: '#00000000',
    resizable: false,
    maximizable: false,
    minimizable: false,
    fullscreenable: false,
    alwaysOnTop: true,
    skipTaskbar: true,
    hasShadow: false,
    show: false,
    webPreferences: {
      preload: path.join(APP_DIR, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      backgroundThrottling: false
    }
  });

  win.setAlwaysOnTop(true, 'screen-saver'); // 盖住大多数窗口，不被全屏应用抢焦点
  win.loadURL('pet://local/desktop-pet/renderer/index.html');

  win.once('ready-to-show', () => win.showInactive()); // 不抢当前应用焦点
  win.on('closed', () => { win = null; });
}

// ---------- 拖拽：主进程轮询鼠标坐标，窗口跟着走 ----------
function startDrag() {
  if (!win) return;
  const startCursor = screen.getCursorScreenPoint();
  const [startX, startY] = win.getPosition();
  stopDrag();
  dragTimer = setInterval(() => {
    if (!win || win.isDestroyed()) return stopDrag();
    const p = screen.getCursorScreenPoint();
    win.setPosition(startX + (p.x - startCursor.x), startY + (p.y - startCursor.y));
  }, 16);
}

function stopDrag() {
  if (dragTimer) clearInterval(dragTimer);
  dragTimer = null;
}

// Windows DPAPI：凭证只由 Electron 主进程读取；网页和精灵渲染层拿不到。
const credentialPath = () => path.join(app.getPath('userData'), `desktop-pair-${PORT}.bin`);
let pendingPair = null;
let pairingFlow = null;
function openDailyPage(suffix = '/') {
  return shell.openExternal((process.platform === 'win32' ? 'microsoft-edge:' : '') + BASE + suffix);
}

function desktopRequest(action, payload, token) {
  return new Promise((resolve, reject) => {
    const body = payload === undefined ? null : JSON.stringify(payload);
    const req = http.request({
      host: '127.0.0.1', port: PORT, path: '/api/desktop/' + action, method: body ? 'POST' : 'GET',
      headers: { Origin: BASE,
        ...(body ? {'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body)} : {}),
        ...(token ? {'X-Orvyth-Desktop': token} : {}) }
    }, (res) => {
      const chunks = [];
      res.on('data', (c) => chunks.push(c));
      res.on('end', () => {
        try {
          const value = JSON.parse(Buffer.concat(chunks).toString('utf8'));
          if (res.statusCode !== 200) {
            const error = new Error(value.error || '桌面配对暂时不可用。');
            error.status = res.statusCode;
            reject(error);
          } else resolve(value);
        } catch (err) {
          reject(err);
        }
      });
    });
    req.setTimeout(5000, () => req.destroy(new Error('连接超时')));
    req.on('error', reject);
    req.end(body || undefined);
  });
}

async function getPairedSession() {
  if (process.platform !== 'win32' || !safeStorage.isEncryptionAvailable()) {
    throw new Error('当前系统无法安全保存桌面凭证。');
  }
  let token;
  try {
    token = safeStorage.decryptString(await fs.readFile(credentialPath()));
  } catch (error) {
    if (error.code !== 'ENOENT') throw new Error('无法读取本机桌面凭证。');
  }
  if (!token) {
    if (!pendingPair) {
      pendingPair = await desktopRequest('start', {});
      const response = await dialog.showMessageBox(win, {
        type: 'info', title: '配对桌面精灵', message: '桌面精灵配对码：' + pendingPair.code,
        detail: '五分钟内，在日常账户的网页输入此码并点击确认；确认后回到这里重新发送消息。',
        buttons: ['打开 Edge 确认', '稍后确认'], cancelId: 1
      });
      if (response.response === 0) await openDailyPage('/?desktop=1');
      throw new Error('请先在日常账户网页确认配对，再重新发送。');
    }
    let result;
    try { result = await desktopRequest('claim', pendingPair); }
    catch (error) { if (error.status === 400) pendingPair = null; throw error; }
    if (result.waiting) throw new Error('还在等你在网页确认配对。');
    pendingPair = null;
    token = result.token;
    await fs.writeFile(credentialPath(), safeStorage.encryptString(token), { flag: 'wx' });
  }
  try {
    return { state: await desktopRequest('session', undefined, token), token };
  } catch (error) {
    if (error.status === 401) await fs.rm(credentialPath(), { force: true });
    throw error;
  }
}

async function ask(text) {
  if (!pairingFlow) pairingFlow = getPairedSession().finally(() => { pairingFlow = null; });
  const {state, token} = await pairingFlow;
  if (!state.active_chat) throw new Error('还没有可用的聊天，先打开一次网页版 Orvyth 再试。');

  const body = JSON.stringify({ message: text, chat_id: state.active_chat });
  return new Promise((resolve, reject) => {
    let settled = false;
    let answer = '';
    const finish = (err) => {
      if (settled) return;
      settled = true;
      if (err) reject(err); else resolve(answer);
    };

    const req = http.request({
      host: '127.0.0.1', port: PORT, path: '/api/chat', method: 'POST',
      headers: {
        Host: `127.0.0.1:${PORT}`,
        Origin: BASE,
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(body),
        'X-Orvyth-Desktop': token
      }
    }, (res) => {
      if (res.statusCode !== 200) {
        const chunks = [];
        res.on('data', (c) => chunks.push(c));
        res.on('end', () => {
          let msg = `服务返回 ${res.statusCode}`;
          try { msg = JSON.parse(Buffer.concat(chunks).toString('utf8')).error || msg; } catch (_) {}
          finish(new Error(msg));
        });
        return;
      }

      let buffer = '';
      res.setEncoding('utf8');
      res.on('data', (chunk) => {
        buffer += chunk;
        let idx;
        while ((idx = buffer.indexOf('\n')) >= 0) {
          const line = buffer.slice(0, idx).trim();
          buffer = buffer.slice(idx + 1);
          if (!line) continue;
          let event;
          try { event = JSON.parse(line); } catch (_) { continue; }
          if (event.type === 'delta' && event.content) {
            answer += event.content;
            if (win && !win.isDestroyed()) win.webContents.send('pet:delta', answer);
          } else if (event.type === 'error') {
            finish(new Error(event.message || '模型报错'));
          } else if (event.type === 'done') {
            finish(null);
          }
        }
      });
      res.on('aborted', () => finish(new Error('桌面聊天已断开，请检查配对状态。')));
      res.on('end', () => finish(new Error('桌面聊天连接结束，未收到完整回复。')));
      res.on('error', finish);
    });

    req.setTimeout(180000, () => req.destroy(new Error('等待模型超时')));
    req.on('error', (err) => finish(err));
    req.write(body);
    req.end();
  });
}

// ---------- IPC ----------
ipcMain.on('pet:drag-start', () => startDrag());
ipcMain.on('pet:drag-end', () => stopDrag());
ipcMain.on('pet:ignore', (_event, ignore) => {
  if (win && !win.isDestroyed()) win.setIgnoreMouseEvents(!!ignore, { forward: true });
});
ipcMain.on('pet:open-chat', () => openDailyPage().catch(() => {}));
ipcMain.on('pet:quit', () => app.quit());
ipcMain.handle('pet:ask', async (_event, text) => {
  const message = String(text || '').trim();
  if (!message) return '';
  try {
    return await ask(message);
  } catch (err) {
    throw new Error(err && err.message ? err.message : String(err));
  }
});

// ---------- 生命周期 ----------
app.whenReady().then(() => {
  protocol.handle('pet', async (request) => {
    try {
      const url = new URL(request.url);
      const rel = decodeURIComponent(url.pathname).replace(/^\/+/, '');
      const target = path.resolve(REPO_ROOT, rel);
      if (target !== REPO_ROOT && !target.startsWith(REPO_ROOT + path.sep)) {
        return new Response('forbidden', { status: 403 });
      }
      const data = await fs.readFile(target);
      return new Response(data, {
        status: 200,
        headers: { 'content-type': MIME[path.extname(target).toLowerCase()] || 'application/octet-stream' }
      });
    } catch (err) {
      return new Response('not found: ' + (err && err.message), { status: 404 });
    }
  });

  createWindow();

  // 兜底：万一点击穿透误开、窗口点不到，用这个快捷键恢复可点击
  globalShortcut.register('CommandOrControl+Shift+O', () => {
    if (!win || win.isDestroyed()) return;
    win.setIgnoreMouseEvents(false);
    win.setAlwaysOnTop(true, 'screen-saver');
    win.showInactive();
  });

  app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });
});

app.on('will-quit', () => { stopDrag(); globalShortcut.unregisterAll(); });
app.on('window-all-closed', () => app.quit());
