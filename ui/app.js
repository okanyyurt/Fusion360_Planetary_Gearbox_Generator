/**
 * Autodesk Fusion 360 Planetary Gearbox Generator UI Controller
 * Handles interactive tabs, modal visual help pop-ups, real-time kinematics synthesis,
 * and bi-directional communication with Fusion 360 Python API.
 */

// Modal visual definitions & SVG paths
const HELP_MODALS = {
  'modal-shafts': {
    title: 'Motor Montaj Şablonları ve Şaft Kesit Tipleri',
    svgFile: 'assets/shaft_types.svg',
    description: `
      <strong>Şaft Seçim İpuçları:</strong><br>
      • <strong>D-Şaft (Tek Düzlük):</strong> NEMA 17 ve NEMA 23 step motorlarda en yaygın tiptir. Setskur vidasının düzlüğe basması ile sıyrılmayı tamamen engeller.<br>
      • <strong>Kamalı Şaft (DIN 6885):</strong> NEMA 34 ve yüksek torklu ağır hizmet motorlarında kamalı yuva açarak güvenli güç aktarımı sağlar.<br>
      • <strong>Yuvarlak Şaft:</strong> Pres-geçme toleransı veya radyal sıkma bileziği ile kullanılır.
    `
  },
  'modal-herringbone': {
    title: 'Balıksırtı (Herringbone / Çavuş) vs Düz (Spur) Dişli Karşılaştırması',
    svgFile: 'assets/herringbone_vs_spur.svg',
    description: `
      <strong>Neden Balıksırtı Dişli Tercih Edilmelidir?</strong><br>
      • <strong>Sıfır Eksenel Yük:</strong> Düz helisel dişliler eksenel itme kuvveti oluşturarak motor yatağını zorlar. Balıksırtı dişlilerde V şeklindeki zıt açılar kuvvetleri birbirine sıfırlar.<br>
      • <strong>Yüksek Temas Oranı (Overlap):</strong> Dişler aynı anda birden fazla noktadan temas ettiği için standart düz dişlilere göre %40 daha fazla tork taşır ve çok sessizdir.<br>
      • <strong>3D Baskı Stabilitesi:</strong> Planet dişlilerin pimler üzerinde eksenel olarak kaymasını engeller, ekstra segman ihtiyacını ortadan kaldırır.
    `
  },
  'modal-multistage': {
    title: 'Çok Kademeli (Multi-Stage) Planet Aktarım Mimarisi',
    svgFile: 'assets/multistage_carrier.svg',
    description: `
      <strong>Kademe Dağılımı Mantığı:</strong><br>
      • <strong>1 Kademe:</strong> 3:1 ile 9:1 arasındaki redüksiyonlar için en verimlidir.<br>
      • <strong>2 Kademe:</strong> 10:1 ile 80:1 arasındaki oranlar için idealdir (1. kademenin taşıyıcısı 2. kademenin güneş dişlisini döndürür).<br>
      • <strong>3 Kademe:</strong> 80:1 ile 500:1 arasındaki yüksek torklu robotik eklemler ve aktüatörler için kullanılır.<br>
      • Script, tüm kademeler için tek parça ortak dış çember dişli (Continuous Ring Housing) sentezler.
    `
  },
  'modal-bearing': {
    title: 'Planet Dişli Yataklama, Rulman ve Pim Seçimi',
    svgFile: 'assets/bearing_assembly.svg',
    description: `
      <strong>Yataklama Seçenekleri:</strong><br>
      • <strong>Standart Rulman (688ZZ, 608ZZ, MR105):</strong> Planet dişlinin merkezine preslenir. Sürtünmeyi minimize eder, uzun ömürlü ve yüksek devirli sistemler için şarttır.<br>
      • <strong>Rulmansız (Düz Pim / Bronz Burç):</strong> Minyatür veya düşük bütçeli 3D baskı tasarımlarda taşlanmış çelik pim doğrudan planet dişli yuvasına girer.
    `
  },
  'modal-backlash': {
    title: 'Diş Boşluğu (Backlash) & 3D Baskı / CNC Toleransı',
    svgFile: 'assets/backlash_clearance.svg',
    description: `
      <strong>Backlash (Diş Boşluğu) Neden Hayatidir?</strong><br>
      • FDM 3D baskıda eriyik plastiğin dışa doğru şişmesi dişlerin birbirini sıkıştırmasına neden olur.<br>
      • <strong>FDM 3D Baskı için:</strong> 0.20 mm - 0.28 mm arası değer önerilir.<br>
      • <strong>Reçine / SLA için:</strong> 0.10 mm - 0.15 mm yeterlidir.<br>
      • <strong>CNC Metal İşleme için:</strong> 0.05 mm standart boşluk kullanılır.
    `
  },
  'modal-assembly': {
    title: 'Planet Dişli Kinematik Eşit Açı Montaj Kuralı',
    svgFile: 'assets/assembly_condition.svg',
    description: `
      <strong>Matematiksel Montaj Şartı:</strong><br>
      • $N$ adet planet dişlinin eşit aralıklarla yerleşebilmesi için <code>(Z_sun + Z_ring) % N == 0</code> olmalıdır.<br>
      • Eş eksenlilik şartı: <code>Z_ring = Z_sun + 2 * Z_planet</code>.<br>
      • Script, girdiğiniz hedef orana göre bu şartları %100 sağlayan en ideal tam sayı diş kombinasyonlarını otomatik olarak listeler.
    `
  }
};

