/* Reference-matched ribbon: a clean image plate animated with a WebGL flow field. */
(() => {
  'use strict';
  const canvas = document.getElementById('particles');
  const motion = matchMedia('(prefers-reduced-motion: reduce)');
  const gl = canvas.getContext('webgl', {alpha: true, antialias: false, powerPreference: 'low-power'});
  if (!gl) return; // CSS retains the reference image and the entry link.
  const vertex = `attribute vec2 position; varying vec2 uv;
    void main(){uv=position*.5+.5;gl_Position=vec4(position,0.,1.);}`;
  const fragment = `precision highp float;
    varying vec2 uv; uniform sampler2D plate; uniform vec2 resolution;
    uniform float imageAspect; uniform float time; uniform vec2 pointer;
    void main(){
      float aspect=resolution.x/resolution.y;
      vec2 fit=vec2(min(1.,aspect/imageAspect),min(1.,imageAspect/aspect));
      vec2 p=(uv-.5)*fit+.5;
      if(p.x<0.||p.x>1.||p.y<0.||p.y>1.){gl_FragColor=vec4(0.,0.,0.,0.);return;}
      float edge=smoothstep(0.,.12,p.x)*(1.-smoothstep(.88,1.,p.x));
      float field=smoothstep(.14,.35,p.y)*(1.-smoothstep(.95,1.,p.y))*edge;
      vec2 broad=vec2(sin(p.y*9.+p.x*3.-time*.24),cos(p.x*7.-p.y*3.+time*.18));
      vec2 fine=vec2(sin(p.y*23.-p.x*9.+time*.45),cos(p.x*21.+p.y*6.-time*.38));
      vec2 displacement=(broad*vec2(.021,.036)+fine*.0035)*field;
      vec2 sampleUV=clamp(p+displacement+pointer*.006*field,vec2(.001),vec2(.999));
      vec3 color=texture2D(plate,sampleUV).rgb;
      float light=1.+.045*sin(p.x*16.+p.y*13.-time*.85)*field;
      gl_FragColor=vec4(color*light,1.);
    }`;
  function shader(type, code) {
    const s=gl.createShader(type); gl.shaderSource(s,code); gl.compileShader(s);
    if(!gl.getShaderParameter(s,gl.COMPILE_STATUS)) throw new Error('Shader unavailable');
    return s;
  }
  let program;
  try {
    program=gl.createProgram();
    gl.attachShader(program,shader(gl.VERTEX_SHADER,vertex));
    gl.attachShader(program,shader(gl.FRAGMENT_SHADER,fragment));
    gl.linkProgram(program);
    if(!gl.getProgramParameter(program,gl.LINK_STATUS)) throw new Error('WebGL unavailable');
  } catch { canvas.hidden=true; return; }
  gl.useProgram(program);
  const buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buffer);
  gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,-1,1,1,-1,1,1]),gl.STATIC_DRAW);
  const position=gl.getAttribLocation(program,'position');
  gl.enableVertexAttribArray(position);gl.vertexAttribPointer(position,2,gl.FLOAT,false,0,0);
  const uniforms=Object.fromEntries(['resolution','imageAspect','time','pointer','plate'].map(n=>[n,gl.getUniformLocation(program,n)]));
  const texture=gl.createTexture();gl.bindTexture(gl.TEXTURE_2D,texture);
  gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);
  let ready=false,frame=0,last=0,time=0,mouseX=0,mouseY=0,x=0,y=0,lost=false;
  const image=new Image();
  function render(){
    if(!ready||lost)return;
    gl.uniform2f(uniforms.resolution,canvas.width,canvas.height);
    gl.uniform1f(uniforms.imageAspect,image.naturalWidth/image.naturalHeight);
    gl.uniform1f(uniforms.time,motion.matches?0:time);
    gl.uniform2f(uniforms.pointer,motion.matches?0:x,motion.matches?0:y);
    gl.drawArrays(gl.TRIANGLES,0,6);
  }
  function resize(){
    const dpr=Math.min(devicePixelRatio||1,1.5);
    canvas.width=Math.round(innerWidth*dpr);canvas.height=Math.round(innerHeight*dpr);
    gl.viewport(0,0,canvas.width,canvas.height);render();
  }
  function tick(now){
    frame=0;if(document.hidden||motion.matches||lost||!ready)return;
    if(last)time+=Math.min((now-last)/1000,.05);last=now;
    x+=(mouseX-x)*.03;y+=(mouseY-y)*.03;render();
    frame=requestAnimationFrame(tick);
  }
  function resume(){
    cancelAnimationFrame(frame);frame=0;last=0;
    if(ready&&!document.hidden&&!motion.matches&&!lost)frame=requestAnimationFrame(tick);
    else render();
  }
  image.onload=()=>{
    if(lost)return;
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL,true);
    gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,image);
    gl.uniform1i(uniforms.plate,0);ready=true;resize();resume();
  };
  image.onerror=()=>{canvas.hidden=true;};
  image.src='/assets/particle-ribbon.png';
  addEventListener('resize',resize);
  addEventListener('pointermove',event=>{mouseX=event.clientX/innerWidth-.5;mouseY=.5-event.clientY/innerHeight;});
  document.addEventListener('pointerleave',()=>{mouseX=mouseY=0;});
  document.addEventListener('visibilitychange',resume);
  motion.addEventListener('change',resume);
  canvas.addEventListener('webglcontextlost',event=>{event.preventDefault();lost=true;cancelAnimationFrame(frame);canvas.hidden=true;});
  // Context restoration keeps the static plate usable; a page refresh restores animation.
  resize();
})();
