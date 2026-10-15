/**
 * Planetary Gearbox Generator UI Controller
 * Handles interactive tabs, modal visual help pop-ups, real-time kinematics synthesis,
 * and bi-directional communication with the CAD backend. The same page runs in three hosts:
 *   - 'fusion'     : Fusion 360 HTML palette (adsk.fusionSendData)
 *   - 'pywebview'  : standalone desktop app (window.pywebview.api, OpenCascade backend)
 *   - 'http'       : standalone backend served to a regular browser (python -m standalone serve)
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
      • <strong>4–5 Kademe:</strong> çok yüksek oranlar (yüzlerce – binlerce :1) veya dar çap içindir: kademe oranı düştükçe güneş büyür, daha çok planet sığar, son (en yüklü) kademe aynı çapta daha güçlü olur. Bedeli: her kademe ~%5–6 verim kaybı (4 kademe ~%78, 5 kademe ~%73), daha uzun gövde ve daha çok parça. Çıkıştaki boşluk esas olarak son kademeden gelir (önceki kademelerinki oranlarına bölünür).<br>
      • <strong>Otomatik:</strong> her kademe sayısı ayrı aranır; en küçük hacimli uygun tasarım seçilir, ek kademe hacmi en az %10 küçültmeli. Çap / boy sınırı içinde ya da yükü taşıyacak tasarım yoksa kademe sayısı kendiliğinden artar.<br>
      • <strong>Oranı yükten hesapla:</strong> uygulama yükü × kuvvet kolu ve motor torkundan, önerilen rezervle yükü kaldıran en düşük oran bulunur (kademe verimi dahil — ek kademe biraz daha yüksek oran ister).<br>
      • Tüm kademeler tek parça ortak dış çember dişliyi (Continuous Ring Housing) paylaşır.
    `,
    en: {
      title: 'Multi-Stage Planetary Architecture',
      description: `
        <strong>How the stages are split:</strong><br>
        • <strong>1 stage:</strong> most efficient for 3:1 to 9:1.<br>
        • <strong>2 stages:</strong> ideal for 10:1 to 80:1 (the first carrier drives the second sun).<br>
        • <strong>3 stages:</strong> 80:1 to 500:1, high-torque robot joints and actuators.<br>
        • <strong>4–5 stages:</strong> very high ratios (hundreds to thousands :1) or a tight diameter: lower stage ratios mean a larger sun and more planets, so the last (most loaded) stage is stronger in the same diameter. The price: ~5–6 % efficiency per stage (4 stages ~78 %, 5 stages ~73 %), a longer housing and more parts. The output backlash comes mainly from the last stage (the earlier ones are divided by the following ratios).<br>
        • <strong>Automatic:</strong> every stage count is searched; the smallest suitable design wins, a further stage must save at least 10 % of the volume. When nothing fits the diameter / length limit or carries the load, the count rises by itself.<br>
        • <strong>Ratio from the load:</strong> the lowest ratio that moves load × lever arm with the recommended reserve over the motor torque (stage efficiency included — a further stage needs a slightly higher ratio).<br>
        • All stages share one continuous ring gear housing.
      `
    }
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
  'modal-addendum': {
    title: 'Diş Yüksekliği Katsayısı (h*ₐ) — Avantajlar ve Dezavantajlar',
    svgFile: 'assets/tooth_depth.svg',
    description: `
      <strong>Ne değişir?</strong> Diş başı h*ₐ·m, diş dibi (h*ₐ + 0.157)·m olur; modül ve diş sayısı aynı kalır. Çember dişlide uç ve boşluk dibi de aynı oranda değişir.<br>
      • <strong>0.80 – Kısa diş:</strong> kuvvet diş dibine daha yakın etkir → kök %5–20 daha sağlam; eksen mesafesi ve baskı hatalarına daha toleranslı, uçlar kalın (FDM için kolay). Dezavantajı: kavrama oranı düşer (aynı anda daha az diş temas eder), dişli biraz daha sesli ve titreşimli çalışır.<br>
      • <strong>1.00 – Standart:</strong> dengeli seçim; çoğu tasarım için önerilen değer.<br>
      • <strong>1.10 – 1.25 – Uzun diş:</strong> kavrama oranı artar → daha yumuşak, sessiz; yük iki dişe paylaşılır. Dezavantajları: kuvvet kolunun uzaması kökü %5–20 zayıflatır, uçlar sivrilir (FDM'de 0.4 mm'nin altına inen uç eksik basılır), girişim artar (program uçları otomatik kırpar; kırpılınca ek yükseklik kaybolur), kayma ve sürtünme artar → ısı, aşınma, verim kaybı; eksen mesafesi hatasına daha hassastır.<br>
      Mukavemet hesabı katsayıya göre ISO 6336-3 form faktörüyle düzeltilir; uç kırpılması ve ince uçlar uyarı olarak bildirilir.
    `,
    en: {
      title: 'Tooth Depth (Addendum) Coefficient h*ₐ — Pros and Cons',
      description: `
        <strong>What changes?</strong> Addendum h*ₐ·m, dedendum (h*ₐ + 0.157)·m; module and tooth counts stay the same. The ring tips and tooth-space roots change likewise.<br>
        • <strong>0.80 – Stub teeth:</strong> the force acts closer to the root → 5–20 % stronger root; more tolerant of centre distance and print errors, thick tips (easy to print). Drawback: lower contact ratio (fewer teeth in mesh), a little noisier.<br>
        • <strong>1.00 – Standard:</strong> balanced, recommended for most designs.<br>
        • <strong>1.10 – 1.25 – Long teeth:</strong> higher contact ratio → smoother, quieter, load shared by two teeth. Drawbacks: the longer lever weakens the root by 5–20 %, tips get pointed (below ~0.4 mm FDM prints them incompletely), more interference (tips are topped automatically, then the extra depth is lost), more sliding → heat, wear, lower efficiency; more sensitive to centre distance errors.<br>
        The strength calculation corrects the root with the ISO 6336-3 form factor; topped or thin tips are reported as warnings.
      `
    }
  },
  'modal-shift': {
    title: 'Profil Kaydırma (x) — Diş Kalınlığını Dengelemek',
    svgFile: 'assets/profile_shift.svg',
    description: `
      <strong>Ne yapar?</strong> Dişli, kesici kremayer x·m kadar dışarı (veya içeri) kaydırılmış gibi üretilir: uç ve kök daireleri x·m kayar, bölüm dairesindeki diş kalınlığı m(π/2 + 2x·tanα) olur. Diş sayısı, modül ve oran aynı kalır.<br>
      • <strong>Planet redüktörde (V-sıfır):</strong> güneş +x, planet ve çember −x alır; böylece güneş-planet ve planet-çember eksen mesafeleri değişmez — montaj, faz ve kinematik aynıdır.<br>
      • <strong>Neden?</strong> Küçük güneşte (12–16 diş) kök dar kalır, eşleşen planetin ucu girişim yüzünden kırpılır; +x kökü kalınlaştırır, teması dişin dışına taşır. Planet iki yönde eğildiği için (ters eğilme ×0.7) çoğu zaman en zayıf dişlidir; büyük güneşlerde otomatik seçim güneşe −x verip planeti güçlendirir.<br>
      • <strong>Otomatik:</strong> her kademede güneş, planet ve çemberin diş dibi dayanımını ISO 6336-3 form faktörüyle dengeler; alt kesme sınırları ve basılabilir uç (≥ 0.3·m) korunur, %2 içinde en küçük |x| seçilir.<br>
      • <strong>Dikkat:</strong> büyük +x uçları sivriltir, büyük −x kökü inceltir. Güneşe −x verildiğinde çemberin boşluk dibi x·m kadar dışarı kayar (gövde duvarı o kadar incelir).
    `,
    en: {
      title: 'Profile Shift (x) — Balancing the Tooth Thickness',
      description: `
        <strong>What it does:</strong> the gear is made as if the cutting rack were moved x·m outward (or inward): the tip and root circles move by x·m, the tooth thickness at the pitch circle becomes m(π/2 + 2x·tanα). Tooth counts, module and ratio stay the same.<br>
        • <strong>In a planetary (V-zero):</strong> the sun gets +x, the planet and the ring −x, so the sun-planet and planet-ring centre distances do not change — assembly, phasing and kinematics are unchanged.<br>
        • <strong>Why?</strong> A small sun (12–16 teeth) has a narrow root and the mating planet tip has to be topped against interference; +x thickens the root and moves the contact outward. The planet bends both ways (reversed bending ×0.7) and is often the weakest gear; for large suns the automatic choice gives the sun −x to strengthen the planet.<br>
        • <strong>Automatic:</strong> balances the root strength of sun, planet and ring per stage with the ISO 6336-3 form factor, within the undercut limits and printable tips (≥ 0.3·m); within 2 % the smallest |x| wins.<br>
        • <strong>Caution:</strong> a large +x makes tips pointed, a large −x thins the root. With a −x sun the ring tooth-space root moves out by x·m (the housing wall gets that much thinner).
      `
    }
  },
  'modal-calibration': {
    title: 'Tolerans Kalibrasyon Parçası',
    svgFile: 'assets/backlash_clearance.svg',
    description: `
      Her yazıcı, filament ve dilimleme ayarı delikleri ve dişleri biraz farklı basar. Kalibrasyon parçası seçili tasarımın gerçek ölçüleriyle numaralı denemeler üretir:<br>
      • <strong>Rulman yuvaları:</strong> tasarımdaki her rulman için 6 yuva (D −0.05 … +0.20 mm). Doğru yuva rulmanı hafif baskıyla alır, ters çevirince düşürmez.<br>
      • <strong>Pim delikleri:</strong> her çelik pim çapı için 6 delik (d −0.10 … +0.15 mm). Doğru delik pimi sıkı tutar, plaka çatlamaz.<br>
      • <strong>Diş boşluğu:</strong> tasarımın modülünde 5 dişli çifti (boşluk 0.10 … 0.30 mm), tabandaki pimlerde tam eksen mesafesinde. Göbekteki nokta sayısı = numara. Doğru çift hiç sıkışmaz ve en az boşlukludur.<br>
      Parçaları redüktörü basacağınız malzeme ve ayarlarla basın. En iyi numaraları bu bölümde seçip <b>Uygula</b>'ya basın: değerler forma yazılır ve bu bilgisayarda hatırlanır (uygulama her açılışta uygular). Farklı malzeme / yazıcı için kalibrasyonu tekrarlayın.
    `,
    en: {
      title: 'Tolerance Calibration Coupon',
      description: `
        Every printer, filament and slicer setting prints holes and teeth a little differently. The coupon makes numbered trials with the real sizes of the selected design:<br>
        • <strong>Bearing pockets:</strong> 6 pockets per bearing of the design (D −0.05 … +0.20 mm). The right one takes the bearing with light pressure and holds it upside down.<br>
        • <strong>Pin holes:</strong> 6 holes per steel pin diameter (d −0.10 … +0.15 mm). The right one holds the pin tight without cracking the plate.<br>
        • <strong>Backlash:</strong> 5 gear pairs at the design module (backlash 0.10 … 0.30 mm) on posts at the exact centre distance. Dots on the hub = number. The right pair never binds and has the least play.<br>
        Print them with the material and settings of the gearbox. Choose the best numbers here and press <b>Apply</b>: the values go into the form and are remembered on this computer (applied at every start). Repeat for another material / printer.
      `
    }
  },
  'modal-load': {
    title: 'Uygulama Yükü: Uygun mu, değil mi?',
    svgFile: 'assets/load_check.svg',
    description: `
      <strong>Nasıl hesaplanır?</strong> Gereken tork T = F × r. F: kol ucundaki / halattaki en büyük kuvvet (kg girilirse × 9.81 N), r: kuvvetin eksene uzaklığı (kol çıkışında kol boyu, makarada yarıçap). Doğrudan tork biliniyorsa Nm seçin.<br>
      • <strong>Motor + oran:</strong> redüktörün verdiği tork (motor torku × oran × verim) yükün en az ×1.5 katı olmalı (step motor: devir arttıkça tork düşer, yetmezse adım kaçırır; diğer motorlarda ×1.25).<br>
      • <strong>Dayanım:</strong> dişlilerin ve çıkışın sürekli taşıyabildiği tork yükten büyük olmalı.<br>
      • <strong>Yan yük:</strong> kuvvet çıkışı yana da iter — çıkış rulmanı ve (mil çıkışında) mil eğilmesi kontrol edilir.<br>
      Sonuç: <b>✓ Uygun</b>, <b>⚠ Sınırda</b> (çalışır ama rezerv az) veya <b>✗ Uygun değil</b>; değilse oran, motor torku veya kuvvet kolu için gereken değer yazılır.
    `,
    en: {
      title: 'Application Load: suitable or not?',
      description: `
        <strong>How is it calculated?</strong> Needed torque T = F × r. F: the largest force at the arm tip / on the rope (kg × 9.81 N), r: its distance from the axis (arm length for an arm output, radius for a pulley). If you know the torque, choose Nm.<br>
        • <strong>Motor + ratio:</strong> the gearbox torque (motor torque × ratio × efficiency) should be at least 1.5× the load (stepper: torque falls with speed and a stepper short of torque loses steps; 1.25× for other motors).<br>
        • <strong>Strength:</strong> the continuous torque the gears and the output can carry must exceed the load.<br>
        • <strong>Side load:</strong> the force also pushes the output sideways — the output bearing and (shaft outputs) the shaft bending are checked.<br>
        Result: <b>✓ Suitable</b>, <b>⚠ Marginal</b> (works with little reserve) or <b>✗ Not suitable</b>, with the ratio, motor torque or lever arm that would be needed.
      `
    }
  },
  'modal-arrangement': {
    title: 'Redüktör Düzeni: Standart, Dönen Gövde, Hız Artırıcı',
    svgFile: 'assets/arrangements.svg',
    description: `
      Bir planet kademesinde üç eleman var: güneş, taşıyıcı (planetleri tutar) ve çember. Biri sabit tutulur, biri giriş, biri çıkış olur.<br>
      • <strong>Standart (taşıyıcı çıkışı):</strong> çember = sabit gövde, motor güneşi çevirir, taşıyıcı çıkıştır. Oran i = 1 + Zr/Zs, aynı yönde döner. En yüksek oran ve en küçük gövde; mil, flanş veya kol çıkışı.<br>
      • <strong>Dönen gövde (tambur):</strong> son kademenin taşıyıcısı sabit tabana pimlenir, çember kapaklı bir tambur olur ve döner. Oran i = Zr/Zs (bir eksik), <b>ters yönde</b> döner. Avantajı: çıkış büyük çaplı bir yüzey — tekerlek, kasnak veya tabla doğrudan vidalanır; vinç tamburu, döner tabla, döner kol için ideal. Tambur, kapağındaki rulmanla sabit taşıyıcının göbeğinde döner; kol yükü geniş çaplı yataklamaya biner. Aynı tork için diş kuvveti ~%20–30 arttığından gövde biraz büyük çıkabilir.<br>
      • <strong>Hız artırıcı:</strong> standart redüktör tersten çalıştırılır: kol / mil / flanş el krankı veya rüzgâr rotoruyla çevrilir, motor yerine takılan jeneratör oran kadar hızlı döner (n_jen = n_giriş × i). Planet dişliler geri sürülebilir (verim ~%90+), ancak oran büyüdükçe sürtünme ve motorun takılma (cogging) torku girişte oran kadar büyür — 30:1'in altı önerilir.<br>
      Not: Bir sonraki adım olarak <i>Wolfrom (bileşik / bölünmüş çember)</i> düzeni tek kademede 100:1 üstü oran ve dönen gövde sağlayabilir.
    `,
    en: {
      title: 'Gearbox Arrangement: Standard, Rotating Housing, Speed-up',
      description: `
        A planetary stage has three members: sun, carrier (holds the planets) and ring. One is held, one is the input, one the output.<br>
        • <strong>Standard (carrier output):</strong> ring = fixed housing, the motor turns the sun, the carrier is the output. Ratio i = 1 + Zr/Zs, same direction. Highest ratio, smallest housing; shaft, flange or arm output.<br>
        • <strong>Rotating housing (drum):</strong> the last carrier is pinned to a fixed base plate, the ring becomes a drum with a lid and turns. Ratio i = Zr/Zs (one less), <b>opposite direction</b>. Advantage: the output is a large face — a wheel, pulley or table bolts straight on; ideal for winch drums, turntables, swinging arms. The drum turns on a bearing in its lid on the stub of the fixed carrier; an arm load acts on a wide bearing base. The tooth forces are ~20–30 % higher for the same torque, so the housing may come out a bit larger.<br>
        • <strong>Speed-up:</strong> a standard gearbox driven backwards: a hand crank or wind rotor turns the arm / shaft / flange, the generator in place of the motor spins ratio times faster (n_gen = n_in × i). Planetary gears back-drive well (efficiency ~90 %+), but friction and the motor's cogging torque grow by the ratio at the input — keep it below 30:1.<br>
        Note: a <i>Wolfrom (compound / split-ring)</i> arrangement would give above 100:1 in one stage with a rotating housing — a possible next step.
      `
    }
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
  'NEMA17': { shaft_dia: 5.0, shaft_type: 'D_CUT', torque: 0.40, speed: 300 },
  'NEMA23': { shaft_dia: 6.35, shaft_type: 'D_CUT', torque: 1.00, speed: 300 },
  'NEMA34': { shaft_dia: 14.0, shaft_type: 'KEYWAY', torque: 3.50, speed: 300 },
  'MOTOR_775': { shaft_dia: 5.0, shaft_type: 'ROUND', torque: 0.12, speed: 9000 },
  'MOTOR_540_550': { shaft_dia: 3.175, shaft_type: 'D_CUT', torque: 0.03, speed: 15000 },
  'CUSTOM': { shaft_dia: 5.0, shaft_type: 'ROUND', torque: 0.30, speed: 1000 }
};

// Manufacturing Presets Data
const MFG_PRESETS = {
  'FDM_3D': { backlash: 0.22, bearing_tol: 0.08 },
  'SLA_RESIN': { backlash: 0.12, bearing_tol: 0.04 },
  'CNC_METAL': { backlash: 0.05, bearing_tol: 0.01 },
  'CUSTOM': { backlash: 0.20, bearing_tol: 0.05 }
};

// Bearing dimensions (mirror of core/bearing_catalog.py) for live safety ratios
const BEARING_CATALOG = {
  '608ZZ': { d_inner: 8.0, d_outer: 22.0, width: 7.0 },
  '688ZZ': { d_inner: 8.0, d_outer: 16.0, width: 5.0 },
  '686ZZ': { d_inner: 6.0, d_outer: 13.0, width: 5.0 },
  '684ZZ': { d_inner: 4.0, d_outer: 9.0, width: 4.0 },
  '623ZZ': { d_inner: 3.0, d_outer: 10.0, width: 4.0 },
  'MR105ZZ': { d_inner: 5.0, d_outer: 10.0, width: 4.0 },
  'MR117ZZ': { d_inner: 7.0, d_outer: 11.0, width: 3.0 },
  'MR128ZZ': { d_inner: 8.0, d_outer: 12.0, width: 3.5 },
  '6700ZZ': { d_inner: 10.0, d_outer: 15.0, width: 4.0 },
  'CUSTOM_PIN': { d_inner: 5.0, d_outer: 5.0, width: 0.0 }
};

// ─── Host Bridge (Fusion 360 / standalone desktop / browser) ─────────────────
const UI_VERSION = '2.9.0';

function fusionReady() {
  return typeof adsk !== 'undefined' && !!adsk && !!adsk.fusionSendData;
}

/* Fusion injects the `adsk` object into the palette, sometimes only after the page has loaded */
function waitForFusion(timeoutMs) {
  if (fusionReady()) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const t0 = Date.now();
    const timer = setInterval(() => {
      if (fusionReady()) { clearInterval(timer); resolve(); }
      else if (Date.now() - t0 > (timeoutMs || 10000)) {
        clearInterval(timer);
        reject(new Error(tr('fusionLinkFail', 'Fusion 360 bağlantısı kurulamadı (adsk nesnesi yok).')));
      }
    }, 100);
  });
}

