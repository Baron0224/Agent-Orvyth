/* Per-particle position/velocity simulation, shared by renderer and tests. */
((root) => {
  'use strict';
  // Arc-length tracks: particles travel along the ribbon, rather than orbiting a fixed pixel.
  class RibbonFlow {
    constructor(homes, phases, {width, height}) {
      // Paths follow the marked upper sweep, lower return and inner curl.
      // Open endpoints sit beyond the viewport; no visible branch fades out midway.
      const curves = [
        // Main: left inlet through the central stream and inner curl to the right.
        [[-.18,.60],[.00,.51],[.17,.30],[.25,.43],
         [.32,.52],[.47,.49],[.55,.49],
         [.68,.44],[.78,.23],[.79,.41],
         [.78,.53],[1.01,.51],[1.18,.36]],
        // Main: upper-right sweep returns left, then rejoins the central stream.
        [[1.18,.05],[.92,.10],[.87,.06],[.71,.10],
         [.55,.13],[.50,.36],[.46,.48],
         [.52,.51],[.69,.45],[.78,.43],
         [.98,.48],[1.04,.23],[.91,.13],
         [.86,.07],[1.03,.06],[1.18,.01]],
        // Secondary: broad lower loop.
        [[-.18,.16],[.00,.26],[.17,.35],[.22,.48],
         [.30,.69],[.38,.91],[.57,.90],
         [.80,.93],[.70,.52],[.84,.48],
         [.98,.43],[1.06,.53],[1.18,.46]],
        // Secondary: lighter stream across the middle-bottom gap.
        [[-.18,.72],[.13,.61],[.34,.54],[.50,.58],
         [.62,.62],[.66,.65],[.74,.62],
         [.90,.59],[1.02,.48],[1.18,.50]],
      ];
      this.tracks = curves.map(points => {
        const xy = [], lengths = [0];
        for(let segment=0;segment<(points.length-1)/3;segment++) {
          const p=points.slice(segment*3,segment*3+4);
          for(let k=segment ? 1 : 0;k<=100;k++) {
            const t=k/100,u=1-t;
            const x=width*(u*u*u*p[0][0]+3*u*u*t*p[1][0]+3*u*t*t*p[2][0]+t*t*t*p[3][0]);
            const y=height*(u*u*u*p[0][1]+3*u*u*t*p[1][1]+3*u*t*t*p[2][1]+t*t*t*p[3][1]);
            if(xy.length) lengths.push(lengths[lengths.length-1]+Math.hypot(x-xy[xy.length-2],y-xy[xy.length-1]));
            xy.push(x,y);
          }
        }
        return {xy,lengths,length:lengths[lengths.length-1]};
      });
      const n=phases.length;
      this.recycled=new Uint8Array(n);this.track=new Uint8Array(n);this.start=new Float32Array(n);
      this.distance=new Float32Array(n);this.offset=new Float32Array(n);this.speed=new Float32Array(n);
      this.layer=new Uint8Array(n);this.wisp=new Float32Array(n);this.height=height;
      this.original=new Float32Array(homes);
      for(let i=0;i<n;i++) {
        // Balanced lanes and decorrelated widths prevent travelling clumps and empty cuts.
        const slot=i%100, route=slot<42 ? 0 : slot<74 ? 1 : slot<92 ? 2 : 3, tr=this.tracks[route];
        this.track[i]=route;this.start[i]=this.distance[i]=i/n*tr.length;
        const noise=Math.sin(i*127.1+phases[i]*311.7)*43758.5453;
        const spread=(noise-Math.floor(noise))*2-1;
        const noise2=Math.sin(i*269.5+37.2)*18391.317;
        const secondary=noise2-Math.floor(noise2);
        // Dense wisps, a soft wider cloud, then sparse spray beyond the silhouette.
        this.layer[i]=i%10<5 ? 0 : i%10<9 ? 1 : 2;
        this.wisp[i]=(i%23)/23*Math.PI*2;
        if(this.layer[i]===0) this.offset[i]=spread*height*.013;
        else {
          const gaussian=Math.sqrt(-2*Math.log(Math.max(.0001,secondary)))*Math.cos((spread+1)*Math.PI);
          this.offset[i]=gaussian*height*(this.layer[i]===1 ? .065 : .17);
        }
        this.speed[i]=Math.max(22,width*.038)*( .8+.4*(Math.sin(phases[i])* .5+.5))/6;
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
        let lo=0,hi=lens.length-2;
        while(lo<hi){const m=(lo+hi+1)>>>1;if(lens[m]<=d)lo=m;else hi=m-1;}
        const j=lo*2, dx=a[j+2]-a[j],dy=a[j+3]-a[j+1], len=lens[lo+1]-lens[lo];
        const t=(d-lens[lo])/len, phase=this.wisp[i], h=this.height;
        const breath=.9+.25*Math.sin(d*.006+this.track[i]*2)+.13*Math.sin(d*.019);
        let offset=this.offset[i]*breath;
        // Interwoven strands meander independently instead of sharing a ruler-straight edge.
        if(this.layer[i]===0) offset+=h*(.034*Math.sin(d*.007+phase)+.024*Math.sin(d*.015+phase*2.3));
        else offset+=h*.014*Math.sin(d*.012+phase);
        const x=a[j]+dx*t-dy/len*offset, y=a[j+1]+dy*t+dx/len*offset;
        // Wrap only while invisible, so recycling cannot streak across the screen.
        homes[i*2]=x;homes[i*2+1]=y;
        const fade=Math.min(1,progress*tr.length/65,(1-progress)*tr.length/65);
        opacity[i]=fade*fade*(3-2*fade)*(this.layer[i]===2 ? .5 : 1);
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
