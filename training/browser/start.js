/* Procedural flowing particles: no video, external asset or network request. */
(() => {
  'use strict';
  const canvas = document.getElementById('particles');
  const ctx = canvas.getContext('2d');
  if (!ctx) return; // Background and entry link remain usable without Canvas.
  const motion = matchMedia('(prefers-reduced-motion: reduce)');
  let width = 0, height = 0, points = [], frame = 0, time = 0, last = 0;
  let pointerX = 0, pointerY = 0, offsetX = 0, offsetY = 0;
  let seed = 413;
  const random = () => {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
    return seed / 4294967296;
  };
  const sprite = document.createElement('canvas');
  sprite.width = sprite.height = 32;
  const glow = sprite.getContext('2d');
  const gradient = glow.createRadialGradient(16, 16, 0, 16, 16, 16);
  gradient.addColorStop(0, '#edf8ff');
  gradient.addColorStop(.15, '#b9dfff');
  gradient.addColorStop(.4, '#729fc766');
  gradient.addColorStop(1, '#729fc700');
  glow.fillStyle = gradient;
  glow.fillRect(0, 0, 32, 32);

  function resize() {
    width = innerWidth;
    height = innerHeight;
    const dpr = Math.min(devicePixelRatio || 1, 1.75);
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    seed = 413;
    const count = width < 650 ? 2400 : 6200;
    points = Array.from({length: count}, () => ({
      u: random(), phase: random() * Math.PI * 2,
      radius: Math.pow(random(), 2), size: .35 + Math.pow(random(), 5) * 2.1,
      light: .2 + random() * .8, band: random() > .6 ? 1 : -1,
    }));
    render();
  }

  function render() {
    ctx.clearRect(0, 0, width, height);
    const scale = Math.min(width * .36, height * .83);
    const centerY = height * .45;
    ctx.globalCompositeOperation = 'lighter';
    // Fine continuous strands give the moving points a readable ribbon shape.
    for (let strand = 0; strand < 36; strand++) {
      const band = strand < 18 ? -1 : 1;
      const phase = strand * 2.399 + time * .14;
      ctx.beginPath();
      for (let step = 0; step <= 100; step++) {
        const u = (step / 100 - .5) * 4.4;
        const r = .025 + (strand % 18) / 18 * .11;
        const y = Math.sin(u * 1.55 + time * .16 + band * .65) * .28
          + Math.cos(phase + u * .9) * r;
        const z = Math.cos(u * 1.6 + band) * .23 + Math.sin(phase + u * .9) * r;
        const perspective = 2.5 / (2.5 + z);
        const px = width / 2 + u * scale * perspective + offsetX * (z + .5);
        const py = centerY + y * scale * perspective + offsetY * (z + .5);
        if (!step) ctx.moveTo(px, py); else ctx.lineTo(px, py);
      }
      ctx.lineWidth = .5;
      ctx.strokeStyle = '#91c6ec';
      ctx.globalAlpha = .06;
      ctx.stroke();
    }
    for (const point of points) {
      // The fade at either edge hides wraparound; the flow has no timed ending.
      const progress = (point.u + time * .025) % 1;
      const u = (progress - .5) * 4.4;
      const phase = point.phase + time * .14 + u * .9;
      const radius = .035 + point.radius * (.15 + .13 * (1 + Math.sin(u * 1.8)));
      const x = u;
      const y = Math.sin(u * 1.55 + time * .16 + point.band * .65) * .28
        + Math.cos(phase) * radius;
      const z = Math.cos(u * 1.6 + point.band) * .23 + Math.sin(phase) * radius;
      const perspective = 2.5 / (2.5 + z);
      const px = width / 2 + x * scale * perspective + offsetX * (z + .5);
      const py = centerY + y * scale * perspective + offsetY * (z + .5);
      const fade = Math.min(1, progress * 9, (1 - progress) * 9);
      const size = point.size * perspective;
      ctx.globalAlpha = fade * point.light * (.45 + .35 * perspective);
      if (size > 1.1) {
        const diameter = size * 5;
        ctx.drawImage(sprite, px - diameter / 2, py - diameter / 2, diameter, diameter);
      } else {
        ctx.fillStyle = '#b9d6ec';
        ctx.fillRect(px, py, size, size);
      }
    }
    ctx.globalAlpha = 1;
    ctx.globalCompositeOperation = 'source-over';
  }

  function tick(now) {
    frame = 0;
    if (document.hidden || motion.matches) return;
    if (last) time += Math.min((now - last) / 1000, .05);
    last = now;
    offsetX += (pointerX - offsetX) * .035;
    offsetY += (pointerY - offsetY) * .035;
    render();
    frame = requestAnimationFrame(tick);
  }
  function resume() {
    cancelAnimationFrame(frame);
    frame = 0;
    last = 0;
    if (!document.hidden && !motion.matches) frame = requestAnimationFrame(tick);
    else render();
  }
  addEventListener('resize', resize);
  addEventListener('pointermove', event => {
    if (motion.matches) return;
    pointerX = (event.clientX / width - .5) * 35;
    pointerY = (event.clientY / height - .5) * 25;
  });
  document.addEventListener('pointerleave', () => { pointerX = pointerY = 0; });
  document.addEventListener('visibilitychange', resume);
  motion.addEventListener('change', resume);
  resize();
  resume();
})();
