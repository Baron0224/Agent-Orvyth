/* DOM-only basic Markdown. Raw HTML is text; only HTTP(S) links become anchors. */
(function(){
 const node=(tag,text)=>{const el=document.createElement(tag);if(text!==undefined)el.textContent=text;return el;};
 async function copy(button,text){try{await navigator.clipboard.writeText(text);button.textContent='已复制';}catch{button.textContent='复制失败，请手动选择';}}
 function inline(parent,text){
  const pattern=/`([^`]+)`|\*\*([^*]+)\*\*|\[([^\]]+)\]\(([^\s)]+)\)|(https?:\/\/[^\s<>]+)/g;let start=0,match;
  while((match=pattern.exec(text))){parent.append(document.createTextNode(text.slice(start,match.index)));let el;
   if(match[1])el=node('code',match[1]);else if(match[2])el=node('strong',match[2]);else{
    const href=match[4]||match[5];let safe=false;try{const url=new URL(href);safe=['http:','https:'].includes(url.protocol)&&!url.username&&!url.password;}catch{}
    el=node(safe?'a':'span',match[3]||match[5]);if(safe){el.href=href;el.target='_blank';el.rel='noopener noreferrer';}
   }parent.append(el);start=pattern.lastIndex;
  }parent.append(document.createTextNode(text.slice(start)));
 }
 function render(body,text){
  body.rawText=text;body.replaceChildren();body.classList.add('markdown');const lines=text.split('\n');let i=0;
  while(i<lines.length){const line=lines[i];if(!line.trim()){i++;continue;}
   if(/^\s*```/.test(line)){i++;const content=[];while(i<lines.length&&!/^\s*```/.test(lines[i]))content.push(lines[i++]);if(i<lines.length)i++;
    const block=node('section');block.className='code-block';const button=node('button','复制代码');button.type='button';button.addEventListener('click',()=>copy(button,content.join('\n')));const pre=node('pre');pre.append(node('code',content.join('\n')));block.append(button,pre);body.append(block);continue;}
   const list=line.match(/^\s*(?:([-*])\s+|(\d+)[.)、]\s+)(.*)$/);
   if(list){const ul=node(list[2]?'ol':'ul');const ordered=!!list[2];while(i<lines.length){const item=lines[i].match(/^\s*(?:([-*])\s+|(\d+)[.)、]\s+)(.*)$/);if(!item||!!item[2]!==ordered)break;const li=node('li');inline(li,item[3]);ul.append(li);i++;}body.append(ul);continue;}
   const heading=line.match(/^(#{1,3})\s+(.*)$/);if(heading){const h=node('h'+(heading[1].length+2));inline(h,heading[2]);body.append(h);i++;continue;}
   const p=node('p');inline(p,line);body.append(p);i++;
  }
 }
 function files(entry,items){
  entry.querySelector('.file-results')?.remove();if(!items?.length)return;
  const group=node('div');group.className='file-results';
  for(const item of items){const card=node('section');card.className='file-card';card.append(node('strong',item.name),node('small',(item.kind==='directory'?'目录':'文件')+' · '+({exact:'名称精确匹配',approximate:'近似名称候选',project:'项目目录'}[item.match]||'历史候选，匹配程度未记录')));
   const path=node('code',item.path);path.className='file-path';card.append(path,node('small',item.notice));const actions=node('div');const button=node('button','复制路径');button.type='button';button.addEventListener('click',()=>copy(button,item.path));actions.append(button);
   if(item.preview_url?.startsWith('/api/file-preview?')){const show=node('button','预览图片');show.type='button';show.addEventListener('click',()=>{
    const dialog=node('dialog');dialog.className='image-preview';const close=node('button','关闭预览');close.type='button';close.onclick=()=>dialog.close();const status=node('p','正在加载授权图片…');const img=node('img');img.alt=item.name;img.onload=()=>status.remove();img.onerror=()=>{status.textContent='预览失败：图片未授权、已变化、过大或无法解码。';img.remove();};img.src=item.preview_url;dialog.append(close,status,img);dialog.addEventListener('close',()=>dialog.remove());document.body.append(dialog);dialog.showModal();
   });actions.append(show);}card.append(actions);group.append(card);
  }entry.append(group);
 }
 window.OrvythAnswerView={render,files};
})();
