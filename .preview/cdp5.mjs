const PORT = 9222;
const sleep = ms => new Promise(r => setTimeout(r, ms));
const fs = await import('node:fs/promises');
const targets = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
const page = targets.find(t => t.type === 'page');
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
let id = 0;
const pending = new Map();
ws.onmessage = event => {
  const msg = JSON.parse(event.data);
  if (msg.id && pending.has(msg.id)) {
    const { resolve, reject } = pending.get(msg.id);
    pending.delete(msg.id);
    msg.error ? reject(new Error(JSON.stringify(msg.error))) : resolve(msg.result);
  }
};
function send(method, params = {}) {
  const messageId = ++id;
  ws.send(JSON.stringify({ id: messageId, method, params }));
  return new Promise((resolve, reject) => pending.set(messageId, { resolve, reject }));
}
async function evaluate(expression) {
  const result = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
  if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails.exception || result.exceptionDetails));
  return result.result.value;
}
await send('Page.enable');
await send('Runtime.enable');
await send('Emulation.setDeviceMetricsOverride', { width: 1120, height: 860, deviceScaleFactor: 1, mobile: false });
await send('Page.navigate', { url: 'http://127.0.0.1:8775/' });
await sleep(8000);
const a = await evaluate(`(() => {
  window.dispatchEvent(new CustomEvent('orvyth-pet-change', {detail:'robot'}));
  return 'sent';
})()`);
console.log(a);
await sleep(2500);
console.log(await evaluate(`document.getElementById('pet').dataset.kind + ' | ' + document.getElementById('pet').dataset.activity`));
const data = await send('Page.captureScreenshot', { format: 'png' });
await fs.writeFile('.preview/app-robot-stage.png', Buffer.from(data.data, 'base64'));
console.log('saved');
ws.close();
process.exit(0);