const Host = {
  mode: 'browser',
  isStandalone() { return this.mode === 'pywebview' || this.mode === 'http'; },   // has the 3D viewer
  hasEngine() { return this.isStandalone() || this.mode === 'fusion'; },           // design + engineering
  call(method, ...args) {
    if (this.mode === 'pywebview') return window.pywebview.api[method](...args);
    if (this.mode === 'fusion') {
      // Fusion 360: the palette handler answers through HTMLEventArgs.returnData
      // (CEF browser: synchronous string, Qt browser: Promise)
      return waitForFusion().then(() => {
        const r = adsk.fusionSendData('api', JSON.stringify({ method, args }));
        return Promise.resolve(r).then(x => (typeof x === 'string' ? JSON.parse(x || '{}') : x));
      });
    }
    if (this.mode === 'http') {
      return fetch('/api/' + method, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-PGB-Client': '1' },
        body: JSON.stringify({ args })
      }).then(r => r.json());
    }
    return Promise.reject(new Error('No CAD backend'));
  }
};

// Current Synthesized Candidates Cache
let currentCandidates = [];
let selectedCandidateIndex = 0;
let lastResult = null;
let lastExportFolder = null;

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
  document.querySelectorAll('[data-i18n-title]').forEach(el => {
    const key = el.getAttribute('data-i18n-title');
    if (T[key] !== undefined) el.title = T[key];
  });
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    const key = el.getAttribute('data-i18n-placeholder');
    if (T[key] !== undefined) el.placeholder = T[key];
  });

  // version badge always follows the real UI version
  const vBadge = document.querySelector('[data-i18n="badgeVersion"]');
  if (vBadge) vBadge.textContent = `v${UI_VERSION}`;

  // Update page title
  const hostName = Host.isStandalone() ? 'Standalone' : 'Fusion 360';
  document.title = lang === 'en'
    ? `${hostName} Planetary Gearbox Designer`
    : `${hostName} Planet Redüktör Tasarımcısı`;

  // Standalone host: no Fusion 360 wording on the generate button / badge
  if (Host.isStandalone()) {
    const genLabel = document.querySelector('#btn_generate [data-i18n="btnGenerate"]');
    if (genLabel && T.btnGenerateStandalone) genLabel.textContent = T.btnGenerateStandalone;
    const badge = document.querySelector('[data-i18n="badgeFusion"]');
    if (badge && T.badgeStandalone) badge.textContent = T.badgeStandalone;
  }

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
  if (Host.hasEngine()) updateVisibility();      // hints that depend on the form (load lever arm)
}

function toggleLanguage() {
  applyTranslations(currentLang === 'tr' ? 'en' : 'tr');
  // texts written by the engine (status, hints, load verdict) come in the form language: refresh them
  if (Host.hasEngine() && currentCandidates.length) scheduleDesign(0);
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

  // Progress messages from the Python side (Fusion palette or standalone backend)
  window.hostMessageReceived = function(eventData) {
    try {
      const data = typeof eventData === 'string' ? JSON.parse(eventData) : eventData;
      if (data.event === 'progress') {
        showProgress(data.message, data.percent == null ? null : data.percent);
      } else if (data.event === 'done') {
        hideProgress();
      } else if (data.event === 'error') {
        hideProgress();
        alert((currentLang === 'tr' ? 'Hata: ' : 'Error: ') + data.message);
      }
    } catch(e) {}
  };
  window.fusionMessageReceived = window.hostMessageReceived;
  // Fusion 360 delivers palette.sendInfoToHTML(action, data) through this handler object
  window.fusionJavaScriptHandler = {
    handle: function(action, data) {
      if (action === 'fusionMessageReceived') window.hostMessageReceived(data);
      return 'OK';
    }
  };

  detectHost();

  // Run initial calculation
  recalculateKinematics();
});

/* Summary card: collapsible (compact one-liner); remembered per computer, collapsed by default in Fusion */
function initCalcToggle() {
  const btn = document.getElementById('calc_toggle');
  if (!btn || btn.dataset.ready) return;
  btn.dataset.ready = '1';
  let collapsed = Host.mode === 'fusion';
  try {
    const saved = localStorage.getItem('pgb_calc_collapsed');
    if (saved !== null) collapsed = saved === '1';
  } catch (e) {}
  document.body.classList.toggle('calc-collapsed', collapsed);
  btn.addEventListener('click', () => {
    const now = !document.body.classList.contains('calc-collapsed');
    document.body.classList.toggle('calc-collapsed', now);
    try { localStorage.setItem('pgb_calc_collapsed', now ? '1' : '0'); } catch (e) {}
  });
}

