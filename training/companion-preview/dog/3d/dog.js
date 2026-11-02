import * as T from 'three';
import {makeDog} from './model.js';

const stage=document.getElementById('stage'),status=document.getElementById('status');
const reduced=matchMedia('(prefers-reduced-motion: reduce)');
const clamp=T.MathUtils.clamp,random=(a,b)=>a+Math.random()*(b-a);
let renderer,rig,scene,camera,frame=0,lastTime=0;
let pointer={x:0,y:0},lastInput=-Infinity,nextIdle=0,action=null,actionStart=0,nextBlink=0,blinkStart=-Infinity;
let box,frames=0,frameStart=0;
const q=new T.Quaternion(),euler=new T.Euler();
function message(text){if(status.textContent!==text)status.textContent=text;}
function reportError(error){document.getElementById('error').hidden=false;document.getElementById('error').textContent='3D 预览没有启动：'+error.message;message('请确认浏览器支持 WebGL 2，再刷新重试。');console.error(error);}
function resize(){box=stage.getBoundingClientRect();camera.aspect=box.width/box.height;camera.updateProjectionMatrix();renderer.setSize(box.width,box.height,false);renderer.render(scene,camera);}
function activity(kind){if(!rig)return;action=kind;actionStart=performance.now()/1000;stage.dataset.activity=kind;message(kind==='pat'?'开心地回应你的摸摸':'歪头看看你');start();}
function rotate(bone,x,y,z,smoothing){q.setFromEuler(euler.set(x,y,z));bone.quaternion.slerp(q,smoothing);}
function draw(nowMs){
 frame=0;if(!rig||document.hidden)return;
 const now=nowMs/1000,dt=lastTime?Math.min(now-lastTime,.05):1/60;lastTime=now;
 const quiet=now-lastInput>3.5,motion=!reduced.matches;
 if(motion&&!action&&quiet&&now>nextIdle){action=['look','sniff','stretch','wag'][Math.floor(Math.random()*4)];actionStart=now;stage.dataset.activity=action;}
 let yaw=!quiet?pointer.x*.40:0,pitch=!quiet?pointer.y*.18:0,tilt=0,wag=0,lean=0;
 const breath=motion?Math.sin(now*1.65):0;
 if(action&&motion){
  const t=now-actionStart,duration=action==='pat'?3.0:4;
  if(t>duration){action=null;nextIdle=now+random(5,10);stage.dataset.activity='rest';}
  else{
   const env=Math.sin(Math.PI*t/duration)**2;
   if(action==='pat'){tilt=Math.sin(t*2)*.12*env;wag=Math.sin(t*9)*.23*env;pitch=-.08*env;}
   if(action==='look'){yaw=.30*Math.sin(t*1.2)*env;tilt=.12*env;}
   if(action==='sniff'){pitch=.18*env;lean=.035*env;}
   if(action==='stretch'){pitch=-.14*env;lean=-.035*env;}
   if(action==='wag')wag=Math.sin(t*6)*.2*env;
   if(action!=='pat')message(({look:'自己看看周围',sniff:'低头闻一闻',stretch:'轻轻抬头伸展',wag:'摇摇尾巴'})[action]);
  }
 }else if(!action)message(quiet?'安静陪着你，偶尔自己活动':'正看向你的鼠标');
 if(!motion){yaw=0;pitch=0;tilt=0;wag=0;lean=0;action=null;message('系统已设置减少动态效果');}
 const a=1-Math.exp(-dt/.16);
 // Head and neck share rotation; skin weights deform the connecting mesh.
 rotate(rig.spine,lean+breath*.003,yaw*.10,0,a*.6);
 rotate(rig.neck,pitch*.35,yaw*.30,tilt*.30,a);
 rotate(rig.head,pitch*.65,yaw*.60,tilt*.70,a);
 for(let i=0;i<rig.tailBones.length;i++)rig.tailBones[i].rotation.y=(wag+(motion?Math.sin(now*1.1)*.012:0))*(1-i*.14);
 if(motion&&now>nextBlink){blinkStart=now;nextBlink=now+random(3.5,6.5);}
 const bt=now-blinkStart,blink=motion&&bt>=0&&bt<.2?Math.sin(Math.PI*bt/.2)**2:0;
 rig.eyes.forEach(eye=>{eye.scale.y=rig.eyeHeight*(1-.94*blink);});
 renderer.render(scene,camera);
 frames++;if(nowMs-frameStart>1000){stage.dataset.fps=String(Math.round(frames*1000/(nowMs-frameStart)));frames=0;frameStart=nowMs;}
 if(motion)frame=requestAnimationFrame(draw);
}
function start(){if(frame||!rig||document.hidden)return;lastTime=0;frame=requestAnimationFrame(draw);}
function stop(){cancelAnimationFrame(frame);frame=0;lastTime=0;}
try{
 renderer=new T.WebGLRenderer({antialias:true,alpha:false,powerPreference:'default'});
 renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.setClearColor('#ffffff');renderer.outputColorSpace=T.SRGBColorSpace;
 renderer.toneMapping=T.ACESFilmicToneMapping;renderer.toneMappingExposure=1.05;
 renderer.shadowMap.enabled=true;renderer.shadowMap.type=T.PCFSoftShadowMap;
 stage.append(renderer.domElement);scene=new T.Scene();camera=new T.PerspectiveCamera(37,1,.1,50);camera.position.set(0,1.65,6.1);camera.lookAt(0,1.14,-.12);
 scene.add(new T.HemisphereLight('#fff9f1','#9c948b',2.0));
 const key=new T.DirectionalLight('#fff4e5',2.5);key.position.set(-3,6,5);key.castShadow=true;key.shadow.mapSize.set(1024,1024);key.shadow.radius=4;key.shadow.camera.left=-2;key.shadow.camera.right=2;key.shadow.camera.top=4;key.shadow.camera.bottom=-1;key.shadow.normalBias=.03;key.shadow.bias=-.0001;scene.add(key);
 const fill=new T.DirectionalLight('#e5edff',1.4);fill.position.set(4,3,-3);scene.add(fill);
 const ground=new T.Mesh(new T.PlaneGeometry(200,200),new T.ShadowMaterial({opacity:.10}));ground.rotation.x=-Math.PI/2;ground.position.y=-.015;ground.receiveShadow=true;scene.add(ground);
 rig=makeDog();scene.add(rig.dog);
 stage.dataset.mesh='skinned-3d';stage.dataset.activity='rest';stage.dataset.vertices=String(rig.mesh.geometry.attributes.position.count);
 const now=performance.now()/1000;nextIdle=now+4.5;nextBlink=now+2;resize();start();
}catch(error){reportError(error);}
document.addEventListener('pointermove',event=>{
 if(!rig||event.pointerType==='touch')return;
 pointer.x=clamp((event.clientX-box.left-box.width/2)/(box.width*.42),-1,1);
 pointer.y=clamp((event.clientY-box.top-box.height*.38)/(box.height*.65),-1,1);lastInput=performance.now()/1000;
});
stage.addEventListener('pointermove',event=>{if(event.pointerType==='touch'&&rig){pointer.x=clamp((event.clientX-box.left-box.width/2)/(box.width*.4),-1,1);pointer.y=clamp((event.clientY-box.top-box.height*.4)/(box.height*.6),-1,1);lastInput=performance.now()/1000;}});
document.documentElement.addEventListener('pointerleave',()=>{lastInput=-Infinity;});
const raycaster=new T.Raycaster(),hitPointer=new T.Vector2();
let tapStart=null;
stage.addEventListener('pointerdown',event=>{tapStart=[event.clientX,event.clientY];});
stage.addEventListener('pointerup',event=>{
 if(!rig||!tapStart)return;
 const moved=Math.hypot(event.clientX-tapStart[0],event.clientY-tapStart[1]);tapStart=null;
 if(moved>8)return;
 hitPointer.set((event.clientX-box.left)/box.width*2-1,-(event.clientY-box.top)/box.height*2+1);
 raycaster.setFromCamera(hitPointer,camera);
 if(raycaster.intersectObject(rig.dog,true).length)activity('pat');
});
stage.addEventListener('pointercancel',()=>{tapStart=null;});
stage.addEventListener('keydown',event=>{if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Escape'].includes(event.key)){event.preventDefault();pointer={x:({ArrowLeft:-1,ArrowRight:1})[event.key]||0,y:({ArrowUp:-1,ArrowDown:1})[event.key]||0};lastInput=performance.now()/1000;start();}if(event.key===' '||event.key==='Enter'){event.preventDefault();activity('pat');}});
window.addEventListener('resize',()=>{if(renderer)resize();});window.addEventListener('scroll',()=>{box=stage.getBoundingClientRect();},{passive:true});
document.addEventListener('visibilitychange',()=>{if(document.hidden)stop();else{const now=performance.now()/1000;frameStart=now*1000;frames=0;nextIdle=now+random(4,8);nextBlink=now+2;action=null;start();}});
reduced.addEventListener('change',()=>{stop();start();});
if(renderer){renderer.domElement.addEventListener('webglcontextlost',event=>{event.preventDefault();stop();message('3D 显示暂时中断，请刷新预览。');});}
