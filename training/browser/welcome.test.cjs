const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
function preview(reduced=false){
  let now=0,nextId=0;
  const timers=new Map(),events={},changes=[],redirects=[];
  const greeting={dataset:{},set textContent(value){changes.push({time:now,value});}};
  const scope={document:{getElementById:id=>id==='welcome-text' ? greeting : {getContext:()=>null}},
    matchMedia:()=>({matches:reduced}),location:{replace:path=>redirects.push({time:now,path})},
    setTimeout:(fn,delay)=>{const id=++nextId;timers.set(id,{fn,time:now+delay});return id;},
    clearTimeout:id=>timers.delete(id),addEventListener:(name,fn)=>{events[name]=fn;}};
  vm.runInNewContext(fs.readFileSync(__dirname+'/start.js','utf8'),scope);
  return {changes,redirects,events,advance(until){
    while(true){const entry=[...timers].sort((a,b)=>a[1].time-b[1].time)[0];
      if(!entry||entry[1].time>until)break;
      timers.delete(entry[0]);now=entry[1].time;entry[1].fn();
    }now=until;
  }};
}
test('greeting types progressively even without WebGL, then waits a full 3 seconds',()=>{
  const p=preview();p.advance(1320);
  assert.deepEqual(p.changes.map(c=>c.value),['H','Hi','Hi ','Hi B','Hi Bo','Hi Bos','Hi Boss']);
  p.advance(4319);assert.equal(p.redirects.length,0);
  p.advance(4320);assert.deepEqual(p.redirects,[{time:4320,path:'/'}]);
});
test('reduced motion shows the full greeting and preserves the 3-second hold',()=>{
  const p=preview(true);p.advance(300);assert.deepEqual(p.changes,[{time:300,value:'Hi Boss'}]);
  p.advance(3299);assert.equal(p.redirects.length,0);p.advance(3300);assert.equal(p.redirects.length,1);
});
test('leaving the welcome page cancels its pending redirect',()=>{
  const p=preview();p.advance(1500);p.events.pagehide();p.advance(10000);assert.equal(p.redirects.length,0);
});