/* Host detection: Fusion palette, pywebview desktop window or HTTP-served standalone backend */
function hostHint() {
  try { return new URLSearchParams(location.search).get('host'); } catch (e) { return null; }
}

function detectHost() {
  // The add-in opens the palette as index.html?host=fusion: engine mode right away, calls wait for `adsk`
  if (hostHint() === 'fusion' || fusionReady()) {
    enableEngineMode('fusion');
    return;
  }
  if (window.pywebview && window.pywebview.api) {
    enableStandaloneMode('pywebview');
    return;
  }
  window.addEventListener('pywebviewready', () => enableStandaloneMode('pywebview'));
  if (location.protocol === 'http:' || location.protocol === 'https:') {
    fetch('/api/get_app_info', { method: 'POST', headers: { 'X-PGB-Client': '1' }, body: '{}' })
      .then(r => r.ok ? r.json() : null)
      .then(info => { if (info && info.success && Host.mode === 'browser') enableStandaloneMode('http'); })
      .catch(() => {});
  }
  // Older palettes without the URL hint: Fusion may inject `adsk` a moment after the page loaded
  let tries = 0;
  const watch = setInterval(() => {
    if (Host.mode !== 'browser') { clearInterval(watch); return; }
    if (fusionReady()) { clearInterval(watch); enableEngineMode('fusion'); }
    else if (++tries > 50) clearInterval(watch);
  }, 100);
}

/* Header badges + a banner when the Python side is a different version (e.g. an old add-in copy) */
function showHostInfo(info, error) {
  const host = Host.mode === 'fusion' ? 'Fusion 360' : 'Standalone';
  const badge = document.querySelector('[data-i18n="badgeFusion"]');
  if (badge) badge.textContent = host;
  const st = document.getElementById('host_status');
  if (st) {
    st.hidden = false;
    st.className = 'badge ' + (info && info.success ? 'badge-success' : 'badge-danger');
    st.textContent = info && info.success
      ? `v${info.version} · ${tr('hostConnected', 'motor bağlı')}` : `v${UI_VERSION} · ${tr('hostNoLink', 'bağlantı yok')}`;
    if (info && info.app_dir) st.title = info.app_dir;
  }
  const banner = document.getElementById('host_banner');
  if (!banner) return;
  let msg = '';
  if (error) {
    msg = `${tr('hostNoLink', 'bağlantı yok')}: ${error}`;
  } else if (info && info.success && info.version !== UI_VERSION) {
    msg = tr('versionMismatch', 'Arayüz v{ui}, Python tarafı v{py}: eklentinin eski bir kopyası çalışıyor olabilir ({dir}). Fusion\'da Betikler ve Eklentiler penceresinden bu klasörü seçin.')
      .replace('{ui}', UI_VERSION).replace('{py}', info.version).replace('{dir}', info.app_dir || '?');
  }
  banner.textContent = msg;
  banner.hidden = !msg;
}

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
      const base = HELP_MODALS[modalKey];
      if (!base) return;
      const data = (currentLang === 'en' && base.en) ? Object.assign({}, base, base.en) : base;

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
      const tq = document.getElementById('motor_torque');
      const sp = document.getElementById('motor_speed');
      if (tq && preset.torque !== undefined) tq.value = preset.torque.toFixed(2);
      if (sp && preset.speed !== undefined) sp.value = preset.speed;
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
        updateMetricsDisplay();
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

  ['pressure_angle', 'helix_angle', 'face_width', 'pin_dia', 'addendum_coef'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('input', updateMetricsDisplay);
  });
}

function recalculateKinematics() {
  if (Host.hasEngine()) {
    scheduleDesign();
    return;
  }
  const targetRatio = parseFloat(document.getElementById('target_ratio').value) || 25.0;
  const stagesCount = parseInt(document.getElementById('stages_count').value, 10) || 2;
  const moduleVal = parseFloat(document.getElementById('module').value) || 1.0;
  const numPlanets = parseInt(document.getElementById('num_planets').value, 10) || 3;   // AUTO: 3 in the quick preview

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
      const parts = cand.stages.map((s, i) => `${i + 1}.K: ${s.ratio}:1 (Zs:${s.z_sun}, Zp:${s.z_planet})`);
      opt.text = `#${idx + 1}: Toplam ${cand.total_ratio}:1 [${parts.join(' | ')} | Ortak Zr:${cand.z_ring}]`;
    }
    selectEl.appendChild(opt);
  });

  updateMetricsDisplay();
}

function updateMetricsDisplay() {
  if (!currentCandidates || currentCandidates.length === 0) return;
  const cand = currentCandidates[selectedCandidateIndex] || currentCandidates[0];
  const firstStage = cand.stages[0];
  if (Host.hasEngine() && cand.engineering) {
    updateStandaloneMetrics(cand);
    return;
  }
  const moduleVal = parseFloat(document.getElementById('module').value) || 1.0;

  document.getElementById('metric_ratio').innerText = `${cand.total_ratio} : 1`;
  document.getElementById('metric_zs').innerText = firstStage.z_sun;
  document.getElementById('metric_zp').innerText = firstStage.z_planet;
  document.getElementById('metric_zr').innerText = cand.z_ring || firstStage.z_ring;
  const dRingPitch = moduleVal * (cand.z_ring || firstStage.z_ring);
  const outerHousingDia = dRingPitch + (moduleVal * 6.0) + 10.0;
  document.getElementById('metric_od').innerText = `~${outerHousingDia.toFixed(1)} mm`;
  const cr = contactRatio(firstStage, moduleVal);
  const crEl = document.getElementById('metric_contact');
  crEl.innerText = cr.text;
  crEl.title = cr.title;

  // Real-Time Dişli / Rulman & Şaft / Güneş Safety Ratios
  const bearingCode = document.getElementById('bearing_type').value;
  let bearingInfo = BEARING_CATALOG[bearingCode] || { d_outer: 16.0, d_inner: 8.0 };
  if (bearingCode === 'CUSTOM_PIN') {
    const pd = parseFloat(document.getElementById('pin_dia').value) || bearingInfo.d_inner;
    bearingInfo = { d_inner: pd, d_outer: pd, width: 0 };
  }
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
    // 3-stage synthesis with common ring gear (same search as core/kinematics.py).
    // Stages are ordered by non-increasing ratio (highest reduction at the low-torque input stage),
    // which also removes duplicate permutations of the same tooth sets.
    for (let zr = 36; zr < 120; zr++) {
      const validStages = [];
      for (let zs = 12; zs < zr - 18; zs++) {
        if ((zr - zs) % 2 !== 0) continue;
        const zp = (zr - zs) / 2;
        if (zp < 10) continue;
        if ((zs + zr) % numPlanets !== 0) continue;
        const a = moduleVal * (zs + zp) / 2.0;
        const c2c = 2.0 * a * Math.sin(Math.PI / numPlanets);
        if ((c2c - moduleVal * (zp + 2)) <= 0.4 * moduleVal) continue;
        validStages.push({ z_sun: zs, z_planet: zp, z_ring: zr, ratio: parseFloat((1.0 + zr / zs).toFixed(2)), num_planets: numPlanets, module: moduleVal });
      }
      validStages.sort((p, q) => q.ratio - p.ratio);
      for (let i = 0; i < validStages.length; i++) {
        for (let j = i; j < validStages.length; j++) {
          for (let k = j; k < validStages.length; k++) {
            const s1 = validStages[i], s2 = validStages[j], s3 = validStages[k];
            const totRatio = s1.ratio * s2.ratio * s3.ratio;
            const err = Math.abs(totRatio - targetRatio) / targetRatio;
            if (err <= 0.12) {
              results.push({
                total_ratio: parseFloat(totRatio.toFixed(2)),
                error_percent: parseFloat((err * 100).toFixed(1)),
                stages: [s1, s2, s3],
                z_ring: zr
              });
            }
          }
        }
      }
    }
  }

  results.sort((a, b) => a.error_percent - b.error_percent || a.z_ring - b.z_ring);
  return results.slice(0, 10);
}

// Transverse contact ratio (sun-planet) + herringbone overlap ratio per helix half
function contactRatio(stage, m) {
  const pa = (parseFloat(document.getElementById('pressure_angle').value) || 20) * Math.PI / 180;
  const ha = Math.min(1.3, Math.max(0.75, parseFloat(document.getElementById('addendum_coef').value) || 1.0));
  const rs = m * stage.z_sun / 2, rp = m * stage.z_planet / 2;
  const a = rs + rp;
  const ga = Math.sqrt(Math.max(0, (rs + ha * m) ** 2 - (rs * Math.cos(pa)) ** 2)) +
             Math.sqrt(Math.max(0, (rp + ha * m) ** 2 - (rp * Math.cos(pa)) ** 2)) - a * Math.sin(pa);
  const eAlpha = ga / (Math.PI * m * Math.cos(pa));
  const herring = !['SPUR', 'HCR'].includes(document.querySelector('input[name="gear_type"]:checked').value);
  if (!herring) return { text: eAlpha.toFixed(2), title: `εα = ${eAlpha.toFixed(2)}` };
  const beta = (parseFloat(document.getElementById('helix_angle').value) || 25) * Math.PI / 180;
  const fw = parseFloat(document.getElementById('face_width').value) || 12;
  const eBeta = (fw / 2) * Math.sin(beta) / (Math.PI * m);
  return { text: (eAlpha + eBeta).toFixed(2), title: `εα ${eAlpha.toFixed(2)} + εβ ${eBeta.toFixed(2)}` };
}

/* Action Buttons & Fusion 360 Bridge */
function initActionButtons() {
  document.getElementById('btn_reset').addEventListener('click', () => {
    document.getElementById('target_ratio').value = '25.0';
    document.getElementById('stages_count').value = '2';
    const rfl = document.getElementById('ratio_from_load');
    if (rfl) rfl.checked = false;
    document.getElementById('motor_preset').value = 'NEMA17';
    document.getElementById('motor_preset').dispatchEvent(new Event('change'));
    const arr = document.getElementById('arrangement');
    if (arr) { arr.value = 'CARRIER'; updateVisibility(); }
    recalculateKinematics();
  });

  document.getElementById('btn_generate').addEventListener('click', () => {
    if (!currentCandidates || currentCandidates.length === 0) {
      alert('Lütfen geçerli bir dişli oranı kombinasyonu seçin!');
      return;
    }

    const selectedConfig = currentCandidates[selectedCandidateIndex] || currentCandidates[0];
    
    if (Host.hasEngine()) {
      const sp = collectParams();
      sp.total_ratio = selectedConfig.total_ratio;
      sp.stages = selectedConfig.stages;
      if (Host.mode === 'fusion') runFusionGeneration(sp);
      else runStandaloneGeneration(sp);
      return;
    }

    const payload = {
      action: 'generate_gearbox',
      total_ratio: selectedConfig.total_ratio,
      stages: selectedConfig.stages,
      is_herringbone: document.querySelector('input[name="gear_type"]:checked').value === 'HERRINGBONE',
    gear_type: document.querySelector('input[name="gear_type"]:checked').value,
      gear_type: document.querySelector('input[name="gear_type"]:checked').value,
      helix_angle: parseFloat(document.getElementById('helix_angle').value) || 25.0,
      face_width: parseFloat(document.getElementById('face_width').value) || 12.0,
      pressure_angle: parseFloat(document.getElementById('pressure_angle').value) || 20.0,
      motor_preset: document.getElementById('motor_preset').value,
      motor_shaft_dia: parseFloat(document.getElementById('motor_shaft_dia').value) || 5.0,
      motor_shaft_type: document.getElementById('motor_shaft_type').value,
      bearing_type: document.getElementById('bearing_type').value,
      circlip_type: document.getElementById('circlip_type').value,
      generate_circlips: document.getElementById('generate_circlips') ? document.getElementById('generate_circlips').checked : true,
      pin_dia: parseFloat(document.getElementById('pin_dia').value) || 5.0,
      generate_housing: document.getElementById('generate_housing').checked,
      output_shaft_dia: parseFloat(document.getElementById('output_shaft_dia').value) || 8.0,
      output_shaft_len: parseFloat(document.getElementById('output_shaft_len').value) || 20.0,
      carrier_thick: parseFloat(document.getElementById('carrier_thick').value) || 3.5,
      backlash: parseFloat(document.getElementById('backlash').value) || 0.22,
      bearing_tolerance: parseFloat(document.getElementById('bearing_tolerance').value) || 0.08,
      lang: currentLang
    };

    // No CAD backend (page opened directly in a browser): show what would be generated
    alert(`${tr('noBackend', 'CAD motoru bağlı değil. Uygulamayı Baslat_Standalone.bat ile veya Fusion 360 eklentisi olarak açın.')}

`
      + `${payload.total_ratio}:1 · ${payload.stages.length} ${tr('stageWord', 'Kademe')}`);
  });
}