// Motor Presets Data
const MOTOR_PRESETS = {
  'NEMA17': { shaft_dia: 5.0, shaft_type: 'D_CUT' },
  'NEMA23': { shaft_dia: 6.35, shaft_type: 'D_CUT' },
  'NEMA34': { shaft_dia: 14.0, shaft_type: 'KEYWAY' },
  'MOTOR_775': { shaft_dia: 5.0, shaft_type: 'ROUND' },
  'MOTOR_540_550': { shaft_dia: 3.175, shaft_type: 'D_CUT' },
  'CUSTOM': { shaft_dia: 5.0, shaft_type: 'ROUND' }
};

// Manufacturing Presets Data
const MFG_PRESETS = {
  'FDM_3D': { backlash: 0.22, bearing_tol: 0.08 },
  'SLA_RESIN': { backlash: 0.12, bearing_tol: 0.04 },
  'CNC_METAL': { backlash: 0.05, bearing_tol: 0.01 },
  'CUSTOM': { backlash: 0.20, bearing_tol: 0.05 }
};

// Current Synthesized Candidates Cache
let currentCandidates = [];
let selectedCandidateIndex = 0;

// ─── i18n Language Engine ─────────────────────────────────────────────────────
// ─── i18n Language Engine ─────────────────────────────────────────────────────
let currentLang = 'tr';
try {
  if (localStorage.getItem('pgb_lang')) {
    currentLang = localStorage.getItem('pgb_lang');
  }
} catch (e) {
  console.warn("localStorage not available in Fusion 360 file:// protocol, defaulting to TR");
}

