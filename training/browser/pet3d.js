import * as T from '/companion3d/vendor/three.module.js';
import {makeDog,makeCat,makeRabbit,makeRobot} from '/companion3d/model.js';

const stage=document.getElementById('pet');
const reduced=matchMedia('(prefers-reduced-motion: reduce)');
const clamp=T.MathUtils.clamp,random=(a,b)=>a+Math.random()*(b-a);
let renderer,rig,scene,camera,clippingPlane,petWall,petBack,frame=0,lastTime=0;
const rigs=new Map();let currentKind=null;
let pointer={x:0,y:0},lastInput=-Infinity,nextIdle=0,action=null,actionStart=0,nextBlink=0,blinkStart=-Infinity;
let box,frames=0,frameStart=0;
const q=new T.Quaternion(),euler=new T.Euler();
function message(text){}
function reportError(error){stage.querySelector('.pet-fallback').textContent='精灵暂时无法显示';console.error(error);}
function resize(){box=stage.getBoundingClientRect();if(!box.width||!box.height)return;camera.aspect=box.width/box.height;camera.updateProjectionMatrix();renderer.setSize(box.width,box.height,false);renderer.render(scene,camera);}
function activity(kind){if(!rig)return;action=kind;actionStart=performance.now()/1000;stage.dataset.activity=kind;message(kind==='pat'?'开心地回应你的摸摸':'歪头看看你');start();}
function rotate(bone,x,y,z,smoothing){q.setFromEuler(euler.set(x,y,z));bone.quaternion.slerp(q,smoothing);}
function draw(nowMs){
 frame=0;if(!rig||document.hidden)return;
 const now=nowMs/1000,dt=lastTime?Math.min(now-lastTime,.05):1/60;lastTime=now;
 const quiet=now-lastInput>3.5,motion=!reduced.matches&&!document.body.classList.contains('motion-off');
 if(motion&&!action&&quiet&&now>nextIdle){action=['look','sniff','stretch'][Math.floor(Math.random()*3)];actionStart=now;stage.dataset.activity=action;}
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
 if(rig.earRoots)rig.earRoots.forEach((ear,i)=>{ear.rotation.z=motion?Math.sin(now*1.15+i*1.7)*.022:0;});
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
function changeCharacter(kind){
 if(!scene||!clippingPlane)return;
 kind=['cat','rabbit','robot'].includes(kind)?kind:'dog';if(kind===currentKind)return;
 stop();if(rig)scene.remove(rig.dog);
 if(!rigs.has(kind)){
  const next=kind==='cat'?makeCat():kind==='rabbit'?makeRabbit():kind==='robot'?makeRobot():makeDog();next.dog.position.z=.32;next.tailBones[0].parent.visible=false;
  if(kind==='rabbit'){next.dog.scale.setScalar(.90);next.dog.position.y=-.03;}
  if(kind==='robot'){next.dog.position.y=-.02;}
  next.dog.traverse(object=>{if(object.isMesh||object.isLine)for(const material of (Array.isArray(object.material)?object.material:[object.material])){material.clippingPlanes=[clippingPlane];material.clipShadows=true;}});
  rigs.set(kind,next);
 }
 rig=rigs.get(kind);currentKind=kind;scene.add(rig.dog);stage.dataset.kind=kind;
 // All four pets share the same opening, camera and studio lights.
 if(petWall)petWall.visible=true;
 if(petBack)petBack.material.color.set('#a8998a');
 camera.zoom=kind==='rabbit'?1.08:kind==='robot'?1.04:1;
 stage.dataset.vertices=String(rig.mesh.geometry.attributes.position.count);
 action=null;lastInput=-Infinity;nextIdle=performance.now()/1000+4;nextBlink=performance.now()/1000+2;blinkStart=-Infinity;
 resize();start();
}
window.addEventListener('orvyth-pet-change',event=>{try{changeCharacter(event.detail);}catch(error){reportError(error);}});
try{
 renderer=new T.WebGLRenderer({antialias:true,alpha:false,preserveDrawingBuffer:true,powerPreference:'default'});
 renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.setClearColor('#ffffff');renderer.outputColorSpace=T.SRGBColorSpace;
 renderer.toneMapping=T.ACESFilmicToneMapping;renderer.toneMappingExposure=1.05;
 renderer.localClippingEnabled=true;renderer.shadowMap.enabled=true;renderer.shadowMap.type=T.PCFSoftShadowMap;
 stage.append(renderer.domElement);stage.classList.add('is-ready');scene=new T.Scene();camera=new T.PerspectiveCamera(37,1,.1,50);camera.position.set(0,1.68,3.9);camera.lookAt(0,1.68,0);
 scene.add(new T.HemisphereLight('#fff9f1','#9c948b',2.0));
 const key=new T.DirectionalLight('#fff4e5',2.5);key.position.set(-3,6,5);key.castShadow=true;key.shadow.mapSize.set(1024,1024);key.shadow.radius=4;key.shadow.camera.left=-2;key.shadow.camera.right=2;key.shadow.camera.top=4;key.shadow.camera.bottom=-1;key.shadow.normalBias=.03;key.shadow.bias=-.0001;scene.add(key);
 const fill=new T.DirectionalLight('#e5edff',1.4);fill.position.set(4,3,-3);scene.add(fill);
 // A hole cut into a vertical wall; the dog remains a real 3D animated model.
 const lowerEdge=1.10, holeCenter=1.72, wallDepth=.30;
 clippingPlane=new T.Plane(new T.Vector3(0,1,0),-lowerEdge);
 const shape=new T.Shape();
 shape.moveTo(-8,-5);shape.lineTo(8,-5);shape.lineTo(8,7);shape.lineTo(-8,7);shape.closePath();
 const opening=new T.Path();
 // An uneven opening, close to the head instead of a circular frame.
 const edge=[[-.69,1.36],[-.65,1.19],[-.47,1.09],[-.20,1.12],[.08,1.08],[.36,1.11],[.59,1.20],[.67,1.37],[.65,1.57],[.69,1.80],[.64,2.04],[.51,2.25],[.29,2.37],[-.03,2.40],[-.29,2.35],[-.53,2.24],[-.66,2.03],[-.69,1.80],[-.65,1.57]];
 opening.moveTo(...edge[0]);for(const point of edge.slice(1))opening.lineTo(...point);opening.closePath();shape.holes.push(opening);
 const wall=new T.Mesh(new T.ExtrudeGeometry(shape,{depth:.10,bevelEnabled:false,curveSegments:32}),new T.MeshStandardMaterial({color:'#eee8df',roughness:1,side:T.DoubleSide}));
 wall.position.z=wallDepth;scene.add(wall);
 petWall=wall;
 const back=new T.Mesh(new T.PlaneGeometry(4,4),new T.MeshStandardMaterial({color:'#a8998a',roughness:1}));
 back.position.set(0,holeCenter,-.85);scene.add(back);
 petBack=back;
 changeCharacter(stage.dataset.kind || 'dog');
 const selected=currentKind;
 for(const kind of ['dog','cat','rabbit','robot']){changeCharacter(kind);renderer.render(scene,camera);document.getElementById('pet-thumb-'+kind).src=renderer.domElement.toDataURL('image/png');}
 changeCharacter(selected);
 stage.dataset.mesh='skinned-3d';stage.dataset.activity='rest';stage.dataset.vertices=String(rig.mesh.geometry.attributes.position.count);
 const now=performance.now()/1000;nextIdle=now+4.5;nextBlink=now+2;resize();start();
}catch(error){reportError(error);}
document.addEventListener('pointermove',event=>{
 if(!rig||!box||event.pointerType==='touch'||document.body.classList.contains('motion-off')||reduced.matches)return;
 pointer.x=clamp((event.clientX-box.left-box.width/2)/(box.width*.42),-1,1);
 pointer.y=clamp((event.clientY-box.top-box.height*.38)/(box.height*.65),-1,1);lastInput=performance.now()/1000;
});
stage.addEventListener('pointermove',event=>{if(event.pointerType==='touch'&&rig&&box&&!reduced.matches&&!document.body.classList.contains('motion-off')){pointer.x=clamp((event.clientX-box.left-box.width/2)/(box.width*.4),-1,1);pointer.y=clamp((event.clientY-box.top-box.height*.4)/(box.height*.6),-1,1);lastInput=performance.now()/1000;}});
document.documentElement.addEventListener('pointerleave',()=>{lastInput=-Infinity;});
stage.addEventListener('click',()=>activity('pat'));
document.getElementById('pet-pat').addEventListener('click',()=>activity('pat'));
window.addEventListener('resize',()=>{if(renderer)resize();});window.addEventListener('scroll',()=>{box=stage.getBoundingClientRect();},{passive:true});
document.addEventListener('visibilitychange',()=>{if(document.hidden)stop();else{const now=performance.now()/1000;frameStart=now*1000;frames=0;nextIdle=now+random(4,8);nextBlink=now+2;action=null;start();}});
reduced.addEventListener('change',()=>{stop();start();});
if(renderer){renderer.domElement.addEventListener('webglcontextlost',event=>{event.preventDefault();stop();message('3D 显示暂时中断，请刷新预览。');});}

new ResizeObserver(()=>{if(renderer&&camera)resize();}).observe(stage);
new MutationObserver(()=>{stop();start();}).observe(document.body,{attributes:true,attributeFilter:['class']});