/* ─── Standalone (OpenCascade) Mode ────────────────────────────────────────── */
function tr(key, fallback) {
  const T = (window.TRANSLATIONS && window.TRANSLATIONS[currentLang]) || {};
  return T[key] !== undefined ? T[key] : fallback;
}

function enableEngineMode(mode) {
  if (Host.hasEngine()) return;
  Host.mode = mode;
  document.body.classList.add('engine', 'fusion');
  // Fusion has its own 3D view: the result panel (summary, engineering, warnings, parts) sits under the form
  const results = document.getElementById('engine_results');
  const side = document.getElementById('viewer_side');
  if (results && side) results.insertBefore(side, document.getElementById('engine_actions').nextSibling);
  applyTranslations(currentLang);
  initStandaloneForm();
  initAssistant();
  initCalcToggle();
  Host.call('get_app_info').then(info => showHostInfo(info)).catch(err => showHostInfo(null, err.message || err));
}

function enableStandaloneMode(mode) {
  if (Host.isStandalone()) return;
  Host.mode = mode;
  document.body.classList.add('engine', 'standalone');
  applyTranslations(currentLang);
  initViewerControls();
  initStandaloneForm();
  initAssistant();
  initCalcToggle();
  window.GearViewer.init(document.getElementById('viewer_canvas')).catch(err => {
    document.getElementById('viewer_empty').querySelector('.viewer-empty-text').textContent = String(err);
  });
  Host.call('get_app_info').then(info => {
    showHostInfo(info);
    if (info && info.export_dir) setExportStatus(`${tr('exportTarget', 'Dışa aktarma klasörü')}: ${info.export_dir}`);
  }).catch(err => showHostInfo(null, err.message || err));
}

function initViewerControls() {
  const slider = document.getElementById('explode_slider');
  slider.addEventListener('input', () => window.GearViewer.setExplode(slider.value / 100));
  const xray = document.getElementById('xray_toggle');
  xray.addEventListener('change', () => window.GearViewer.setHousingOpacity(xray.checked ? 0.18 : 1));
  const edges = document.getElementById('edges_toggle');
  edges.addEventListener('change', () => window.GearViewer.setEdges(edges.checked));
  const section = document.getElementById('section_toggle');
  section.addEventListener('change', () => window.GearViewer.setSection(section.checked));
  document.querySelectorAll('.tool-btn[data-view]').forEach(b => {
    b.addEventListener('click', () => window.GearViewer.fit(b.getAttribute('data-view')));
  });
  document.getElementById('btn_export_all').addEventListener('click', exportAll);
  document.getElementById('btn_export_step').addEventListener('click', exportStep);
  document.getElementById('btn_export_dir').addEventListener('click', chooseExportDir);
  if (Host.mode === 'http') {
    document.getElementById('btn_export_dir').style.display = 'none';
  }
}

async function runStandaloneGeneration(payload) {
  showProgress(tr('progressStart', 'Model hazırlanıyor...'), 2);
  let poll = null;
  if (Host.mode === 'http') {
    poll = setInterval(() => {
      Host.call('get_progress').then(p => { if (p && p.running && p.message) showProgress(p.message, p.percent); });
    }, 250);
  }
  try {
    const res = await Host.call('generate', payload);
    if (poll) clearInterval(poll);
    if (!res || !res.success) {
      hideProgress();
      if (!(res && res.cancelled)) alert(`${tr('errorPrefix', 'Hata')}: ${res ? res.error : '?'}`);
      return;
    }
    showProgress(tr('progressMesh', '3D görüntü hazırlanıyor...'), 100);
    const mesh = await Host.call('get_mesh', 'normal');
    if (!mesh || !mesh.success) throw new Error(mesh ? mesh.error : 'mesh');
    await window.GearViewer.init(document.getElementById('viewer_canvas'));
    await window.GearViewer.load(mesh);
    document.getElementById('viewer_empty').style.display = 'none';
    window.GearViewer.setExplode(document.getElementById('explode_slider').value / 100);
    window.GearViewer.setEdges(document.getElementById('edges_toggle').checked);
    lastResult = res;
    renderResult(res, mesh);
    initKinematicsBar(mesh.output_factor);
    document.getElementById('btn_export_all').disabled = false;
    document.getElementById('btn_export_step').disabled = false;
    hideProgress();
  } catch (err) {
    if (poll) clearInterval(poll);
    hideProgress();
    alert(`${tr('errorPrefix', 'Hata')}: ${err && err.message ? err.message : err}`);
  }
}

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

function renderResult(res, mesh) {
  const s = res.summary;
  const sumEl = document.getElementById('result_summary');
  sumEl.innerHTML = '';
  const arrKey = { RING: 'arrShortRing', SPEED_UP: 'arrShortSpeedUp', WOLFROM: 'arrShortWolfrom', CYCLOID: 'arrShortCycloid' }[s.arrangement] || 'arrShortCarrier';
  const wf = s.wolfrom, cy = s.cycloid;
  const rows = [
    [tr('sumArrangement', 'Düzen'), tr(arrKey, s.arrangement || 'CARRIER')],
    ...(s.drum_bearing ? [[tr('sumDrum', 'Tambur'), `Ø${s.drum_diameter} mm · ${s.drum_bearing === 'PLAIN' ? tr('plainBearing', 'kaymalı yatak') : s.drum_bearing}`]] : []),
    ...(cy ? [[tr('sumCycloid', 'Sikloid'), `${cy.n_pins} × Ø${cy.pin_d} @ R${cy.R} · e ${cy.e} · ${cy.n_out} × Ø${cy.d_out}`]] : []),
    ...(wf ? [[tr('sumWolfrom', 'Wolfrom dişleri'), `Zs${wf.zs} · Zp${wf.zp1}/${wf.zp2} · Zr${wf.zr1}/${wf.zr2} · ${wf.self_locking ? tr('sumLocking', 'kendiliğinden kilitli') : tr('sumNoLock', 'geri sürülebilir')}`]] : []),
    [tr('sumRatio', 'Oran'), `${s.total_ratio} : 1`],
    [tr('sumType', 'Diş tipi'), s.herringbone ? tr('typeHerringbone', 'Balıksırtı') : (s.helical ? tr('typeHelical', 'Tek helis') : (s.hcr ? tr('typeHcr', 'HCR') : tr('typeSpur', 'Düz')))],
    [tr('sumOuter', 'Dış çap'), `${s.outer_diameter} mm`],
    [tr('sumLength', 'Toplam boy'), `${s.overall_length} mm`],
    [s.arrangement === 'SPEED_UP' ? tr('engGen', 'Jeneratör') : tr('sumOutTorque', 'Çıkış torku'),
     `${s.output_torque} Nm @ ${s.output_speed} rpm`],
    [tr('sumMaxTorque', 'Sürekli kapasite'), `${s.max_output_torque} Nm`],
    ...(res.engineering && res.engineering.load ? [[tr('sumLoad', 'Yük kontrolü'), res.engineering.load.short]] : []),
    ...(s.addendum && Math.abs(s.addendum - 1) > 1e-6 ? [[tr('sumAddendum', 'Diş yüksekliği h*a'), s.addendum.toFixed(2)]] : []),
    [tr('sumMass', 'Baskı kütlesi'), `~${s.printed_mass_g} g`],
    [tr('sumParts', 'Parça adedi'), `${s.part_count} (${s.unique_parts} ${tr('sumUnique', 'farklı')})`],
    [tr('sumTime', 'Üretim süresi'), mesh ? `${res.elapsed} s · ${(mesh.triangles / 1000).toFixed(0)}k △`
      : `${res.elapsed} s${res.stl_count != null ? ` · ${res.stl_count} STL` : ''}`],
  ];
  rows.forEach(([k, v]) => {
    const row = el('div', 'summary-row');
    row.appendChild(el('span', 'summary-key', k));
    row.appendChild(el('span', 'summary-val', v));
    sumEl.appendChild(row);
  });

  renderEngineering(document.getElementById('result_engineering'), res.engineering, true);

  const wSec = document.getElementById('warnings_section');
  const wList = document.getElementById('result_warnings');
  wList.innerHTML = '';
  (res.warnings || []).forEach(w => wList.appendChild(el('li', '', w)));
  wSec.hidden = !(res.warnings && res.warnings.length);

  renderPartsList(res.parts);
  document.getElementById('viewer_side').hidden = false;
}

function renderPartsList(parts) {
  const partsEl = document.getElementById('result_parts');
  partsEl.innerHTML = '';
  const groups = [];
  parts.forEach(p => {
    let g = groups.find(x => x.key === p.group);
    if (!g) { g = { key: p.group, label: p.group_label, parts: [] }; groups.push(g); }
    g.parts.push(p);
  });
  groups.forEach(g => {
    const box = el('div', 'part-group');
    const head = el('label', 'part-group-head');
    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.checked = true;
    cb.addEventListener('change', () => {
      if (Host.isStandalone()) window.GearViewer.setGroupVisible(g.key, cb.checked);
      else Host.call('set_group_visible', g.key, cb.checked).catch(() => {});
    });
    head.appendChild(cb);
    head.appendChild(el('span', '', g.label));
    box.appendChild(head);
    g.parts.forEach(p => {
      const row = el('div', 'part-row');
      const sw = el('span', 'part-swatch');
      sw.style.background = p.color;
      row.appendChild(sw);
      const nm = el('span', 'part-name', p.label);
      if (!p.printable) { nm.classList.add('purchased'); nm.title = p.spec || ''; }
      row.appendChild(nm);
      row.appendChild(el('span', 'part-qty', `×${p.quantity}`));
      box.appendChild(row);
    });
    partsEl.appendChild(box);
  });
}

/* ─── Tolerance calibration coupon ─────────────────────────────────────────── */
const CALIB_KEY = 'pgb_calibration';
let lastCalibration = null;

function calibLoad() {
  try { return JSON.parse(localStorage.getItem(CALIB_KEY) || 'null'); } catch (e) { return null; }
}

function calibApplyValues(v, silent) {
  const setNum = (id, x) => { const e = document.getElementById(id); if (e && x !== undefined && x !== null) e.value = Number(x).toFixed(2); };
  setNum('bearing_tolerance', v.bearing_tolerance);
  setNum('pin_tolerance', v.pin_tolerance);
  setNum('backlash', v.backlash);
  calibShowSaved(v);
  if (!silent && Host.hasEngine()) scheduleDesign(0);
}

function calibShowSaved(v) {
  const s = document.getElementById('calib_saved');
  if (!s) return;
  s.textContent = v ? tr('calibSaved', 'Kayıtlı kalibrasyon uygulandı: rulman {b} · pim {p} · boşluk {bl} mm ({d})')
    .replace('{b}', (v.bearing_tolerance >= 0 ? '+' : '') + Number(v.bearing_tolerance).toFixed(2))
    .replace('{p}', (v.pin_tolerance >= 0 ? '+' : '') + Number(v.pin_tolerance).toFixed(2))
    .replace('{bl}', Number(v.backlash).toFixed(2)).replace('{d}', v.date || '') : '';
}