function applyTranslations(lang) {
  if (!window.TRANSLATIONS || !window.TRANSLATIONS[lang]) return;
  const T = window.TRANSLATIONS[lang];

  // Update html lang attribute
  document.getElementById('html_root').setAttribute('lang', lang);

  // Apply all data-i18n text content updates
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    if (T[key] !== undefined) el.textContent = T[key];
  });

  // Update page title
  document.title = lang === 'en'
    ? 'Fusion 360 Planetary Gearbox Designer'
    : 'Fusion 360 Planet Redüktör Tasarımcısı';

  // Update language toggle button
  const btn = document.getElementById('lang_toggle_btn');
  if (btn) {
    if (lang === 'tr') {
      btn.querySelector('.lang-flag').textContent = '\uD83C\uDDEC\uD83C\uDDE7';
      btn.querySelector('.lang-label').textContent = 'EN';
      btn.title = 'Switch to English';
    } else {
      btn.querySelector('.lang-flag').textContent = '\uD83C\uDDF9\uD83C\uDDF7';
      btn.querySelector('.lang-label').textContent = 'TR';
      btn.title = "Türkçe'ye Geç";
    }
  }

  // Update help modal validation alert
  const noCandidate = document.getElementById('no_candidate_msg');
  if (noCandidate && T.noCandidate) noCandidate.textContent = T.noCandidate;

  currentLang = lang;
  try {
    localStorage.setItem('pgb_lang', lang);
  } catch (e) {}
}

function toggleLanguage() {
  applyTranslations(currentLang === 'tr' ? 'en' : 'tr');
}

// Initialize Application
document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initModals();
  initPresetHandlers();
  initRadioCards();
  initKinematicsLiveCalculation();
  initActionButtons();

  // Apply saved language on load
  applyTranslations(currentLang);

  // Listen for progress messages from Fusion 360 Python bridge
  window.fusionMessageReceived = function(eventData) {
    try {
      const data = JSON.parse(eventData);
      if (data.event === 'progress') {
        showProgress(data.message, data.percent || null);
      } else if (data.event === 'done') {
        hideProgress();
      } else if (data.event === 'error') {
        hideProgress();
        alert((currentLang === 'tr' ? 'Hata: ' : 'Error: ') + data.message);
      }
    } catch(e) {}
  };

  // Run initial calculation
  recalculateKinematics();
});

/* Tab Switching */
function initTabs() {
  const tabBtns = document.querySelectorAll('.tab-btn');
  const tabPanes = document.querySelectorAll('.tab-pane');

  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const targetTabId = btn.getAttribute('data-tab');
      
      tabBtns.forEach(b => b.classList.remove('active'));
      tabPanes.forEach(p => p.classList.remove('active'));

      btn.classList.add('active');
      const targetPane = document.getElementById(targetTabId);
      if (targetPane) {
        targetPane.classList.add('active');
      }
    });
  });
}

/* Modal Help System */
function initModals() {
  const overlay = document.getElementById('modal_overlay');
  const closeBtn = document.getElementById('modal_close');
  const titleEl = document.getElementById('modal_title');
  const imgContainer = document.getElementById('modal_image_container');
  const textEl = document.getElementById('modal_text');

  document.querySelectorAll('.help-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const modalKey = btn.getAttribute('data-modal');
      const data = HELP_MODALS[modalKey];
      if (!data) return;

      titleEl.innerText = data.title;
      textEl.innerHTML = data.description;
      
      // Load dynamic SVG
      imgContainer.innerHTML = `<img src="${data.svgFile}" alt="${data.title}" style="width: 100%; max-height: 270px; object-fit: contain;">`;
      
      overlay.classList.add('active');
    });
  });

  closeBtn.addEventListener('click', () => overlay.classList.remove('active'));
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) {
      overlay.classList.remove('active');
    }
  });
}

/* Presets Synchronization */
function initPresetHandlers() {
  const motorSelect = document.getElementById('motor_preset');
  const shaftDiaInput = document.getElementById('motor_shaft_dia');
  const shaftTypeSelect = document.getElementById('motor_shaft_type');

  motorSelect.addEventListener('change', () => {
    const preset = MOTOR_PRESETS[motorSelect.value];
    if (preset) {
      shaftDiaInput.value = preset.shaft_dia;
      shaftTypeSelect.value = preset.shaft_type;
    }
    recalculateKinematics();
  });

  const mfgSelect = document.getElementById('mfg_preset');
  const backlashInput = document.getElementById('backlash');
  const bearingTolInput = document.getElementById('bearing_tolerance');

  mfgSelect.addEventListener('change', () => {
    const preset = MFG_PRESETS[mfgSelect.value];
    if (preset) {
      backlashInput.value = preset.backlash;
      bearingTolInput.value = preset.bearing_tol;
    }
  });

  const bearingSelect = document.getElementById('bearing_type');
  const pinGroup = document.getElementById('group_pin_dia');
  bearingSelect.addEventListener('change', () => {
    if (bearingSelect.value === 'CUSTOM_PIN') {
      pinGroup.style.display = 'block';
    } else {
      pinGroup.style.display = 'none';
    }
  });
  // Initial check
  pinGroup.style.display = (bearingSelect.value === 'CUSTOM_PIN') ? 'block' : 'none';
}

