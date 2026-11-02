import * as T from 'three';

// A smooth union surface forms one connected torso, neck and head. No image layers.
const smooth=(a,b,x)=>{const t=T.MathUtils.clamp((x-a)/(b-a),0,1);return t*t*(3-2*t);};
const union=(a,b,k=.15)=>{const h=Math.max(k-Math.abs(a-b),0)/k;return Math.min(a,b)-h*h*k*.25;};
const shapes=[
 [0,.85,-.08,.54,.55,.43], [0,1.30,.02,.41,.40,.34], [0,1.90,.04,.74,.59,.56],
 [-.19,1.73,.51,.30,.23,.26],[.19,1.73,.51,.30,.23,.26],
 [-.31,.45,.21,.16,.43,.19],[.31,.45,.21,.16,.43,.19],
 [-.31,.15,.32,.20,.14,.27],[.31,.15,.32,.20,.14,.27],
 [-.43,.37,-.14,.24,.31,.29],[.43,.37,-.14,.24,.31,.29],
 [-.51,2.37,-.01,.21,.30,.18],[.51,2.37,-.01,.21,.30,.18]
];
function field(x,y,z){
 let d=100;
 for(let i=0;i<shapes.length;i++){
  const [cx,cy,cz,rx,ry,rz]=shapes[i],u=(y-cy)/ry;
  // Taper the ears toward a rounded tip, with wider lower cheeks.
  const width=i>=11?rx*Math.max(.18,1-.56*Math.max(0,u)):i===2?rx*(.89+.11*(1-smooth(1.85,2.35,y))):rx;
  const e=(Math.hypot((x-cx)/width,u,(z-cz)/rz)-1)*Math.min(width,ry,rz);
  d=union(d,e,i>=11?.09:.15);
 }
 return d;
}
const puppyY=y=>y<1.65?y*.80:y-.33;
function furMaterial(layer=0){
 const material=new T.MeshStandardMaterial({vertexColors:true,roughness:.96});
 material.onBeforeCompile=shader=>{
  shader.vertexShader=shader.vertexShader.replace('#include <common>','#include <common>\nvarying vec3 vFurP;');
  shader.vertexShader=shader.vertexShader.replace('#include <begin_vertex>',`#include <begin_vertex>\nvFurP=position; transformed+=objectNormal*${(layer*.004).toFixed(4)};`);
  shader.fragmentShader=shader.fragmentShader.replace('#include <common>',`#include <common>
varying vec3 vFurP;
float furHash(vec3 p){p=fract(p*.3183099+vec3(.1,.2,.3));p*=17.0;return fract(p.x*p.y*p.z*(p.x+p.y+p.z));}
float furNoise(vec3 p){vec3 i=floor(p),f=fract(p);f=f*f*(3.0-2.0*f);return mix(mix(mix(furHash(i),furHash(i+vec3(1,0,0)),f.x),mix(furHash(i+vec3(0,1,0)),furHash(i+vec3(1,1,0)),f.x),f.y),mix(mix(furHash(i+vec3(0,0,1)),furHash(i+vec3(1,0,1)),f.x),mix(furHash(i+vec3(0,1,1)),furHash(i+vec3(1,1,1)),f.x),f.y),f.z);}
`);
  shader.fragmentShader=shader.fragmentShader.replace('#include <color_fragment>',`#include <color_fragment>
float furGrain=furNoise(vFurP*vec3(210.0,55.0,210.0));
diffuseColor.rgb*=.965+furGrain*.07;
${layer?'if(furGrain<.62)discard;':''}
`);
  shader.fragmentShader=shader.fragmentShader.replace('#include <normal_fragment_maps>',`#include <normal_fragment_maps>
vec3 furSx=normalize(dFdx(-vViewPosition)),furSy=normalize(dFdy(-vViewPosition));
vec3 furR1=cross(furSy,normal),furR2=cross(normal,furSx);
float furDet=dot(furSx,furR1);
vec3 furGrad=sign(furDet)*(dFdx(furGrain)*furR1+dFdy(furGrain)*furR2);
normal=normalize(abs(furDet)*normal-furGrad*.012);
`);
 };
 material.customProgramCacheKey=()=>`puppy-short-fur-${layer}`;
 return material;
}
function colorAt(x,y,z){
 const tan=new T.Color('#b97a42'),cream=new T.Color('#f7eddc');
 const muzzle=smooth(1.51,1.70,y)*(1-smooth(1.77,1.94,y))*smooth(.20,.43,z);
 const cheeks=(1-smooth(1.85,1.99,y))*smooth(.2,.4,z)*smooth(1.45,1.60,y);
 const chest=(1-smooth(1.35,1.63,y))*smooth(.08,.26,z)*(1-smooth(.26,.40,Math.abs(x)));
 const paws=1-smooth(.19,.32,y);
 return tan.lerp(cream,Math.max(muzzle,cheeks,chest,paws));
}
function makeSurface(){
 const nx=53,ny=84,nz=49,lo=[-.94,-.08,-.67],hi=[.94,3.1,.85];
 const idx=(x,y,z)=>(x*(ny+1)+y)*(nz+1)+z;
 const values=new Float32Array((nx+1)*(ny+1)*(nz+1));
 const point=(x,y,z)=>[lo[0]+x*(hi[0]-lo[0])/nx,lo[1]+y*(hi[1]-lo[1])/ny,lo[2]+z*(hi[2]-lo[2])/nz];
 for(let x=0;x<=nx;x++)for(let y=0;y<=ny;y++)for(let z=0;z<=nz;z++)values[idx(x,y,z)]=field(...point(x,y,z));
 const offsets=[[0,0,0],[1,0,0],[1,1,0],[0,1,0],[0,0,1],[1,0,1],[1,1,1],[0,1,1]];
 const tetra=[[0,5,1,6],[0,1,2,6],[0,2,3,6],[0,3,7,6],[0,7,4,6],[0,4,5,6]];
 const pos=[],norm=[],colors=[],skin=[],weights=[];
 function vertex(p){
  const [x,y,z]=p,e=.002;
  const n=new T.Vector3(field(x+e,y,z)-field(x-e,y,z),field(x,y+e,z)-field(x,y-e,z),field(x,y,z+e)-field(x,y,z-e)).normalize();
  pos.push(x,puppyY(y),z);n.y/=(y<1.65?.8:1);n.normalize();norm.push(n.x,n.y,n.z);const c=colorAt(x,y,z);colors.push(c.r,c.g,c.b);
  const h=smooth(1.23,1.75,y),nWeight=smooth(.91,1.41,y)*(1-h),sWeight=smooth(.22,.75,y)*(1-h-nWeight);
  skin.push(0,1,2,3);weights.push(1-h-nWeight-sWeight,sWeight,nWeight,h);
 }
 function triangle(a,b,c){
  const ab=new T.Vector3(...b).sub(new T.Vector3(...a)),ac=new T.Vector3(...c).sub(new T.Vector3(...a));
  const mid=a.map((v,i)=>(v+b[i]+c[i])/3),e=.002;
  const normal=new T.Vector3(field(mid[0]+e,mid[1],mid[2])-field(mid[0]-e,mid[1],mid[2]),field(mid[0],mid[1]+e,mid[2])-field(mid[0],mid[1]-e,mid[2]),field(mid[0],mid[1],mid[2]+e)-field(mid[0],mid[1],mid[2]-e));
  if(ab.cross(ac).dot(normal)<0)[b,c]=[c,b];vertex(a);vertex(b);vertex(c);
 }
 for(let x=0;x<nx;x++)for(let y=0;y<ny;y++)for(let z=0;z<nz;z++){
  const v=offsets.map(o=>values[idx(x+o[0],y+o[1],z+o[2])]);if(v.every(a=>a>=0)||v.every(a=>a<0))continue;
  const p=offsets.map(o=>point(x+o[0],y+o[1],z+o[2]));
  for(const tet of tetra){
   const ins=tet.filter(i=>v[i]<0),out=tet.filter(i=>v[i]>=0);if(!ins.length||!out.length)continue;
   const cut=(a,b)=>{const t=v[a]/(v[a]-v[b]);return p[a].map((c,i)=>c+(p[b][i]-c)*t);};
   if(ins.length===1)triangle(...out.map(i=>cut(ins[0],i)));
   else if(ins.length===3)triangle(...ins.map(i=>cut(i,out[0])));
   else{const a=cut(ins[0],out[0]),b=cut(ins[0],out[1]),c=cut(ins[1],out[0]),d=cut(ins[1],out[1]);triangle(a,b,c);triangle(b,d,c);}
  }
 }
 const geo=new T.BufferGeometry();geo.setAttribute('position',new T.Float32BufferAttribute(pos,3));geo.setAttribute('normal',new T.Float32BufferAttribute(norm,3));geo.setAttribute('color',new T.Float32BufferAttribute(colors,3));geo.setAttribute('skinIndex',new T.Uint16BufferAttribute(skin,4));geo.setAttribute('skinWeight',new T.Float32BufferAttribute(weights,4));return geo;
}
export function makeDog(){
 const dog=new T.Group(),root=new T.Bone(),spine=new T.Bone(),neck=new T.Bone(),head=new T.Bone();
 root.name='Root';spine.name='Spine';neck.name='Neck';head.name='Head';
 spine.position.y=.65*.8;neck.position.y=.59*.8;head.position.y=.41*.8;root.add(spine);spine.add(neck);neck.add(head);
 const mesh=new T.SkinnedMesh(makeSurface(),furMaterial());
 mesh.add(root);mesh.bind(new T.Skeleton([root,spine,neck,head]));mesh.castShadow=true;mesh.receiveShadow=true;dog.add(mesh);
 for(let layer=1;layer<=2;layer++){const shell=new T.SkinnedMesh(mesh.geometry,furMaterial(layer));shell.bind(mesh.skeleton,mesh.bindMatrix);shell.receiveShadow=true;dog.add(shell);}
 const materials={dark:new T.MeshPhysicalMaterial({color:'#211712',roughness:.25,clearcoat:.8}),iris:new T.MeshPhysicalMaterial({color:'#41291a',roughness:.17,clearcoat:1}),pupil:new T.MeshPhysicalMaterial({color:'#100b08',roughness:.09,clearcoat:1}),white:new T.MeshStandardMaterial({color:'#fff9ec',roughness:.3}),ear:new T.MeshStandardMaterial({color:'#b17a66',roughness:.96}),mouth:new T.MeshStandardMaterial({color:'#684534',roughness:1})};
 const sphere=new T.SphereGeometry(1,32,24);
 function ball(parent,pos,size,mat){const m=new T.Mesh(sphere,mat);m.position.set(...pos);m.scale.set(...size);parent.add(m);m.castShadow=true;return m;}
 const facePos=(x,y,z)=>[x,y-1.9,z];
 const eyes=[];
 for(const side of [-1,1]){
  const eye=ball(head,facePos(side*.30,2.28,.55),[.105,.126,.059],materials.dark);eyes.push(eye);
  ball(eye,[0,0,.73],[.76,.82,.36],materials.iris);
  ball(eye,[0,0,1.03],[.43,.56,.12],materials.pupil);
  ball(eye,[-.26,.33,1.07],[.15,.15,.055],materials.white);
  ball(head,facePos(side*.51,2.59,.195),[.075,.105,.025],materials.ear).rotation.z=-side*.16;
 }
 const nose=ball(head,facePos(0,2.055,.77),[.12,.075,.067],materials.dark.clone());
 const pores=new Uint8Array(64*64*4);for(let i=0;i<pores.length;i+=4){const value=100+Math.random()*155;pores[i]=pores[i+1]=pores[i+2]=value;pores[i+3]=255;}
 const poreMap=new T.DataTexture(pores,64,64);poreMap.wrapS=poreMap.wrapT=T.RepeatWrapping;poreMap.magFilter=T.LinearFilter;poreMap.minFilter=T.LinearFilter;poreMap.needsUpdate=true;nose.material.bumpMap=poreMap;nose.material.bumpScale=.003;nose.material.roughness=.4;
 const mouthCurve=new T.CatmullRomCurve3([new T.Vector3(-.15,.035,.74),new T.Vector3(-.07,-.005,.76),new T.Vector3(0,.012,.77),new T.Vector3(.07,-.005,.76),new T.Vector3(.15,.035,.74)]);
 const mouth=new T.Mesh(new T.TubeGeometry(mouthCurve,24,.009,6,false),materials.mouth);head.add(mouth);
 // Smooth tail geometry with a real bone chain, not a pasted sprite.
 const curve=new T.CatmullRomCurve3([new T.Vector3(.36,.69*.8,-.29),new T.Vector3(.72,.76*.8,-.26),new T.Vector3(.94,1.04*.8,-.22),new T.Vector3(.86,1.33*.8,-.12),new T.Vector3(.61,1.31*.8,-.02)]);
 const tailGeo=new T.TubeGeometry(curve,36,.13,10,false),tailBones=[],tailIndices=[],tailWeights=[];
 const tailColors=[],tailColor=new T.Color('#be8c54'),tailPoint=new T.Vector3();
 for(let i=0;i<tailGeo.attributes.position.count;i++){
  const t=Math.floor(i/11)/36,center=curve.getPoint(t);
  tailPoint.fromBufferAttribute(tailGeo.attributes.position,i).sub(center).multiplyScalar(1+Math.sin(Math.PI*t)*.34).add(center);
  tailGeo.attributes.position.setXYZ(i,tailPoint.x,tailPoint.y,tailPoint.z);tailColors.push(tailColor.r,tailColor.g,tailColor.b);
 }
 tailGeo.computeVertexNormals();tailGeo.setAttribute('color',new T.Float32BufferAttribute(tailColors,3));
 for(let i=0;i<5;i++){const b=new T.Bone(),p=curve.getPoint(i/4);b.position.copy(i?p.clone().sub(curve.getPoint((i-1)/4)):p);if(i)tailBones[i-1].add(b);tailBones.push(b);}
 for(let i=0;i<tailGeo.attributes.position.count;i++){const t=Math.floor(i/11)/36*4,a=Math.min(3,Math.floor(t)),f=t-a;tailIndices.push(a,a+1,0,0);tailWeights.push(1-f,f,0,0);}
 tailGeo.setAttribute('skinIndex',new T.Uint16BufferAttribute(tailIndices,4));tailGeo.setAttribute('skinWeight',new T.Float32BufferAttribute(tailWeights,4));
 const tail=new T.SkinnedMesh(tailGeo,new T.MeshStandardMaterial({vertexColors:true,roughness:.96}));tail.add(tailBones[0]);tail.bind(new T.Skeleton(tailBones));tail.castShadow=true;dog.add(tail);
 ball(tailBones[4],[0,0,0],[.13,.13,.13],materials.white);
 return {dog,root,spine,neck,head,eyes,tailBones,mesh};
}
