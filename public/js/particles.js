/* ============================================
   PARTICLES SYSTEM — Star of David, $, Coins, Menorah
   Custom Canvas API implementation
   ============================================ */

(function () {
  const canvas = document.getElementById('particles-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');

  let width, height;
  let particles = [];
  let mouseX = innerWidth / 2;
  let mouseY = innerHeight / 2;
  const motionQuery=matchMedia('(prefers-reduced-motion: reduce)');
  let animationFrame=0;
  const isMobile = window.innerWidth < 768;
  const MAX_PARTICLES = isMobile ? 30 : 65;

  function resize() {
    width = canvas.width = window.innerWidth;
    height = canvas.height = window.innerHeight;
  }

  resize();
  window.addEventListener('resize', resize);

  document.addEventListener('mousemove', function (e) {
    mouseX = e.clientX;
    mouseY = e.clientY;
  });

  // Particle types with weights
  const TYPES = [
    { type: 'star', weight: 50 },
    { type: 'dollar', weight: 20 },
    { type: 'coin', weight: 20 },
    { type: 'menorah', weight: 3 },
    { type: 'line', weight: 7 }
  ];

  function pickType() {
    const total = TYPES.reduce((s, t) => s + t.weight, 0);
    let r = Math.random() * total;
    for (const t of TYPES) {
      r -= t.weight;
      if (r <= 0) return t.type;
    }
    return 'star';
  }

  function createParticle() {
    const type = pickType();
    return {
      x: Math.random() * width,
      y: height + 20,
      size: 6 + Math.random() * 14,
      speedY: 0.2 + Math.random() * 0.5,
      speedX: 0,
      sinOffset: Math.random() * Math.PI * 2,
      sinSpeed: 0.005 + Math.random() * 0.01,
      sinAmp: 15 + Math.random() * 25,
      opacity: 0.05 + Math.random() * 0.15,
      type: type,
      rotation: Math.random() * Math.PI * 2,
      rotSpeed: (Math.random() - 0.5) * 0.005
    };
  }

  // Initialize particles
  for (let i = 0; i < MAX_PARTICLES; i++) {
    const p = createParticle();
    p.y = Math.random() * height;
    particles.push(p);
  }

  // Draw Star of David
  function drawStar(x, y, size, rotation) {
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(rotation);
    const r = size / 2;
    // Triangle 1 (pointing up)
    ctx.beginPath();
    for (let i = 0; i < 3; i++) {
      const angle = (i * 2 * Math.PI) / 3 - Math.PI / 2;
      const px = Math.cos(angle) * r;
      const py = Math.sin(angle) * r;
      if (i === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    }
    ctx.closePath();
    ctx.stroke();
    // Triangle 2 (pointing down)
    ctx.beginPath();
    for (let i = 0; i < 3; i++) {
      const angle = (i * 2 * Math.PI) / 3 + Math.PI / 2;
      const px = Math.cos(angle) * r;
      const py = Math.sin(angle) * r;
      if (i === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    }
    ctx.closePath();
    ctx.stroke();
    ctx.restore();
  }

  // Draw Dollar Sign
  function drawDollar(x, y, size) {
    ctx.font = `${size}px Inter, sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('$', x, y);
  }

  // Draw Coin (circle)
  function drawCoin(x, y, size) {
    ctx.beginPath();
    ctx.arc(x, y, size / 3, 0, Math.PI * 2);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(x, y, size / 5, 0, Math.PI * 2);
    ctx.stroke();
  }

  // Draw Menorah (simplified)
  function drawMenorah(x, y, size) {
    ctx.save();
    ctx.translate(x, y);
    const s = size / 20;
    // Base
    ctx.beginPath();
    ctx.moveTo(-6 * s, 8 * s);
    ctx.lineTo(6 * s, 8 * s);
    ctx.stroke();
    // Center stem
    ctx.beginPath();
    ctx.moveTo(0, 8 * s);
    ctx.lineTo(0, -6 * s);
    ctx.stroke();
    // Branches
    const branches = [-4, -2.5, 2.5, 4];
    branches.forEach(bx => {
      ctx.beginPath();
      ctx.moveTo(0, 2 * s);
      ctx.quadraticCurveTo(bx * s * 0.5, -2 * s, bx * s, -6 * s);
      ctx.stroke();
    });
    // Flames
    const flameX = [0, -4 * s, -2.5 * s, 2.5 * s, 4 * s];
    flameX.forEach(fx => {
      ctx.beginPath();
      ctx.arc(fx, -7 * s, 1.2 * s, 0, Math.PI * 2);
      ctx.fill();
    });
    ctx.restore();
  }

  function draw() {
    if(document.hidden||motionQuery.matches){animationFrame=0;return;}
    ctx.clearRect(0, 0, width, height);

    for (let i = particles.length - 1; i >= 0; i--) {
      const p = particles[i];

      // Move
      p.y -= p.speedY;
      p.sinOffset += p.sinSpeed;
      const baseX = p.x + Math.sin(p.sinOffset) * p.sinAmp;
      p.rotation += p.rotSpeed;

      // Parallax from mouse
      const dx = (mouseX - width / 2) * 0.008 * (p.size / 20);
      const dy = (mouseY - height / 2) * 0.005 * (p.size / 20);
      const drawX = baseX + dx;
      const drawY = p.y + dy;

      // Remove if off screen
      if (p.y < -30) {
        particles.splice(i, 1);
        continue;
      }

      // Draw particle
      const goldColor = `rgba(201, 168, 76, ${p.opacity})`;
      ctx.strokeStyle = goldColor;
      ctx.fillStyle = goldColor;
      ctx.lineWidth = 0.8;

      switch (p.type) {
        case 'star':
          drawStar(drawX, drawY, p.size, p.rotation);
          break;
        case 'dollar':
          drawDollar(drawX, drawY, p.size);
          break;
        case 'coin':
          drawCoin(drawX, drawY, p.size);
          break;
        case 'menorah':
          drawMenorah(drawX, drawY, p.size * 1.5);
          break;
        case 'line':
          // Draw connecting line to nearest particle
          let nearest = null;
          let nearestDist = 150;
          for (let j = 0; j < particles.length; j++) {
            if (j === i) continue;
            const other = particles[j];
            const dist = Math.hypot(drawX - other.x, drawY - other.y);
            if (dist < nearestDist) {
              nearest = other;
              nearestDist = dist;
            }
          }
          if (nearest) {
            const lineOpacity = p.opacity * (1 - nearestDist / 150);
            ctx.strokeStyle = `rgba(201, 168, 76, ${lineOpacity})`;
            ctx.beginPath();
            ctx.moveTo(drawX, drawY);
            ctx.lineTo(nearest.x, nearest.y);
            ctx.stroke();
          }
          // Also draw a small dot
          ctx.fillStyle = goldColor;
          ctx.beginPath();
          ctx.arc(drawX, drawY, 2, 0, Math.PI * 2);
          ctx.fill();
          break;
      }
    }

    // Spawn new particles
    while (particles.length < MAX_PARTICLES) {
      particles.push(createParticle());
    }

    animationFrame=requestAnimationFrame(draw);
  }

  function resume(){if(animationFrame)cancelAnimationFrame(animationFrame);animationFrame=0;if(!motionQuery.matches&&!document.hidden)draw();else ctx.clearRect(0,0,width,height);}
  document.addEventListener('visibilitychange',resume);
  motionQuery.addEventListener('change',resume);
  resume();
})();
