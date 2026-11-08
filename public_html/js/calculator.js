/**
 * Planetary Gearbox Generator - Interactive Kinematics & Animated Visualizer
 * Domain: pgg.gryntech.net
 */

(function () {
  const arrangementSelect = document.getElementById('calcArrangement');
  const moduleInput = document.getElementById('calcModule');
  const sunInput = document.getElementById('calcSun');
  const planetInput = document.getElementById('calcPlanet');
  const countInput = document.getElementById('calcCount');
  const rpmInput = document.getElementById('calcRpm');
  const torqueInput = document.getElementById('calcTorque');

  const statusCard = document.getElementById('calcStatusCard');
  const statusIcon = document.getElementById('statusIcon');
  const statusTitle = document.getElementById('statusTitle');
  const statusDesc = document.getElementById('statusDesc');

  const valRingTeeth = document.getElementById('valRingTeeth');
  const valRatio = document.getElementById('valRatio');
  const valOutRpm = document.getElementById('valOutRpm');
  const valOutTorque = document.getElementById('valOutTorque');
  const valPitchSun = document.getElementById('valPitchSun');
  const valPitchPlanet = document.getElementById('valPitchPlanet');
  const valPitchRing = document.getElementById('valPitchRing');
  const valClearance = document.getElementById('valClearance');

  const canvas = document.getElementById('gearCanvas');
  const ctx = canvas ? canvas.getContext('2d') : null;

  let animAngle = 0;
  let lastTimestamp = 0;

  function updateCalculations() {
    if (!arrangementSelect || !sunInput || !planetInput || !countInput) return;

    const arrangement = arrangementSelect.value;
    const m = parseFloat(moduleInput.value) || 1.5;
    const Zs = parseInt(sunInput.value, 10) || 12;
    const Zp = parseInt(planetInput.value, 10) || 18;
    const N = parseInt(countInput.value, 10) || 3;
    const rpmIn = parseFloat(rpmInput.value) || 1000;
    const torqueIn = parseFloat(torqueInput.value) || 1.0;

    // Coaxial equation: Zr = Zs + 2 * Zp
    const Zr = Zs + 2 * Zp;

    // Assembly condition: (Zs + Zr) % N === 0
    const assemblySum = Zs + Zr;
    const isAssemblyValid = (assemblySum % N === 0);

    // Pitch diameters
    const ds = m * Zs;
    const dp = m * Zp;
    const dr = m * Zr;

    // Center distance
    const a = (ds + dp) / 2;

    // Clearance between adjacent planets
    // Distance between adjacent planet pin centers: 2 * a * sin(pi / N)
    const pinDist = 2 * a * Math.sin(Math.PI / N);
    const planetTipDia = dp + 2 * m; // da = d + 2m
    const planetGap = pinDist - planetTipDia;
    const isClearanceValid = planetGap > 0.4;

    // Ratio calculation based on arrangement
    let ratio = 1.0;
    let eta = 0.97; // efficiency

    if (arrangement === 'standard') {
      ratio = 1.0 + (Zr / Zs);
    } else if (arrangement === 'drum') {
      ratio = (Zs + Zr) / Zr;
    } else if (arrangement === 'speedup') {
      ratio = 1.0 / (1.0 + (Zr / Zs));
    } else if (arrangement === 'wolfrom') {
      // Wolfrom approx ratio for demonstration
      ratio = 45.0;
      eta = 0.85;
    } else if (arrangement === 'cycloid') {
      // Cycloid ratio = pin count - 1
      ratio = 29.0;
      eta = 0.90;
    }

    const rpmOut = Math.abs(rpmIn / ratio);
    const torqueOut = torqueIn * Math.abs(ratio) * eta;

    // Update DOM values
    if (valRingTeeth) valRingTeeth.textContent = Zr;
    if (valRatio) valRatio.textContent = ratio.toFixed(2) + ' : 1';
    if (valOutRpm) valOutRpm.textContent = rpmOut.toFixed(1);
    if (valOutTorque) valOutTorque.textContent = torqueOut.toFixed(1);
    if (valPitchSun) valPitchSun.textContent = 'Ø ' + ds.toFixed(1);
    if (valPitchPlanet) valPitchPlanet.textContent = 'Ø ' + dp.toFixed(1);
    if (valPitchRing) valPitchRing.textContent = 'Ø ' + dr.toFixed(1);
    if (valClearance) {
      valClearance.textContent = planetGap > 0 ? (planetGap.toFixed(2) + ' mm') : 'Çakışma!';
      valClearance.style.color = planetGap > 0 ? '#38bdf8' : '#f43f5e';
    }

    // Status Banner
    const isLangEn = document.documentElement.lang === 'en';

    if (isAssemblyValid && isClearanceValid) {
      statusCard.className = 'calc-status-card valid';
      statusIcon.textContent = '✓';
      statusTitle.textContent = isLangEn ? 'Valid Kinematic Assembly' : 'Montaj Kuralları Doğrulandı';
      statusDesc.textContent = isLangEn 
        ? `(${Zs} + ${Zr}) = ${assemblySum} is divisible by ${N}. Tooth mesh & clearance are geometrically sound.`
        : `(${Zs} + ${Zr}) = ${assemblySum}, ${N} gezegene tam bölünür. Diş kavrama açısı ve boşluk geometrik olarak kusursuz.`;
    } else if (!isAssemblyValid) {
      statusCard.className = 'calc-status-card invalid';
      statusIcon.textContent = '⚠';
      statusTitle.textContent = isLangEn ? 'Assembly Rule Violation' : 'Eşit Açılı Montaj Kuralı İhlali';
      statusDesc.textContent = isLangEn
        ? `(${Zs} + ${Zr}) = ${assemblySum} is not divisible by ${N}. Teeth cannot mesh simultaneously!`
        : `(${Zs} + ${Zr}) = ${assemblySum}, ${N} gezegene tam bölünmüyor! Gezegen dişliler aynı anda kavrayamaz.`;
    } else {
      statusCard.className = 'calc-status-card invalid';
      statusIcon.textContent = '✕';
      statusTitle.textContent = isLangEn ? 'Planets Interference' : 'Planet Dişliler Birbirine Çarpıyor';
      statusDesc.textContent = isLangEn
        ? `Clearance gap is negative (${planetGap.toFixed(2)} mm). Reduce planet teeth or count.`
        : `Planet dişliler arası boşluk negatif (${planetGap.toFixed(2)} mm). Planet sayısını veya diş sayısını düşürün.`;
    }
  }

  // Animation Loop for Gear Visualizer
  function drawGears(timestamp) {
    if (!ctx || !canvas) return;

    if (!lastTimestamp) lastTimestamp = timestamp;
    const delta = (timestamp - lastTimestamp) / 1000;
    lastTimestamp = timestamp;

    const w = canvas.width = canvas.clientWidth * window.devicePixelRatio;
    const h = canvas.height = canvas.clientHeight * window.devicePixelRatio;
    ctx.clearRect(0, 0, w, h);

    const centerX = w / 2;
    const centerY = h / 2;
    const scale = Math.min(w, h) / 180;

    const Zs = parseInt(sunInput?.value, 10) || 12;
    const Zp = parseInt(planetInput?.value, 10) || 18;
    const N = parseInt(countInput?.value, 10) || 3;
    const Zr = Zs + 2 * Zp;

    const arrangement = arrangementSelect ? arrangementSelect.value : 'standard';

    // Speed relationships
    // If standard: Ring stationary.
    // Carrier angular speed = omega_sun / (1 + Zr/Zs)
    // Planet relative rotation speed
    const omegaSun = 1.2; // rad/s
    const ratio = 1.0 + (Zr / Zs);
    const omegaCarrier = omegaSun / ratio;

    animAngle += omegaCarrier * delta;

    // Relative tooth counts
    const rRing = (Zr / 2) * scale * 0.9;
    const rSun = (Zs / 2) * scale * 0.9;
    const rPlanet = (Zp / 2) * scale * 0.9;
    const rCenter = (rSun + rPlanet);

    // 1. Draw Ring Gear (Housing)
    ctx.save();
    ctx.translate(centerX, centerY);

    ctx.beginPath();
    ctx.arc(0, 0, rRing + 12 * scale, 0, Math.PI * 2);
    ctx.strokeStyle = '#1e3357';
    ctx.lineWidth = 14 * scale;
    ctx.stroke();

    ctx.beginPath();
    ctx.arc(0, 0, rRing, 0, Math.PI * 2);
    ctx.strokeStyle = '#38bdf8';
    ctx.lineWidth = 2 * scale;
    ctx.setLineDash([4 * scale, 3 * scale]);
    ctx.stroke();
    ctx.setLineDash([]);

    // 2. Draw Sun Gear (Center)
    ctx.save();
    const sunAngle = animAngle * ratio;
    ctx.rotate(sunAngle);

    ctx.beginPath();
    ctx.arc(0, 0, rSun, 0, Math.PI * 2);
    ctx.fillStyle = '#f59e0b';
    ctx.fill();
    ctx.strokeStyle = '#d97706';
    ctx.lineWidth = 2 * scale;
    ctx.stroke();

    // Sun shaft hole
    ctx.beginPath();
    ctx.arc(0, 0, rSun * 0.4, 0, Math.PI * 2);
    ctx.fillStyle = '#091222';
    ctx.fill();

    // Sun teeth markers
    for (let i = 0; i < Zs; i++) {
      const a = (i * 2 * Math.PI) / Zs;
      ctx.beginPath();
      ctx.moveTo(Math.cos(a) * (rSun - 2 * scale), Math.sin(a) * (rSun - 2 * scale));
      ctx.lineTo(Math.cos(a) * (rSun + 3 * scale), Math.sin(a) * (rSun + 3 * scale));
      ctx.strokeStyle = '#fbbf24';
      ctx.lineWidth = 2 * scale;
      ctx.stroke();
    }
    ctx.restore();

    // 3. Draw Carrier Spider Lines & Planets
    ctx.beginPath();
    for (let i = 0; i < N; i++) {
      const pAngle = animAngle + (i * 2 * Math.PI) / N;
      const px = Math.cos(pAngle) * rCenter;
      const py = Math.sin(pAngle) * rCenter;
      if (i === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    }
    ctx.closePath();
    ctx.strokeStyle = 'rgba(56, 189, 248, 0.3)';
    ctx.lineWidth = 3 * scale;
    ctx.stroke();

    // Draw Planets
    for (let i = 0; i < N; i++) {
      const pAngle = animAngle + (i * 2 * Math.PI) / N;
      const px = Math.cos(pAngle) * rCenter;
      const py = Math.sin(pAngle) * rCenter;

      ctx.save();
      ctx.translate(px, py);

      // Planet self rotation: omega_planet = -omegaCarrier * (Zr / Zp)
      const selfAngle = -(animAngle * (Zr / Zp));
      ctx.rotate(selfAngle);

      ctx.beginPath();
      ctx.arc(0, 0, rPlanet, 0, Math.PI * 2);
      ctx.fillStyle = '#0284c7';
      ctx.fill();
      ctx.strokeStyle = '#38bdf8';
      ctx.lineWidth = 2 * scale;
      ctx.stroke();

      // Planet pin
      ctx.beginPath();
      ctx.arc(0, 0, rPlanet * 0.35, 0, Math.PI * 2);
      ctx.fillStyle = '#070d18';
      ctx.fill();
      ctx.strokeStyle = '#7dd3fc';
      ctx.lineWidth = 1.5 * scale;
      ctx.stroke();

      // Planet teeth markers
      for (let j = 0; j < Zp; j++) {
        const ta = (j * 2 * Math.PI) / Zp;
        ctx.beginPath();
        ctx.moveTo(Math.cos(ta) * (rPlanet - 2 * scale), Math.sin(ta) * (rPlanet - 2 * scale));
        ctx.lineTo(Math.cos(ta) * (rPlanet + 3 * scale), Math.sin(ta) * (rPlanet + 3 * scale));
        ctx.strokeStyle = '#38bdf8';
        ctx.lineWidth = 1.5 * scale;
        ctx.stroke();
      }

      ctx.restore();
    }

    ctx.restore();
    requestAnimationFrame(drawGears);
  }

  // Bind Events
  const inputs = [arrangementSelect, moduleInput, sunInput, planetInput, countInput, rpmInput, torqueInput];
  inputs.forEach(el => {
    if (el) {
      el.addEventListener('input', updateCalculations);
      el.addEventListener('change', updateCalculations);
    }
  });

  // Initial Run
  updateCalculations();
  requestAnimationFrame(drawGears);

  // Expose to window for language change updates
  window.updateGearCalculator = updateCalculations;
})();

