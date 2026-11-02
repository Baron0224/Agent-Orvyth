const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const scope = {module: {exports: {}}};
vm.runInNewContext(fs.readFileSync(__dirname + '/particle-field.js', 'utf8'), scope);
const Field = scope.module.exports;
const inactive = {active: false};

test('particles have independent motion without translating the entire scene', () => {
  const f = new Field([0,0,100,100], [0,2], [4,3]);
  for (let i=0;i<120;i++) f.step(1/60,i/60,inactive);
  const p=f.position;
  assert.ok(Math.hypot(p[0],p[1])>.1);
  assert.ok(Math.hypot(p[2]-100,p[3]-100)>.1);
  assert.ok(Math.abs(p[0]-(p[2]-100))>.1);
});

test('cursor affects nearby particles and they return after release', () => {
  const f = new Field([10,0,500,500], [0,1], [0,0]);
  const pointer={active:true,x:0,y:0,radius:120};
  for(let i=0;i<180;i++) f.step(1/60,i/60,pointer);
  const displacement=Math.hypot(f.position[0]-10,f.position[1]);
  assert.ok(displacement>20);
  assert.ok(Math.abs(f.position[2]-500)<.001);
  for(let i=0;i<240;i++) f.step(1/60,3+i/60,inactive);
  assert.ok(Math.hypot(f.position[0]-10,f.position[1])<displacement*.01);
});

test('cursor exactly on a particle and delayed frames remain finite; reset clears momentum', () => {
  const f=new Field([20,20], [1], [2]);
  for(let i=0;i<120;i++) f.step(10,i,{active:true,x:20,y:20,radius:120});
  assert.ok(Array.from(f.position).every(Number.isFinite));
  assert.ok(Array.from(f.velocity).every(Number.isFinite));
  f.reset();
  assert.deepEqual(Array.from(f.position),[20,20]);
  assert.deepEqual(Array.from(f.velocity),[0,0]);
});
