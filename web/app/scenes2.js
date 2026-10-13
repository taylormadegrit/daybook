// ================= more home scenes + sounds (all drawn/synthesized on this PC — no downloads, work offline) =================
(function () {
  const custom = SCENES.custom; delete SCENES.custom;
  Object.assign(SCENES, {
    aurora: {name: "Northern lights", em: "🌠", bg: "linear-gradient(#020617,#0b3b3a)"},
    storm: {name: "Thunderstorm", em: "⛈️", bg: "linear-gradient(#0b0f1a,#26324a)"},
    city: {name: "City at night", em: "🌃", bg: "linear-gradient(#070a1a,#2a1f4a)"},
    cafe: {name: "Cozy café", em: "☕", bg: "linear-gradient(#1c120c,#4a2c1a)"},
    underwater: {name: "Underwater", em: "🐠", bg: "linear-gradient(#033b5a,#011627)"},
    sakura: {name: "Cherry blossoms", em: "🌸", bg: "linear-gradient(#ffd6e4,#8fb8de)"},
    space: {name: "Deep space", em: "🪐", bg: "linear-gradient(#000,#1b0b3a)"},
    dunes: {name: "Desert dusk", em: "🏜️", bg: "linear-gradient(#ffb36b,#6b3a6e)"},
    custom,
  });
  const stars = (st, w, h, n, maxY = 1) => st.stars || (st.stars = Array.from({length: n}, () => ({x: R(0, w), y: R(0, h * maxY), r: R(.4, 1.6), p: R(0, 6.28)})));
  const drawStars = (g, st, t, a = 1) => { for (const s of st.stars) { g.globalAlpha = a * (.45 + .45 * Math.sin(t * 1.3 + s.p)); g.fillStyle = "#fff"; g.fillRect(s.x, s.y, s.r, s.r); } g.globalAlpha = 1; };
  const ridge = (g, w, base, amp, seed, col) => { g.fillStyle = col; g.beginPath(); g.moveTo(0, base);
    for (let x = 0; x <= w; x += w / 60) g.lineTo(x, base - amp * (.5 + .3 * Math.sin(x / w * 7 + seed) + .2 * Math.sin(x / w * 17 + seed * 2)));
    g.lineTo(w, 4000); g.lineTo(0, 4000); g.closePath(); g.fill(); };
  Object.assign(DRAW, {
    aurora(g, w, h, dt, t, st) {
      let gr = g.createLinearGradient(0, 0, 0, h); gr.addColorStop(0, "#01030d"); gr.addColorStop(1, "#071d2a"); g.fillStyle = gr; g.fillRect(0, 0, w, h);
      stars(st, w, h, 260, .7); drawStars(g, st, t, .8);
      g.globalCompositeOperation = "lighter";
      for (let b = 0; b < 3; b++) {
        const hue = [150, 175, 280][b], yb = h * (.22 + b * .09);
        for (let x = 0; x < w; x += 6) {
          const y = yb + Math.sin(x / w * 5 + t * .25 + b) * h * .07 + Math.sin(x / w * 13 - t * .4) * h * .02;
          const len = h * (.18 + .1 * Math.sin(x / w * 9 + t * .3 + b * 2)), a = .05 + .05 * Math.sin(x / w * 11 + t * .6 + b);
          const lg = g.createLinearGradient(0, y, 0, y + len); lg.addColorStop(0, `hsla(${hue},90%,60%,0)`); lg.addColorStop(.3, `hsla(${hue},90%,62%,${a})`); lg.addColorStop(1, `hsla(${hue},90%,55%,0)`);
          g.fillStyle = lg; g.fillRect(x, y, 6, len);
        }
      }
      g.globalCompositeOperation = "source-over";
      ridge(g, w, h * .86, h * .16, 1.3, "#04121a"); ridge(g, w, h * .93, h * .1, 4.1, "#020a10");
    },
    storm(g, w, h, dt, t, st) {
      if (!st.drops) { st.drops = Array.from({length: 420}, () => ({x: R(0, w), y: R(0, h), v: R(900, 1500), l: R(10, 26)})); st.flash = 0; st.next = t + R(4, 9); }
      if (t > st.next) { st.flash = 1; st.next = t + R(6, 16); st.bolt = Array.from({length: 9}, (_, i) => [R(-40, 40), i]); st.bx = R(w * .15, w * .85); if (typeof ambSfx === "function") setTimeout(() => ambSfx("thunder"), R(300, 1400)); }
      const f = st.flash; st.flash = Math.max(0, f - dt * 2.2);
      let gr = g.createLinearGradient(0, 0, 0, h); gr.addColorStop(0, `rgb(${12 + f * 120},${16 + f * 125},${28 + f * 140})`); gr.addColorStop(1, `rgb(${30 + f * 60},${40 + f * 60},${60 + f * 60})`);
      g.fillStyle = gr; g.fillRect(0, 0, w, h);
      if (f > .6 && st.bolt) { g.strokeStyle = `rgba(230,240,255,${f})`; g.lineWidth = 2.2; g.beginPath(); let x = st.bx, y = 0; g.moveTo(x, y);
        for (const [dx] of st.bolt) { x += dx; y += h * .07; g.lineTo(x, y); } g.stroke(); }
      g.strokeStyle = "rgba(180,200,230,.35)"; g.lineWidth = 1; g.beginPath();
      for (const d of st.drops) { d.y += d.v * dt; d.x += 120 * dt; if (d.y > h) { d.y = -20; d.x = R(-100, w); } g.moveTo(d.x, d.y); g.lineTo(d.x - 3, d.y - d.l); }
      g.stroke(); ridge(g, w, h * .95, h * .07, 2.2, "#06080f");
    },
    city(g, w, h, dt, t, st) {
      if (!st.b) { st.b = []; let x = 0; while (x < w) { const bw = R(40, 110) * (w / 1600), bh = R(.18, .55) * h; st.b.push({x, bw, bh, win: Array.from({length: 60}, () => Math.random() < .45), seed: R(0, 9)}); x += bw + R(2, 8); }
        stars(st, w, h, 120, .4); st.cars = []; }
      let gr = g.createLinearGradient(0, 0, 0, h); gr.addColorStop(0, "#05071a"); gr.addColorStop(.7, "#2a1f4a"); gr.addColorStop(1, "#ff7a59"); g.fillStyle = gr; g.fillRect(0, 0, w, h);
      drawStars(g, st, t, .6);
      g.fillStyle = "rgba(255,240,200,.85)"; g.beginPath(); g.arc(w * .82, h * .16, h * .045, 0, 6.3); g.fill();
      for (const b of st.b) {
        g.fillStyle = "#0b0d1c"; g.fillRect(b.x, h - b.bh, b.bw, b.bh);
        const cols = Math.max(2, b.bw / 14 | 0), rows = Math.max(3, b.bh / 22 | 0);
        for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) { const i = (r * cols + c) % 60; if (!b.win[i]) continue;
          const on = Math.sin(t * .2 + b.seed + i) > -.85; if (!on) continue; g.fillStyle = (i + r) % 7 ? "rgba(255,214,140,.75)" : "rgba(160,210,255,.7)";
          g.fillRect(b.x + 5 + c * (b.bw - 8) / cols, h - b.bh + 8 + r * 20, 5, 8); }
      }
      if (Math.random() < dt * 1.2) { const v = R(160, 320) * (Math.random() < .5 ? 1 : -1); st.cars.push({x: v > 0 ? -20 : w + 20, v}); }
      st.cars = st.cars.filter(c => c.x > -60 && c.x < w + 60);
      for (const c of st.cars) { c.x += c.v * dt; g.fillStyle = c.v > 0 ? "rgba(255,240,200,.9)" : "rgba(255,60,60,.9)"; g.fillRect(c.x, h - 6, 6, 2); }
    },
    cafe(g, w, h, dt, t, st) {
      if (!st.bk) st.bk = Array.from({length: 46}, () => ({x: R(0, w), y: R(0, h), r: R(18, 70) * (h / 900), hue: R(20, 50), p: R(0, 6.3), vx: R(-6, 6), vy: R(-4, 4)}));
      let gr = g.createRadialGradient(w * .5, h * .7, 10, w * .5, h * .6, h); gr.addColorStop(0, "#5a3520"); gr.addColorStop(1, "#140b07"); g.fillStyle = gr; g.fillRect(0, 0, w, h);
      g.globalCompositeOperation = "lighter";
      for (const b of st.bk) { b.x += b.vx * dt; b.y += b.vy * dt; if (b.x < -80) b.x = w + 80; if (b.x > w + 80) b.x = -80; if (b.y < -80) b.y = h + 80; if (b.y > h + 80) b.y = -80;
        const a = .08 + .05 * Math.sin(t * .7 + b.p); const rg = g.createRadialGradient(b.x, b.y, 0, b.x, b.y, b.r);
        rg.addColorStop(0, `hsla(${b.hue},95%,65%,${a * 2})`); rg.addColorStop(.7, `hsla(${b.hue},95%,60%,${a})`); rg.addColorStop(1, `hsla(${b.hue},95%,55%,0)`); g.fillStyle = rg; g.beginPath(); g.arc(b.x, b.y, b.r, 0, 6.3); g.fill(); }
      g.globalCompositeOperation = "source-over";
      g.fillStyle = "rgba(20,10,6,.85)"; g.fillRect(0, h * .86, w, h);   // table
      const cx = w * .5, cy = h * .86;  // a cup with steam
      g.fillStyle = "#e8ddd0"; g.beginPath(); g.ellipse(cx, cy - 4, 46 * h / 900, 10 * h / 900, 0, 0, 6.3); g.fill(); g.fillRect(cx - 38 * h / 900, cy - 60 * h / 900, 76 * h / 900, 56 * h / 900);
      g.strokeStyle = "rgba(255,255,255,.18)"; g.lineWidth = 3; for (let k = 0; k < 3; k++) { g.beginPath(); for (let y = 0; y < 120; y += 4) { const yy = cy - 70 * h / 900 - y * h / 900;
        g.lineTo(cx + (k - 1) * 14 + Math.sin(y / 14 + t * 1.5 + k) * 8, yy); } g.stroke(); }
    },
    underwater(g, w, h, dt, t, st) {
      if (!st.bub) { st.bub = []; st.fish = Array.from({length: 7}, () => ({x: R(0, w), y: R(h * .2, h * .8), v: R(30, 80) * (Math.random() < .5 ? 1 : -1), s: R(8, 18) * h / 900, hue: R(10, 60)})); }
      let gr = g.createLinearGradient(0, 0, 0, h); gr.addColorStop(0, "#0a6f9a"); gr.addColorStop(1, "#011627"); g.fillStyle = gr; g.fillRect(0, 0, w, h);
      g.globalCompositeOperation = "lighter";
      for (let i = 0; i < 7; i++) { const x = w * (i / 7) + Math.sin(t * .3 + i) * 60; const lg = g.createLinearGradient(x, 0, x + 120, h); lg.addColorStop(0, "rgba(160,230,255,.10)"); lg.addColorStop(1, "rgba(160,230,255,0)");
        g.fillStyle = lg; g.beginPath(); g.moveTo(x - 30, 0); g.lineTo(x + 30, 0); g.lineTo(x + 220, h); g.lineTo(x + 100, h); g.closePath(); g.fill(); }
      g.globalCompositeOperation = "source-over";
      if (Math.random() < dt * 8) st.bub.push({x: R(0, w), y: h + 10, r: R(2, 6), v: R(40, 90), p: R(0, 6)});
      st.bub = st.bub.filter(b => (b.y -= b.v * dt) > -10);
      g.strokeStyle = "rgba(200,240,255,.5)"; for (const b of st.bub) { g.beginPath(); g.arc(b.x + Math.sin(t * 2 + b.p) * 6, b.y, b.r, 0, 6.3); g.stroke(); }
      for (const f of st.fish) { f.x += f.v * dt; if (f.x > w + 40) f.x = -40; if (f.x < -40) f.x = w + 40; const d = Math.sign(f.v), y = f.y + Math.sin(t + f.x / 90) * 8;
        g.fillStyle = `hsl(${f.hue},90%,60%)`; g.beginPath(); g.ellipse(f.x, y, f.s * 1.6, f.s * .7, 0, 0, 6.3); g.fill();
        g.beginPath(); g.moveTo(f.x - d * f.s * 1.4, y); g.lineTo(f.x - d * f.s * 2.4, y - f.s * .8); g.lineTo(f.x - d * f.s * 2.4, y + f.s * .8); g.closePath(); g.fill(); }
      g.fillStyle = "#06243a"; ridge(g, w, h * .97, h * .06, 3.3, "#052033");
    },
    sakura(g, w, h, dt, t, st) {
      if (!st.pt) st.pt = Array.from({length: 90}, () => ({x: R(0, w), y: R(-h, h), s: R(5, 11) * h / 900, v: R(30, 70), sw: R(.5, 2), p: R(0, 6.3), rot: R(0, 6.3)}));
      let gr = g.createLinearGradient(0, 0, 0, h); gr.addColorStop(0, "#ffe3ee"); gr.addColorStop(.6, "#c9def2"); gr.addColorStop(1, "#8fb8de"); g.fillStyle = gr; g.fillRect(0, 0, w, h);
      ridge(g, w, h * .9, h * .2, .7, "rgba(120,150,190,.55)"); ridge(g, w, h * .97, h * .1, 2.9, "rgba(90,120,160,.7)");
      // a branch
      g.strokeStyle = "#4a2e2a"; g.lineWidth = 10 * h / 900; g.lineCap = "round"; g.beginPath(); g.moveTo(-10, h * .12); g.quadraticCurveTo(w * .25, h * .2, w * .42, h * .08); g.stroke();
      for (let i = 0; i < 26; i++) { const k = i / 26, x = -10 + (w * .42) * k, y = h * .12 + Math.sin(k * 3.1) * h * .05 - k * h * .04;
        g.fillStyle = i % 3 ? "rgba(255,182,206,.95)" : "rgba(255,215,228,.95)"; g.beginPath(); g.arc(x + R(-1, 1), y + 14 * Math.sin(i), 9 * h / 900, 0, 6.3); g.fill(); }
      const wind = (SC.mx - .5) * 60;
      for (const p of st.pt) { p.y += p.v * dt; p.x += (Math.sin(t * p.sw + p.p) * 30 + wind) * dt; p.rot += dt * p.sw; if (p.y > h + 20) { p.y = -20; p.x = R(-50, w); }
        g.save(); g.translate(p.x, p.y); g.rotate(p.rot); g.fillStyle = "rgba(255,170,198,.9)"; g.beginPath(); g.ellipse(0, 0, p.s, p.s * .55, 0, 0, 6.3); g.fill(); g.restore(); }
    },
    space(g, w, h, dt, t, st) {
      if (!st.l) st.l = [0, 1, 2].map(z => Array.from({length: 140 - z * 30}, () => ({x: R(0, w), y: R(0, h), r: R(.5, 1.4) * (z + 1) * .8})));
      g.fillStyle = "#03010a"; g.fillRect(0, 0, w, h);
      g.globalCompositeOperation = "lighter";
      [[.3, .4, 280], [.7, .6, 200], [.5, .2, 330]].forEach(([fx, fy, hue], i) => { const x = w * fx + Math.sin(t * .05 + i) * 40, y = h * fy, r = h * .45;
        const rg = g.createRadialGradient(x, y, 0, x, y, r); rg.addColorStop(0, `hsla(${hue},80%,55%,.22)`); rg.addColorStop(1, `hsla(${hue},80%,40%,0)`); g.fillStyle = rg; g.fillRect(x - r, y - r, r * 2, r * 2); });
      g.globalCompositeOperation = "source-over";
      st.l.forEach((layer, z) => { g.fillStyle = `rgba(255,255,255,${.4 + z * .25})`; for (const s of layer) { s.x -= (4 + z * 10) * dt; if (s.x < 0) s.x = w; g.fillRect(s.x, s.y, s.r, s.r); } });
      const px = w * .78, py = h * .7, pr = h * .16;  // a planet with a ring
      const pg = g.createRadialGradient(px - pr * .4, py - pr * .4, pr * .1, px, py, pr); pg.addColorStop(0, "#f7c08a"); pg.addColorStop(1, "#5a2a5e"); g.fillStyle = pg; g.beginPath(); g.arc(px, py, pr, 0, 6.3); g.fill();
      g.strokeStyle = "rgba(255,220,180,.55)"; g.lineWidth = 3; g.beginPath(); g.ellipse(px, py, pr * 1.7, pr * .35, -.3, 0, 6.3); g.stroke();
    },
    dunes(g, w, h, dt, t, st) {
      let gr = g.createLinearGradient(0, 0, 0, h); gr.addColorStop(0, "#3b2a5e"); gr.addColorStop(.5, "#ff8a5b"); gr.addColorStop(.75, "#ffc37a"); gr.addColorStop(1, "#c9774a"); g.fillStyle = gr; g.fillRect(0, 0, w, h);
      const sy = h * (.52 + .02 * Math.sin(t * .05)); const sg = g.createRadialGradient(w * .62, sy, 0, w * .62, sy, h * .3);
      sg.addColorStop(0, "rgba(255,240,200,1)"); sg.addColorStop(.12, "rgba(255,210,150,.9)"); sg.addColorStop(1, "rgba(255,150,90,0)"); g.fillStyle = sg; g.fillRect(0, 0, w, h);
      const dune = (base, amp, off, col) => { g.fillStyle = col; g.beginPath(); g.moveTo(0, base); for (let x = 0; x <= w; x += w / 80) g.lineTo(x, base - amp * Math.sin(x / w * 3.2 + off) ** 2); g.lineTo(w, h); g.lineTo(0, h); g.fill(); };
      dune(h * .78, h * .12, 0.4 + t * .004, "#b4603c"); dune(h * .86, h * .1, 1.9 + t * .006, "#8e4430"); dune(h * .95, h * .08, 3.1 + t * .008, "#5e2c25");
      if (!st.birds) st.birds = Array.from({length: 5}, (_, i) => ({x: R(0, w), y: R(h * .2, h * .4), v: R(20, 40), p: i}));
      g.strokeStyle = "rgba(40,20,30,.7)"; g.lineWidth = 2;
      for (const b of st.birds) { b.x += b.v * dt; if (b.x > w + 20) b.x = -20; const f = Math.sin(t * 6 + b.p) * 5; g.beginPath(); g.moveTo(b.x - 8, b.y - f); g.lineTo(b.x, b.y); g.lineTo(b.x + 8, b.y - f); g.stroke(); }
    },
  });

  // ---- sounds (also pickable on their own, with any scene) ----
  Object.assign(SOUNDS, {
    aurora() { const wnd = auNoise("pink", [["bandpass", 300, .5]], .08); auLFO(wnd.gain, .03, .05, .08); pad([220, 277, 330, 415], .018); },
    storm() { SOUNDS.rain(); every(9000, () => { if (Math.random() < .5) ambSfx("thunder"); }); },
    city() { const hum = auNoise("brown", [["lowpass", 260]], .3); auLFO(hum.gain, .05, .06, .3);
      every(3500, () => { if (Math.random() < .5) auBurst(R(500, 900), R(2, 3.5), .12, .6); }); },
    cafe() { const m = auNoise("pink", [["bandpass", 900, .9], ["lowpass", 2500]], .16); auLFO(m.gain, .3, .04, .16);
      every(600, () => { if (Math.random() < .18) { const f = R(2600, 4200); auChirp(f, f * 1.01, .25, .03); setTimeout(() => auChirp(f * 1.5, f * 1.5, .18, .015), 40); } }); },
    underwater() { auNoise("brown", [["lowpass", 180]], .5); const s = auNoise("pink", [["bandpass", 600, .4]], .05); auLFO(s.gain, .1, .03, .05);
      every(300, () => { if (Math.random() < .25) auChirp(R(300, 700), R(900, 1500), .07, .05); }); },
    sakura() { const wnd = auNoise("pink", [["bandpass", 600, .5]], .05); auLFO(wnd.gain, .06, .04, .05); chimes(); stream(.05); },
    space() { pad([55, 82.5, 110, 164.8], .03); const n = auNoise("brown", [["lowpass", 120]], .08); auLFO(n.gain, .02, .05, .08); },
    dunes() { const wnd = auNoise("pink", [["bandpass", 450, .3]], .16); auLFO(wnd.gain, .04, .12, .16); every(4000, () => { if (Math.random() < .3) auChirp(1800, 1500, .25, .02); }); },
    // sound-only choices
    whitenoise() { auNoise("white", [["lowpass", 9000]], .18); },
    brownnoise() { auNoise("brown", [["lowpass", 500]], .6); },
    stream() { stream(.18); },
    chimes() { chimes(); auNoise("pink", [["bandpass", 500, .5]], .04); },
  });
  function stream(v) { const s = auNoise("white", [["bandpass", 1800, .6]], v); auLFO(s.gain, .9, v * .3, v); const s2 = auNoise("pink", [["bandpass", 700, .8]], v * .6); auLFO(s2.gain, 1.3, v * .2, v * .6); }
  function chimes() { const notes = [523.3, 587.3, 659.3, 784, 880, 1046.5]; every(1700, () => { if (Math.random() < .55) { const n = notes[Math.random() * notes.length | 0]; auChirp(n, n, R(1.6, 2.6), .045); } }); }
  function pad(freqs, vol) {  // slow evolving chord
    const c = AU.ctx; freqs.forEach((f, i) => { const o = c.createOscillator(), g = c.createGain(); o.type = i % 2 ? "triangle" : "sine"; o.frequency.value = f; o.detune.value = R(-6, 6);
      g.gain.value = vol; o.connect(g); g.connect(AU.master); o.start(); AU.nodes.push(o); auLFO(g.gain, .03 + i * .011, vol * .8, vol); });
  }
  window.SOUND_CHOICES = [["", "Match the scene"], ["rain", "Rain"], ["storm", "Thunderstorm"], ["fireplace", "Crackling fire"], ["ocean", "Ocean waves"],
    ["forest", "Forest birds"], ["night", "Night crickets"], ["meadow", "Spring meadow"], ["snow", "Winter wind"], ["cafe", "Café"], ["city", "City hum"],
    ["underwater", "Underwater"], ["stream", "Babbling stream"], ["chimes", "Wind chimes"], ["sakura", "Garden (chimes + stream)"], ["aurora", "Calm pad"],
    ["space", "Deep space drone"], ["dunes", "Desert wind"], ["whitenoise", "White noise"], ["brownnoise", "Brown noise"]];
})();
