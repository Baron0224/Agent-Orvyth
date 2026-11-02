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
function field(x,y,z){let d=100;for(const [cx,cy,cz,rx,ry,rz] of shapes){const e=(Math.hypot((x-cx)/rx,(y-cy)/ry,(z-cz)/rz)-1)*Math.min(rx,ry,rz);d=union(d,e);}return d;}
function colorAt(x,y,z){
 const tan=new T.Color('#da9652'),cream=new T.Color('#fff0d5');
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
  pos.push(x,y,z);norm.push(n.x,n.y,n.z);const c=colorAt(x,y,z);colors.push(c.r,c.g,c.b);
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
 spine.position.y=.65;neck.position.y=.59;head.position.y=.41;root.add(spine);spine.add(neck);neck.add(head);
 const mesh=new T.SkinnedMesh(makeSurface(),new T.MeshStandardMaterial({vertexColors:true,roughness:.8}));
 mesh.add(root);mesh.bind(new T.Skeleton([root,spine,neck,head]));mesh.castShadow=true;mesh.receiveShadow=true;dog.add(mesh);
 const materials={dark:new T.MeshPhysicalMaterial({color:'#221b17',roughness:.21,clearcoat:.7}),white:new T.MeshStandardMaterial({color:'#fff9ec',roughness:.3}),ear:new T.MeshStandardMaterial({color:'#b76f53',roughness:.9}),mouth:new T.MeshStandardMaterial({color:'#684534',roughness:1})};
 const sphere=new T.SphereGeometry(1,32,24);
 function ball(parent,pos,size,mat){const m=new T.Mesh(sphere,mat);m.position.set(...pos);m.scale.set(...size);parent.add(m);m.castShadow=true;return m;}
 const facePos=(x,y,z)=>[x,y-1.9,z];
 const eyes=[];
 for(const side of [-1,1]){
  const eye=ball(head,facePos(side*.30,2.28,.55),[.105,.126,.059],materials.dark);eyes.push(eye);
  ball(eye,[-.27,.32,.84],[.22,.22,.10],materials.white);
  ball(head,facePos(side*.51,2.64,.19),[.085,.14,.028],materials.ear).rotation.z=-side*.16;
 }
 ball(head,facePos(0,2.055,.77),[.12,.075,.067],materials.dark);
 const mouthCurve=new T.CatmullRomCurve3([new T.Vector3(-.15,.035,.74),new T.Vector3(-.07,-.005,.76),new T.Vector3(0,.012,.77),new T.Vector3(.07,-.005,.76),new T.Vector3(.15,.035,.74)]);
 const mouth=new T.Mesh(new T.TubeGeometry(mouthCurve,24,.009,6,false),materials.mouth);head.add(mouth);
 // Smooth tail geometry with a real bone chain, not a pasted sprite.
 const curve=new T.CatmullRomCurve3([new T.Vector3(.36,.69,-.29),new T.Vector3(.72,.76,-.26),new T.Vector3(.94,1.04,-.22),new T.Vector3(.86,1.33,-.12),new T.Vector3(.61,1.31,-.02)]);
 const tailGeo=new T.TubeGeometry(curve,36,.13,10,false),tailBones=[],tailIndices=[],tailWeights=[];
 for(let i=0;i<5;i++){const b=new T.Bone(),p=curve.getPoint(i/4);b.position.copy(i?p.clone().sub(curve.getPoint((i-1)/4)):p);if(i)tailBones[i-1].add(b);tailBones.push(b);}
 for(let i=0;i<tailGeo.attributes.position.count;i++){const t=Math.floor(i/11)/36*4,a=Math.min(3,Math.floor(t)),f=t-a;tailIndices.push(a,a+1,0,0);tailWeights.push(1-f,f,0,0);}
 tailGeo.setAttribute('skinIndex',new T.Uint16BufferAttribute(tailIndices,4));tailGeo.setAttribute('skinWeight',new T.Float32BufferAttribute(tailWeights,4));
 const tail=new T.SkinnedMesh(tailGeo,new T.MeshStandardMaterial({color:'#dfaa6b',roughness:.8}));tail.add(tailBones[0]);tail.bind(new T.Skeleton(tailBones));tail.castShadow=true;dog.add(tail);
 ball(tailBones[4],[0,0,0],[.13,.13,.13],materials.white);
 return {dog,root,spine,neck,head,eyes,tailBones,mesh};
}
