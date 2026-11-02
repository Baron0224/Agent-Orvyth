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


test('ribbon particles keep travelling over long distances and recycle without streaking', () => {
  const homes=[], phases=[], drift=[];
  for(let i=0;i<300;i++){homes.push(i/299*1200,180+160*Math.sin(i/299*Math.PI));phases.push(i*.7);drift.push(2);}
  const f=new Field(homes, phases, drift, {width:1200,height:650});
  const initial=Array.from(f.home);
  let wrapped=false;
  for(let i=0;i<10800;i++) {
    f.step(1/60,i/60,inactive);
    assert.ok(Array.from(f.position).every(Number.isFinite));
    assert.ok(Array.from(f.opacity).every(a=>a>=0&&a<=1));
    if(f.flow.recycled.some(Boolean)) {
      wrapped=true;
      for(let k=0;k<phases.length;k++) if(f.flow.recycled[k]) {
        assert.ok(Math.hypot(f.position[k*2]-f.home[k*2],f.position[k*2+1]-f.home[k*2+1])<3);
        assert.ok(f.opacity[k]<.01);
      }
    }
    if(i===1800) assert.ok(phases.some((_,k)=>Math.hypot(f.home[k*2]-initial[k*2],f.home[k*2+1]-initial[k*2+1])>100));
  }
  assert.ok(wrapped);
  f.reset();assert.deepEqual(Array.from(f.home),initial);
});


test('all ribbon branches stay supplied and main routes dominate, secondary routes remain supplied, and speed is halved', () => {
  const n=3000, homes=new Float32Array(n*2), phases=Float32Array.from({length:n},(_,i)=>i*.7);
  const f=new Field(homes,phases,new Float32Array(n),{width:1200,height:650});
  for(let i=0;i<n;i++) assert.ok(Math.abs(f.flow.speed[i]-Math.max(22,1200*.038)*(.8+.4*(Math.sin(phases[i])*.5+.5))/6)<.00001);
  const counts=[0,0,0,0];for(const route of f.flow.track)counts[route]++;
  assert.deepEqual(counts,[1260,960,540,240]);
  for(let seconds=0;seconds<=120;seconds++) {
    const bins=Array.from({length:4},()=>new Uint16Array(16));
    for(let i=0;i<n;i++) bins[f.flow.track[i]][Math.min(15,Math.floor(f.flow.progress[i]*16))]++;
    assert.ok(bins.every(b=>Array.from(b).every(count=>count>=4)), 'no empty section along any path');
    for(let frame=0;frame<30;frame++) f.flow.advance(1/30,f.home,f.opacity);
  }
});
