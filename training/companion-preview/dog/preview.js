const pet = document.getElementById('pet');
const follow = document.getElementById('follow'), idle = document.getElementById('idle');
const status = document.getElementById('status'), head = document.getElementById('head');
const torso = document.getElementById('torso'), tail = document.getElementById('tail'), closed = document.getElementById('closed-eyes');
const controls = [...document.querySelectorAll('[data-pose]')];
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
const random = (a,b) => a + Math.random()*(b-a), clamp = (v,a,b) => Math.max(a,Math.min(b,v));
let gaze={x:0,y:0}, position={x:0,y:0,tilt:0}, lastPointer=-Infinity, lastFrame=0, frame=0, ready=false, bounds;
let action=null, actionStart=0, nextIdle=0, nextBlink=0, blinkEnd=0, staticPose=0, isBlinking=false;
function updateBounds(){bounds=pet.getBoundingClientRect();}
function setStatus(text){if(status.textContent!==text)status.textContent=text;}
function highlight(index){controls.forEach(b=>b.setAttribute('aria-pressed',String(Number(b.dataset.pose)===index)));}
function setBlink(value){if(value===isBlinking)return;isBlinking=value;closed.style.opacity=value?'1':'0';}
function act(kind,now=performance.now()){
  if(!ready)return;
  action=kind;actionStart=now;nextIdle=now+random(8500,14000);pet.dataset.activity=kind;
  setStatus(({pat:'被摸摸了，开心地摇摇尾巴',curious:'歪头看看你',sniff:'低头闻一闻',stretch:'伸个小懒腰',wag:'自己摇一会儿尾巴'})[kind]);
  highlight(kind==='pat'?5:-1);
  if(reducedMotion.matches){setStatus('已收到互动，当前已减少动态效果');action=null;}
}
function rest(now){action=null;pet.dataset.activity='rest';highlight(follow.checked?-1:staticPose);nextIdle=now+random(7000,12000);}
function resetTransforms(){head.style.transform='';torso.style.transform='';tail.style.transform='';}
function draw(now){
  frame=0;if(!ready||document.hidden)return;
  const dt=lastFrame?Math.min((now-lastFrame)/1000,.05):1/60;lastFrame=now;
  if(reducedMotion.matches){resetTransforms();setBlink(false);return;}
  const quiet=now-lastPointer>3000;
  if(!action&&idle.checked&&quiet&&now>=nextIdle)act(['curious','sniff','stretch','wag'][Math.floor(Math.random()*4)],now);
  let x=follow.checked&&quiet?0:gaze.x,y=follow.checked&&quiet?0:gaze.y,tilt=0,nod=0,bounce=0,wag=0;
  const breathing=idle.checked?Math.sin(now*.00165):0;
  if(action){
    const t=(now-actionStart)/1000,duration=action==='pat'?2.7:3.8;
    if(t>duration)rest(now);
    else{
      // Zero-slope envelope prevents jumps at the start and end of each action.
      const e=Math.sin(Math.PI*t/duration)**2;
      if(action==='pat'){tilt=Math.sin(t*2.5)*9*e;wag=Math.sin(t*14)*17*e;bounce=Math.sin(t*5)*1.7*e;}
      if(action==='curious'){tilt=11*e;x=-.15*e;nod=-2*e;}
      if(action==='sniff'){y=.5*e;nod=Math.sin(t*8)*1.8*e;}
      if(action==='stretch'){y=-.5*e;bounce=-3*e;}
      if(action==='wag')wag=Math.sin(t*9)*13*e;
    }
  }else setStatus(quiet&&idle.checked?'安静陪着你，也会自己动一动':'慢慢看向你');
  if(idle.checked&&quiet)tilt+=Math.sin(now*.00063)*1.15;
  // Time-based damping gives the same response at different refresh rates.
  const smoothing=1-Math.exp(-dt/.14);
  position.x+=(x-position.x)*smoothing;position.y+=(y-position.y)*smoothing;position.tilt+=(tilt-position.tilt)*smoothing;
  head.style.transform='translate3d('+(position.x*7)+'px,'+(position.y*4+breathing*.65+nod+bounce)+'px,0) rotateY('+(position.x*13)+'deg) rotateX('+(-position.y*8)+'deg) rotateZ('+(position.x*3+position.tilt)+'deg)';
  torso.style.transform='translateY('+(breathing*.45+bounce*.3)+'px) scale('+(1+breathing*.003)+','+(1+breathing*.006)+')';
  tail.style.transform='rotate('+(wag+(idle.checked?Math.sin(now*.0017)*1.6:0))+'deg)';
  if(idle.checked&&now>=nextBlink){blinkEnd=now+random(110,160);nextBlink=now+random(3300,6500);}
  setBlink(idle.checked&&now<blinkEnd);frame=requestAnimationFrame(draw);
}
function start(){if(!ready||document.hidden||frame)return;lastFrame=0;frame=requestAnimationFrame(draw);}
function stop(){cancelAnimationFrame(frame);frame=0;lastFrame=0;}
document.addEventListener('pointermove',event=>{
  if(event.pointerType==='touch'||!follow.checked||!ready)return;
  gaze.x=clamp((event.clientX-bounds.left-bounds.width/2)/Math.max(180,bounds.width*.75),-1,1);
  gaze.y=clamp((event.clientY-bounds.top-bounds.height*.32)/Math.max(180,bounds.height*.75),-1,1);
  lastPointer=performance.now();
});
document.documentElement.addEventListener('pointerleave',()=>{lastPointer=-Infinity;});
window.addEventListener('blur',()=>{lastPointer=-Infinity;});
window.addEventListener('resize',updateBounds);window.addEventListener('scroll',updateBounds,{passive:true});
document.addEventListener('visibilitychange',()=>{
  if(document.hidden)stop();
  else{const now=performance.now();nextIdle=now+random(4000,8000);nextBlink=now+random(1500,3500);action=null;start();}
});
follow.addEventListener('change',()=>{gaze={x:0,y:0};lastPointer=-Infinity;staticPose=0;highlight(follow.checked?-1:0);start();});
idle.addEventListener('change',()=>{rest(performance.now());setBlink(false);start();});
function manualPose(index){
  follow.checked=false;staticPose=index;rest(performance.now());
  gaze=([{x:0,y:0},{x:-1,y:0},{x:1,y:0},{x:0,y:-1},{x:0,y:1}])[index];
  highlight(index);lastPointer=performance.now();start();
}
controls.forEach(b=>b.addEventListener('click',()=>{const index=Number(b.dataset.pose);if(index===5)act('pat');else manualPose(index);}));
pet.addEventListener('click',()=>act('pat'));
document.getElementById('idle-demo').addEventListener('click',()=>act('curious'));
pet.addEventListener('keydown',event=>{
  const index={ArrowLeft:1,ArrowRight:2,ArrowUp:3,ArrowDown:4,Escape:0}[event.key];
  if(index===undefined)return;event.preventDefault();manualPose(index);
});
reducedMotion.addEventListener('change',()=>{stop();start();});
const image=new Image();
image.onload=()=>{
  ready=true;pet.disabled=false;document.querySelectorAll('button.control').forEach(b=>{b.disabled=false;});
  document.getElementById('loading').hidden=true;updateBounds();
  const now=performance.now();nextIdle=now+4800;nextBlink=now+2200;highlight(-1);pet.dataset.activity='rest';start();
};
image.onerror=()=>{document.getElementById('loading').textContent='素材没有载入，请刷新重试。';};
image.src='./dog-rig.png';
