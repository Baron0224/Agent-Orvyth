(() => {
 const dialog=document.querySelector('#pi-dialog'), form=document.querySelector('#pi-form');
 const status=document.querySelector('#pi-status'), output=document.querySelector('#pi-output'), log=document.querySelector('#pi-log'), run=document.querySelector('#pi-run');
 let running=false;
 document.querySelector('#pi-open').addEventListener('click',async()=>{
  dialog.showModal();
  try {const response=await fetch('/api/pi/status'); const data=await response.json(); if(!running)status.textContent=data.installed?`已连接 Pi · 本机模型 ${data.model}`:'Pi 尚未安装，请按接入说明准备。';}
  catch {status.textContent='无法连接服务，请重启网页版。';}
 });
 document.querySelector('#pi-close').addEventListener('click',()=>dialog.close());
 form.addEventListener('submit',async event=>{
  event.preventDefault();if(running)return;
  running=true;run.disabled=true;output.textContent='';log.replaceChildren();status.textContent='正在连接 Pi…';
  let terminal=false;
  try {
   const response=await fetch('/api/pi/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({folder:document.querySelector('#pi-folder').value.trim(),task:document.querySelector('#pi-task').value.trim()})});
   if(!response.ok){const error=await response.json();throw new Error(error.error||'任务未能启动。');}
   const reader=response.body.getReader(), decoder=new TextDecoder();let pending='';
   function consume(line){
    if(!line.trim())return;const data=JSON.parse(line);
    if(data.type==='delta')output.textContent+=data.content;
    if(data.type==='status')status.textContent=data.message;
    if(data.type==='tool'){const row=document.createElement('li');row.textContent=(data.name==='list_project'?'查看目录：':'读取文件：')+data.path;log.append(row);}
    if(data.type==='done'){status.textContent='任务完成';terminal=true;}
    if(data.type==='error'){status.textContent='任务未完成：'+data.message;terminal=true;}
   }
   while(true){const {value,done}=await reader.read();pending+=decoder.decode(value,{stream:!done});const lines=pending.split('\n');pending=lines.pop();lines.forEach(consume);if(done)break;}
   if(pending.trim())consume(pending);
   if(!terminal)throw new Error('连接中断，任务未确认完成。');
  }catch(error){status.textContent=error.message;}
  finally{running=false;run.disabled=false;}
 });
})();
