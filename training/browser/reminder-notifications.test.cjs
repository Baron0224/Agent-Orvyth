const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, 'reminder-notifications.js'), 'utf8');
function setup(permission = 'granted') {
  const created = [], memory = new Map();
  class FakeNotification {
    static permission = permission;
    constructor(title, opts) { this.title=title; this.options=opts; created.push(this); }
    close() {}
  }
  const context={window:{}}; vm.runInNewContext(source,context);
  const storage={getItem: k => memory.get(k),setItem:(k,v)=>memory.set(k,v),removeItem:k=>memory.delete(k)};
  const manager=context.window.OrvythNotifications.create({Notification:FakeNotification,storage,focus(){},failed(){}});
  return {manager,created,FakeNotification,storage};
}
test('due task sends one system notification and does not repeat', () => {
  const {manager,created}=setup(); const task={id:'a',due_at:123,remind_due:true,title:'喝水'};
  assert.equal(manager.notify(task),true); assert.equal(manager.notify(task),false);
  assert.equal(created.length,1); assert.equal(created[0].options.body,'喝水');
});
test('waiting task or denied permission sends nothing', () => {
  const {manager,created}=setup('denied');
  assert.equal(manager.notify({id:'a',due_at:3,remind_due:true,title:'喝水'}),false);
  assert.equal(created.length,0);
  const other=setup(); assert.equal(other.manager.notify({id:'b',due_at:4,remind_due:false,title:'喝水'}),false);
});
test('daily reminder is eligible on the next occurrence', () => {
  const {manager,created}=setup();
  manager.notify({id:'daily',occurrence_date:'2026-11-02',remind_due:true,title:'打卡'});
  manager.notify({id:'daily',occurrence_date:'2026-11-03',remind_due:true,title:'打卡'});
  assert.equal(created.length,2);
});
test('failed delivery can be retried explicitly', () => {
  const {manager,created}=setup(); const task={id:'a',due_at:3,remind_due:true,title:'喝水'};
  manager.notify(task); created[0].onerror(); assert.equal(manager.notify(task),false);
  manager.retry(); assert.equal(manager.notify(task),true);
});