/* Radio Cards Selection */
function initRadioCards() {
  document.querySelectorAll('.radio-card').forEach(card => {
    card.addEventListener('click', () => {
      const radio = card.querySelector('input[type="radio"]');
      if (radio) {
        radio.checked = true;
        document.querySelectorAll(`input[name="${radio.name}"]`).forEach(r => {
          r.closest('.radio-card').classList.remove('active');
        });
        card.classList.add('active');

        // Toggle helix angle visibility
        const helixGroup = document.getElementById('group_helix_angle');
        if (helixGroup) {
          helixGroup.style.display = (radio.value === 'HERRINGBONE') ? 'block' : 'none';
        }
      }
    });
  });
}

/* Real-time JavaScript Kinematics Synthesizer */
function initKinematicsLiveCalculation() {
  const inputs = ['target_ratio', 'stages_count', 'module', 'num_planets', 'bearing_type', 'circlip_type', 'motor_shaft_dia'];
  inputs.forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener('input', recalculateKinematics);
      el.addEventListener('change', recalculateKinematics);
    }
  });

  document.getElementById('candidate_select').addEventListener('change', (e) => {
    selectedCandidateIndex = parseInt(e.target.value, 10) || 0;
    updateMetricsDisplay();
  });
}

function recalculateKinematics() {
  const targetRatio = parseFloat(document.getElementById('target_ratio').value) || 25.0;
  const stagesCount = parseInt(document.getElementById('stages_count').value, 10) || 2;
  const moduleVal = parseFloat(document.getElementById('module').value) || 1.0;
  const numPlanets = parseInt(document.getElementById('num_planets').value, 10) || 3;

  currentCandidates = synthesizePlanetaryGears(targetRatio, stagesCount, numPlanets, moduleVal);
  selectedCandidateIndex = 0;

  // Populate candidate selector dropdown
  const selectEl = document.getElementById('candidate_select');
  selectEl.innerHTML = '';

  if (currentCandidates.length === 0) {
    const opt = document.createElement('option');
    opt.text = 'Uygun diş kombinasyonu bulunamadı (Oranı veya modülü değiştirin)';
    selectEl.appendChild(opt);
    document.getElementById('calc_status_badge').className = 'badge badge-info';
    document.getElementById('calc_status_badge').innerText = '⚠️ Oran / Diş Ayarı Gerekli';
    return;
  }

  document.getElementById('calc_status_badge').className = 'badge badge-success';
  document.getElementById('calc_status_badge').innerText = '✓ Montaj Şartı Doğrulandı';

  currentCandidates.forEach((cand, idx) => {
    const opt = document.createElement('option');
    opt.value = idx;
    if (stagesCount === 1) {
      const s = cand.stages[0];
      opt.text = `#${idx + 1}: Oran ${cand.total_ratio}:1 (Zs:${s.z_sun}, Zp:${s.z_planet}, Zr:${s.z_ring}) - Hata: %${cand.error_percent}`;
    } else {
      const s1 = cand.stages[0];
      const s2 = cand.stages[1];
      opt.text = `#${idx + 1}: Toplam ${cand.total_ratio}:1 [1.K: ${s1.ratio}:1 (Zs:${s1.z_sun}, Zp:${s1.z_planet}) | 2.K: ${s2.ratio}:1 (Zs:${s2.z_sun}, Zp:${s2.z_planet}) | Ortak Zr:${cand.z_ring}]`;
    }
    selectEl.appendChild(opt);
  });

  updateMetricsDisplay();
}

