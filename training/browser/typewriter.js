(function(root){
  function create({render,delay=14,schedule=setTimeout,unschedule=clearTimeout}) {
    let chunks=[],offset=0,text='',timer=null,cancelled=false,ending=false,waiters=[];
    function settle(){if(ending && offset===chunks.length && timer===null){for(const waiter of waiters)waiter.resolve(text);waiters=[];}}
    function tick(){timer=null;if(cancelled)return;
      if(offset<chunks.length){text+=chunks[offset++];render(text);}
      if(offset<chunks.length)timer=schedule(tick,delay);else{chunks=[];offset=0;settle();}
    }
    return {
      append(value){if(cancelled)return;chunks.push(...Array.from(value));if(timer===null&&chunks.length>offset)timer=schedule(tick,delay);},
      finish(){ending=true;if(cancelled)return Promise.reject(Object.assign(new Error('已停止显示'),{name:'AbortError'}));return new Promise((resolve,reject)=>{waiters.push({resolve,reject});settle();});},
      cancel(){cancelled=true;if(timer!==null)unschedule(timer);timer=null;chunks=[];offset=0;for(const waiter of waiters)waiter.reject(Object.assign(new Error('已停止显示'),{name:'AbortError'}));waiters=[];},
      get text(){return text;}
    };
  }
  if(typeof module==='object'&&module.exports)module.exports={create};else root.OrvythTypewriter={create};
})(typeof window==='undefined'?globalThis:window);
