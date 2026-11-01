const $ = selector => document.querySelector(selector);
const input = $('#message'), send = $('#send'), clear = $('#clear');
const messages = $('#messages'), area = $('#scroll-area'), notice = $('#notice');
let busy = false, ready = false, initialized = false, privacy = '';

function setNotice(text = '') { notice.textContent = text; }
function controls() {
  send.disabled = busy || !ready || !initialized || !input.value.trim();
  clear.disabled = busy || !initialized;
  document.querySelectorAll('[data-prompt]').forEach(button => { button.disabled = busy || !ready || !initialized; });
  send.querySelector('span').textContent = busy ? '回复中' : '发送';
  input.readOnly = busy;
}
function resize() {
  input.style.height = 'auto';
  input.style.height = `${Math.min(input.scrollHeight, 144)}px`;
  $('#counter').textContent = `${input.value.length} / 2000`;
  controls();
}
function follow(force = false) {
  if (force || area.scrollHeight - area.scrollTop - area.clientHeight < 180) area.scrollTop = area.scrollHeight;
}
function addMessage(role, text = '') {
  $('#welcome').hidden = true;
  const entry = document.createElement('article');
  entry.className = `message ${role}`;
  const label = document.createElement('div');
  label.className = 'label';
  label.textContent = role === 'user' ? '你' : 'OpenAgent';
  const body = document.createElement('div');
  body.className = 'body';
  body.textContent = text;
  entry.append(label, body);
  messages.append(entry);
  return { entry, body };
}
async function requestJSON(path, body) {
  const response = await fetch(path, body === undefined ? {} : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || '请求失败，请重试。');
  return data;
}
async function checkConnection() {
  const status = $('#connection');
  status.textContent = '正在连接';
  status.className = 'connection';
  try {
    const data = await requestJSON('/api/status');
    ready = data.ready;
    status.textContent = ready ? '可以聊天' : '暂未连接';
    status.className = `connection ${ready ? 'ready' : 'error'}`;
    $('#reconnect').hidden = ready;
    setNotice(ready ? '' : data.message);
  } catch {
    ready = false;
    status.textContent = '服务已断开';
    status.className = 'connection error';
    $('#reconnect').hidden = false;
    setNotice('请保持启动窗口开启，再点检查连接。');
  }
  controls();
}
async function initialize() {
  try {
    const session = await requestJSON('/api/session');
    privacy = session.privacy;
    messages.replaceChildren();
    $('#welcome').hidden = false;
    for (const message of session.messages) addMessage(message.role, message.content);
    initialized = true;
    follow(true);
    await checkConnection();
  } catch (error) {
    setNotice(error.message || '连接失败，请刷新页面。');
    $('#reconnect').hidden = false;
  }
  controls();
}
async function submit(text) {
  text = text.trim();
  if (!text || busy || !ready || !initialized) return;
  if (text === '/clear') { await clearConversation(); return; }
  if (text.length > 2000) { setNotice('一次最多发送 2000 字，请拆短一些。'); return; }
  busy = true;
  setNotice();
  input.value = '';
  resize();
  addMessage('user', text);
  const answer = addMessage('assistant', '正在想怎么回答…');
  answer.entry.classList.add('pending');
  follow(true);
  let output = '', done = false;
  try {
    const response = await fetch('/api/chat', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message: text })
    });
    if (!response.ok) {
      const data = await response.json();
      throw new Error(data.error || '暂时无法回答，请重试。');
    }
    const reader = response.body.getReader(), decoder = new TextDecoder();
    let buffer = '';
    const consume = line => {
      if (!line.trim()) return;
      const event = JSON.parse(line);
      if (event.type === 'error') throw new Error(event.message);
      if (event.type === 'done') done = true;
      if (event.type === 'delta') {
        const nearBottom = area.scrollHeight - area.scrollTop - area.clientHeight < 180;
        output += event.content;
        answer.entry.classList.remove('pending');
        answer.body.textContent = output;
        follow(nearBottom);
      }
    };
    try {
      while (true) {
        const part = await reader.read();
        if (part.done) { buffer += decoder.decode(); break; }
        buffer += decoder.decode(part.value, { stream: true });
        let index;
        while ((index = buffer.indexOf('\n')) !== -1) {
          consume(buffer.slice(0, index));
          buffer = buffer.slice(index + 1);
        }
      }
      if (buffer.trim()) consume(buffer);
      if (!done || !output) throw new Error('回复中断，请稍后重试。');
    } finally { await reader.cancel().catch(() => {}); }
    if (document.activeElement !== $('#privacy-dialog')) input.focus();
  } catch (error) {
    answer.entry.classList.remove('pending');
    answer.entry.classList.add('failed');
    answer.body.textContent = output || '这次没能收到回答。';
    setNotice(error.message || '服务暂时无法连接，请重试。');
    input.value = text;
  } finally {
    busy = false;
    resize();
  }
}
$('#composer').addEventListener('submit', event => { event.preventDefault(); submit(input.value); });
input.addEventListener('input', resize);
input.addEventListener('keydown', event => {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing && event.keyCode !== 229) {
    event.preventDefault(); submit(input.value);
  }
});
document.querySelectorAll('[data-prompt]').forEach(button => button.addEventListener('click', () => submit(button.dataset.prompt)));
async function clearConversation() {
  if (busy || !initialized) return;
  busy = true; controls();
  try {
    await requestJSON('/api/clear', {});
    messages.replaceChildren();
    $('#welcome').hidden = false;
    setNotice('已清空当前对话。');
    input.value = '';
  } catch (error) { setNotice(error.message); }
  finally { busy = false; resize(); input.focus(); }
}
clear.addEventListener('click', clearConversation);
$('#current').addEventListener('click', () => { follow(true); input.focus(); });
$('#reconnect').addEventListener('click', () => initialized ? checkConnection() : initialize());
for (const button of [$('#privacy'), $('#privacy-top')]) button.addEventListener('click', () => { $('#privacy-text').textContent = privacy || '正在读取对话说明，请稍后再试。'; $('#privacy-dialog').showModal(); });
$('#close-privacy').addEventListener('click', () => $('#privacy-dialog').close());
initialize();
