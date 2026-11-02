/* Actual WebGL point sprites. The reference is sampled once, never drawn as a background. */
(() => {
  'use strict';
  const canvas=document.getElementById('particles');
  const gl=canvas.getContext('webgl',{alpha:true,antialias:false,powerPreference:'high-performance'});
  if(!gl)return;
  const motion=matchMedia('(prefers-reduced-motion: reduce)');
  const vs=`attribute vec2 position;attribute vec4 appearance;attribute float visibility;uniform vec2 viewport;uniform float dpr;varying vec4 ink;
    void main(){vec2 p=position/viewport*2.-1.;gl_Position=vec4(p.x,-p.y,0.,1.);gl_PointSize=appearance.a*dpr;ink=vec4(appearance.rgb,visibility);}`;
  const fs=`precision mediump float;varying vec4 ink;
    void main(){float r=length(gl_PointCoord-.5)*2.;if(r>1.)discard;
      float alpha=exp(-r*r*5.)*.85;gl_FragColor=vec4(ink.rgb,alpha*ink.a);}`;
  function compile(type,code){const s=gl.createShader(type);gl.shaderSource(s,code);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw new Error('shader');return s;}
  let program;
  try{program=gl.createProgram();gl.attachShader(program,compile(gl.VERTEX_SHADER,vs));gl.attachShader(program,compile(gl.FRAGMENT_SHADER,fs));gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw new Error('program');}catch{canvas.hidden=true;return;}
  gl.useProgram(program);gl.enable(gl.BLEND);gl.blendFunc(gl.SRC_ALPHA,gl.ONE);
  gl.clearColor(0,0,0,0);
  const positions=gl.createBuffer(),appearance=gl.createBuffer(),visibility=gl.createBuffer();
  const positionAttr=gl.getAttribLocation(program,'position'),appearanceAttr=gl.getAttribLocation(program,'appearance');
  const visibilityAttr=gl.getAttribLocation(program,'visibility');
  const viewport=gl.getUniformLocation(program,'viewport'),density=gl.getUniformLocation(program,'dpr');
  let width=0,height=0,dpr=1,field=null,count=0,frame=0,last=0,time=0,lost=false;
  let seed=87;
  const rand=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296;};
  const pointer={x:0,y:0,radius:135,active:false};
  const image=new Image();
  let loaded=false;
  function build(){
    if(!loaded||lost)return;
    seed=87;
    const sample=document.createElement('canvas');
    const ratio=Math.min(1,1000/width,1000/height);
    sample.width=Math.max(1,Math.round(width*ratio));sample.height=Math.max(1,Math.round(height*ratio));
    const c=sample.getContext('2d',{willReadFrequently:true});
    const sx=image.naturalWidth*.08,sy=image.naturalHeight*.06,sw=image.naturalWidth*.84,sh=image.naturalHeight*.62;
    const scale=Math.max(sample.width/sw,sample.height/sh);
    c.drawImage(image,sx,sy,sw,sh,(sample.width-sw*scale)/2,(sample.height-sh*scale)/2,sw*scale,sh*scale);
    const pixels=c.getImageData(0,0,sample.width,sample.height).data;
    const totalPixels=sample.width*sample.height,cdf=new Float32Array(totalPixels);
    let total=0;
    for(let i=0;i<totalPixels;i++){
      const j=i*4,light=pixels[j]*.2126+pixels[j+1]*.7152+pixels[j+2]*.0722;
      total+=Math.pow(Math.max(0,light-24),1.35);cdf[i]=total;
    }
    if(!total)return;
    count=width<650?26000:70000;
    const homes=new Float32Array(count*2),phases=new Float32Array(count),drift=new Float32Array(count),colors=new Float32Array(count*4);
    for(let i=0;i<count;i++){
      const target=rand()*total;let lo=0,hi=totalPixels-1;
      while(lo<hi){const mid=(lo+hi)>>>1;if(cdf[mid]<target)lo=mid+1;else hi=mid;}
      homes[i*2]=((lo%sample.width)+rand())/sample.width*width;
      homes[i*2+1]=(Math.floor(lo/sample.width)+rand())/sample.height*height;
      phases[i]=rand()*Math.PI*2;drift[i]=1+rand()*4;
      const j=i*4,k=lo*4;
      colors[j]=Math.min(1,pixels[k]/255*1.35+.08);
      colors[j+1]=Math.min(1,pixels[k+1]/255*1.35+.08);
      colors[j+2]=Math.min(1,pixels[k+2]/255*1.35+.08);
      colors[j+3]=.8+Math.pow(rand(),4)*3.8;
    }
    field=new OrvythParticleField(homes,phases,drift,{width,height});
    canvas.dataset.renderer='independent-points';canvas.dataset.particleCount=String(count);
    gl.bindBuffer(gl.ARRAY_BUFFER,appearance);gl.bufferData(gl.ARRAY_BUFFER,colors,gl.STATIC_DRAW);
    gl.enableVertexAttribArray(appearanceAttr);gl.vertexAttribPointer(appearanceAttr,4,gl.FLOAT,false,0,0);
    gl.bindBuffer(gl.ARRAY_BUFFER,positions);gl.bufferData(gl.ARRAY_BUFFER,field.position,gl.DYNAMIC_DRAW);
    gl.enableVertexAttribArray(positionAttr);gl.vertexAttribPointer(positionAttr,2,gl.FLOAT,false,0,0);
    gl.bindBuffer(gl.ARRAY_BUFFER,visibility);gl.bufferData(gl.ARRAY_BUFFER,field.opacity,gl.DYNAMIC_DRAW);
    gl.enableVertexAttribArray(visibilityAttr);gl.vertexAttribPointer(visibilityAttr,1,gl.FLOAT,false,0,0);
    draw();
  }
  function draw(){
    if(!field||lost)return;
    gl.clear(gl.COLOR_BUFFER_BIT);gl.uniform2f(viewport,width,height);gl.uniform1f(density,dpr);
    gl.bindBuffer(gl.ARRAY_BUFFER,positions);gl.bufferSubData(gl.ARRAY_BUFFER,0,field.position);
    gl.bindBuffer(gl.ARRAY_BUFFER,visibility);gl.bufferSubData(gl.ARRAY_BUFFER,0,field.opacity);
    gl.drawArrays(gl.POINTS,0,count);
  }
  function resize(){width=innerWidth;height=innerHeight;dpr=Math.min(devicePixelRatio||1,1.5);canvas.width=Math.round(width*dpr);canvas.height=Math.round(height*dpr);gl.viewport(0,0,canvas.width,canvas.height);pointer.radius=Math.min(150,width*.2);build();resume();}
  function tick(now){
    frame=0;if(document.hidden||motion.matches||lost||!field)return;
    const dt=last?Math.min((now-last)/1000,1/30):1/60;last=now;time+=dt;
    field.step(dt,time,pointer);draw();frame=requestAnimationFrame(tick);
  }
  function resume(){cancelAnimationFrame(frame);frame=0;last=0;if(motion.matches&&field){field.reset();draw();}else if(field&&!lost&&!document.hidden)frame=requestAnimationFrame(tick);}
  image.onload=()=>{loaded=true;resize();};
  image.onerror=()=>{canvas.dataset.renderer='unavailable';};
  image.src='/assets/particle-ribbon.png';
  addEventListener('resize',resize);
  addEventListener('pointermove',event=>{pointer.x=event.clientX;pointer.y=event.clientY;pointer.active=!motion.matches;});
  document.addEventListener('pointerleave',()=>{pointer.active=false;});
  addEventListener('blur',()=>{pointer.active=false;});
  addEventListener('pointerup',event=>{if(event.pointerType==='touch')pointer.active=false;});
  document.addEventListener('visibilitychange',()=>{pointer.active=false;resume();});
  motion.addEventListener('change',resume);
  canvas.addEventListener('webglcontextlost',event=>{event.preventDefault();lost=true;cancelAnimationFrame(frame);canvas.hidden=true;});
  resize();
})();