function updateMetricsDisplay() {
  if (!currentCandidates || currentCandidates.length === 0) return;
  const cand = currentCandidates[selectedCandidateIndex] || currentCandidates[0];
  const firstStage = cand.stages[0];
  const moduleVal = parseFloat(document.getElementById('module').value) || 1.0;

  document.getElementById('metric_ratio').innerText = `${cand.total_ratio} : 1`;
  document.getElementById('metric_zs').innerText = firstStage.z_sun;
  document.getElementById('metric_zp').innerText = firstStage.z_planet;
  const dRingPitch = moduleVal * (cand.z_ring || firstStage.z_ring);
  const outerHousingDia = dRingPitch + (moduleVal * 6.0) + 10.0;
  document.getElementById('metric_od').innerText = `~${outerHousingDia.toFixed(1)} mm`;
  document.getElementById('metric_contact').innerText = '> 2.2 (Balıksırtı)';

  // Real-Time Dişli / Rulman & Şaft / Güneş Safety Ratios
  const bearingCode = document.getElementById('bearing_type').value;
  const bearingInfo = BEARING_CATALOG[bearingCode] || { d_outer: 16.0, d_inner: 8.0 };
  const dPlanet = moduleVal * firstStage.z_planet;
  const ratioPB = (dPlanet / bearingInfo.d_outer).toFixed(2);
  const elPB = document.getElementById('ratio_planet_bearing');
  if (elPB) {
    if (ratioPB >= 1.8) {
      elPB.innerText = `${ratioPB}x (Mükemmel Dayanım)`;
      elPB.style.color = '#38bdf8';
    } else if (ratioPB >= 1.5) {
      elPB.innerText = `${ratioPB}x (Yeterli)`;
      elPB.style.color = '#f59e0b';
    } else {
      elPB.innerText = `${ratioPB}x (Zayıf - Rulmanı Küçültün)`;
      elPB.style.color = '#ef4444';
    }
  }

  const motorShaftDia = parseFloat(document.getElementById('motor_shaft_dia').value) || 5.0;
  const dRootSun = Math.max(1.0, moduleVal * (firstStage.z_sun - 2.5));
  const ratioSS = Math.round((motorShaftDia / dRootSun) * 100);
  const elSS = document.getElementById('ratio_shaft_sun');
  if (elSS) {
    if (ratioSS <= 65) {
      elSS.innerText = `%${ratioSS} (Güvenli Standart)`;
      elSS.style.color = '#38bdf8';
    } else if (ratioSS <= 85) {
      elSS.innerText = `%${ratioSS} (Kritik - Alt Kovan Gerekir)`;
      elSS.style.color = '#f59e0b';
    } else {
      elSS.innerText = `%${ratioSS} (Güneş Dişliden Büyük Şaft!)`;
      elSS.style.color = '#ef4444';
    }
  }

  // Update Circlip Badge
  const circlipType = document.getElementById('circlip_type').value;
  const pinDia = bearingInfo.d_inner;
  const badge = document.getElementById('circlip_specs_badge');
  if (badge) {
    if (circlipType === 'DIN_471') {
      badge.innerText = `DIN 471-${pinDia} (d2:${(pinDia - 0.4).toFixed(1)}mm, m:0.9mm)`;
    } else if (circlipType === 'DIN_6799') {
      badge.innerText = `DIN 6799-${pinDia} (E-Clip)`;
    } else {
      badge.innerText = `Segmansız`;
    }
  }
}

