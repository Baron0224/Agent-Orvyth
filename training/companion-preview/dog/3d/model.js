import * as T from './vendor/three.module.js';

// A smooth union surface forms one connected torso, neck and head. No image layers.
const smooth=(a,b,x)=>{const t=T.MathUtils.clamp((x-a)/(b-a),0,1);return t*t*(3-2*t);};
const union=(a,b,k=.15)=>{const h=Math.max(k-Math.abs(a-b),0)/k;return Math.min(a,b)-h*h*k*.25;};
const shapes=[
 [0,.91,-.25,.53,.65,.69], [0,1.39,.12,.42,.49,.40], [0,1.70,.16,.49,.54,.43],
 [-.105,1.58,.585,.15,.14,.12],[.105,1.58,.585,.15,.14,.12],
 [-.29,.26,.20,.18,.28,.20],[.29,.26,.20,.18,.28,.20],
 [-.32,.26,-.58,.18,.28,.20],[.32,.26,-.58,.18,.28,.20],
 [-.31,2.08,.12,.15,.28,.12],[.31,2.08,.12,.15,.28,.12]
];
function field(x,y,z){
 let d=100;
 for(let i=0;i<shapes.length;i++){
  const [cx,cy,cz,rx,ry,rz]=shapes[i],u=(y-cy)/ry;
  // Taper the ears toward a rounded tip, with wider lower cheeks.
  const width=i>=9?rx*Math.max(.22,1-.45*Math.max(0,u)):rx;
  const e=(Math.hypot((x-cx)/width,u,(z-cz)/rz)-1)*Math.min(width,ry,rz);
  d=union(d,e,i>=9?.07:(i>=5?.19:.13));
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
  const h=smooth(1.15,1.46,y),nWeight=smooth(1.0,1.5,y)*(1-h),sWeight=smooth(.24,.85,y)*(1-h-nWeight);
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


// Calico kitten: rounded silhouette, broad glossy eyes and short layered fur.
export function makeCat(){
 const dog=new T.Group(),root=new T.Bone(),spine=new T.Bone(),neck=new T.Bone(),head=new T.Bone();
 spine.position.y=.8;neck.position.y=.4;head.position.y=.22;dog.add(root);root.add(spine);spine.add(neck);neck.add(head);
 const cream=new T.MeshStandardMaterial({color:'#fff4df',roughness:.93});
 const charcoal=new T.MeshStandardMaterial({color:'#30261f',roughness:.92});
 const pink=new T.MeshStandardMaterial({color:'#d89280',roughness:.83});
 const mouthMat=new T.MeshStandardMaterial({color:'#755247',roughness:1});
 const black=new T.MeshPhysicalMaterial({color:'#0c0b09',roughness:.12,clearcoat:1,clearcoatRoughness:.08});
 const gold=new T.MeshPhysicalMaterial({color:'#af8438',roughness:.29,clearcoat:.7});
 const highlight=new T.MeshBasicMaterial({color:'#fffdf5'});
 const sphere=new T.SphereGeometry(1,64,48);
 function ball(parent,x,y,z,sx,sy,sz,mat){const m=new T.Mesh(sphere,mat);m.position.set(x,y,z);m.scale.set(sx,sy,sz);parent.add(m);m.castShadow=true;return m;}
 let seed=71831;const rand=()=>{seed=(1664525*seed+1013904223)>>>0;return seed/4294967296;};
 const white=new T.Color('#f9efdf'),orange=new T.Color('#d9954e'),dark=new T.Color('#332922');
 function coat(x,y,z,body=false){
  const ripple=.045*Math.sin(y*29+x*17)+.02*Math.sin(x*57-z*21);
  if(body){
   if(z>.15&&Math.abs(x)<.65-y*.12+ripple)return white.clone();
   return (Math.sin(x*5+y*8+z*4)>-.05?orange:dark).clone();
  }
  // White muzzle and a narrow irregular blaze up the centre of the forehead.
  const blaze=.11+Math.max(0,.18-y)*.58+ripple;
  if(z>.18&&(Math.abs(x)<blaze||y<-.28+ripple))return white.clone();
  const patch=x<-.12 ? .8+Math.sin(y*12+z*5)*.38 : Math.sin(x*9+y*7+z*3)*.6-.2;
  return orange.clone().lerp(dark,T.MathUtils.smoothstep(patch,.1,.55));
 }
 function furry(parent,pos,size,body=false,count=6000){
  const geo=sphere.clone(),colors=[],v=new T.Vector3();
  for(let i=0;i<geo.attributes.position.count;i++){v.fromBufferAttribute(geo.attributes.position,i);const c=coat(v.x,v.y,v.z,body);colors.push(c.r,c.g,c.b);}
  geo.setAttribute('color',new T.Float32BufferAttribute(colors,3));
  const mesh=new T.Mesh(geo,new T.MeshStandardMaterial({vertexColors:true,roughness:.98}));mesh.position.set(...pos);mesh.scale.set(...size);mesh.castShadow=true;parent.add(mesh);
  const points=[],hairColors=[];
  for(let i=0;i<count;i++){
   const y=rand()*2-1,a=rand()*Math.PI*2,r=Math.sqrt(1-y*y),x=Math.cos(a)*r,z=Math.sin(a)*r;
   const c=coat(x,y,z,body).multiplyScalar(.95+rand()*.10),length=.005+rand()*.010;
   const bx=pos[0]+x*size[0],by=pos[1]+y*size[1],bz=pos[2]+z*size[2];
   points.push(bx,by,bz,bx+x*length,by+y*length-length*.25,bz+z*length);
   hairColors.push(c.r,c.g,c.b,c.r,c.g,c.b);
  }
  const hairs=new T.BufferGeometry();hairs.setAttribute('position',new T.Float32BufferAttribute(points,3));hairs.setAttribute('color',new T.Float32BufferAttribute(hairColors,3));
  parent.add(new T.LineSegments(hairs,new T.LineBasicMaterial({vertexColors:true,transparent:true,opacity:.25})));
  return mesh;
 }
 furry(spine,[0,.34,.03],[.32,.48,.29],true,4000);
 const mesh=furry(head,[0,.33,.12],[.48,.405,.365],false,14000);
 // Rounded tapered ears, coloured outer shell and recessed peach interior.
 for(const side of [-1,1]){
  const shape=new T.Shape();shape.moveTo(side*.20,.55);
  shape.bezierCurveTo(side*.21,.70,side*.32,.96,side*.38,.91);
  shape.bezierCurveTo(side*.48,.83,side*.49,.64,side*.43,.49);shape.closePath();
  const ear=new T.Mesh(new T.ExtrudeGeometry(shape,{depth:.075,bevelEnabled:true,bevelSegments:5,steps:1,bevelSize:.027,bevelThickness:.03,curveSegments:24}),charcoal);ear.position.z=.06;ear.castShadow=true;head.add(ear);
  const inner=new T.Shape();inner.moveTo(side*.255,.60);inner.bezierCurveTo(side*.29,.74,side*.35,.87,side*.377,.85);inner.bezierCurveTo(side*.435,.78,side*.435,.65,side*.405,.575);inner.closePath();
  const inset=new T.Mesh(new T.ShapeGeometry(inner,24),new T.MeshStandardMaterial({color:'#dca08b',roughness:.95,side:T.DoubleSide}));inset.position.z=.18;head.add(inset);
  for(let i=0;i<20;i++){
   const y=.59+i*.011,x=side*(.40-(y-.59)*.15);
   const curl=new T.CatmullRomCurve3([new T.Vector3(x,y,.19),new T.Vector3(x-side*.022,y+.015,.205),new T.Vector3(x-side*(.045+rand()*.024),y+.021,.20)]);
   head.add(new T.Mesh(new T.TubeGeometry(curl,5,.0012,3,false),cream));
  }
 }
 const eyes=[];
 for(const side of [-1,1]){
  ball(head,side*.194,.352,.432,.141,.153,.070,charcoal);
  const eye=ball(head,side*.194,.352,.452,.125,.137,.065,gold);eyes.push(eye);
  ball(eye,0,.035,.53,.79,.86,.68,black);
  ball(eye,-.32,.46,1.08,.19,.19,.08,highlight);
  ball(eye,.30,-.33,1.12,.065,.065,.04,highlight);
  // Small soft muzzle; broad white colouring is carried by the head itself.
  ball(head,side*.066,.145,.452,.085,.066,.041,cream);
  for(let line=0;line<3;line++){
   const y=.16-line*.029;
   const curve=new T.CatmullRomCurve3([new T.Vector3(side*.125,y,.47),new T.Vector3(side*.30,y+.016,.48),new T.Vector3(side*.52,y+.03-line*.025,.40)]);
   head.add(new T.Mesh(new T.TubeGeometry(curve,14,.0013,4,false),cream));
  }
 }
 const noseShape=new T.Shape();noseShape.moveTo(-.033,.205);noseShape.quadraticCurveTo(0,.216,.033,.205);noseShape.quadraticCurveTo(.02,.19,0,.175);noseShape.quadraticCurveTo(-.02,.19,-.033,.205);
 const nose=new T.Mesh(new T.ExtrudeGeometry(noseShape,{depth:.009,bevelEnabled:true,bevelSegments:3,bevelSize:.006,bevelThickness:.004}),pink);nose.position.z=.498;head.add(nose);
 const lipPaths=[[[0,.18,.503],[0,.146,.504]],[[0,.146,.504],[-.022,.125,.49],[-.049,.121,.484]],[[0,.146,.504],[.022,.125,.49],[.049,.121,.484]]];
 for(const points of lipPaths){const curve=new T.CatmullRomCurve3(points.map(p=>new T.Vector3(...p)));head.add(new T.Mesh(new T.TubeGeometry(curve,10,.002,5,false),mouthMat));}
 const tailGroup=new T.Group(),tailBones=[new T.Bone()];tailGroup.add(tailBones[0]);dog.add(tailGroup);
 return {dog,root,spine,neck,head,eyes,eyeHeight:.137,tailBones,mesh};
}

// Rabbit uses the kitten's actual layered eye, muzzle, fur and rig construction.
export function makeRabbit(){
 const dog=new T.Group(),root=new T.Bone(),spine=new T.Bone(),neck=new T.Bone(),head=new T.Bone();
 spine.position.y=.8;neck.position.y=.4;head.position.y=.22;dog.add(root);root.add(spine);spine.add(neck);neck.add(head);
 const cream=new T.MeshStandardMaterial({color:'#fff4df',roughness:.93});
 const charcoal=new T.MeshStandardMaterial({color:'#bda78c',roughness:.92});
 const pink=new T.MeshStandardMaterial({color:'#cf968c',roughness:.83});
 const mouthMat=new T.MeshStandardMaterial({color:'#755247',roughness:1});
 const black=new T.MeshPhysicalMaterial({color:'#0c0b09',roughness:.12,clearcoat:1,clearcoatRoughness:.08});
 const gold=new T.MeshPhysicalMaterial({color:'#8c6944',roughness:.29,clearcoat:.7});
 const highlight=new T.MeshBasicMaterial({color:'#fffdf5'});
 const sphere=new T.SphereGeometry(1,64,48);
 function ball(parent,x,y,z,sx,sy,sz,mat){const m=new T.Mesh(sphere,mat);m.position.set(x,y,z);m.scale.set(sx,sy,sz);parent.add(m);m.castShadow=true;return m;}
 let seed=71831;const rand=()=>{seed=(1664525*seed+1013904223)>>>0;return seed/4294967296;};
 const white=new T.Color('#f9efdf'),orange=new T.Color('#d9954e'),dark=new T.Color('#332922');
 function coat(x,y,z,body=false){
  // Same vertex-colour coat as the kitten, with a quiet ivory/beige rabbit palette.
  const shade=T.MathUtils.smoothstep(Math.abs(x),.60,.98)*(1-T.MathUtils.smoothstep(z,.1,.65));
  return new T.Color('#f9efdf').lerp(new T.Color('#d8c4a8'),shade*.24);
 }
 function furry(parent,pos,size,body=false,count=6000){
  const geo=sphere.clone(),colors=[],v=new T.Vector3();
  for(let i=0;i<geo.attributes.position.count;i++){v.fromBufferAttribute(geo.attributes.position,i);const c=coat(v.x,v.y,v.z,body);colors.push(c.r,c.g,c.b);}
  geo.setAttribute('color',new T.Float32BufferAttribute(colors,3));
  const mesh=new T.Mesh(geo,new T.MeshStandardMaterial({vertexColors:true,roughness:.98}));mesh.position.set(...pos);mesh.scale.set(...size);mesh.castShadow=true;parent.add(mesh);
  const points=[],hairColors=[];
  for(let i=0;i<count;i++){
   const y=rand()*2-1,a=rand()*Math.PI*2,r=Math.sqrt(1-y*y),x=Math.cos(a)*r,z=Math.sin(a)*r;
   const c=coat(x,y,z,body).multiplyScalar(.95+rand()*.10),length=.005+rand()*.010;
   const bx=pos[0]+x*size[0],by=pos[1]+y*size[1],bz=pos[2]+z*size[2];
   points.push(bx,by,bz,bx+x*length,by+y*length-length*.25,bz+z*length);
   hairColors.push(c.r,c.g,c.b,c.r,c.g,c.b);
  }
  const hairs=new T.BufferGeometry();hairs.setAttribute('position',new T.Float32BufferAttribute(points,3));hairs.setAttribute('color',new T.Float32BufferAttribute(hairColors,3));
  parent.add(new T.LineSegments(hairs,new T.LineBasicMaterial({vertexColors:true,transparent:true,opacity:.25})));
  return mesh;
 }
 furry(spine,[0,.34,.03],[.32,.48,.29],true,4000);
 const mesh=furry(head,[0,.33,.12],[.48,.405,.365],false,14000);
 // Broad, rounded upright ears, with slightly different tips and recessed interiors.
 const earRoots=[];
 for(const side of [-1,1]){
  const earRoot=new T.Group();earRoot.position.set(side*.23,.60,.055);head.add(earRoot);earRoots.push(earRoot);
  const h=side<0?.035:0,point=(x,y)=>[side*(x-.23),y-.60];
  const shape=new T.Shape();shape.moveTo(...point(.16,.58));
  shape.bezierCurveTo(...point(.12,.86),...point(.18,1.20+h),...point(.27,1.24+h));
  shape.bezierCurveTo(...point(.37,1.27+h),...point(.43,.95),...point(.35,.64));
  shape.quadraticCurveTo(...point(.28,.52),...point(.16,.58));shape.closePath();
  const ear=new T.Mesh(new T.ExtrudeGeometry(shape,{depth:.055,bevelEnabled:true,bevelSegments:5,steps:1,bevelSize:.025,bevelThickness:.025,curveSegments:32}),cream);ear.castShadow=true;ear.name='rabbit-upright-ear';earRoot.add(ear);
  const inner=new T.Shape();inner.moveTo(...point(.205,.66));
  inner.bezierCurveTo(...point(.18,.87),...point(.23,1.13+h),...point(.28,1.16+h));
  inner.bezierCurveTo(...point(.33,1.17+h),...point(.36,.94),...point(.30,.70));
  inner.quadraticCurveTo(...point(.26,.63),...point(.205,.66));inner.closePath();
  const inset=new T.Mesh(new T.ShapeGeometry(inner,24),new T.MeshStandardMaterial({color:'#ddc3b4',roughness:.95,side:T.DoubleSide}));inset.position.z=.084;earRoot.add(inset);
 }
 const eyes=[];
 for(const side of [-1,1]){
  ball(head,side*.205,.352,.432,.116,.132,.050,charcoal);
  const eye=ball(head,side*.205,.352,.452,.104,.119,.050,gold);eyes.push(eye);
  ball(eye,0,.035,.53,.79,.86,.68,black);
  ball(eye,-.32,.46,1.08,.15,.15,.06,highlight);
  ball(eye,.30,-.33,1.12,.065,.065,.04,highlight);
  // Small soft muzzle; broad white colouring is carried by the head itself.
  ball(head,side*.066,.145,.452,.085,.066,.041,cream);
  for(let line=0;line<2;line++){
   const y=.16-line*.029;
   const curve=new T.CatmullRomCurve3([new T.Vector3(side*.125,y,.47),new T.Vector3(side*.30,y+.016,.48),new T.Vector3(side*.46,y+.03-line*.025,.40)]);
   head.add(new T.Mesh(new T.TubeGeometry(curve,14,.0013,4,false),cream));
  }
 }
 const noseShape=new T.Shape();noseShape.moveTo(-.033,.205);noseShape.quadraticCurveTo(0,.216,.033,.205);noseShape.quadraticCurveTo(.02,.19,0,.175);noseShape.quadraticCurveTo(-.02,.19,-.033,.205);
 const nose=new T.Mesh(new T.ExtrudeGeometry(noseShape,{depth:.009,bevelEnabled:true,bevelSegments:3,bevelSize:.006,bevelThickness:.004}),pink);nose.position.z=.498;head.add(nose);
 const lipPaths=[[[0,.18,.503],[0,.146,.504]],[[0,.146,.504],[-.022,.125,.49],[-.049,.121,.484]],[[0,.146,.504],[.022,.125,.49],[.049,.121,.484]]];
 for(const points of lipPaths){const curve=new T.CatmullRomCurve3(points.map(p=>new T.Vector3(...p)));head.add(new T.Mesh(new T.TubeGeometry(curve,10,.002,5,false),mouthMat));}
 const tailGroup=new T.Group(),tailBones=[new T.Bone()];tailGroup.add(tailBones[0]);dog.add(tailGroup);
 return {dog,root,spine,neck,head,eyes,eyeHeight:.119,tailBones,mesh,earRoots};
}

// Robot companion: same bones, scale and framing as the animals, but built from
// rounded plastic shells so it still reads as a pet at thumbnail size.
export function makeRobot(){
 const dog=new T.Group(),root=new T.Bone(),spine=new T.Bone(),neck=new T.Bone(),head=new T.Bone();
 spine.position.y=.8;neck.position.y=.4;head.position.y=.22;dog.add(root);root.add(spine);spine.add(neck);neck.add(head);
 const shell=new T.MeshStandardMaterial({color:'#e9e4da',roughness:.42,metalness:.05});
 const joint=new T.MeshStandardMaterial({color:'#c9c0b2',roughness:.62,metalness:.08});
 const visor=new T.MeshPhysicalMaterial({color:'#2e3a41',roughness:.20,clearcoat:.85,clearcoatRoughness:.15});
 const glow=new T.MeshStandardMaterial({color:'#123a3a',emissive:'#5fd3cc',emissiveIntensity:1.6,roughness:.45});
 const spark=new T.MeshBasicMaterial({color:'#f2fffd'});
 const accent=new T.MeshStandardMaterial({color:'#a6d8d2',roughness:.50,metalness:.10});
 const sphere=new T.SphereGeometry(1,64,48);
 function ball(parent,x,y,z,sx,sy,sz,mat){const m=new T.Mesh(sphere,mat);m.position.set(x,y,z);m.scale.set(sx,sy,sz);parent.add(m);m.castShadow=true;return m;}
 // Torso: soft barrel, waist joint, chest screen and rounded shoulder caps.
 ball(spine,0,.34,.03,.325,.40,.275,shell);
 ball(spine,0,.05,.05,.285,.21,.25,joint);
 ball(spine,0,.60,.06,.135,.085,.135,joint);
 ball(spine,0,.35,.20,.215,.16,.06,joint);
 ball(spine,0,.35,.245,.155,.105,.02,visor);
 ball(spine,0,.35,.262,.085,.055,.012,glow);
 for(const side of [-1,1])ball(spine,side*.335,.45,.02,.085,.105,.085,accent);
 // Head: rounded shell, recessed face frame and a dark screen the eyes sit on.
 const mesh=ball(head,0,.33,.12,.455,.375,.355,shell);
 head.scale.setScalar(1.15);
 ball(head,0,.34,.415,.345,.265,.075,joint);
 ball(head,0,.34,.465,.315,.235,.055,visor);
 const eyes=[];
 for(const side of [-1,1]){
  eyes.push(ball(head,side*.135,.365,.505,.088,.106,.030,glow));
  ball(head,side*.135,.392,.528,.030,.034,.012,spark);
  ball(head,side*.45,.33,.06,.055,.115,.115,accent);
 }
 const smile=new T.CatmullRomCurve3([new T.Vector3(-.055,.214,.514),new T.Vector3(0,.186,.522),new T.Vector3(.055,.214,.514)]);
 head.add(new T.Mesh(new T.TubeGeometry(smile,14,.0072,8,false),glow));
 // Antenna on the crown keeps the silhouette readable when the card is small.
 const rod=new T.Mesh(new T.CylinderGeometry(.0075,.0075,.19,12),joint);rod.position.set(0,.80,.10);rod.castShadow=true;head.add(rod);
 ball(head,0,.915,.10,.038,.038,.038,glow);
 const tailGroup=new T.Group(),tailBones=[new T.Bone()];tailGroup.add(tailBones[0]);dog.add(tailGroup);
 return {dog,root,spine,neck,head,eyes,eyeHeight:.106,tailBones,mesh};
}