function initCalibration() {
  const btn = document.getElementById('btn_calibration');
  if (!btn || btn.dataset.ready) return;
  btn.dataset.ready = '1';
  const box = document.getElementById('group_calibration');
  if (box && !Host.isStandalone()) box.style.display = 'none';      // the coupon is printed from the standalone app
  const saved = calibLoad();
  if (saved) calibApplyValues(saved, true);
  btn.addEventListener('click', runCalibration);
  document.getElementById('btn_calib_apply').addEventListener('click', () => {
    if (!lastCalibration) return;
    const pick = (id, list, fallback) => {
      const e = document.getElementById(id);
      const k = e ? parseInt(e.value, 10) : NaN;
      const s = (list || []).find(x => x.index === k);
      return s ? s.value : fallback;
    };
    const cur = lastCalibration.current || {};
    // one form value per test: the mean of the sizes tested (a printer shrinks them about alike)
    const mean = (list, prefix, fallback) => {
      const vals = (list || []).map((x, i) => pick(`${prefix}_${i}`, x.steps, NaN)).filter(x => !isNaN(x));
      return vals.length ? Math.round(vals.reduce((a, c) => a + c, 0) / vals.length * 100) / 100 : fallback;
    };
    const v = {
      bearing_tolerance: mean(lastCalibration.bearings, 'calib_bearing', cur.bearing_tolerance),
      pin_tolerance: mean(lastCalibration.pins, 'calib_pin', cur.pin_tolerance),
      backlash: pick('calib_backlash', (lastCalibration.backlash || {}).steps, cur.backlash),
      date: new Date().toLocaleDateString(),
    };
    try { localStorage.setItem(CALIB_KEY, JSON.stringify(v)); } catch (e) {}
    calibApplyValues(v, false);
  });
  document.getElementById('btn_calib_forget').addEventListener('click', () => {
    try { localStorage.removeItem(CALIB_KEY); } catch (e) {}
    calibShowSaved(null);
  });
}

/* one select per test: the numbers printed on the coupon and the value each stands for */
function renderCalibrationInputs(cal) {
  const rows = document.getElementById('calib_rows');
  rows.innerHTML = '';
  const add = (id, title, steps, fmt, current) => {
    const wrap = el('div', 'form-group');
    const lab = el('label', '', title);
    lab.htmlFor = id;
    const sel = document.createElement('select');
    sel.id = id;
    let best = steps[0];                                // preselect the step closest to the current form value
    steps.forEach(s => { if (Math.abs(s.value - current) < Math.abs(best.value - current)) best = s; });
    steps.forEach(s => {
      const o = document.createElement('option');
      o.value = String(s.index);
      o.textContent = `${s.index} → ${fmt(s.value)}`;
      if (s === best) o.selected = true;
      sel.appendChild(o);
    });
    wrap.appendChild(lab);
    wrap.appendChild(sel);
    rows.appendChild(wrap);
  };
  const cur = cal.current || {};
  const sgn = x => `${x >= 0 ? '+' : ''}${x.toFixed(2)} mm`;
  (cal.bearings || []).forEach((b, i) => add(`calib_bearing_${i}`, `${tr('calibBearing', 'Rulman yuvası')} ${b.code}`,
    b.steps, sgn, cur.bearing_tolerance));
  (cal.pins || []).forEach((p, i) => add(`calib_pin_${i}`, `${tr('calibPin', 'Pim deliği')} Ø${p.d}`, p.steps, sgn,
    cur.pin_tolerance));
  if (cal.backlash) add('calib_backlash', `${tr('calibBacklash', 'Diş boşluğu')} (m${cal.backlash.module})`,
    cal.backlash.steps, x => `${x.toFixed(2)} mm`, cur.backlash);
  const note = el('span', 'field-hint', tr('calibNoteFirst', 'Birden çok rulman / pim ölçüsü varsa seçimlerin ortalaması kullanılır (aynı yazıcıda ölçüler benzer küçülür).'));
  rows.appendChild(note);
  document.getElementById('calib_results').hidden = false;
}

async function runCalibration() {
  if (!currentCandidates || !currentCandidates.length) {
    alert(tr('calibNeedDesign', 'Önce bir tasarım (aday) seçin: kalibrasyon parçası onun rulman, pim ve modülünü kullanır.'));
    return;
  }
  const cand = currentCandidates[selectedCandidateIndex] || currentCandidates[0];
  const sp = collectParams();
  sp.total_ratio = cand.total_ratio;
  sp.stages = cand.stages;
  showProgress(tr('calibProgress', 'Kalibrasyon parçası hazırlanıyor...'), 5);
  try {
    const res = await Host.call('generate_calibration', sp);
    if (!res || !res.success) {
      hideProgress();
      alert(`${tr('errorPrefix', 'Hata')}: ${res ? res.error : '?'}`);
      return;
    }
    showProgress(tr('progressMesh', '3D görüntü hazırlanıyor...'), 100);
    const mesh = await Host.call('get_mesh', 'normal');
    if (!mesh || !mesh.success) throw new Error(mesh ? mesh.error : 'mesh');
    await window.GearViewer.init(document.getElementById('viewer_canvas'));
    await window.GearViewer.load(mesh);
    document.getElementById('viewer_empty').style.display = 'none';
    window.GearViewer.setExplode(0);
    lastCalibration = res.calibration;
    lastResult = res;
    const sumEl = document.getElementById('result_summary');
    sumEl.innerHTML = '';
    [[tr('calibTitle', 'Kalibrasyon parçası'), `${res.summary.part_count} ${tr('partsWord', 'parça')}`],
     [tr('calibBearing', 'Rulman yuvası'), (res.summary.bearings || []).join(' / ') || '–'],
     [tr('calibPin', 'Pim deliği'), (res.summary.pins || []).map(d => `Ø${d}`).join(' / ') || '–'],
     [tr('calibBacklash', 'Diş boşluğu'), `m${res.summary.module} · z${res.calibration.backlash.z}`]].forEach(([k, v]) => {
      const row = el('div', 'summary-row');
      row.appendChild(el('span', 'summary-key', k));
      row.appendChild(el('span', 'summary-val', v));
      sumEl.appendChild(row);
    });
    const eng = document.getElementById('result_engineering');
    eng.innerHTML = '';
    const ol = el('ol', 'calib-steps');
    (res.steps || []).forEach(s => ol.appendChild(el('li', '', s)));
    eng.appendChild(ol);
    document.getElementById('warnings_section').hidden = true;
    renderPartsList(res.parts);
    document.getElementById('viewer_side').hidden = false;
    renderCalibrationInputs(res.calibration);
    document.getElementById('btn_export_all').disabled = false;
    document.getElementById('btn_export_step').disabled = false;
    hideProgress();
  } catch (err) {
    hideProgress();
    alert(`${tr('errorPrefix', 'Hata')}: ${err && err.message ? err.message : err}`);
  }
}

function setExportStatus(text, folder) {
  const st = document.getElementById('export_status');
  st.innerHTML = '';
  st.appendChild(el('span', 'export-status-text', text));
  if (folder) {
    const a = el('button', 'link-btn', tr('openFolder', 'Klasörü Aç'));
    a.addEventListener('click', () => Host.call('open_path', folder));
    st.appendChild(a);
  }
}

async function exportAll() {
  showProgress(tr('progressExport', 'STEP ve STL dosyaları yazılıyor...'), null);
  try {
    const r = await Host.call('export_all');
    hideProgress();
    if (r && r.success) {
      lastExportFolder = r.folder;
      setExportStatus(`✓ ${tr('exportDone', 'Kaydedildi')}: ${r.folder}`, r.folder);
    } else if (r && !r.cancelled) {
      alert(`${tr('errorPrefix', 'Hata')}: ${r.error}`);
    }
  } catch (err) {
    hideProgress();
    alert(`${tr('errorPrefix', 'Hata')}: ${err}`);
  }
}

async function exportStep() {
  const r = await Host.call('export_step');
  if (r && r.success) {
    setExportStatus(`✓ STEP: ${r.path}`, null);
  } else if (r && !r.cancelled) {
    alert(`${tr('errorPrefix', 'Hata')}: ${r.error}`);
  }
}

async function chooseExportDir() {
  const r = await Host.call('choose_export_dir');
  if (r && r.success) setExportStatus(`${tr('exportTarget', 'Dışa aktarma klasörü')}: ${r.export_dir}`);
}

/* ─── Kinematics: turn the input, every gear follows ─────────────────────── */
let kinTimer = null;
let kinBusy = false;
let kinOutputFactor = 0;

function initKinematicsBar(outputFactor) {
  kinOutputFactor = outputFactor || 0;
  const bar = document.getElementById('kin_bar');
  bar.hidden = false;
  if (Host.isStandalone()) {
    document.querySelector('.viewer-toolbar').appendChild(bar);
    window.GearViewer.onAngle((th, out) => showKinAngle(th));
  }
  if (bar.dataset.ready) { setKinAngle(0); return; }
  bar.dataset.ready = '1';
  const slider = document.getElementById('kin_angle');
  slider.addEventListener('input', () => setKinAngle(parseFloat(slider.value) * Math.PI / 180));
  document.getElementById('kin_play').addEventListener('click', toggleKinPlay);
  setKinAngle(0);
}

function showKinAngle(theta) {
  const deg = theta * 180 / Math.PI;
  document.getElementById('kin_readout').textContent = `${deg.toFixed(0)}° → ${(deg * kinOutputFactor).toFixed(2)}°`;
  const slider = document.getElementById('kin_angle');
  if (document.activeElement !== slider) slider.value = ((deg + 720) % 1440 + 1440) % 1440 - 720;
}

async function setKinAngle(theta) {
  showKinAngle(theta);
  if (Host.isStandalone()) {
    window.GearViewer.setAngle(theta);
  } else if (Host.mode === 'fusion' && !kinBusy) {
    kinBusy = true;
    try { await Host.call('rotate', theta * 180 / Math.PI); } finally { kinBusy = false; }
  }
}

function toggleKinPlay() {
  const btn = document.getElementById('kin_play');
  if (Host.isStandalone()) {
    const on = !window.GearViewer.isPlaying();
    window.GearViewer.setPlaying(on);
    btn.textContent = on ? '⏸' : '▶';
    return;
  }
  if (kinTimer) {
    clearInterval(kinTimer);
    kinTimer = null;
    btn.textContent = '▶';
    return;
  }
  btn.textContent = '⏸';
  let deg = parseFloat(document.getElementById('kin_angle').value) || 0;
  kinTimer = setInterval(() => { if (!kinBusy) { deg += 12; setKinAngle(deg * Math.PI / 180); } }, 80);
}

/* ─── Fusion 360: geometry from the shared engine, imported as a STEP assembly ── */
async function runFusionGeneration(payload) {
  showProgress(tr('progressStart', 'Model hazırlanıyor...'), 2);
  try {
    const res = await Host.call('generate', payload);
    hideProgress();
    if (!res || !res.success) {
      alert(`${tr('errorPrefix', 'Hata')}: ${res ? res.error : '?'}`);
      return;
    }
    lastResult = res;
    if (res.engineering) renderEngineering(document.getElementById('engineering_box'), res.engineering, false);
    const st = document.getElementById('design_status');
    st.innerHTML = '';
    st.appendChild(el('span', '', `✓ ${res.product} · ${res.elapsed} s${res.stl_count != null ? ` · ${res.stl_count} STL` : ''}`));
    if (res.kinematics && res.kinematics.ok) initKinematicsBar(res.kinematics.output_factor);
    else if (res.kinematics && res.kinematics.error) {
      st.appendChild(el('span', 'kin-fail', ` · ${tr('kinFusionFail', 'Hareket bağlantıları kurulamadı')}: ${res.kinematics.error}`));
    }
    if (res.parts && res.summary) renderResult(res, null);
    const actions = document.getElementById('engine_actions');
    actions.innerHTML = '';
    [[tr('openReport', 'Raporu Aç'), res.report], [tr('openFolder', 'Klasörü Aç'), res.folder]].forEach(([label, path]) => {
      if (!path) return;
      const b = el('button', 'btn btn-secondary btn-sm', label);
      b.addEventListener('click', () => Host.call('open_path', path));
      actions.appendChild(b);
    });
    const tabBtn = document.getElementById('tab_btn_results');
    tabBtn.hidden = false;
    tabBtn.click();
  } catch (err) {
    hideProgress();
    alert(`${tr('errorPrefix', 'Hata')}: ${err && err.message ? err.message : err}`);
  }
}

/* ─── Standalone design engine (Python core/design.py) ─────────────────────── */
let designTimer = null;
let designSeq = 0;

