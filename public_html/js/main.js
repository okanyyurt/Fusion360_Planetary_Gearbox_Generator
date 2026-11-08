/**
 * Planetary Gearbox Generator (PGG) - Main JavaScript
 * Domain: pgg.gryntech.net
 */

(function () {
  'use strict';

  // --- 1. Gallery State & View Controller ---
  const galleryState = {
    model: 'std',
    view: 'color'
  };

  const galleryData = {
    std: {
      title_tr: 'Standart Planet Redüktör (Taşıyıcı Çıkışlı)',
      title_en: 'Standard Planetary Gearbox (Carrier Output)',
      desc_tr: 'Sabit çember dişli gövdesi, güneş dişli girişi ve taşıyıcı kafes çıkışı. 3:1 - 10:1 kademe oranı; yüksek torklu robotik mafsallar ve servo sürücüler için ideal.',
      desc_en: 'Fixed outer ring housing, sun input and carrier output. 3:1 to 10:1 ratio per stage; ideal for high-torque robotic joints and servo drives.',
      color: 'images/std_arm_color.png',
      ghost: 'images/std_arm_ghost.png',
      section: 'images/std_arm_section.png'
    },
    wolfrom: {
      title_tr: 'Wolfrom (3K) Diferansiyel Planet',
      title_en: 'Wolfrom (3K) Compound Differential Drive',
      desc_tr: 'Sabit gövde çemberi ile dönen çıkış çemberi arasındaki mikro diş farkıyla tek kademede 30:1\'den 500:1\'e kadar devasa redüksiyon sağlar.',
      desc_en: 'Delivers massive reduction ratios (30:1 to 500:1+) in a single stage via tooth differential between fixed housing ring and rotating output ring.',
      color: 'images/wolfrom_color.png',
      ghost: 'images/wolfrom_ghost.png',
      section: 'images/wolfrom_section.png'
    },
    cycloid: {
      title_tr: 'Sikloidal Redüktör (Sıfır Boşluklu)',
      title_en: 'Precision Cycloidal Drive (Zero-Backlash)',
      desc_tr: 'Eksantrik kam rulmanı, çift sikloid disk ve çevre makaralı pimler. Yüksek şok darbesi dayanımı ve sıfıra yakın histerezis boşluğu.',
      desc_en: 'Eccentric cam bearings, twin cycloidal discs and roller housing pins. Exceptional shock resistance and near-zero backlash for precision robotics.',
      color: 'images/cycloid_color.png',
      ghost: 'images/cycloid_ghost.png',
      section: 'images/cycloid_section.png'
    },
    ring_drum: {
      title_tr: 'Dönen Gövde / Tambur Redüktörü',
      title_en: 'Rotating Housing / Drum Drive',
      desc_tr: 'Sabit taşıyıcı mafsalı ve dışarıdan dönen çember gövde yapısı. AGV / AMR çekiş tekerlekleri, konveyör silindirleri ve vinç tamburları için üretilmiştir.',
      desc_en: 'Fixed carrier shaft and directly rotating outer ring housing. Designed for AGV/AMR motorized wheels, conveyor rollers, and winch drums.',
      color: 'images/ring_drum_color.png',
      ghost: 'images/ring_drum_ghost.png',
      section: 'images/ring_drum_section.png'
    }
  };

  const galleryImg = document.getElementById('galleryImg');
  const galleryTitle = document.getElementById('galleryTitle');
  const galleryDesc = document.getElementById('galleryDesc');
  const modelTabBtns = document.querySelectorAll('.gallery-tab-btn');
  const viewSubtabBtns = document.querySelectorAll('.view-subtab-btn');

  function updateGallery() {
    if (!galleryImg) return;
    const item = galleryData[galleryState.model];
    if (!item) return;

    const isEn = document.documentElement.lang === 'en';

    galleryImg.style.opacity = '0';
    galleryImg.style.transform = 'scale(0.97)';

    setTimeout(() => {
      galleryImg.src = item[galleryState.view] || item.color;
      galleryImg.alt = isEn ? item.title_en : item.title_tr;
      if (galleryTitle) galleryTitle.textContent = isEn ? item.title_en : item.title_tr;
      if (galleryDesc) galleryDesc.textContent = isEn ? item.desc_en : item.desc_tr;
      galleryImg.style.opacity = '1';
      galleryImg.style.transform = 'scale(1)';
    }, 180);
  }

  modelTabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      modelTabBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      galleryState.model = btn.getAttribute('data-model');
      updateGallery();
    });
  });

  viewSubtabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      viewSubtabBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      galleryState.view = btn.getAttribute('data-view');
      updateGallery();
    });
  });

  // --- 2. Installation Tabs ---
  const installTabs = document.querySelectorAll('.install-tab-btn');
  const installPanels = document.querySelectorAll('.install-panel');

  installTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const targetId = tab.getAttribute('data-target');
      installTabs.forEach(t => t.classList.remove('active'));
      installPanels.forEach(p => p.classList.remove('active'));

      tab.classList.add('active');
      const panel = document.getElementById(targetId);
      if (panel) panel.classList.add('active');
    });
  });

  // --- 3. Copy Code Buttons ---
  const copyButtons = document.querySelectorAll('.code-copy-btn');
  copyButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const codeBlock = btn.closest('.code-block');
      const codeText = codeBlock.querySelector('code').innerText;

      navigator.clipboard.writeText(codeText).then(() => {
        const isEn = document.documentElement.lang === 'en';
        const originalText = btn.textContent;
        btn.textContent = isEn ? 'Copied!' : 'Kopyalandı!';
        btn.style.background = '#10b981';
        btn.style.color = '#fff';

        setTimeout(() => {
          btn.textContent = originalText;
          btn.style.background = '';
          btn.style.color = '';
        }, 2000);
      });
    });
  });

  // --- 4. Mobile Menu Navigation ---
  const mobileToggle = document.getElementById('mobileToggle');
  const navLinks = document.getElementById('navLinks');

  if (mobileToggle && navLinks) {
    mobileToggle.addEventListener('click', () => {
      navLinks.classList.toggle('active');
    });
    // Close nav on click
    navLinks.querySelectorAll('a').forEach(link => {
      link.addEventListener('click', () => {
        navLinks.classList.remove('active');
      });
    });
  }

  // --- 5. Bilingual System (TR / EN) ---
  const langToggleBtn = document.getElementById('langToggle');

  const translations = {
    tr: {
      nav_arch: 'Mimariler',
      nav_feat: 'Kabiliyetler',
      nav_gallery: 'CAD Galeri',
      nav_calc: 'Hesaplayıcı',
      nav_standards: 'Mühendislik',
      nav_install: 'Kurulum',
      btn_download: 'Windows İçin İndir',
      btn_github: 'GitHub Reposu',
      btn_calc: 'Hesaplayıcıyı Başlat',
      hero_badge: '🚀 Sürüm 2.9.0 · Tam Bağımsız CAD & Fusion 360 Add-In',
      hero_title_1: 'Parametrik Planet, Wolfrom &',
      hero_title_2: 'Sikloidal Redüktör Tasarımcısı',
      hero_desc: 'Üretime hazır, tam montajlı çok kademeli planet redüktörleri saniyeler içinde tasarlayın. ISO 6336 diş mukavemeti analizi, VDI 2736 plastik kontrolü, dilimleyici hazır 3MF/STEP doğrudan üretim çıktıları ve tek tıkla çalışan bağımsız Windows uygulaması.',
      tag_5arch: '5 Redüktör Mimarisi',
      tag_iso: 'ISO 6336 / VDI 2736',
      tag_3mf: 'Doğrudan 3MF / STEP',
      tag_teeth: 'Balıksırtı V-Twist Dişli',
      tag_ai: 'Gemini AI Asistanı',
      arch_label: 'KİNEMATİK DÜZENLER',
      arch_title: '5 Farklı Planet & Sikloid Mimarisi',
      arch_subtitle: 'Uygulamanızın tork, redüksiyon oranı ve montaj geometrisine tam uyumlu 5 farklı kinematik mekanizma.',
      feat_label: 'MÜHENDİSLİK GÜCÜ',
      feat_title: 'Profesyonel CAD & Hesaplama Yetenekleri',
      feat_subtitle: 'Sadece bir 3D çizici değil; gerçek mühendislik standartları, malzeme analizi ve tolerans yönetimi bir arada.',
      gallery_label: '3 BOYUTLU CAD MODELLERİ',
      gallery_title: 'Üretilmiş Modelleri Keşfedin',
      gallery_subtitle: 'Tam model, saydam gövde (ghost) ve teknik kesit görünümleriyle tüm mekanizmanın iç anatomisini inceleyin.',
      calc_label: 'CANLI DİNAMİK SİMÜLATÖR',
      calc_title: 'Kinematik & Redüksiyon Hesaplayıcı',
      calc_subtitle: 'Diş sayılarını ve modülü girin; eş eksenlilik, montaj kuralları ve planet boşluğunu canlı animasyonla görün.',
      standards_label: 'STANDARTLAR VE ANALİZ',
      standards_title: 'Gerçek Standartlara Dayalı Mukavemet Kontrolleri',
      standards_subtitle: 'Tasarımınız sadece CAD\'de güzel görünmekle kalmaz; gerçek yükler altında kırılmayacak şekilde doğrulanır.',
      install_label: 'HEMEN BAŞLAYIN',
      install_title: 'Hızlı Kurulum ve Çalıştırma',
      install_subtitle: 'İster bağımsız çevrimdışı masaüstü uygulaması olarak, ister doğrudan Fusion 360 eklentisi olarak kullanın.',
      cta_title: 'Gelişmiş Redüktörünüzü Şimdi Tasarlayın',
      cta_desc: 'Tüm planet, Wolfrom ve sikloidal mekanizmaları 100% açık kaynak ve ücretsiz olarak üretin. Windows uygulamasını indirin veya depoya yıldız verin.',
      footer_desc: 'Autodesk Fusion 360 ve bağımsız OpenCascade CAD motoru üzerinde çalışan profesyonel planet redüktör tasarım ve analiz sistemi.'
    },
    en: {
      nav_arch: 'Architectures',
      nav_feat: 'Capabilities',
      nav_gallery: 'CAD Gallery',
      nav_calc: 'Calculator',
      nav_standards: 'Engineering',
      nav_install: 'Install',
      btn_download: 'Download for Windows',
      btn_github: 'GitHub Repo',
      btn_calc: 'Open Calculator',
      hero_badge: '🚀 Version 2.9.0 · Standalone CAD & Fusion 360 Add-In',
      hero_title_1: 'Parametric Planetary, Wolfrom &',
      hero_title_2: 'Cycloidal Gearbox Generator',
      hero_desc: 'Design ready-to-manufacture, multi-stage planetary gearboxes in seconds. Built-in ISO 6336 tooth bending & surface checks, VDI 2736 thermoplastic engineering, direct 3MF/STEP export, and an offline portable Windows application.',
      tag_5arch: '5 Gearbox Architectures',
      tag_iso: 'ISO 6336 / VDI 2736',
      tag_3mf: 'Direct 3MF / STEP',
      tag_teeth: 'Herringbone V-Twist',
      tag_ai: 'Gemini AI Assistant',
      arch_label: 'KINEMATIC CONFIGURATIONS',
      arch_title: '5 Distinct Planetary & Cycloid Architectures',
      arch_subtitle: '5 kinematic configurations engineered to match your torque, gear ratio, and spatial packaging requirements.',
      feat_label: 'ENGINEERING POWER',
      feat_title: 'Professional CAD & Sizing Capabilities',
      feat_subtitle: 'Not just a 3D generator; real engineering standards, stress validation, and manufacturing tolerances combined.',
      gallery_label: '3D CAD MODEL SHOWCASE',
      gallery_title: 'Explore Generated Assemblies',
      gallery_subtitle: 'Inspect the internal anatomy of your gearbox with complete, ghosted see-through, and engineering section views.',
      calc_label: 'LIVE DYNAMIC SIMULATOR',
      calc_title: 'Kinematics & Gear Ratio Calculator',
      calc_subtitle: 'Enter teeth and module; inspect coaxiality, assembly divisibility rules, and planet clearance with live gear rotation.',
      standards_label: 'STANDARDS & VALIDATION',
      standards_title: 'Calculated to Real International Standards',
      standards_subtitle: 'Your design does not merely look good in CAD; it is structurally verified against bending and pitting failure modes.',
      install_label: 'GET STARTED',
      install_title: 'Quick Setup & Getting Started',
      install_subtitle: 'Use it as an offline standalone Windows desktop app, or integrate natively as an Autodesk Fusion 360 Add-In.',
      cta_title: 'Design Your Precision Gearbox Today',
      cta_desc: 'Build planetary, Wolfrom, and cycloidal gear drives with complete 100% open-source freedom. Download the offline app or star the repo.',
      footer_desc: 'Professional planetary gearbox generator and engineering analysis suite powered by Autodesk Fusion 360 and OpenCascade CAD.'
    }
  };

  function setLanguage(lang) {
    document.documentElement.lang = lang;
    localStorage.setItem('pgg_lang', lang);

    if (langToggleBtn) {
      langToggleBtn.innerHTML = lang === 'en' 
        ? '<span style="font-size:1.1rem">🇹🇷</span> TR' 
        : '<span style="font-size:1.1rem">🇬🇧</span> EN';
    }

    const dict = translations[lang] || translations.tr;
    document.querySelectorAll('[data-i18n]').forEach(el => {
      const key = el.getAttribute('data-i18n');
      if (dict[key]) {
        el.textContent = dict[key];
      }
    });

    updateGallery();
    if (window.updateGearCalculator) {
      window.updateGearCalculator();
    }
  }

  if (langToggleBtn) {
    langToggleBtn.addEventListener('click', () => {
      const current = document.documentElement.lang || 'tr';
      const next = current === 'tr' ? 'en' : 'tr';
      setLanguage(next);
    });
  }

  // Load Saved Language (default TR)
  const savedLang = localStorage.getItem('pgg_lang') || 'tr';
  setLanguage(savedLang);

  // Initialize Gallery
  updateGallery();
})();

