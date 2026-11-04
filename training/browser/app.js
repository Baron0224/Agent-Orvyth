const $ = selector => document.querySelector(selector);
const input = $('#message'), send = $('#send'), clear = $('#clear');
const messages = $('#messages'), area = $('#scroll-area'), notice = $('#notice');
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
let state = null, activeChat = null, busy = false, ready = false, initialized = false;
let draftAvatar = '', managingChat = null, petTimer = null, confirmResolve = null;
const taskBusy = new Set();
function setNotice(text = '') { notice.textContent = text; }
const notificationButton = $('#enable-notifications'), notificationStatus = $('#notification-status');
const notifier = window.OrvythNotifications.create({
  Notification: window.Notification, storage: window.localStorage,
  focus: () => window.focus(),
  failed: () => { notificationStatus.textContent = '系统通知未能显示，请检查浏览器和电脑的通知设置。'; }
});
const shownReminders = new Set();
function notificationSettings() {
  const permission = notifier.permission();
  notificationButton.hidden = permission === 'unsupported';
  notificationButton.disabled = permission === 'denied';
  notificationButton.textContent = permission === 'granted' ? '测试桌面通知' : '开启桌面通知';
  notificationStatus.textContent = permission === 'unsupported' ? '当前浏览器不支持桌面通知，可换用 Chrome 或 Edge。' :
    permission === 'denied' ? '通知被阻止，请在浏览器设置中允许。' :
    permission === 'granted' ? '浏览器已允许通知。请点上方按钮测试，并确认电脑右下角是否出现通知。页面需保持打开。' : '点击开启后，请在浏览器的提示中选择允许；页面需保持打开。';
}
function reminderKey(task) { return `${task.id}:${task.due_at ?? task.occurrence_date}`; }
function showReminderPopup(tasks) {
  const old = document.querySelector('.reminder-popup'); if (old) old.remove();
  const popup = document.createElement('div'); popup.className = 'reminder-popup'; popup.setAttribute('role', 'alert');
  const close = document.createElement('button'); close.type = 'button'; close.setAttribute('aria-label', '关闭提醒'); close.textContent = '×';
  close.addEventListener('click', () => popup.remove());
  const title = document.createElement('strong'); title.textContent = 'Orvyth 网页提醒';
  const content = document.createElement('span'); content.textContent = `时间到：${tasks.map(task => task.title).join('、')}`;
  popup.append(close, title, content); document.body.append(popup);
}
function deliverReminders(tasks) {
  const due = tasks.filter(task => task.remind_due && !task.done && !task.waiting);
  const fresh = due.filter(task => !shownReminders.has(reminderKey(task)));
  fresh.forEach(task => shownReminders.add(reminderKey(task)));
  if (fresh.length) {
    const text = `时间到：${fresh.map(task => task.title).join('、')}`;
    $('#task-notice').textContent = text;
    if (!busy) setPet('happy', text);
    showReminderPopup(fresh);
  }
  due.forEach(task => notifier.notify(task));
}
notificationButton.addEventListener('click', async () => {
  if (!notifier.supported()) return;
  const waiting = setTimeout(() => {
    notificationStatus.textContent = '正在等待浏览器授权，请查看地址栏附近是否有通知权限提示。';
  }, 2000);
  try {
    const permission = await Notification.requestPermission();
    clearTimeout(waiting);
    notificationSettings();
    if (permission === 'granted') {
      notifier.retry();
      const test = new Notification('Orvyth 通知已开启', {body:'提醒到时间时，会像这样弹出。', tag:'orvyth-notification-test'});
      test.onclick = () => { window.focus(); test.close(); };
      test.onshow = () => { notificationStatus.textContent = '浏览器已发送测试，请确认电脑右下角是否真的出现通知。页面需保持打开。'; };
      test.onerror = () => { notificationStatus.textContent = '测试通知未显示，请检查浏览器和电脑通知设置。'; };
      if (state) deliverReminders(state.tasks);
    }
  } catch { clearTimeout(waiting); notificationStatus.textContent = '暂时无法开启桌面通知，请检查浏览器和电脑的通知设置。'; }
});
notificationSettings();
function controls() {
  send.disabled = busy || !ready || !initialized || !input.value.trim();
  clear.disabled = busy || !initialized || !messages.children.length;
  $('#new-chat').disabled = busy || !initialized;
  document.querySelectorAll('.chat-open,.chat-more').forEach(button => { button.disabled = busy; });
  document.querySelectorAll('[data-prompt]').forEach(button => { button.disabled = busy || !ready || !initialized; });
  send.querySelector('span').textContent = busy ? '回复中' : '发送';
  input.readOnly = busy;
}
function resize() {
  input.style.height = 'auto'; input.style.height = `${Math.min(input.scrollHeight, 144)}px`;
  $('#counter').textContent = `${input.value.length} / 2000`; controls();
}
function follow(force = false) {
  if (force || area.scrollHeight - area.scrollTop - area.clientHeight < 180) area.scrollTop = area.scrollHeight;
}
function paintAvatar(target, avatar, name) {
  target.replaceChildren();
  if (avatar) {
    const image = document.createElement('img'); image.src = avatar; image.alt = '用户头像';
    image.addEventListener('error', () => { target.textContent = Array.from(name || '我')[0]; }, {once:true});
    target.append(image);
  } else target.textContent = Array.from(name === '我的空间' ? '我' : name || '我')[0];
}
function formatAssistantText(text) {
  if (text.includes('```')) return text;
  const lines = text.split('\n');
  const isList = line => /^\s*(?:[-*•]\s+|\d+[.、)]\s*|[👉●◆])/.test(line);
  return lines.map((line, i) => {
    if (!i) return line;
    const previous = lines[i - 1];
    if (!line.trim() || !previous.trim() || isList(line) || isList(previous)) return '\n' + line;
    const separator = /[\u3400-\u9fff，。！？；：、]$/.test(previous.trimEnd()) && /^[\u3400-\u9fff]/.test(line.trimStart()) ? '' : ' ';
    return separator + line.trimStart();
  }).join('');
}
function addMessage(role, text = '', complete = true) {
  $('#welcome').hidden = true;
  const entry = document.createElement('article'); entry.className = `message ${role}`;
  const label = document.createElement('div'); label.className = 'label';
  const avatar = document.createElement('span'); avatar.className = 'message-avatar'; avatar.setAttribute('aria-hidden','true');
  if (role === 'user') paintAvatar(avatar, state?.profile.avatar, state?.profile.name);
  else avatar.textContent = 'o';
  const name = document.createElement('span');
  name.textContent = role === 'user' ? (state?.profile.name === '我的空间' ? '你' : state?.profile.name || '你') : 'Orvyth';
  label.append(avatar, name);
  const body = document.createElement('div'); body.className = 'body'; body.textContent = role === 'assistant' ? formatAssistantText(text) : text;
  entry.append(label, body);
  let copy = null;
  if (role === 'assistant') {
    copy = document.createElement('button'); copy.type = 'button'; copy.className = 'message-copy';
    copy.textContent = '复制'; copy.setAttribute('aria-label', '复制这条回答'); copy.hidden = !complete || !text;
    copy.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(body.textContent);
        copy.textContent = '已复制'; copy.setAttribute('aria-label', '回答已复制');
        clearTimeout(copy.resetTimer);
        copy.resetTimer = setTimeout(() => { copy.textContent = '复制'; copy.setAttribute('aria-label', '复制这条回答'); }, 1800);
      } catch { setNotice('复制失败，请选中回答后手动复制。'); }
    });
    entry.append(copy);
  }
  messages.append(entry); return {entry, body, copy};
}
async function requestJSON(path, body) {
  const response = await fetch(path, body === undefined ? {} : {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || '请求失败，请稍后重试。');
  return data;
}
function renderProfile() {
  const profile = state.profile;
  $('#profile-name').textContent = profile.name;
  paintAvatar($('#user-avatar'), profile.avatar, profile.name);
  $('#pet-name').textContent = profile.pet_name;
  $('#pet').dataset.kind=profile.pet_kind || 'dog';
  window.dispatchEvent(new CustomEvent('orvyth-pet-change',{detail:profile.pet_kind || 'dog'}));
  $('#pet').setAttribute('aria-label', `和${profile.pet_name}互动`);
  document.body.classList.toggle('motion-off', !profile.pet_motion);
  document.querySelectorAll('.message.user .message-avatar').forEach(avatar => paintAvatar(avatar,profile.avatar,profile.name));
  document.querySelectorAll('.message.user .label > span:last-child').forEach(label => { label.textContent = profile.name === '我的空间' ? '你' : profile.name; });
}
function renderHistory() {
  const list = $('#chat-list'), scroll = list.scrollTop; list.replaceChildren();
  for (const chat of state.chats) {
    const row = document.createElement('div'); row.className = `chat-row${chat.id === activeChat ? ' active' : ''}`;
    const open = document.createElement('button'); open.type = 'button'; open.className = 'chat-open'; open.textContent = chat.title; open.title = chat.title;
    if (chat.id === activeChat) open.setAttribute('aria-current','page');
    open.addEventListener('click', () => switchChat(chat.id));
    const more = document.createElement('button'); more.type = 'button'; more.className = 'chat-more'; more.textContent = '···'; more.setAttribute('aria-label', `管理聊天：${chat.title}`);
    more.addEventListener('click', () => openChatActions(chat)); row.append(open, more); list.append(row);
  }
  list.scrollTop = scroll;
  $('#chat-title').textContent = state.chats.find(chat => chat.id === activeChat)?.title || '新聊天';
}
function taskRow(task) {
  const row = document.createElement('li'); row.className = 'task-row';
  const check = document.createElement('input'); check.type = 'checkbox'; check.checked = !!task.done && !task.waiting; check.id = `task-${task.id}`; check.disabled = taskBusy.has(task.id) || !!task.waiting || !!task.expired;
  const label = document.createElement('label'); label.htmlFor = check.id;
  const title = document.createElement('span'); title.textContent = task.title; label.append(title);
  if (task.remind_time) {
    const detail = document.createElement('small'); detail.className = 'task-schedule';
    const duration = task.end_date === task.start_date ? '一次' : (task.end_date ? `每天 · 至 ${task.end_date}` : '每天');
    const due = task.due_at ? new Date(task.due_at * 1000).toLocaleString('zh-CN', {hour12:false}) : task.remind_time;
    detail.textContent = task.expired ? '周期已结束' : (task.waiting ? `等待 ${due} · ${duration}` : `${duration} · ${due}`);
    label.append(detail);
  }
  check.addEventListener('change', () => updateTask(task, 'toggle', {done:check.checked}));
  const remove = document.createElement('button'); remove.type = 'button'; remove.textContent = '×'; remove.setAttribute('aria-label', `删除任务：${task.title}`); remove.disabled = taskBusy.has(task.id);
  remove.addEventListener('click', () => updateTask(task, 'delete'));
  row.append(check, label, remove); return row;
}
function renderTasks() {
  const pending = state.tasks.filter(task => !task.done && !task.waiting), waiting = state.tasks.filter(task => task.waiting), done = state.tasks.filter(task => task.done && !task.waiting);
  $('#tasks-pending').replaceChildren(...pending.map(taskRow)); $('#tasks-scheduled').replaceChildren(...waiting.map(taskRow)); $('#tasks-done').replaceChildren(...done.map(taskRow));
  $('#scheduled-tasks').hidden = !waiting.length; $('#scheduled-label').textContent = `即将提醒 (${waiting.length})`;
  $('#tasks-empty').hidden = pending.length > 0 || waiting.length > 0;
  $('#task-count').textContent = String(pending.length);
  $('#completed-tasks').hidden = !done.length; $('#completed-label').textContent = `已完成 (${done.length})`;
}
function applyState(data, full = false) {
  state = data;
  if (full) activeChat = data.active_chat;
  renderProfile(); renderHistory(); renderTasks();
  if (full) {
    messages.replaceChildren(); $('#welcome').hidden = false;
    for (const message of data.messages) addMessage(message.role, message.content);
    follow(true);
  }
  controls();
}
async function checkConnection() {
  const status = $('#connection'); status.textContent = '正在连接'; status.className = 'connection';
  try {
    const data = await requestJSON('/api/status'); ready = data.ready;
    status.textContent = ready ? '可以聊天' : '暂未连接'; status.className = `connection ${ready ? 'ready' : 'error'}`;
    $('#reconnect').hidden = ready; setNotice(ready ? '' : data.message);
  } catch {
    ready = false; status.textContent = '服务已断开'; status.className = 'connection error'; $('#reconnect').hidden = false;
    setNotice('请保持启动窗口开启，再点检查连接。');
  }
  controls();
}
async function initialize() {
  try {
    const data = await requestJSON('/api/session'); initialized = true; applyState(data, true);
    deliverReminders(data.tasks);
    await checkConnection();
  } catch (error) { setNotice(error.message || '连接失败，请刷新页面。'); $('#reconnect').hidden = false; }
  controls();
}
function setPet(mood, text) {
  clearTimeout(petTimer); $('#pet').dataset.mood = mood;
  $('#pet-status').textContent = ({idle:'安静陪伴中', happy:'收到你的互动', thinking:'正在认真思考', speaking:'正在回复你'})[mood];
  if (text) $('#pet-bubble').textContent = text;
  if (mood === 'happy') petTimer = setTimeout(() => { if (!busy) setPet('idle'); }, 1500);
}
function interactPet() {
  if (busy) { $('#pet-bubble').textContent = '我在认真想你的话，再等我一小会儿。'; return; }
  const count = state?.tasks.filter(task => !task.done).length || 0;
  const lines = ['被你点到了。我在呢，想说什么就慢慢说。', '收到你的摸摸了。今天也想听你说说。', count ? `还有 ${count} 件小事，我们可以一件件来。` : '今天的小事和大事，都可以放在这里。'];
  setPet('happy', lines[Math.floor(Math.random() * lines.length)]);
}
async function submit(text) {
  text = text.trim();
  if (!text || busy || !ready || !initialized) return;
  if (text === '/clear') { await clearConversation(); return; }
  if (text.length > 2000) { setNotice('一次最多发送 2000 字，请拆短一些。'); return; }
  busy = true; setNotice(); input.value = ''; resize();
  const conversation = activeChat;
  addMessage('user', text); const answer = addMessage('assistant', '正在想怎么回答…', false);
  answer.entry.classList.add('pending'); follow(true); setPet('thinking', '这句话我听见了，正在认真想。');
  let output = '', done = false;
  try {
    const response = await fetch('/api/chat', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:text,chat_id:conversation})});
    if (!response.ok) { const data = await response.json(); throw new Error(data.error || '暂时无法回答，请重试。'); }
    const reader = response.body.getReader(), decoder = new TextDecoder(); let buffer = '';
    const consume = line => {
      if (!line.trim()) return; const event = JSON.parse(line);
      if (event.type === 'error') throw new Error(event.message);
      if (event.type === 'done') done = true;
      if (event.type === 'status' && !output) answer.body.textContent = event.message;
      if (event.type === 'tool' && !output) answer.body.textContent = (event.name === 'list_project' ? '正在查看目录：' : '正在读取：') + event.path;
      if (event.type === 'delta') {
        if (!output) setPet('speaking', '想好一点，就先说给你听。');
        const nearBottom = area.scrollHeight - area.scrollTop - area.clientHeight < 180;
        output += event.content; answer.entry.classList.remove('pending'); answer.body.textContent = formatAssistantText(output); follow(nearBottom);
      }
    };
    try {
      while (true) {
        const part = await reader.read(); if (part.done) { buffer += decoder.decode(); break; }
        buffer += decoder.decode(part.value, {stream:true}); let index;
        while ((index = buffer.indexOf('\n')) !== -1) { consume(buffer.slice(0,index)); buffer = buffer.slice(index+1); }
      }
      if (buffer.trim()) consume(buffer);
      if (!done || !output) throw new Error('回复中断，请稍后重试。');
      answer.copy.hidden = false;
    } finally { await reader.cancel().catch(() => {}); }
    try { applyState(await requestJSON('/api/session')); } catch { setNotice('回答已收到，列表暂时未刷新。'); }
    input.focus(); setPet('idle', '我听着呢，想继续说就接着说。');
  } catch (error) {
    answer.entry.classList.remove('pending'); answer.entry.classList.add('failed'); answer.body.textContent = output || '这次没能收到回答。';
    setNotice(error.message || '服务暂时无法连接，请重试。'); input.value = text; setPet('idle', '这次连接没跟上，我们可以再试一次。');
  } finally { busy = false; resize(); }
}
async function conversationAction(path, data) {
  if (busy || !initialized) return;
  busy = true; controls(); setNotice();
  try { applyState(await requestJSON(path, data), true); input.value = ''; closeDrawers(); }
  catch (error) { setNotice(error.message); }
  finally { busy = false; resize(); input.focus(); }
}
function switchChat(id) { return conversationAction('/api/chats/open', {chat_id:id}); }
function confirmAction(title, copy) {
  $('#confirm-title').textContent = title; $('#confirm-copy').textContent = copy; $('#confirm-dialog').showModal();
  return new Promise(resolve => { confirmResolve = resolve; });
}
function finishConfirm(result) { const resolve = confirmResolve; confirmResolve = null; $('#confirm-dialog').close(); resolve?.(result); }
async function clearConversation() {
  if (busy || !initialized) return;
  if (await confirmAction('清空当前聊天？', '这会删除当前聊天中的记录，其他聊天和任务会保留。此操作无法在页面恢复。')) await conversationAction('/api/clear', {chat_id:activeChat});
}
function openChatActions(chat) {
  managingChat = chat.id; $('#chat-name-input').value = chat.title; $('#chat-action-error').textContent = ''; $('#chat-actions-dialog').showModal();
}
async function updateTask(task, action, extra = {}) {
  if (taskBusy.has(task.id)) return; taskBusy.add(task.id); renderTasks(); $('#task-notice').textContent = '';
  try {
    applyState(await requestJSON(`/api/tasks/${action}`, {id:task.id,...extra}));
    if (action === 'toggle') setPet('happy', extra.done ? '又完成了一件小事，替你记下啦。' : '没关系，重新放回待办里就好。');
  } catch (error) { $('#task-notice').textContent = error.message; }
  finally { taskBusy.delete(task.id); renderTasks(); }
}
function openSettings() {
  if (!state) return;
  $('#profile-menu').hidden = true; $('#profile-button').setAttribute('aria-expanded','false');
  const profile = state.profile; draftAvatar = profile.avatar;
  selectPetDraft(profile.pet_kind || 'dog');
  $('#name-input').value = profile.name; $('#pet-name-input').value = profile.pet_name; $('#motion-input').checked = profile.pet_motion;
  paintAvatar($('#avatar-edit'), draftAvatar, profile.name); $('#settings-error').textContent = ''; $('#settings-dialog').showModal();
}
function closeDrawers() { $('#sidebar').classList.remove('open'); $('#companion-panel').classList.remove('open'); $('#drawer-shade').hidden = true; }
function openDrawer(id) { closeDrawers(); $(id).classList.add('open'); $('#drawer-shade').hidden = false; }
$('#composer').addEventListener('submit', event => { event.preventDefault(); submit(input.value); });
input.addEventListener('input', resize);
input.addEventListener('keydown', event => {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing && event.keyCode !== 229) { event.preventDefault(); submit(input.value); }
});
document.querySelectorAll('[data-prompt]').forEach(button => button.addEventListener('click', () => submit(button.dataset.prompt)));
clear.addEventListener('click', clearConversation);
$('#new-chat').addEventListener('click', () => conversationAction('/api/chats/new', {}));
$('#reconnect').addEventListener('click', () => initialized ? checkConnection() : initialize());
$('#rename-form').addEventListener('submit', async event => {
  event.preventDefault();
  try { applyState(await requestJSON('/api/chats/rename',{chat_id:managingChat,title:$('#chat-name-input').value})); $('#chat-actions-dialog').close(); }
  catch(error) { $('#chat-action-error').textContent = error.message; }
});
$('#delete-chat').addEventListener('click', async () => {
  if (!await confirmAction('删除这段聊天？','聊天及其中的记录会从本机列表删除，无法在页面恢复。任务和个人资料不会受影响。')) return;
  try { applyState(await requestJSON('/api/chats/delete', {chat_id:managingChat}),true); $('#chat-actions-dialog').close(); }
  catch(error) { $('#chat-action-error').textContent = error.message; }
});
$('#close-chat-actions').addEventListener('click', () => $('#chat-actions-dialog').close());
$('#confirm-cancel').addEventListener('click', () => finishConfirm(false)); $('#confirm-ok').addEventListener('click', () => finishConfirm(true));
$('#confirm-dialog').addEventListener('cancel', event => { event.preventDefault(); finishConfirm(false); });
$('#task-form').addEventListener('submit', async event => {
  event.preventDefault(); const title = $('#task-input').value.trim(); if (!title) return;
  const button = $('#task-form button'); if (button.disabled) return; button.disabled = true; $('#task-notice').textContent = '';
  try { applyState(await requestJSON('/api/tasks/add', {title})); $('#task-input').value = ''; setPet('happy','这件事已经记好啦，按你的节奏来。'); }
  catch(error) { $('#task-notice').textContent = error.message; }
  finally { button.disabled = false; }
});
$('#profile-button').addEventListener('click', () => { const menu = $('#profile-menu'); menu.hidden = !menu.hidden; $('#profile-button').setAttribute('aria-expanded',String(!menu.hidden)); });
document.addEventListener('click', event => { if (!event.target.closest('.sidebar-bottom')) { $('#profile-menu').hidden = true; $('#profile-button').setAttribute('aria-expanded','false'); } });
$('#settings').addEventListener('click', openSettings);
$('#settings-close').addEventListener('click', () => $('#settings-dialog').close());
$('#settings-form').noValidate = true;
$('#settings-form').addEventListener('submit', async event => {
  event.preventDefault(); $('#settings-save').disabled = true; $('#settings-error').textContent = '';
  try {
    const data = await requestJSON('/api/profile',{name:$('#name-input').value,pet_name:$('#pet-name-input').value,pet_motion:$('#motion-input').checked,pet_kind:$('#pet-kind-input').value,avatar:draftAvatar});
    applyState(data); $('#settings-dialog').close(); setNotice('设置已保存在本机。');
  } catch(error) { $('#settings-error').textContent = error.message; }
  finally { $('#settings-save').disabled = false; }
});
$('#avatar-edit').addEventListener('click', () => $('#avatar-file').click()); $('#choose-avatar').addEventListener('click', () => $('#avatar-file').click());
$('#remove-avatar').addEventListener('click', () => { draftAvatar = ''; paintAvatar($('#avatar-edit'),'', $('#name-input').value); });
$('#avatar-file').addEventListener('change', async () => {
  const file = $('#avatar-file').files[0]; if (!file) return;
  let url;
  try {
    if (!['image/png','image/jpeg','image/webp'].includes(file.type) || file.size > 10*1024*1024) throw new Error('请选择不超过 10MB 的 JPG、PNG 或 WebP 图片。');
    url = URL.createObjectURL(file); const image = new Image();
    await new Promise((resolve,reject) => { image.onload = resolve; image.onerror = () => reject(new Error('无法读取这张图片，请换一张。')); image.src = url; });
    if (image.naturalWidth > 10000 || image.naturalHeight > 10000) throw new Error('图片尺寸太大，请缩小后再试。');
    const canvas = document.createElement('canvas'); canvas.width = canvas.height = 128;
    const size = Math.min(image.naturalWidth,image.naturalHeight);
    canvas.getContext('2d').drawImage(image,(image.naturalWidth-size)/2,(image.naturalHeight-size)/2,size,size,0,0,128,128);
    draftAvatar = canvas.toDataURL('image/png'); paintAvatar($('#avatar-edit'),draftAvatar,$('#name-input').value); $('#settings-error').textContent = '';
  } catch(error) { $('#settings-error').textContent = error.message; }
  finally { if (url) URL.revokeObjectURL(url); $('#avatar-file').value = ''; }
});
$('#privacy').addEventListener('click', () => { $('#profile-menu').hidden = true; $('#privacy-text').textContent = state?.privacy || ''; $('#privacy-dialog').showModal(); });
$('#close-privacy').addEventListener('click', () => $('#privacy-dialog').close());
$('#nav-toggle').addEventListener('click', () => openDrawer('#sidebar')); $('#pet-toggle').addEventListener('click', () => openDrawer('#companion-panel'));
$('#close-pet').addEventListener('click', closeDrawers); $('#drawer-shade').addEventListener('click',closeDrawers);
document.addEventListener('keydown', event => { if (event.key === 'Escape') { closeDrawers(); $('#profile-menu').hidden = true; } });
$('#pet').addEventListener('click',interactPet); $('#pet-pat').addEventListener('click',interactPet);
$('#pet-talk').addEventListener('click', () => { closeDrawers(); input.focus(); setPet('happy','我听着呢，先说你最想说的那句。'); });
let checkingReminders = false;
async function refreshReminders() {
  if (checkingReminders || !initialized || !state?.tasks.some(task => task.remind_time)) return;
  checkingReminders = true;
  try {
    const data = await requestJSON('/api/session');
    deliverReminders(data.tasks);
    // Avoid changing the chat UI during streaming; the notification still arrives.
    if (!busy) applyState(data);
  } catch {} finally { checkingReminders = false; }
}
setInterval(refreshReminders, 5000);
document.addEventListener('visibilitychange', () => { if (!document.hidden) refreshReminders(); });
setInterval(() => { if (!document.hidden && !busy && initialized && !document.querySelector('dialog[open]')) setPet('idle', state.tasks.some(task => !task.done) ? '待办我替你记着，想聊也随时可以说。' : '安静待一会儿也没关系，我在这儿。'); },60000);
initialize();

function selectPetDraft(kind){
 $('#pet-kind-input').value=kind;
 $('#chosen-pet-label').textContent=kind==='cat'?'小猫 ›':'小柴犬 ›';
 document.querySelectorAll('[data-pet-kind]').forEach(card=>card.setAttribute('aria-pressed',String(card.dataset.petKind===kind)));
}
$('#choose-pet').addEventListener('click',()=>$('#pet-choice-dialog').showModal());
$('#pet-choice-close').addEventListener('click',()=>$('#pet-choice-dialog').close());
document.querySelectorAll('[data-pet-kind]').forEach(card=>card.addEventListener('click',()=>{selectPetDraft(card.dataset.petKind);$('#pet-choice-dialog').close();}));
