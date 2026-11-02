/* Per-particle position/velocity simulation, shared by renderer and tests. */
((root) => {
  'use strict';
  class ParticleField {
    constructor(homes, phases, drift) {
      this.home = new Float32Array(homes);
      this.position = new Float32Array(homes);
      this.velocity = new Float32Array(homes.length);
      this.phases = phases;
      this.drift = drift;
    }
    step(seconds, time, pointer) {
      const frames = Math.min(Math.max(seconds, 0), 1 / 30) * 60;
      const damping = Math.pow(.86, frames);
      const p = this.position, v = this.velocity, h = this.home;
      for (let i = 0; i < this.phases.length; i++) {
        const j = i * 2, phase = this.phases[i], drift = this.drift[i];
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
    reset() { this.position.set(this.home); this.velocity.fill(0); }
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = ParticleField;
  else root.OrvythParticleField = ParticleField;
})(typeof globalThis !== 'undefined' ? globalThis : this);
