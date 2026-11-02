import * as T from 'three';

// A smooth union surface forms one connected torso, neck and head. No image layers.
const smooth=(a,b,x)=>{const t=T.MathUtils.clamp((x-a)/(b-a),0,1);return t*t*(3-2*t);};
const union=(a,b,k=.15)=>{const h=Math.max(k-Math.abs(a-b),0)/k;return Math.min(a,b)-h*h*k*.25;};
const shapes=[
 [0,.91,-.25,.53,.65,.69], [0,1.39,.12,.42,.49,.40], [0,1.70,.16,.49,.54,.43],
 [-.105,1.58,.585,.15,.14,.12],[.105,1.58,.585,.15,.14,.12],
 [-.31,.26,.24,.15,.30,.16],[.31,.26,.24,.15,.30,.16],
 [-.33,.26,-.65,.16,.30,.18],[.33,.26,-.65,.16,.30,.18],
 [-.31,2.08,.12,.15,.28,.12],[.31,2.08,.12,.15,.28,.12]
];
function field(x,y,z){
 let d=100;
 for(let i=0;i<shapes.length;i++){
  const [cx,cy,cz,rx,ry,rz]=shapes[i],u=(y-cy)/ry;
  if(i>=5&&i<=8){
   const qx=Math.abs(x-cx)-.06,qy=Math.abs(y-.30)-.14,qz=Math.abs(z-cz)-.075;
   const foot=Math.hypot(Math.max(qx,0),Math.max(qy,0),Math.max(qz,0))+Math.min(Math.max(qx,qy,qz),0)-.095;
   d=union(d,foot,.10);continue;
  }
  // Taper the ears toward a rounded tip, with wider lower cheeks.
  const width=i>=9?rx*Math.max(.22,1-.45*Math.max(0,u)):rx;
  const e=(Math.hypot((x-cx)/width,u,(z-cz)/rz)-1)*Math.min(width,ry,rz);
  d=union(d,e,i>=9?.07:.13);
 }
 return d;
}

function colorAt(x,y,z){
 const orange=new T.Color('#d97b3e'),cream=new T.Color('#fff0d7');
 const muzzle=(1-smooth(.86,1.1,Math.hypot(x/.24,(y-1.57)/.15)))*smooth(.48,.57,z);
 return orange.lerp(cream,muzzle);
}
function makeSurface(){
 const nx=53,ny=84,nz=49,lo=[-.78,-.08,-1.08],hi=[.78,2.50,.85];
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
  const h=smooth(1.40,1.82,y),nWeight=smooth(1.0,1.5,y)*(1-h),sWeight=smooth(.24,.85,y)*(1-h-nWeight);
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
 spine.position.y=.80;neck.position.y=.40;head.position.y=.22;root.add(spine);spine.add(neck);neck.add(head);
 const mesh=new T.SkinnedMesh(makeSurface(),new T.MeshStandardMaterial({vertexColors:true,roughness:.72}));
 mesh.add(root);mesh.bind(new T.Skeleton([root,spine,neck,head]));mesh.castShadow=true;mesh.receiveShadow=true;dog.add(mesh);
 const orange=new T.MeshStandardMaterial({color:'#d97b3e',roughness:.72});
 const dark=new T.MeshPhysicalMaterial({color:'#2b2623',roughness:.37,clearcoat:.4});
 const innerEar=new T.MeshStandardMaterial({color:'#f4b183',roughness:.8});
 const sphere=new T.SphereGeometry(1,32,24);
 function ball(parent,pos,size,mat){const m=new T.Mesh(sphere,mat);m.position.set(...pos);m.scale.set(...size);parent.add(m);m.castShadow=true;return m;}
 const facePos=(x,y,z)=>[x,y-1.42,z];
 const eyes=[];
 for(const side of [-1,1]){
  const eye=ball(head,facePos(side*.135,1.81,.565),[.048,.065,.028],dark);eyes.push(eye);
  ball(head,facePos(side*.31,2.10,.24),[.072,.145,.018],innerEar).rotation.z=-side*.13;
 }
 ball(head,facePos(0,1.695,.707),[.065,.042,.036],dark);
 // A tiny mouth between two soft cream muzzle lobes.
 const smile=new T.CatmullRomCurve3([new T.Vector3(-.067,.122,.702),new T.Vector3(0,.106,.717),new T.Vector3(.067,.122,.702)]);
 head.add(new T.Mesh(new T.TubeGeometry(smile,16,.004,6,false),dark));
 // Smooth tail geometry with a real bone chain, not a pasted sprite.
 const curve=new T.CatmullRomCurve3([new T.Vector3(0,.95,-.79),new T.Vector3(0,1.10,-1.0),new T.Vector3(0,1.30,-1.03),new T.Vector3(0,1.40,-.91),new T.Vector3(0,1.35,-.80)]);
 const tailGeo=new T.TubeGeometry(curve,36,.13,10,false),tailBones=[],tailIndices=[],tailWeights=[];
 const tailColors=[],tailColor=new T.Color('#d97b3e'),tailPoint=new T.Vector3();
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
 ball(tailBones[4],[0,0,0],[.13,.13,.13],orange);
 return {dog,root,spine,neck,head,eyes,eyeHeight:.065,tailBones,mesh};
}
