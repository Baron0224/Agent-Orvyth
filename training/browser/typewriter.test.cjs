const assert=require('node:assert/strict');
require('./typewriter.js');const {create}=globalThis.OrvythTypewriter;
(async()=>{
 let jobs=[],frames=[];const schedule=fn=>{jobs.push(fn);return fn;};const unschedule=fn=>{jobs=jobs.filter(x=>x!==fn);};
 const writer=create({render:t=>frames.push(t),schedule,unschedule});writer.append('中𠮷');
 let finished=false;const done=writer.finish().then(()=>finished=true);
 assert.equal(frames.length,0);jobs.shift()();assert.deepEqual(frames,['中']);assert.equal(finished,false);
 jobs.shift()();await done;assert.equal(writer.text,'中𠮷');assert.equal(finished,true);
 const cancelled=create({render:()=>{throw Error('cancelled render');},schedule,unschedule});cancelled.append('旧消息');const waiting=cancelled.finish().catch(e=>e.name);cancelled.cancel();assert.equal(await waiting,'AbortError');assert.equal(jobs.length,0);
 console.log('PASS character increments, Unicode, drain-before-done, cancel without stale render');
})().catch(e=>{console.error(e);process.exitCode=1;});