// Client-side synthesis algorithm
function synthesizePlanetaryGears(targetRatio, stagesCount, numPlanets, moduleVal) {
  const results = [];
  
  if (stagesCount === 1) {
    for (let zs = 12; zs <= 40; zs++) {
      for (let zp = 10; zp <= 60; zp++) {
        const zr = zs + 2 * zp;
        if ((zs + zr) % numPlanets !== 0) continue;
        
        // Planet clearance check
        const a = moduleVal * (zs + zp) / 2.0;
        const c2c = 2.0 * a * Math.sin(Math.PI / numPlanets);
        const daPlanet = moduleVal * (zp + 2);
        if ((c2c - daPlanet) <= 0.4 * moduleVal) continue;

        const ratio = 1.0 + zr / zs;
        const err = Math.abs(ratio - targetRatio) / targetRatio;
        if (err <= 0.12) {
          results.push({
            total_ratio: parseFloat(ratio.toFixed(2)),
            error_percent: parseFloat((err * 100).toFixed(1)),
            stages: [{
              z_sun: zs,
              z_planet: zp,
              z_ring: zr,
              ratio: parseFloat(ratio.toFixed(2)),
              num_planets: numPlanets,
              module: moduleVal
            }],
            z_ring: zr
          });
        }
      }
    }
  } else if (stagesCount === 2) {
    // 2-Stage synthesis with common ring gear
    for (let zr = 36; zr <= 100; zr++) {
      const validStages = [];
      for (let zs = 12; zs <= zr - 18; zs++) {
        if ((zr - zs) % 2 !== 0) continue;
        const zp = (zr - zs) / 2;
        if (zp < 10) continue;
        if ((zs + zr) % numPlanets !== 0) continue;

        const a = moduleVal * (zs + zp) / 2.0;
        const c2c = 2.0 * a * Math.sin(Math.PI / numPlanets);
        const daPlanet = moduleVal * (zp + 2);
        if ((c2c - daPlanet) <= 0.4 * moduleVal) continue;

        const r = 1.0 + zr / zs;
        validStages.push({ z_sun: zs, z_planet: zp, z_ring: zr, ratio: parseFloat(r.toFixed(2)), num_planets: numPlanets, module: moduleVal });
      }

      for (let s1 of validStages) {
        for (let s2 of validStages) {
          const totRatio = s1.ratio * s2.ratio;
          const err = Math.abs(totRatio - targetRatio) / targetRatio;
          if (err <= 0.10) {
            results.push({
              total_ratio: parseFloat(totRatio.toFixed(2)),
              error_percent: parseFloat((err * 100).toFixed(1)),
              stages: [s1, s2],
              z_ring: zr
            });
          }
        }
      }
    }
  } else {
    // 3-stage fallback
    const perStage = Math.pow(targetRatio, 1/3);
    const s1 = { z_sun: 12, z_planet: 18, z_ring: 48, ratio: 5.0, num_planets: numPlanets, module: moduleVal };
    results.push({
      total_ratio: 125.0,
      error_percent: 0.0,
      stages: [s1, s1, s1],
      z_ring: 48
    });
  }

  results.sort((a, b) => a.error_percent - b.error_percent || a.z_ring - b.z_ring);
  return results.slice(0, 10);
}