function val(id, fallback) {
  const e = document.getElementById(id);
  if (!e) return fallback;
  if (e.type === 'checkbox') return e.checked;
  if (e.type === 'number') { const v = parseFloat(e.value); return isNaN(v) ? fallback : v; }
  return e.value;
}

function collectParams() {
  return {
    action: 'generate_gearbox',
    target_ratio: val('target_ratio', 25),
    stages_count: (v => v === 'AUTO' ? 'AUTO' : (parseInt(v, 10) || 2))(val('stages_count', '2')),
    ratio_from_load: val('ratio_from_load', false),
    num_planets: val('num_planets', 'AUTO'), module: val('module', 1.0),
    sizing_mode: val('sizing_mode', 'AUTO'), max_od: val('max_od', 80), ratio_tol: val('ratio_tol', 3),
    strength_required: val('strength_required', true),
    is_herringbone: document.querySelector('input[name="gear_type"]:checked').value === 'HERRINGBONE',
    gear_type: document.querySelector('input[name="gear_type"]:checked').value,
    helix_angle: val('helix_angle', 20), face_width: val('face_width', 12), pressure_angle: val('pressure_angle', 20),
    addendum_coef: val('addendum_coef', 1.0),
    profile_shift: val('profile_shift', 'AUTO') === 'CUSTOM' ? val('profile_shift_x', 0) : val('profile_shift', 'AUTO'),
    load_value: val('load_value', 0), load_unit: val('load_unit', 'KG'), load_radius: val('load_radius', 0),
    motor_preset: val('motor_preset', 'NEMA17'), motor_shaft_dia: val('motor_shaft_dia', 5),
    motor_shaft_type: val('motor_shaft_type', 'D_CUT'), motor_torque: val('motor_torque', 0.4),
    motor_speed: val('motor_speed', 300), bearing_type: val('bearing_type', 'AUTO'),
    bearing_layout: val('bearing_layout', 'AUTO'), pin_type: val('pin_type', 'STEEL'),
    circlip_type: val('circlip_type', 'DIN_471'), generate_circlips: val('generate_circlips', true),
    pin_dia: val('pin_dia', 5), carrier_type: val('carrier_type', 'CAGE'), output_type: val('output_type', 'FLANGE'),
    generate_housing: val('generate_housing', true), output_shaft_dia: val('output_shaft_dia', 8),
    output_shaft_len: val('output_shaft_len', 20), carrier_thick: val('carrier_thick', 4),
    max_length: val('max_length', 0), bed_x: val('bed_x', 256), bed_y: val('bed_y', 256), bed_z: val('bed_z', 256),
    fit_bed: val('fit_bed', true), hub_fastener: val('hub_fastener', 'NUT'),
    slicer_profile: val('slicer_profile', ''), mount_type: val('mount_type', ''), expert_mode: val('expert_mode', false), ambient_temp: val('ambient_temp', 23),
    duty_pct: val('duty_pct', 100), lubrication: val('lubrication', 'GREASE'), hold_hours: val('hold_hours', 0), declutch: val('declutch', false),
    footprint_limit: val('fit_bed', true) ? Math.min(val('bed_x', 256), val('bed_y', 256)) : 0,
    out_hub: val('out_hub', 'AUTO'), arm_shape: val('arm_shape', 'FLAT'), arm_length: val('arm_length', 100),
    arrangement: val('arrangement', 'CARRIER'), rope_dia: val('rope_dia', 4),
    drive_torque: val('drive_torque', 5), drive_speed: val('drive_speed', 60),
    arm_width: val('arm_width', 30), arm_thickness: val('arm_thickness', 8),
    wall_thickness: val('wall_thickness', 3), tie_rod: val('tie_rod', 'AUTO'), mfg_preset: val('mfg_preset', 'FDM_3D'),
    backlash: val('backlash', 0.22), bearing_tolerance: val('bearing_tolerance', 0.08),
    pin_tolerance: val('pin_tolerance', 0.0), gear_material: val('gear_material', 'PLA'),
    struct_material: val('struct_material', 'PLA'), app_factor: val('app_factor', 1.25),
    target_sf: val('target_sf', 1.4), target_sh: val('target_sh', 1.0), target_life: val('target_life', 2000),
    lang: currentLang
  };
}

const DRUM_OUTPUTS = ['DRUM_FLANGE', 'DRUM_ARM', 'DRUM_WINCH'];

/* Arrangement: only the output members of that arrangement are offered (core.design.normalize_output) */
function syncOutputOptions(arrangement) {
  const sel = document.getElementById('output_type');
  if (!sel) return;
  const ring = arrangement === 'RING' || arrangement === 'WOLFROM';
  const wolfrom = arrangement === 'WOLFROM', cycloid = arrangement === 'CYCLOID';
  [...sel.options].forEach(o => {
    const ok = ring === DRUM_OUTPUTS.includes(o.value) && !(wolfrom && o.value === 'DRUM_WINCH')
      && !(cycloid && !['FLANGE', 'ARM'].includes(o.value));
    o.hidden = !ok;
    o.disabled = !ok;
  });
  if (sel.selectedOptions[0] && sel.selectedOptions[0].disabled) {
    const map = ring ? { ARM: 'DRUM_ARM' } : { DRUM_ARM: 'ARM', DRUM_WINCH: cycloid ? 'FLANGE' : 'SHAFT_PRINTED' };
    sel.value = map[sel.value] || (ring ? 'DRUM_FLANGE' : 'FLANGE');
  }
}

function updateVisibility() {
  const standalone = Host.hasEngine();
  const mode = val('sizing_mode', 'AUTO');
  const show = (id, on) => { const e = document.getElementById(id); if (e) e.style.display = on ? '' : 'none'; };
  show('group_max_od', standalone && mode === 'MAX_OD');
  show('group_module', !standalone || mode === 'MANUAL');
  const arrangement = standalone ? val('arrangement', 'CARRIER') : 'CARRIER';
  const wolfrom = arrangement === 'WOLFROM', cycloid = arrangement === 'CYCLOID', special = wolfrom || cycloid;
  const ring = arrangement === 'RING' || wolfrom, speedUp = arrangement === 'SPEED_UP';
  syncOutputOptions(arrangement);
  const outType = val('output_type', 'FLANGE');
  const armOut = outType === 'ARM' || outType === 'DRUM_ARM';
  const hint = document.getElementById('hint_arrangement');
  if (hint) {
    hint.textContent = wolfrom ? tr('hintArrWolfrom', '') : cycloid ? tr('hintArrCycloid', '') : ring ? tr('hintArrRing', '')
      : (speedUp ? tr('hintArrSpeedUp', '') : tr('hintArrCarrier', ''));
  }
  // Wolfrom: one stepped-planet stage, spur teeth, cage carrier, output support chosen by the engine
  ['group_stages', 'group_carrier_type', 'group_profile_shift'].forEach(id => show(id, !special));
  show('group_gear_type', !cycloid);
  show('group_helix_angle', !special);
  show('group_output_dia', !standalone || (!ring && outType !== 'FLANGE' && outType !== 'ARM'));
  show('group_out_hub', standalone && !special && (ring || outType === 'FLANGE' || outType === 'ARM'));
  show('group_hub_fastener', standalone && !special && ['FLANGE', 'ARM', 'DRUM_FLANGE', 'DRUM_ARM'].includes(outType));
  show('group_arm', standalone && armOut);
  show('group_declutch', standalone && ((['ARM', 'FLANGE'].includes(outType) && ['CARRIER', 'CYCLOID'].includes(arrangement))
    || (['DRUM_ARM', 'DRUM_FLANGE'].includes(outType) && ['RING', 'WOLFROM'].includes(arrangement))));
  show('group_arm_thickness', val('arm_shape', 'FLAT') === 'FLAT');
  show('group_output_len', !standalone || outType === 'SHAFT_PRINTED' || outType === 'SHAFT_STEEL');
  show('group_rope_dia', standalone && outType === 'DRUM_WINCH');
  // speed-up: the drive (crank / rotor) replaces the motor torque and speed, no application load
  show('group_drive_torque', standalone && speedUp);
  show('group_drive_speed', standalone && speedUp);
  show('group_motor_torque', standalone && !speedUp);
  show('group_motor_speed', standalone && !speedUp);
  show('group_load_value', standalone && !speedUp);
  // the drum bearing takes the place of the output hub choice
  const hubLbl = document.querySelector('label[for="out_hub"]');
  if (hubLbl) hubLbl.textContent = ring ? tr('labelDrumBearing', 'Tambur Rulmanı') : tr('labelOutHub', 'Çıkış Göbeği / Rulmanı');
  const hubAuto = document.querySelector('#out_hub option[value="AUTO"]');
  if (hubAuto) hubAuto.textContent = ring ? tr('drumBearingAuto', 'Otomatik') : tr('outHubAuto', 'Otomatik');
  const hubHint = document.querySelector('#group_out_hub .field-hint');
  if (hubHint) hubHint.textContent = ring ? tr('hintDrumBearing', '') : tr('hintOutHub', '');
  const housing = document.getElementById('generate_housing');
  if (housing) {
    housing.disabled = standalone && ring;
    if (standalone && ring) housing.checked = true;
    housing.closest('.form-group').title = standalone && ring ? tr('hintHousingRing', '') : '';
  }
  // application load: a torque needs no lever arm; with an arm output 0 means "the arm length"
  show('group_load_radius', standalone && !speedUp && val('load_unit', 'KG') !== 'NM');
  const hintR = document.getElementById('hint_load_radius');
  if (hintR) {
    hintR.textContent = armOut
      ? tr('hintLoadRadiusArm', 'Kol çıkışında 0 = kol boyu ({L} mm); kuvvet kolun başka bir noktasına etkiyorsa o uzaklığı girin.')
        .replace('{L}', val('arm_length', 100))
      : (outType === 'DRUM_WINCH' ? tr('hintLoadRadiusWinch', '')
        : tr('hintLoadRadius', 'Makara / tambur / tekerlek yarıçapı ya da kuvvetin eksene uzaklığı.'));
  }
  const single = val('carrier_type', 'CAGE') === 'SINGLE';
  document.querySelectorAll('.single-carrier-only').forEach(e => { e.style.display = (!standalone || single) ? '' : 'none'; });
  show('group_shift_x', standalone && val('profile_shift', 'AUTO') === 'CUSTOM');
  show('group_mount', standalone);
  const hcard = document.getElementById('card_helical');
  if (hcard) {
    // tooth types per arrangement: Wolfrom (stepped planets) only spur / HCR, cycloidal has no teeth
    const allowed = !standalone ? ['HERRINGBONE', 'HELICAL', 'HCR', 'SPUR']
      : (wolfrom ? ['HCR', 'SPUR'] : (cycloid ? [] : ['HERRINGBONE', 'HELICAL', 'HCR', 'SPUR']));
    document.querySelectorAll('input[name="gear_type"]').forEach(r => {
      const ok = allowed.includes(r.value);
      r.closest('label').style.display = ok ? '' : 'none';
      if (!ok && r.checked) { document.querySelector('input[name="gear_type"][value="SPUR"]').checked = true; }
    });
  }
  const expert = standalone && val('expert_mode', false);
  document.querySelectorAll('.expert-only').forEach(e => { e.style.display = expert ? '' : 'none'; });
  const lifeLbl = document.querySelector('label[for="target_life"]');
  if (lifeLbl) lifeLbl.textContent = expert ? tr('labelTargetLifeExpert', 'Hedef Ömür') : tr('labelTargetLife', 'Hedef Rulman Ömrü L10h');
  if (special) show('group_shift_x', false);
  updateRatioStageHints(standalone, speedUp);
}

/* Ratio from the load / automatic stage count: what the engine chose (res.auto) under the two fields */
let lastAuto = null;

