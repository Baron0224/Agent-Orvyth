/* Per-particle position/velocity simulation, shared by renderer and tests. */
((root) => {
  'use strict';
  // Arc-length tracks: particles travel along the ribbon, rather than orbiting a fixed pixel.
  class RibbonFlow {
    constructor(homes, phases, {width, height}) {
      const curves = [
        [[-.12,.22],[.35,.26],[.52,.92],[1.12,.32]],
        [[.27,.74],[.63,1.36],[.72,.24],[1.08,.48]],
        [[1.08,.38],[.97,-.30],[.70,.20],[.43,.45]],
      ];
      this.tracks = curves.map(points => {
        const xy = [], lengths = [0];
        for (let k=0;k<=160;k++) {
          const t=k/160, u=1-t;
          const x=width*(u*u*u*points[0][0]+3*u*u*t*points[1][0]+3*u*t*t*points[2][0]+t*t*t*points[3][0]);
          const y=height*(u*u*u*points[0][1]+3*u*u*t*points[1][1]+3*u*t*t*points[2][1]+t*t*t*points[3][1]);
          if(k) lengths.push(lengths[k-1]+Math.hypot(x-xy[k*2-2],y-xy[k*2-1]));
          xy.push(x,y);
        }
        return {xy, lengths, length:lengths[160]};
      });
      const n=phases.length;
      this.recycled=new Uint8Array(n);this.track=new Uint8Array(n);this.start=new Float32Array(n);
      this.distance=new Float32Array(n);this.offset=new Float32Array(n);this.speed=new Float32Array(n);
      this.original=new Float32Array(homes);
      for(let i=0;i<n;i++) {
        let best=Infinity, route=0, index=0;
        for(let r=0;r<this.tracks.length;r++) {
          const a=this.tracks[r].xy;
          for(let k=0;k<160;k++) {
            const d=(a[k*2]-homes[i*2])**2+(a[k*2+1]-homes[i*2+1])**2;
            if(d<best){best=d;route=r;index=k;}
          }
        }
        const tr=this.tracks[route], a=tr.xy, j=index*2;
        const dx=a[j+2]-a[j],dy=a[j+3]-a[j+1],len=Math.hypot(dx,dy);
        this.track[i]=route;this.start[i]=this.distance[i]=tr.lengths[index];
        this.offset[i]=height*.18*Math.tanh(((homes[i*2]-a[j])*-dy+(homes[i*2+1]-a[j+1])*dx)/(len*height*.18));
        this.speed[i]=Math.max(22,width*.038)*( .8+.4*(Math.sin(phases[i])* .5+.5));
      }
      // Even arc spacing keeps all branches continuously supplied with particles.
      this.progress=new Float32Array(n);this.initialProgress=new Float32Array(n);
      this.tracks.forEach((tr,r)=>{
        const ids=Array.from({length:n},(_,i)=>i).filter(i=>this.track[i]===r).sort((a,b)=>this.start[a]-this.start[b]);
        ids.forEach((id,k)=>{this.progress[id]=this.initialProgress[id]=(k+.5)/ids.length;});
      });
    }
    advance(seconds, homes, opacity) {
      const dt=Math.min(Math.max(seconds,0),1/30);
      for(let i=0;i<this.distance.length;i++) {
        const tr=this.tracks[this.track[i]], a=tr.xy, lens=tr.lengths;
        const next=this.progress[i]+this.speed[i]*dt/tr.length;
        this.recycled[i]=next>=1 ? 1 : 0;
        const progress=this.progress[i]=next%1;
        const d=this.distance[i]=progress*tr.length;
        let lo=0,hi=159;
        while(lo<hi){const m=(lo+hi+1)>>>1;if(lens[m]<=d)lo=m;else hi=m-1;}
        const j=lo*2, dx=a[j+2]-a[j],dy=a[j+3]-a[j+1], len=lens[lo+1]-lens[lo];
        const t=(d-lens[lo])/len, offset=this.offset[i];
        const x=a[j]+dx*t-dy/len*offset, y=a[j+1]+dy*t+dx/len*offset;
        // Wrap only while invisible, so recycling cannot streak across the screen.
        homes[i*2]=x;homes[i*2+1]=y;
        const fade=Math.min(1,progress*tr.length/65,(1-progress)*tr.length/65);
        opacity[i]=fade*fade*(3-2*fade);
      }
    }
    reset(homes,opacity){this.distance.set(this.start);this.progress.set(this.initialProgress);this.advance(0,homes,opacity);}
  }
  class ParticleField {
    constructor(homes, phases, drift, flowSize) {
      this.home = new Float32Array(homes);
      this.position = new Float32Array(homes);
      this.velocity = new Float32Array(homes.length);
      this.opacity = new Float32Array(phases.length).fill(1);
      this.flow = flowSize ? new RibbonFlow(homes, phases, flowSize) : null;
      if(this.flow) {this.flow.advance(0,this.home,this.opacity);this.position.set(this.home);}
      this.phases = phases;
      this.drift = drift;
    }
    step(seconds, time, pointer) {
      if (this.flow) this.flow.advance(seconds, this.home, this.opacity);
      const frames = Math.min(Math.max(seconds, 0), 1 / 30) * 60;
      const damping = Math.pow(.86, frames);
      const p = this.position, v = this.velocity, h = this.home;
      for (let i = 0; i < this.phases.length; i++) {
        const j = i * 2, phase = this.phases[i], drift = this.drift[i];
        if(this.flow && this.flow.recycled[i]) {p[j]=h[j];p[j+1]=h[j+1];v[j]=v[j+1]=0;}
        let ax = (h[j] + Math.sin(time * .65 + phase) * drift - p[j]) * .028;
        let ay = (h[j+1] + Math.cos(time * .51 + phase * 1.7) * drift * .65 - p[j+1]) * .028;
        if (pointer.active) {
          let dx = p[j] - pointer.x, dy = p[j+1] - pointer.y;
          const distance = Math.hypot(dx, dy);
          if (distance < pointer.radius) {
            const d = Math.max(distance, .01);
            if (distance < .01) { dx = Math.cos(phase) * d; dy = Math.sin(phase) * d; }
            const force = Math.pow(1 - distance / pointer.radius, 2) * 3.4;
            ax += (dx - dy * .48) / d * force;
            ay += (dy + dx * .48) / d * force;
          }
        }
        v[j] = Math.max(-8, Math.min(8, (v[j] + ax * frames) * damping));
        v[j+1] = Math.max(-8, Math.min(8, (v[j+1] + ay * frames) * damping));
        p[j] += v[j] * frames;
        p[j+1] += v[j+1] * frames;
      }
    }
    reset() {
      if (this.flow) this.flow.reset(this.home, this.opacity);
      this.position.set(this.home); this.velocity.fill(0);
    }
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = ParticleField;
  else root.OrvythParticleField = ParticleField;
})(typeof globalThis !== 'undefined' ? globalThis : this);