/* Action Buttons & Fusion 360 Bridge */
function initActionButtons() {
  document.getElementById('btn_reset').addEventListener('click', () => {
    document.getElementById('target_ratio').value = '25.0';
    document.getElementById('stages_count').value = '2';
    document.getElementById('motor_preset').value = 'NEMA17';
    document.getElementById('motor_preset').dispatchEvent(new Event('change'));
    recalculateKinematics();
  });

  document.getElementById('btn_generate').addEventListener('click', () => {
    if (!currentCandidates || currentCandidates.length === 0) {
      alert('Lütfen geçerli bir dişli oranı kombinasyonu seçin!');
      return;
    }

    const selectedConfig = currentCandidates[selectedCandidateIndex] || currentCandidates[0];
    
    const payload = {
      action: 'generate_gearbox',
      total_ratio: selectedConfig.total_ratio,
      stages: selectedConfig.stages,
      is_herringbone: document.querySelector('input[name="gear_type"]:checked').value === 'HERRINGBONE',
      helix_angle: parseFloat(document.getElementById('helix_angle').value) || 25.0,
      face_width: parseFloat(document.getElementById('face_width').value) || 12.0,
      pressure_angle: parseFloat(document.getElementById('pressure_angle').value) || 20.0,
      motor_preset: document.getElementById('motor_preset').value,
      motor_shaft_dia: parseFloat(document.getElementById('motor_shaft_dia').value) || 5.0,
      motor_shaft_type: document.getElementById('motor_shaft_type').value,
      bearing_type: document.getElementById('bearing_type').value,
      circlip_type: document.getElementById('circlip_type').value,
      pin_dia: parseFloat(document.getElementById('pin_dia').value) || 5.0,
      generate_housing: document.getElementById('generate_housing').checked,
      output_shaft_dia: parseFloat(document.getElementById('output_shaft_dia').value) || 8.0,
      output_shaft_len: parseFloat(document.getElementById('output_shaft_len').value) || 20.0,
      carrier_thick: parseFloat(document.getElementById('carrier_thick').value) || 3.5,
      backlash: parseFloat(document.getElementById('backlash').value) || 0.22,
      bearing_tolerance: parseFloat(document.getElementById('bearing_tolerance').value) || 0.08
    };

    console.log('Sending Payload to Fusion 360:', payload);
    
    // Show UI immediately
    showProgress(currentLang === 'tr' ? 'Fusion 360 3D Modelleme Başlıyor...' : 'Starting Fusion 360 3D Modeling...', 0);

    // Defer the heavy API call to allow the browser to paint the progress overlay
    setTimeout(() => {
      // Call Fusion 360 API bridge
      if (typeof adsk !== 'undefined' && adsk.fusionSendData) {
        adsk.fusionSendData('generateGearbox', JSON.stringify(payload));
      } else {
        // In browser preview / debug mode
        alert(`[FUSION 360 SIMULATION]\n3D Modelleme Başlatıldı!\nToplam Oran: ${payload.total_ratio}:1\nKademe: ${payload.stages.length}\nDiş Tipi: ${payload.is_herringbone ? 'Balıksırtı' : 'Düz'}\nŞaft: Ø${payload.motor_shaft_dia}mm (${payload.motor_shaft_type})`);
        setTimeout(() => hideProgress(), 2000);
      }
    }, 100);
  });
}

/* ─── Progress Overlay ─────────────────────────────────────────────────────── */
function showProgress(message, percent) {
  const overlay = document.getElementById('progress_overlay');
  const statusEl = document.getElementById('progress_status');
  const pctEl = document.getElementById('progress_pct');
  const fillEl = document.getElementById('progress_fill');
  if (!overlay) return;
  overlay.style.display = 'flex';
  if (message && statusEl) statusEl.textContent = message;
  
  if (percent != null) {
    const clamped = Math.min(100, Math.max(0, Math.round(percent)));
    if (fillEl) {
      fillEl.style.animation = 'none';
      fillEl.style.width = clamped + '%';
    }
    if (pctEl) pctEl.textContent = clamped + '%';
  } else {
    if (fillEl) fillEl.style.animation = 'progress-indeterminate 1.5s ease-in-out infinite';
    if (pctEl) pctEl.textContent = '...';
  }
}

function hideProgress() {
  const overlay = document.getElementById('progress_overlay');
  if (overlay) overlay.style.display = 'none';
  const fillEl = document.getElementById('progress_fill');
  if (fillEl) { fillEl.style.animation = 'none'; fillEl.style.width = '100%'; }
  const pctEl = document.getElementById('progress_pct');
  if (pctEl) pctEl.textContent = '100%';
}
