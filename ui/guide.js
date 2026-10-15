/* User guide: a "?" button in the corner opens a bilingual manual with diagrams (TR / EN, follows currentLang). */
(function () {
  const C = { line: '#94a3b8', cyan: '#00d2ff', gold: '#ffb703', green: '#06d6a0', red: '#ef476f', fill: '#1f2735' };

  /* ── diagrams ─────────────────────────────────────────────────────────── */
  function toothSvg(kind, label) {
    const lines = [];
    for (let i = 0; i < 7; i++) {
      const x = 14 + i * 16;
      if (kind === 'spur' || kind === 'hcr') lines.push(`<line x1="${x}" y1="12" x2="${x}" y2="${kind === 'hcr' ? 92 : 88}" stroke="${C.cyan}" stroke-width="${kind === 'hcr' ? 6 : 4}" stroke-linecap="round"/>`);
      if (kind === 'helical') lines.push(`<line x1="${x}" y1="12" x2="${x + 18}" y2="88" stroke="${C.cyan}" stroke-width="4" stroke-linecap="round"/>`);
      if (kind === 'herring') lines.push(`<polyline points="${x},12 ${x + 12},50 ${x},88" fill="none" stroke="${C.cyan}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>`);
    }
    const arrow = kind === 'helical'
      ? `<line x1="62" y1="104" x2="100" y2="104" stroke="${C.red}" stroke-width="2"/><polygon points="100,99 108,104 100,109" fill="${C.red}"/>`
      : '';
    return `<svg viewBox="0 0 130 130" width="130" height="130"><rect x="4" y="6" width="122" height="88" rx="6" fill="${C.fill}" stroke="${C.line}"/>${lines.join('')}${arrow}<text x="65" y="124" fill="${C.line}" font-size="11" text-anchor="middle">${label}</text></svg>`;
  }

  function releaseSvg(L) {
    return `<svg viewBox="0 0 420 210" width="100%" style="max-width:520px">
      <rect x="20" y="170" width="300" height="26" rx="3" fill="${C.fill}" stroke="${C.line}"/>
      <text x="170" y="187" fill="${C.line}" font-size="11" text-anchor="middle">${L.face}</text>
      <rect x="70" y="138" width="200" height="30" fill="#2b2f5e" stroke="#7f77dd"/>
      <rect x="140" y="52" width="60" height="88" fill="#2b2f5e" stroke="#7f77dd"/>
      <rect x="30" y="98" width="106" height="38" rx="3" fill="#0f3d36" stroke="${C.green}"/>
      <rect x="204" y="98" width="106" height="38" rx="3" fill="#0f3d36" stroke="${C.green}"/>
      <rect x="128" y="38" width="84" height="12" rx="2" fill="#2b2f5e" stroke="#7f77dd"/>
      <rect x="82" y="40" width="22" height="34" rx="4" fill="${C.gold}"/>
      <rect x="88" y="74" width="10" height="82" fill="${C.gold}"/>
      <line x1="104" y1="56" x2="340" y2="40" stroke="${C.line}" stroke-dasharray="3 3"/>
      <text x="344" y="44" fill="${C.gold}" font-size="11">${L.plunger}</text>
      <line x1="300" y1="118" x2="340" y2="90" stroke="${C.line}" stroke-dasharray="3 3"/>
      <text x="344" y="94" fill="${C.green}" font-size="11">${L.arm}</text>
      <line x1="270" y1="152" x2="340" y2="140" stroke="${C.line}" stroke-dasharray="3 3"/>
      <text x="344" y="144" fill="#afa9ec" font-size="11">${L.collar}</text></svg>`;
  }

  function bracketSvg(L) {
    const g = (x, body, title) => `<g transform="translate(${x},0)"><rect x="0" y="0" width="128" height="120" rx="6" fill="${C.fill}" stroke="${C.line}"/>${body}<text x="64" y="138" fill="${C.line}" font-size="11" text-anchor="middle">${title}</text></g>`;
    const side = `<rect x="14" y="14" width="8" height="96" fill="${C.gold}"/><rect x="22" y="70" width="70" height="8" fill="${C.gold}"/><rect x="40" y="20" width="56" height="50" rx="4" fill="#2b2f5e" stroke="${C.cyan}"/><rect x="52" y="78" width="32" height="26" fill="#334" stroke="${C.line}"/>`;
    const base = `<rect x="14" y="104" width="100" height="8" fill="${C.gold}"/><rect x="26" y="56" width="8" height="50" fill="${C.gold}"/><rect x="94" y="56" width="8" height="50" fill="${C.gold}"/><rect x="22" y="50" width="84" height="8" fill="${C.gold}"/><rect x="36" y="12" width="56" height="38" rx="4" fill="#2b2f5e" stroke="${C.cyan}"/><rect x="48" y="58" width="32" height="40" fill="#334" stroke="${C.line}"/>`;
    const panel = `<rect x="6" y="62" width="116" height="8" fill="${C.gold}"/><rect x="36" y="20" width="56" height="42" rx="4" fill="#2b2f5e" stroke="${C.cyan}"/><rect x="48" y="70" width="32" height="36" fill="#334" stroke="${C.line}"/>`;
    return `<svg viewBox="0 0 430 145" width="100%" style="max-width:520px">${g(0, side, L.side)}${g(150, base, L.base)}${g(300, panel, L.panel)}</svg>`;
  }

  function cycloidSvg(L) {
    let pins = '';
    for (let k = 0; k < 16; k++) {
      const a = 2 * Math.PI * k / 16;
      pins += `<circle cx="${70 + 52 * Math.cos(a)}" cy="${70 + 52 * Math.sin(a)}" r="5" fill="${C.gold}"/>`;
    }
    let d = '';
    for (let i = 0; i <= 180; i++) {
      const t = 2 * Math.PI * i / 180, R = 52, e = 4, n = 16, rp = 5;
      const psi = Math.atan2(Math.sin((1 - n) * t), R / (e * n) - Math.cos((1 - n) * t));
      const x = R * Math.cos(t) - rp * Math.cos(t + psi) - e * Math.cos(n * t) + 4;
      const y = -R * Math.sin(t) + rp * Math.sin(t + psi) + e * Math.sin(n * t);
      d += (i ? 'L' : 'M') + (70 + x).toFixed(1) + ',' + (70 + y).toFixed(1);
    }
    return `<svg viewBox="0 0 140 150" width="150"><path d="${d}Z" fill="#2b2f5e" stroke="${C.cyan}"/>${pins}<circle cx="74" cy="70" r="10" fill="${C.fill}" stroke="${C.line}"/><text x="70" y="146" fill="${C.line}" font-size="11" text-anchor="middle">${L}</text></svg>`;
  }


  function calibSvg(L) {
    const plate = (x, w, title, body) => `<g transform="translate(${x},0)"><rect x="0" y="8" width="${w}" height="92" rx="6" fill="${C.fill}" stroke="${C.line}"/>${body}<text x="${w / 2}" y="118" fill="${C.line}" font-size="11" text-anchor="middle">${title}</text></g>`;
    let pockets = '';
    for (let k = 0; k < 6; k++) {
      const cx = 22 + (k % 3) * 38, cy = 34 + Math.floor(k / 3) * 40;
      pockets += `<circle cx="${cx}" cy="${cy}" r="14" fill="#0b0f15" stroke="${k === 2 ? C.green : C.cyan}" stroke-width="${k === 2 ? 2.5 : 1}"/><text x="${cx}" y="${cy + 4}" fill="${C.gold}" font-size="10" text-anchor="middle">${k + 1}</text>`;
    }
    let holes = '';
    for (let k = 0; k < 6; k++) {
      const cx = 18 + k * 20;
      holes += `<circle cx="${cx}" cy="40" r="${4 + k * 0.4}" fill="#0b0f15" stroke="${k === 1 ? C.green : C.cyan}" stroke-width="${k === 1 ? 2.5 : 1}"/><text x="${cx}" y="70" fill="${C.gold}" font-size="10" text-anchor="middle">${k + 1}</text>`;
    }
    let gears = '';
    for (let k = 0; k < 3; k++) {
      const cx = 30 + k * 46;
      for (const dy of [28, 70]) {
        gears += `<circle cx="${cx}" cy="${dy}" r="17" fill="#2b2f5e" stroke="${k === 1 ? C.green : C.cyan}" stroke-width="${k === 1 ? 2.5 : 1}" stroke-dasharray="3 2"/>`;
      }
      for (let d = 0; d <= k; d++) gears += `<circle cx="${cx - 4 + d * 4}" cy="28" r="1.6" fill="${C.gold}"/>`;
    }
    return `<svg viewBox="0 0 470 125" width="100%" style="max-width:560px">${plate(0, 132, L.bearing, pockets)}${plate(146, 132, L.pin, holes)}${plate(292, 170, L.backlash, gears)}</svg>`;
  }

  const img = (src, w) => `<div class="guide-fig"><img src="${src}" style="max-width:${w || 520}px"></div>`;

  /* ── content ──────────────────────────────────────────────────────────── */
  const TEXT = {
    tr: {
      title: '📘 Kullanım Kılavuzu', button: 'Kullanım kılavuzu',
      sections: () => [
        ['start', 'Hızlı başlangıç', `
          <ol>
            <li><b>1. Motor & Oran:</b> düzeni, hedef oranı (veya "oranı yükten hesapla"), motoru ve uygulama yükünü girin.</li>
            <li><b>2. Dişli & Profil:</b> diş tipi, modül/genişlik, profil kaydırma.</li>
            <li><b>3. Rulmanlar & Pim:</b> planet rulmanı ve pim tipi (çelik pim önerilir).</li>
            <li><b>4. Taşıyıcı & Gövde:</b> çıkış tipi, kol, boşa alma, montaj braketi.</li>
            <li><b>5. 3D Baskı:</b> toleranslar, kalibrasyon parçası, yazıcı profili (3MF).</li>
            <li><b>6. Malzeme & Dayanım:</b> malzeme, emniyet hedefleri, <i>uzman modu</i>.</li>
          </ol>
          <p>Aday listesinden bir tasarım seçin, <b>3D Modeli Oluştur</b> ile üretin; <b>Dışa Aktar</b> STEP, STL, 3MF ve
          mühendislik raporunu bir klasöre yazar. Sağdaki <b>✨ AI Asistan</b> sekmesinde ihtiyacınızı düz cümleyle
          anlatabilirsiniz.</p>
          <p class="guide-tip">S (emniyet) ≥ 1 her kontrolün hedefi karşıladığı anlamına gelir; en küçük S "sınırlayan
          eleman"dır. Kırmızı satırlar neyin zayıf olduğunu gösterir.</p>`],
        ['arr', 'Redüktör düzenleri', `
          ${img('assets/arrangements.svg')}
          <table class="guide-table"><tr><th>Düzen</th><th>Oran</th><th>Verim</th><th>Ne zaman?</th></tr>
          <tr><td><b>Standart</b> (taşıyıcı çıkışı)</td><td>3–5 / kademe, 1–5 kademe</td><td>~%90+/kademe</td><td>Genel amaç, en küçük gövde.</td></tr>
          <tr><td><b>Dönen gövde</b> (tambur)</td><td>Zr/Zs, ters yön</td><td>~%90+</td><td>Tekerlek, vinç, döner tabla, büyük çıkış yüzü.</td></tr>
          <tr><td><b>Hız artırıcı</b></td><td>≤ 30:1 önerilir</td><td>—</td><td>Jeneratör, el krankı, rüzgâr rotoru.</td></tr>
          <tr><td><b>Wolfrom</b></td><td>50–500:1 tek kademe</td><td>%15–60</td><td>Çok yüksek oran, kısa gövde; çoğu <b>kendiliğinden kilitli</b> (yük elektriksiz tutulur).</td></tr>
          <tr><td><b>Sikloidal</b></td><td>6–60:1 tek kademe</td><td>~%80</td><td>Çok rijit, boşluksuz: robot eklemi, döner tabla. Çelik pimler, gres şart.</td></tr></table>
          <div class="guide-row">${cycloidSvg('Sikloid disk + halka pimleri')}<p>Sikloidalde diş yoktur: eksantrik bir disk çelik
          pimler içinde yuvarlanır, oran = pim sayısı − 1. Wolfrom'da kademeli planetler (iki dişli tek parça) sabit ve
          dönen iki çemberle birlikte kavrar.</p></div>`],
        ['teeth', 'Diş tipleri', `
          <div class="guide-row">${toothSvg('spur', 'Düz')}${toothSvg('herring', 'Balıksırtı')}${toothSvg('helical', 'Tek helis')}${toothSvg('hcr', 'HCR (uzun diş)')}</div>
          <table class="guide-table"><tr><th>Tip</th><th>Avantaj</th><th>Dezavantaj</th></tr>
          <tr><td><b>Düz</b></td><td>En kolay baskı ve montaj, eksenel kuvvet yok.</td><td>En gürültülü; temas oranı ~1.5.</td></tr>
          <tr><td><b>Balıksırtı</b></td><td>Sessiz, en güçlü, eksenel kuvvetler birbirini siler.</td><td>Çember iki parçadır; montaj ve baskı daha zor.</td></tr>
          <tr><td><b>Tek helis</b></td><td>Sessiz, düzden güçlü, tek parça çember, montajı kolay.</td><td><span style="color:${C.red}">Eksenel itme</span> (kırmızı ok): motor rulmanını zorlar → itme pulu veya 10–15° helis.</td></tr>
          <tr><td><b>HCR</b> (yüksek temas oranlı düz)</td><td>Aynı anda 2 diş çifti: sessizliğe yakın, eksenel itme yok, baskısı kolay.</td><td>Daha çok diş gerekir (gövde biraz büyür), diş ucu incedir.</td></tr></table>
          <p><b>Kullanılabilirlik:</b> standart, dönen gövde ve hız artırıcıda dördü de; Wolfrom'da düz ve HCR
          (kademeli planette helis uygun değil); sikloidalde dişli yoktur.</p>`],
        ['out', 'Çıkış tipleri', `
          <ul>
            <li><b>Flanş göbeği:</b> ince kesit rulmanda döner; kendi parçanızı M3 vidalarla bağlarsınız.</li>
            <li><b>D-mil (baskı / çelik):</b> kasnak, dişli, kaplin için.</li>
            <li><b>Kol (yassı / yuvarlak):</b> kapak, bariyer, menteşeli mekanizmalar; ucundaki yük 1. sekmeye girilir.</li>
            <li><b>Tambur yüzü / tambur kolu / vinç tamburu:</b> dönen gövde ve Wolfrom'da büyük çaplı çıkış.</li>
          </ul>
          ${img('assets/load_check.svg', 420)}
          <p>Uygulama yükü girildiğinde program yükü kaldırıp kaldıramadığını, motor rezervini ve çıkış rulmanının yan yükünü söyler.</p>`],
        ['release', 'Boşa alma (indeks pimi)', `
          ${releaseSvg({ face: 'Çıkış göbeği / tambur kapağı', plunger: 'Yaylı indeks pimi GN 617.1', arm: 'Kol / flanş diski (serbest)', collar: 'Tahrik bileziği (vidalı)' })}
          <ol>
            <li>Tahrik bileziği çıkışa vidalanır; kol (veya flanş diski) bileziğin boynunda <b>serbest</b> döner.</li>
            <li>Yay, indeks piminin ucunu bilezikteki deliğe iter: kol çıkışla birlikte döner.</li>
            <li><b>Boşa almak:</b> topuzu çekip çeyrek tur çevirin — pim yukarıda kalır, kol elle döner (ör. elektrik kesintisi).</li>
            <li><b>Geri bağlamak:</b> topuzu geri çevirin, kolu biraz oynatın; delikler hizalanınca pim "tık" diye girer.</li>
          </ol>
          <p class="guide-tip">Pim yük altındayken zor çıkar (sürtünme). Önce yükü alın veya motoru hafifçe geri döndürün.
          Pim ölçüsü torka göre otomatik seçilir; ileride topuzun yerine bir çekme solenoidi takılabilir.</p>`],
        ['mount', 'Montaj braketleri', `
          ${bracketSvg({ side: 'Yan montaj (L)', base: 'Ayaklı taban', panel: 'Panel plakası' })}
          <ul>
            <li><b>Yan montaj:</b> eksen montaj yüzeyine paralel — duvar / direk yanına dik veya zemine yatay. Plaka gövdenin
            ve dönen yuvarlak parçaların dışında durur, çıkışın altında biter. Kollar duvar yüzünden dolayı tam tur dönemez:
            serbest açı uyarıda yazar.</li>
            <li><b>Ayaklı taban:</b> eksen yüzeye dik — masaya dik (döner tabla) veya duvardan dışarı (tekerlek, vinç).</li>
            <li><b>Panel:</b> motor panel deliğinden geçer, redüktör panelin üstünde durur.</li>
          </ul>
          <p>Her tipte bağlantı cıvataları braketin rafındaki somunlara uzanır; tepki torku doğrudan brakete geçer.</p>`],
        ['expert', 'Uzman modu', `
          <p>6. sekmede açılır. Ek girdiler: ortam sıcaklığı, çalışma oranı (ED), yağlama (gresli / kuru), durarak yük tutma süresi.</p>
          <ul>
            <li><b>Diş sıcaklığı</b> (VDI 2736 yapısında): plastik dişliler ısındıkça zayıflar; sınırı aşarsa kontrol kırmızıdır.</li>
            <li><b>Çevrim ömrü:</b> hedef ömürdeki diş çevrim sayısına göre diş dibi ve yüzey dayanımı azaltılır.</li>
            <li><b>Aşınma:</b> kuru çalışmada belirgindir; gres aşınmayı ~5 kat azaltır.</li>
            <li><b>Sünme:</b> yük uzun süre hareketsiz tutuluyorsa (ör. kendiliğinden kilitli Wolfrom) kontrol edilir.</li>
          </ul>
          <p class="guide-tip">Sürekli çalışan baskı bir redüktör uzman modunda daha büyük çıkar — bu gerçekçi sonuçtur.
          Katsayılar yaklaşıktır; kritik işlerde deneme baskısıyla doğrulayın.</p>`],
        ['calib', 'Kalibrasyon parçası', `
          <p>Her yazıcı delikleri biraz farklı basar: aynı modelde bir rulman yuvası bir yazıcıda tam oturur, ötekinde
          bol kalır veya hiç girmez. <b>Kalibrasyon parçası</b>, seçili tasarımın gerçek geçmelerini küçük plakalarda
          sizin yazıcınızda dener; en iyi sonuçları forma yazar ve bundan sonraki tüm tasarımlar bu değerlerle üretilir.</p>
          ${calibSvg({ bearing: '1 · Rulman yuvaları', pin: '2 · Pim delikleri', backlash: '3 · Diş boşluğu çiftleri' })}
          <table class="guide-table"><tr><th>Plaka</th><th>Ne dener?</th><th>Doğru sonuç</th><th>Forma yazılan</th></tr>
          <tr><td><b>1 · Rulman yuvaları</b></td><td>Tasarımdaki her rulman için yuva = dış çap D −0.05 … +0.20 mm (6 adım)</td>
              <td>Rulman elle / mengeneyle <b>hafif baskıyla</b> girer, ters çevirince düşmez.</td><td>Rulman toleransı</td></tr>
          <tr><td><b>2 · Pim delikleri</b></td><td>Her çelik pim çapı için delik = d −0.10 … +0.15 mm (6 adım)</td>
              <td>Pim mengene veya hafif çekiçle girer, <b>elle çıkmaz</b>.</td><td>Pim toleransı</td></tr>
          <tr><td><b>3 · Diş boşluğu</b></td><td>Tasarımın modülünde dişli çiftleri, boşluk 0.10 … 0.30 mm (5 çift)</td>
              <td><b>Sıkışmadan, takılmadan</b> dönen çiftlerin <b>en az boşluklu</b> olanı.</td><td>Diş boşluğu</td></tr></table>
          <ol>
            <li>Tasarımı seçin (aday listesi), <b>5. 3D Baskı</b> sekmesinde <b>Kalibrasyon parçasını oluştur</b>'a basın.
            Parçalar görüntüleyicide açılır; <b>Dışa Aktar</b> STL / 3MF dosyalarını ve adım adım bir rehber yazar.</li>
            <li>Plakaları <b>dişlilerle aynı malzeme ve ayarlarla</b> basın (katman yüksekliği, duvar sayısı, akış, yön).
            Soğumalarını bekleyin; zımparalamayın.</li>
            <li>Her yuvaya / deliğe gerçek rulmanı ve pimi deneyin, dişli çiftlerini tabandaki pimlerde elle çevirin.
            Numaralar yüzeye kazınmıştır; dişli çiftleri göbekteki nokta sayısıyla ayrılır.</li>
            <li>En iyi numaraları sekmedeki kutulara girin, <b>Uygula ve hatırla</b>'ya basın: toleranslar forma yazılır ve
            sonraki açılışlarda da kullanılır. Tasarımda birden fazla rulman / pim ölçüsü varsa her biri için en iyi numarayı girin; form tek bir değer kullandığından bunların ortalaması alınır.</li>
          </ol>
          <p class="guide-tip">Yazıcı, nozul, filament veya baskı ayarı değişince kalibrasyonu yenileyin. Rulman iki numara
          arasında kalıyorsa (biri çok sıkı, diğeri bol) bol olanı seçin ve rulmanı hafif baskıyla takın. Kaydı silmek için <b>Kaydı sil</b>.</p>`],
        ['print', 'Baskı ve montaj ipuçları', `
          ${img('assets/tooth_depth.svg', 420)}
          <ul>
            <li>Önce <b>kalibrasyon parçası</b> ile toleransları yazıcınıza göre ayarlayın (yukarıdaki bölüm).</li>
            <li><b>3MF</b> dosyası parçaları tablalara dizer; Creality K1 ailesi profili seçilirse yazıcı ve filament ayarları da içindedir.</li>
            <li>3MF'yi slicer'da <b>proje olarak açın</b> (çift tıklama / Dosya › Aç): tablalar ve parça ayarları korunur. Var olan
            bir projeye <b>içe aktarırsanız</b> parçalar tek tablaya yığılır, <b>Diz (Arrange)</b> ile yeniden dağıtın. Dişli
            parçalar ince katmanla (0.12 / 0.16 mm), gövde, kapak, flanş ve braketler 0.2 mm ile basılır.</li>
            <li>Dişliler %100 dolgu, gövde %40+ ve 4+ duvar; malzeme önerisi: PETG / PA-CF dişli, PLA gövde.</li>
            <li>Dişlileri plastik uyumlu gresle yağlayın, ilk çalıştırmada birkaç dakika iki yönde alıştırın.</li>
            <li>Montaj adımları ve parça listesi dışa aktarılan raporda yazar.</li>
          </ul>`],
      ],
    },
    en: {
      title: '📘 User Guide', button: 'User guide',
      sections: () => [
        ['start', 'Quick start', `
          <ol>
            <li><b>1. Motor & Ratio:</b> arrangement, target ratio (or "ratio from the load"), motor and application load.</li>
            <li><b>2. Gears & Profile:</b> tooth type, module / face width, profile shift.</li>
            <li><b>3. Bearings & Pins:</b> planet bearing and pin type (steel pins recommended).</li>
            <li><b>4. Carrier & Housing:</b> output type, arm, release, mounting bracket.</li>
            <li><b>5. 3D Printing:</b> tolerances, calibration coupon, printer profile (3MF).</li>
            <li><b>6. Materials & Strength:</b> materials, safety targets, <i>expert mode</i>.</li>
          </ol>
          <p>Pick a design from the candidate list, build it with <b>Generate 3D Model</b>; <b>Export</b> writes STEP, STL, 3MF
          and the engineering report. In the <b>✨ AI assistant</b> tab you can describe your need in plain words.</p>
          <p class="guide-tip">S (safety) ≥ 1 means a check meets its target; the smallest S is the "limiting element". Red
          rows show what is weak.</p>`],
        ['arr', 'Arrangements', `
          ${img('assets/arrangements.svg')}
          <table class="guide-table"><tr><th>Arrangement</th><th>Ratio</th><th>Efficiency</th><th>When?</th></tr>
          <tr><td><b>Standard</b> (carrier output)</td><td>3–5 per stage, 1–5 stages</td><td>~90 %+ / stage</td><td>General purpose, smallest housing.</td></tr>
          <tr><td><b>Rotating housing</b> (drum)</td><td>Zr/Zs, reversed</td><td>~90 %+</td><td>Wheel, winch, turntable, large output face.</td></tr>
          <tr><td><b>Speed-up</b></td><td>≤ 30:1 recommended</td><td>—</td><td>Generator, hand crank, wind rotor.</td></tr>
          <tr><td><b>Wolfrom</b></td><td>50–500:1 in one stage</td><td>15–60 %</td><td>Very high ratio, short housing; mostly <b>self-locking</b> (holds the load without power).</td></tr>
          <tr><td><b>Cycloidal</b></td><td>6–60:1 in one stage</td><td>~80 %</td><td>Very stiff, backlash-free: robot joints, turntables. Steel pins, grease.</td></tr></table>
          <div class="guide-row">${cycloidSvg('Cycloid disc + ring pins')}<p>A cycloidal drive has no teeth: an eccentric disc rolls
          inside steel pins, ratio = pin count − 1. In a Wolfrom, stepped planets (two gears in one part) mesh a fixed and
          a turning ring at the same time.</p></div>`],
        ['teeth', 'Tooth types', `
          <div class="guide-row">${toothSvg('spur', 'Spur')}${toothSvg('herring', 'Herringbone')}${toothSvg('helical', 'Single helical')}${toothSvg('hcr', 'HCR (long teeth)')}</div>
          <table class="guide-table"><tr><th>Type</th><th>Advantages</th><th>Disadvantages</th></tr>
          <tr><td><b>Spur</b></td><td>Easiest to print and assemble, no axial force.</td><td>Loudest; contact ratio ~1.5.</td></tr>
          <tr><td><b>Herringbone</b></td><td>Quiet, strongest, the axial forces cancel.</td><td>Two-part ring; harder to assemble and print.</td></tr>
          <tr><td><b>Single helical</b></td><td>Quiet, stronger than spur, one-piece ring, easy assembly.</td><td><span style="color:${C.red}">Axial thrust</span> (red arrow) loads the motor bearing → thrust washers or a 10–15° helix.</td></tr>
          <tr><td><b>HCR</b> (high contact ratio spur)</td><td>Two tooth pairs at once: nearly as quiet, no axial thrust, easy to print.</td><td>Needs more teeth (housing a little larger), thinner tooth tips.</td></tr></table>
          <p><b>Availability:</b> all four in the standard, rotating housing and speed-up arrangements; spur and HCR in the
          Wolfrom (helical does not suit stepped planets); the cycloidal drive has no gears.</p>`],
        ['out', 'Output types', `
          <ul>
            <li><b>Flange hub:</b> runs in a thin-section bearing; bolt your part on with M3 screws.</li>
            <li><b>D-shaft (printed / steel):</b> for pulleys, gears, couplings.</li>
            <li><b>Arm (flat / round):</b> lids, barriers, hinged mechanisms; enter the tip load in tab 1.</li>
            <li><b>Drum face / drum arm / winch drum:</b> large output of the rotating housing and the Wolfrom.</li>
          </ul>
          ${img('assets/load_check.svg', 420)}
          <p>With an application load the program tells whether it can move it, the motor reserve and the output bearing's side load.</p>`],
        ['release', 'Release (index plunger)', `
          ${releaseSvg({ face: 'Output hub / drum lid', plunger: 'Spring index plunger GN 617.1', arm: 'Arm / flange disc (free)', collar: 'Drive collar (screwed)' })}
          <ol>
            <li>The drive collar is screwed to the output; the arm (or flange disc) turns <b>freely</b> on its neck.</li>
            <li>A spring pushes the index plunger's pin into the collar: the arm turns with the output.</li>
            <li><b>Release:</b> pull the knob and turn it a quarter — the pin stays up, the arm turns by hand (e.g. in a power cut).</li>
            <li><b>Re-engage:</b> turn the knob back and move the arm; the pin snaps in when the holes line up.</li>
          </ol>
          <p class="guide-tip">Under load the pin is hard to pull (friction) — unload it first or back the motor off a little. The
          plunger size follows the torque; a pull solenoid can replace the knob later.</p>`],
        ['mount', 'Mounting brackets', `
          ${bracketSvg({ side: 'Side mount (L)', base: 'Base stand', panel: 'Panel plate' })}
          <ul>
            <li><b>Side mount:</b> axis parallel to the surface — upright beside a wall / post or lying on a floor. The plate
            stays outside the housing and every turning round part and ends below the output. Arms cannot turn a full circle
            past the wall: the free angle is reported.</li>
            <li><b>Base stand:</b> axis normal to the surface — upright on a table (turntable) or out of a wall (wheel, winch).</li>
            <li><b>Panel:</b> the motor passes through a panel hole, the gearbox sits on top.</li>
          </ul>
          <p>In every kind the tie rods run on into nuts in the bracket shelf; the reaction torque goes straight into the bracket.</p>`],
        ['expert', 'Expert mode', `
          <p>Switch it on in tab 6. Extra inputs: ambient temperature, duty (ED), lubrication (greased / dry), hours a load is held at rest.</p>
          <ul>
            <li><b>Tooth temperature</b> (VDI 2736 structure): plastic gears weaken as they heat; above the limit the check is red.</li>
            <li><b>Cycle life:</b> root and flank strength fall with the tooth load cycles over the target life.</li>
            <li><b>Wear:</b> significant when dry; grease cuts it about five times.</li>
            <li><b>Creep:</b> checked when a load is held still for long (e.g. a self-locking Wolfrom).</li>
          </ul>
          <p class="guide-tip">A continuously running printed gearbox comes out larger in expert mode — that is the realistic
          answer. The constants are approximate; validate critical work with test prints.</p>`],
        ['calib', 'Calibration coupon', `
          <p>Every printer prints holes a little differently: the same bearing seat fits on one printer and is loose or
          too tight on another. The <b>calibration coupon</b> tries the real fits of the selected design on small plates on
          your printer; the best results go into the form and every following design is built with them.</p>
          ${calibSvg({ bearing: '1 · Bearing seats', pin: '2 · Pin holes', backlash: '3 · Backlash gear pairs' })}
          <table class="guide-table"><tr><th>Plate</th><th>What it tries</th><th>The right result</th><th>Goes into</th></tr>
          <tr><td><b>1 · Bearing seats</b></td><td>For every bearing of the design: seat = outer diameter D −0.05 … +0.20 mm (6 steps)</td>
              <td>The bearing goes in by hand / vice with <b>light pressure</b> and does not fall out upside down.</td><td>Bearing tolerance</td></tr>
          <tr><td><b>2 · Pin holes</b></td><td>For every steel pin diameter: hole = d −0.10 … +0.15 mm (6 steps)</td>
              <td>The pin goes in with a vice or a light hammer and <b>does not come out by hand</b>.</td><td>Pin tolerance</td></tr>
          <tr><td><b>3 · Backlash</b></td><td>Gear pairs in the design's module, backlash 0.10 … 0.30 mm (5 pairs)</td>
              <td>Of the pairs that turn <b>without binding</b>, the one with the <b>least play</b>.</td><td>Backlash</td></tr></table>
          <ol>
            <li>Select the design (candidate list) and press <b>Create the calibration coupon</b> in tab <b>5. 3D Printing</b>. The
            parts open in the viewer; <b>Export</b> writes the STL / 3MF files and a step-by-step guide.</li>
            <li>Print the plates with the <b>same material and settings as the gears</b> (layer height, walls, flow,
            orientation). Let them cool; do not sand.</li>
            <li>Try the real bearings and pins in every seat / hole, turn the gear pairs by hand on the posts of the base.
            The numbers are engraved; the gear pairs are told apart by the dots on the hub.</li>
            <li>Enter the best numbers in the boxes of the tab and press <b>Apply and remember</b>: the tolerances go into the
            form and are used next time too. With several bearing / pin sizes in the design enter the best number of each; the form takes one value, their mean.</li>
          </ol>
          <p class="guide-tip">Repeat the calibration when the printer, nozzle, filament or print settings change. If a bearing
          falls between two numbers (one too tight, the next loose), take the looser one. <b>Forget</b> clears the record.</p>`],
        ['print', 'Printing & assembly tips', `
          ${img('assets/tooth_depth.svg', 420)}
          <ul>
            <li>First tune the tolerances to your printer with the <b>calibration coupon</b> (section above).</li>
            <li>The <b>3MF</b> lays the parts out on plates; with a Creality K1 family profile it carries the printer and filament settings.</li>
            <li><b>Open the 3MF as a project</b> in the slicer (double-click / File › Open): plates and part settings are kept.
            <b>Importing</b> it into an existing project piles the parts onto one plate: spread them again with <b>Arrange</b>.
            Toothed parts print with fine layers (0.12 / 0.16 mm), housings, covers, flanges and brackets with 0.2 mm.</li>
            <li>Gears 100 % infill, housing 40 %+ with 4+ walls; PETG / PA-CF gears, PLA housing work well.</li>
            <li>Grease the gears with a plastic-safe grease and run them in for a few minutes in both directions.</li>
            <li>The exported report lists the assembly steps and the parts.</li>
          </ul>`],
      ],
    },
  };

  /* ── UI ───────────────────────────────────────────────────────────────── */
  function lang() { return (typeof currentLang !== 'undefined' && currentLang === 'en') ? 'en' : 'tr'; }

  function build() {
    const btn = document.createElement('button');
    btn.id = 'guide_btn';
    btn.className = 'guide-btn';
    btn.textContent = '?';
    btn.onclick = open;
    const lang_btn = document.getElementById('lang_toggle_btn');      // top-right corner, next to the language switch
    if (lang_btn) { btn.classList.add('in-header'); lang_btn.insertAdjacentElement('afterend', btn); }
    else document.body.appendChild(btn);
    const ov = document.createElement('div');
    ov.id = 'guide_overlay';
    ov.className = 'guide-overlay';
    ov.innerHTML = '<div class="guide-card"><div class="guide-head"><h3 id="guide_title"></h3>' +
      '<button class="modal-close-btn" id="guide_close">✕</button></div>' +
      '<div class="guide-wrap"><nav id="guide_toc"></nav><div id="guide_body"></div></div></div>';
    document.body.appendChild(ov);
    ov.addEventListener('click', e => { if (e.target === ov) close(); });
    document.getElementById('guide_close').onclick = close;
    document.addEventListener('keydown', e => { if (e.key === 'Escape') close(); });
    btn.title = TEXT[lang()].button;
  }

  function open() {
    const T = TEXT[lang()];
    const secs = T.sections();
    document.getElementById('guide_title').textContent = T.title;
    document.getElementById('guide_btn').title = T.button;
    document.getElementById('guide_toc').innerHTML = secs.map(([id, t]) => `<a href="#" data-sec="${id}">${t}</a>`).join('');
    document.getElementById('guide_body').innerHTML = secs.map(([id, t, h]) =>
      `<section id="guide_${id}"><h2>${t}</h2>${h}</section>`).join('');
    document.querySelectorAll('#guide_toc a').forEach(a => a.onclick = e => {
      e.preventDefault();
      document.getElementById('guide_' + a.dataset.sec).scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
    document.getElementById('guide_overlay').classList.add('active');
  }

  function close() { document.getElementById('guide_overlay').classList.remove('active'); }

  window.openGuide = open;
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', build); else build();
})();