function updateRatioStageHints(standalone, speedUp) {
  const fromLoad = standalone && !speedUp && val('ratio_from_load', false);
  const hasLoad = val('load_value', 0) > 0;
  const ratioEl = document.getElementById('target_ratio');
  if (ratioEl) {
    ratioEl.disabled = fromLoad && hasLoad;
    ratioEl.title = ratioEl.disabled ? tr('hintRatioFromLoad', '') : '';
  }
  const grp = document.getElementById('group_ratio_from_load');
  if (grp) grp.style.display = standalone && !speedUp ? '' : 'none';
  const auto = lastAuto;
  const rh = document.getElementById('hint_target_ratio');
  if (rh) {
    if (fromLoad && !hasLoad) rh.textContent = tr('hintRatioFromLoadNoLoad', 'Önce aşağıda uygulama yükünü (ve kuvvet kolunu) girin.');
    else if (fromLoad && auto && auto.from_load) {
      if (ratioEl) ratioEl.value = auto.ratio.toFixed(1);       // the field shows the ratio in use (kept when unticked)
      rh.textContent = tr('ratioFromLoadResult', 'Yükten: en az {min}:1 → aranan {sel}:1 ({n} kademe)')
        .replace('{min}', auto.min_ratio.toFixed(1)).replace('{sel}', auto.ratio.toFixed(1)).replace('{n}', auto.stages);
    } else if (fromLoad) rh.textContent = tr('hintRatioFromLoad', '');
    else rh.textContent = tr('hintTargetRatio', 'Örn: 25 yazarsanız hızı 25 kat düşürür, torku ~24 kat artırır.');
  }
  const sh = document.getElementById('hint_stages');
  if (sh) {
    const sv = val('stages_count', '2');
    if (sv === 'AUTO') {
      sh.textContent = auto && auto.auto_stages
        ? tr('stagesAutoResult', 'Seçilen: {n} kademe — ayrıntı durum satırında.').replace('{n}', auto.stages)
        : tr('hintStagesAuto', '');
    } else if (sv === '4' || sv === '5') {
      sh.textContent = tr('hintStagesMany', '');
    } else sh.textContent = '';
  }
}

function initStandaloneForm() {
  // defaults for the engineering-driven workflow
  const helix = document.getElementById('helix_angle');
  if (helix && parseFloat(helix.value) === 25) helix.value = '20.0';
  document.getElementById('motor_preset').dispatchEvent(new Event('change'));
  Host.call('get_catalogs').then(cat => {
    if (!cat || !cat.success) return;
    const bSel = document.getElementById('bearing_type');
    const keep = bSel.value;
    bSel.innerHTML = '';
    const auto = document.createElement('option');
    auto.value = 'AUTO';
    auto.textContent = tr('bearingAuto', 'Otomatik — planete sığan en yüksek kapasite');
    bSel.appendChild(auto);
    cat.bearings.forEach(b => {
      const o = document.createElement('option');
      o.value = b.code;
      o.textContent = b.code === 'CUSTOM_PIN' ? tr('bearingCustomPin', b.name)
        : `${b.code} (Ø${b.d} × Ø${b.D} × ${b.B} mm · C ${b.C.toFixed(2)} kN)`;
      bSel.appendChild(o);
    });
    bSel.value = 'AUTO';
    if (keep && keep !== '688ZZ') bSel.value = keep;
    const hSel = document.getElementById('out_hub');
    if (hSel) {
      cat.bearings.filter(b => b.code !== 'CUSTOM_PIN' && b.d >= 8).sort((a, b) => a.d - b.d || a.D - b.D).forEach(b => {
        const o = document.createElement('option');
        o.value = b.code;
        o.textContent = `Ø${b.d} ${tr('hubWord', 'göbek')} — ${b.code} (Ø${b.D} × ${b.B} mm)`;
        hSel.appendChild(o);
      });
    }
    ['gear_material', 'struct_material'].forEach(id => {
      const sel = document.getElementById(id);
      sel.innerHTML = '';
      cat.materials.forEach(m => {
        const o = document.createElement('option');
        o.value = m.code;
        o.textContent = m.name;
        sel.appendChild(o);
      });
      sel.value = 'PLA';
    });
    Object.entries(cat.motors || {}).forEach(([code, m]) => {
      if (MOTOR_PRESETS[code]) { MOTOR_PRESETS[code].torque = m.torque; MOTOR_PRESETS[code].speed = m.speed; }
    });
    scheduleDesign(0);
  }).catch(() => scheduleDesign(0));

  initBedPreset();
  const form = document.querySelector('.tab-content-wrapper');
  form.addEventListener('input', (e) => { if (e.target.id !== 'candidate_select') scheduleDesign(); });
  form.addEventListener('change', (e) => { updateVisibility(); if (e.target.id !== 'candidate_select') scheduleDesign(); });
  document.querySelectorAll('.radio-card').forEach(c => c.addEventListener('click', () => scheduleDesign()));
  initCalibration();
  updateVisibility();
}

/* Print bed: presets fill X/Y/Z; the choice is remembered on this computer */
function initBedPreset() {
  const sel = document.getElementById('bed_preset');
  if (!sel || sel.dataset.ready) return;
  sel.dataset.ready = '1';
  const ids = ['bed_x', 'bed_y', 'bed_z'];
  const apply = (v) => {
    if (v === 'CUSTOM') return;
    v.split(',').forEach((n, i) => { document.getElementById(ids[i]).value = n; });
  };
  try {
    const saved = JSON.parse(localStorage.getItem('pgb_bed') || 'null');
    if (saved && saved.preset) {
      sel.value = saved.preset;
      if (saved.preset === 'CUSTOM') ids.forEach((id, i) => { document.getElementById(id).value = saved.xyz[i]; });
      else apply(saved.preset);
    }
  } catch (e) {}
  const remember = () => {
    try {
      localStorage.setItem('pgb_bed', JSON.stringify({ preset: sel.value, xyz: ids.map(id => document.getElementById(id).value) }));
    } catch (e) {}
  };
  sel.addEventListener('change', () => {
    apply(sel.value);
    remember();
    const sp = document.getElementById('slicer_profile');      // the K1 Max bed brings its slicer profile
    if (sp && sel.value === '300,300,300' && !sp.value) sp.value = 'creality k1 max';
  });
  ids.forEach(id => document.getElementById(id).addEventListener('input', () => { sel.value = 'CUSTOM'; remember(); }));
}

function scheduleDesign(delay) {
  if (designTimer) clearTimeout(designTimer);
  designTimer = setTimeout(requestDesign, delay === undefined ? 350 : delay);
  const st = document.getElementById('design_status');
  if (st) st.textContent = tr('designing', 'Tasarım hesaplanıyor...');
}

let designHint = null;

async function requestDesign() {
  const seq = ++designSeq;
  const params = collectParams();
  if (window.pendingApply && window.pendingApply.pin) {
    params.pin_stages = window.pendingApply.pin.stages;
    params.pin_module = window.pendingApply.pin.module;
  }
  let res;
  try {
    res = await Host.call('design', params);
  } catch (e) {
    return;
  }
  if (seq !== designSeq || !res) return;
  currentCandidates = res.success ? (res.candidates || []) : [];
  // the search's advice (relaxed ratio, planet count, a too weak fixed part) stays in front of the status;
  // an automatic stage count / ratio from the load says what it chose before that
  lastAuto = res.success && res.auto ? res.auto : null;
  updateRatioStageHints(Host.hasEngine(), val('arrangement', 'CARRIER') === 'SPEED_UP');
  const hintText = [lastAuto ? lastAuto.note : '', res.success && res.hint ? res.hint : ''].filter(Boolean).join(' · ');
  designHint = hintText ? { text: hintText, kind: (res.success && res.hint_kind) || '' } : null;
  selectedCandidateIndex = 0;
  const selectEl = document.getElementById('candidate_select');
  selectEl.innerHTML = '';
  const badge = document.getElementById('calc_status_badge');
  const st = document.getElementById('design_status');
  if (!currentCandidates.length) {
    const opt = document.createElement('option');
    opt.text = tr('noCandidate', 'Uygun diş kombinasyonu bulunamadı');
    selectEl.appendChild(opt);
    badge.className = 'badge badge-info';
    badge.innerText = tr('calcBadgeWarn', '⚠️ Oran / Diş Ayarı Gerekli');
    st.textContent = res.success ? (hintText || tr('designNone', 'Bu ayarlarla çözüm yok: oran toleransını, dış çapı veya malzemeyi değiştirin.')) : res.error;
    renderEngineering(document.getElementById('engineering_box'), null, false);
    renderLoadVerdict(null);
    setLoadMetric(null);
    return;
  }
  currentCandidates.forEach((c, idx) => {
    const opt = document.createElement('option');
    opt.value = idx;
    opt.text = `#${idx + 1}: ${c.feasible ? '✓' : '⚠'} ${c.label}${c.load ? ` · ${tr('loadWord', 'yük')} ${c.load.short}` : ''}`;
    selectEl.appendChild(opt);
  });
  const best = currentCandidates[0];
  badge.className = best.feasible ? 'badge badge-success' : 'badge badge-info';
  badge.innerText = best.feasible ? tr('badgeFeasible', '✓ Geometri + dayanım uygun') : tr('badgeWeak', '⚠ Dayanım hedefi sağlanamadı');
  st.textContent = `${hintText ? hintText + ' ' : (res.relaxed_tolerance ? tr('designRelaxed', 'Tolerans içinde çözüm yok, en yakın oranlar gösteriliyor. ') : '')}`
    + `${currentCandidates.length} ${tr('designFound', 'aday')} · ${res.elapsed}s`;
  // a proposal from the AI assistant / requirement solver: select the proposed tooth set
  const pending = window.pendingApply;
  window.pendingApply = null;
  let appliedNote = '';
  if (pending) {
    const sigOf = c => c.stages.map(s => `${s.z_sun}/${s.z_planet}/${s.z_ring}`).join('|') + `@${c.module}`;
    const idx = currentCandidates.findIndex(c => sigOf(c) === pending.sig);
    selectedCandidateIndex = Math.max(0, idx);
    selectEl.value = String(selectedCandidateIndex);
    appliedNote = idx >= 0 ? tr('aiApplied', 'AI önerisi uygulandı')
      : tr('aiAppliedNear', 'önerilen kombinasyon listede yok, en uygun aday seçildi');
  }
  updateMetricsDisplay();
  if (appliedNote) st.textContent = `✓ ${appliedNote} · ${st.textContent}`;
  if (pending && pending.generate) setTimeout(() => document.getElementById('btn_generate').click(), 60);
}

function updateStandaloneMetrics(cand) {
  const e = cand.engineering;
  const compact = document.getElementById('calc_compact');
  if (compact) {
    const tqD = e.output_torque < 1 ? 3 : 1;
    compact.textContent = `${cand.total_ratio}:1 · Ø${cand.outer_diameter}×${cand.overall_length ?? '–'} mm · `
      + `${e.reverse ? tr('engGen', 'Jeneratör') + ' ' : ''}${e.output_torque.toFixed(tqD)} / ${e.max_output_torque.toFixed(tqD)} Nm`
      + `${e.reverse ? ` @ ${e.output_speed.toFixed(0)} rpm` : ''} · S ${cand.margin.toFixed(2)} · `
      + `m${cand.module} · ${cand.stages.map(s => s.num_planets).join('/')} planet`
      + (cand.output && cand.output.drum ? ` · ${tr('sumDrum', 'Tambur')} ${cand.output.bearing}` : '')
      + (cand.load ? ` · ${tr('loadWord', 'yük')} ${cand.load.short}` : '');
  }
  const verdict = cand.load || speedupVerdict(e);
  setLoadMetric(verdict);
  renderLoadVerdict(verdict);
  const s1 = cand.stages[0];
  const set = (id, v, title) => { const x = document.getElementById(id); if (x) { x.innerText = v; if (title !== undefined) x.title = title; } };
  set('metric_ratio', `${cand.total_ratio} : 1`);
  set('metric_zs', cand.stages.map(s => s.z_sun).join(' / '),
      `${tr('labelProfileShift', 'Profil kaydırma (x)')}: ${cand.stages.map(s => (s.x_sun >= 0 ? '+' : '') + (s.x_sun || 0).toFixed(2)).join(' / ')}`);
  set('metric_zp', cand.stages.map(s => s.z_planet).join(' / '));
  set('metric_zr', cand.z_ring);
  set('metric_od', `Ø${cand.outer_diameter} mm`, `${tr('sumBody', 'Gövde')} Ø${cand.housing_diameter} mm · ${cand.tie_rod}`);
  const st0 = e.stages[0];
  set('metric_contact', (st0.eps_alpha_sp + st0.eps_beta).toFixed(2),
      `εα ${st0.eps_alpha_sp.toFixed(2)} / ${st0.eps_alpha_pr.toFixed(2)} + εβ ${st0.eps_beta.toFixed(2)}`);
  const outTq = document.getElementById('metric_out_torque');
  if (outTq && outTq.previousElementSibling) {
    outTq.previousElementSibling.textContent = e.reverse ? tr('metricGenTorque', 'Jeneratör Torku / Kapasite')
      : tr('metricOutTorque', 'Çıkış Torku / Kapasite');
  }
  const tqDigits = e.output_torque < 1 ? 3 : 1;
  set('metric_out_torque', `${e.output_torque.toFixed(tqDigits)} / ${e.max_output_torque.toFixed(tqDigits)} Nm`,
      `${tr('metricOutTip', 'Nominal çıkış / sürekli taşınabilir')} · ${e.output_speed.toFixed(1)} rpm · η ${(e.efficiency * 100).toFixed(1)}%`);
  const sf = document.getElementById('metric_safety');
  sf.innerText = `${cand.margin.toFixed(2)}`;
  sf.style.color = cand.margin >= 1 ? 'var(--accent-green)' : (cand.margin >= 0.7 ? 'var(--accent-gold)' : 'var(--accent-red)');
  sf.title = e.limiting ? `${tr('limitedBy', 'Sınırlayan')}: ${e.limiting.label} (K${e.limiting.stage})` : '';
  const bearings = [...new Set(cand.stages.map(s => s.bearing))].join('/');
  set('metric_module', `m${cand.module} · ${bearings}`, cand.stages.map((s, i) => `K${i + 1}: ${s.bearing} ${s.bearing_layout}`).join('\n'));
  const lenEl = document.getElementById('metric_length');
  if (lenEl && cand.overall_length != null) {
    lenEl.innerText = `${cand.overall_length} mm`;
    lenEl.style.color = cand.length_ok === false ? 'var(--accent-red)' : '';
    lenEl.title = `${tr('sumBody', 'Gövde')}: ${cand.body_length} mm`;
  }
  const out = cand.output || {};
  const hubEl = document.getElementById('metric_out_hub');
  if (hubEl && hubEl.previousElementSibling) {
    hubEl.previousElementSibling.textContent = out.drum ? tr('metricDrum', 'Tambur / Rulman') : tr('metricOutHub', 'Çıkış Göbeği');
  }
  if (hubEl) {
    const isHub = out.type === 'FLANGE' || out.type === 'ARM';
    hubEl.innerText = out.drum ? `Ø${(out.drum_od || 0).toFixed(0)} · ${out.bearing}`
      : (isHub ? `Ø${out.hub_d} · ${out.bearing}` : `Ø${out.shaft_d} · ${out.bearing}`);
    hubEl.style.color = out.strong === false ? 'var(--accent-red)' : '';
    hubEl.title = `${tr('outputNeed', 'Gereken')} ≥ Ø${cand.required_output_dia} mm` +
      (out.strong === false && out.suggest ? ` → ${out.suggest}` : '');
  }
  const bedEl = document.getElementById('metric_bed');
  if (bedEl) {
    bedEl.innerText = cand.bed_ok === false ? tr('bedNo', '✗ büyük') : tr('bedYes', '✓ sığar');
    bedEl.style.color = cand.bed_ok === false ? 'var(--accent-gold)' : 'var(--accent-green)';
  }
  updateHubOptions(out);

  const elPB = document.getElementById('ratio_planet_bearing');
  const dPlanet = cand.module * s1.z_planet;
  const bd = (s1.pocket_dia || 0) - (parseFloat(document.getElementById('bearing_tolerance').value) || 0);
  if (elPB && bd > 0) {
    const r = dPlanet / bd;
    elPB.innerText = `${r.toFixed(2)}x · ${s1.bearing}`;
    elPB.style.color = r >= 1.8 ? '#38bdf8' : (r >= 1.5 ? '#f59e0b' : '#ef4444');
  }
  const elSS = document.getElementById('ratio_shaft_sun');
  if (elSS) {
    const shaft = parseFloat(document.getElementById('motor_shaft_dia').value) || 5.0;
    const ha = s1.addendum || 1.0;                       // root diameter = m (z - 2 (h_a* + 0.157))
    const root = Math.max(1, cand.module * (s1.z_sun - 2 * (ha + 0.157)));
    const pct = Math.round(shaft / root * 100);
    elSS.innerText = `%${pct}`;
    elSS.style.color = pct <= 65 ? '#38bdf8' : (pct <= 85 ? '#f59e0b' : '#ef4444');
  }
  renderEngineering(document.getElementById('engineering_box'), e, false);
  const st = document.getElementById('design_status');
  if (st && e.limiting) {
    const issues = (cand.issues || []).filter(i => i !== 'strength');
    let txt = `${tr('limitedBy', 'Sınırlayan')}: ${e.limiting.label} (K${e.limiting.stage})`;
    if (designHint) txt = `${designHint.text} · ${txt}`;
    if (issues.includes('output') && !(designHint && designHint.kind === 'weak_part')) {
      txt += ` · ${tr('outputWeak', 'Çıkış elemanı zayıf, gereken Ø')}${cand.required_output_dia} mm`;
      if (out.suggest) txt += ` → ${out.suggest}${out.suggest_fits ? '' : ` (${tr('hubGrow', 'gövde büyümeli')} ~Ø${out.suggest_od})`}`;
    }
    if (issues.includes('length')) txt += ` · ${tr('lengthOver', 'Boy sınırı aşıldı')} (${cand.overall_length} mm)`;
    // long teeth: say right away when the extra depth is topped off or the tips get too thin to print
    const longT = cand.stages.filter(s => (s.addendum || 1) > 1.0001);
    if (longT.length) {
      const ha = longT[0].addendum;
      const topped = longT.find(s => Math.min(s.eff_addendum_sun ?? ha, s.eff_addendum_planet ?? ha) < ha - 0.05);
      const land = Math.min(...longT.map(s => s.tip_land ?? 1));
      if (topped) {
        txt += ` · ${tr('depthTopped', 'uçlar kırpıldı, etkin h*a')}: ${tr('sunWord', 'güneş')} ${topped.eff_addendum_sun.toFixed(2)}`
          + ` / ${tr('planetWord', 'planet')} ${topped.eff_addendum_planet.toFixed(2)}`;
      }
      if (val('mfg_preset', 'FDM_3D') === 'FDM_3D' && land < 0.4) {
        txt += ` · ${tr('tipThin', 'diş ucu FDM için ince')}: ${land.toFixed(2)} mm`;
      }
    }
    st.textContent = txt;
  }
}

/* Speed-up gearbox: what the generator gets (and start-up / ratio cautions) in the verdict box */
function speedupVerdict(e) {
  if (!e || !e.speedup) return null;
  const s = e.speedup;
  return { status: s.status, short: `${tr('engGen', 'Jeneratör')} ${s.generator_speed.toFixed(0)} rpm · ${s.power_w.toFixed(1)} W`,
           text: s.text, summary: s.text, fixes: [] };
}

/* Application load: "can this gearbox move my load?" — metric in the summary card + verdict box with the options */
function setLoadMetric(lv) {
  const m = document.getElementById('metric_load');
  if (!m) return;
  m.classList.remove('load-ok', 'load-low', 'load-fail', 'load-incomplete');
  if (lv) {
    m.innerText = lv.short;
    m.classList.add(`load-${lv.status}`);
    m.title = lv.text;
  } else {
    m.innerText = '–';
    m.title = tr('loadNoneTip', '1. sekmede uygulama yükünü girerseniz tasarımın uygun olup olmadığı burada görünür.');
  }
}

function renderLoadVerdict(lv) {
  const box = document.getElementById('load_verdict');
  if (!box) return;
  box.innerHTML = '';
  box.className = 'load-verdict standalone-only' + (lv ? ` ${lv.status}` : '');
  box.hidden = !lv;
  if (!lv) return;
  box.appendChild(el('div', '', lv.summary || lv.text));
  if (lv.fixes && lv.fixes.length) {
    box.appendChild(el('div', 'load-verdict-head', `${tr('loadFixes', 'Seçenekler')}:`));
    const ul = el('ul', 'load-verdict-fixes');
    lv.fixes.forEach(f => ul.appendChild(el('li', '', f)));
    box.appendChild(ul);
  }
}

/* Output hub list: mark which hubs fit this housing and which are strong enough */
function updateHubOptions(out) {
  const sel = document.getElementById('out_hub');
  if (!sel || !out || !out.hub_options) return;
  const byCode = {};
  out.hub_options.forEach(o => { byCode[o.code] = o; });
  [...sel.options].forEach(opt => {
    const o = byCode[opt.value];
    if (!opt.dataset.base) opt.dataset.base = opt.textContent;
    if (!o) return;
    const tag = !o.fits ? tr('hubNoFit', 'sığmaz') : (o.strong ? tr('hubOk', '✓ uygun') : tr('hubWeak', 'zayıf'));
    opt.textContent = `${opt.dataset.base} · ${tag}`;
  });
}

function renderEngineering(box, eng, compact) {
  if (!box) return;
  box.innerHTML = '';
  if (!eng) return;
  if (!compact) {
    const head = el('div', 'eng-head');
    if (eng.reverse) {
      head.appendChild(el('span', '', `${tr('engDrive', 'Giriş')}: ${eng.input_torque.toFixed(2)} Nm @ ${eng.input_speed.toFixed(1)} rpm`));
      head.appendChild(el('span', '', `${tr('engGen', 'Jeneratör')}: ${eng.output_torque.toFixed(3)} Nm @ ${eng.output_speed.toFixed(0)} rpm`));
      head.appendChild(el('span', '', `${tr('engCap', 'Sürekli kapasite')}: ${(eng.max_input_torque || 0).toFixed(2)} Nm`));
    } else {
      head.appendChild(el('span', '', `${tr('engOut', 'Çıkış')}: ${eng.output_torque.toFixed(2)} Nm @ ${eng.output_speed.toFixed(1)} rpm`));
      head.appendChild(el('span', '', `${tr('engCap', 'Sürekli kapasite')}: ${eng.max_output_torque.toFixed(2)} Nm`));
    }
    head.appendChild(el('span', '', `η ${(eng.efficiency * 100).toFixed(1)}%`));
    box.appendChild(head);
  }
  const verdict = eng.load || speedupVerdict(eng);
  if (verdict) {
    const lv = el('div', `load-verdict ${verdict.status}`, compact ? verdict.short : (verdict.summary || verdict.text));
    lv.title = verdict.text;
    box.appendChild(lv);
  }
  eng.stages.forEach(st => {
    const t = el('div', 'eng-stage');
    const title = el('div', 'eng-stage-title', `${tr('stageWord', 'Kademe')} ${st.index} · i ${st.ratio.toFixed(2)} · T ${st.input_torque.toFixed(2)}→${st.output_torque.toFixed(2)} Nm`
      + (st.k_hbeta ? ` · K_Hβ ${st.k_hbeta.toFixed(2)}` : '')
      + (st.expert ? ` · ${tr('engTemp', 'diş')} ${st.expert.temp.toFixed(0)} °C` : ''));
    if (st.k_hbeta) {
      title.title = tr('khbTip', 'Yük dağılımı: diş genişliği boyunca yük eşit değil (pim eğikliği {f} µm). 1.0 = eşit; 2 üstü dişin bir kısmı yük taşımıyor.')
        .replace('{f}', st.misalignment_um.toFixed(1));
      if (st.k_hbeta >= 1.8) title.classList.add('eng-warn');
    }
    t.appendChild(title);
    st.checks.forEach(c => {
      const r = el('div', 'eng-row' + (c.ok ? '' : ' bad'));
      r.appendChild(el('span', 'eng-name', c.label));
      const v = c.unit === 'h' ? `${Math.round(c.value).toLocaleString()} h`
        : (c.unit === 'mm' ? `${c.value.toFixed(2)} mm` : (c.unit ? `${c.value.toFixed(1)} ${c.unit}` : c.value.toFixed(2)));
      r.appendChild(el('span', 'eng-val', v));
      const sEl = el('span', 'eng-s', `S ${c.safety >= 100 ? '>99' : c.safety.toFixed(2)}`);
      r.appendChild(sEl);
      t.appendChild(r);
    });
    box.appendChild(t);
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
