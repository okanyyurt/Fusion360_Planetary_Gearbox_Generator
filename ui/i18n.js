/**
 * Internationalization (i18n) - Turkish & English Language Support
 * Planetary Gearbox Generator UI
 */
window.TRANSLATIONS = {
  tr: {
    // App Header
    appSubtitle: "Parametrik Planet Dişli & Balıksırtı CAD Motoru",
    badgeFusion: "Fusion 360",
    badgeVersion: "v1.0 Pro",

    // Tab Labels
    tabMotor: "Motor & Oran",
    tabGearType: "Dişli & Balıksırtı",
    tabBearings: "Rulman, Mil & Segman",
    tabHousing: "Taşıyıcı & Gövde",
    tabTolerances: "3D Baskı / Tolerans",

    // Tab 1: Motor & Oran
    tab1Title: "Hedef Redüksiyon ve Motor Şaft Girişi",
    labelTargetRatio: "Hedef Hız Düşürme / Tork Artışı Oranı (i)",
    hintTargetRatio: "Örn: 25 yazarsanız hızı 25 kat düşürür, torku ~24 kat artırır.",
    labelStagesCount: "Kademe Sayısı (Stage Count)",
    stage1Label: "1 Kademe (Oran: 3:1 ~ 9:1)",
    stage2Label: "2 Kademe (Oran: 9:1 ~ 80:1)",
    stage3Label: "3 Kademe (Oran: 50:1 ~ 500:1)",
    labelMotorPreset: "Motor Montaj Standardı",
    motorNema17: "NEMA 17 Step Motor (42mm)",
    motorNema23: "NEMA 23 Step Motor (57mm)",
    motorNema34: "NEMA 34 Step Motor (86mm)",
    motor775: "775 DC Motor (44mm)",
    motor540: "540 / 550 RC Motor (36mm)",
    motorCustom: "Özel / Manuel Giriş",
    labelShaftDia: "Motor Şaft Çapı (d_motor)",
    labelShaftType: "Motor Şaft Kesit Tipi",
    shaftDCut: "D-Şaft (Tek Düzlük)",
    shaftRound: "Yuvarlak (Pres-Geçme / Setskur)",
    shaftDoubleD: "Çift D-Şaft (Simetrik Düzlük)",
    shaftKeyway: "Kamalı Şaft (DIN 6885)",
    labelModule: "Dişli Modülü (m)",
    badgeModuleRec: "Öneri: 1.0mm",
    hintModule: "3D Baskı için 0.8mm - 1.5mm idealdir.",
    labelNumPlanets: "Planet Dişli Sayısı (Kademe Başı)",
    planets3: "3 Planet (120° Simetri - En Yaygın)",
    planets4: "4 Planet (90° Simetri - Yüksek Yük)",
    planets5: "5 Planet (72° Simetri - Ağır Hizmet)",

    // Tab 2: Gear Type
    tab2Title: "Dişli Geometrisi ve Balıksırtı (Herringbone) Seçenekleri",
    labelGearType: "Dişli Tipi Tercihi",
    herringboneTitle: "★ Balıksırtı (Herringbone / Çavuş)",
    herringboneDesc: "Zıt açılı çift helis ile eksenel kuvvetleri tamamen sıfırlar. Yüksek tork, sessiz ve 3D baskı için en stabil dişlidir.",
    spurTitle: "Düz Dişli (Spur)",
    spurDesc: "Klasik düz evolvent dişli. İmalatı ve montajı en kolaydır.",
    labelHelixAngle: "Balıksırtı Helis Açısı (β)",
    hintHelixAngle: "Standart: 25° - 30°. Yüksek açı yumuşak kavramayı artırır.",
    labelFaceWidth: "Diş Genişliği (Face Width - b)",
    labelPressureAngle: "Kavrama Açısı (Pressure Angle - α)",
    pa20: "20° (Standart ISO/AGMA)",
    pa25: "25° (3D Baskı / Ağır Yük Diş Kökü)",
    pa14: "14.5° (Hassas / Düşük Boşluk)",

    // Tab 3: Bearings
    tab3Title: "Planet Dişli Yataklama ve Rulman Seçimi",
    labelBearingType: "Planet Yataklama Tipi",
    bearingCustomPin: "Rulmansız (Doğrudan Çelik Pim / Bronz Burç)",
    labelPinDia: "Pim / Mil Çapı (d_pin)",

    // Tab 4: Housing
    tab4Title: "Planet Taşıyıcı (Carrier), Dış Gövde ve Çıkış Şaftı",
    labelGenerateHousing: "Komple Redüktör Gövdesi ve Motor Flanşı Çizilsin",
    hintGenerateHousing: "İşaret kaldırılırsa sadece serbest dişli çarklar ve taşıyıcı çizilir.",
    labelOutputShaftDia: "Redüktör Çıkış Şaft Çapı",
    labelOutputShaftLen: "Çıkış Şaft Uzunluğu",
    labelCarrierThick: "Taşıyıcı Plaka Kalınlığı",

    // Tab 5: Tolerances
    tab5Title: "Üretim Yöntemi, Diş Boşluğu (Backlash) & Toleranslar",
    labelMfgPreset: "Hedef İmalat Yöntemi Preseti",
    mfgFdm: "FDM 3D Yazıcı (PLA / PETG / ABS) - Backlash: 0.22mm",
    mfgSla: "Reçine / SLA 3D Yazıcı - Backlash: 0.12mm",
    mfgCnc: "CNC İşleme / Metal Freze - Backlash: 0.05mm",
    mfgCustom: "Özel Değer Girişi",
    labelBacklash: "Diş Profil Boşluğu (Backlash Clearance)",
    labelBearingTolerance: "Rulman / Pim Yuvası Ofseti",
    hintBearingTolerance: "+ değer yuvaları genişletir (kolay montaj için).",

    // Live Calc Panel
    calcTitle: "📊 Gerçek Zamanlı Dişli & Kinematik Sentezi",
    calcBadgeOk: "✓ Montaj Şartı Doğrulandı",
    calcBadgeWarn: "⚠️ Oran / Diş Ayarı Gerekli",
    metricRatio: "Gerçekleşen Oran",
    metricZs: "Güneş Diş Sayısı (Zs)",
    metricZp: "Planet Diş Sayısı (Zp)",
    metricZr: "Çember Diş Sayısı (Zr)",
    metricOd: "Dış Gövde Çapı",
    metricContact: "Temas Oranı (Overlap)",
    candidateLabel: "Bulunan En Uygun Dişli Kombinasyonları:",
    noCandidate: "Uygun diş kombinasyonu bulunamadı (Oranı veya modülü değiştirin)",

    // Footer Buttons
    btnReset: "Varsayılanlara Sıfırla",
    btnGenerate: "🚀 Fusion 360'ta 3D Çizimi Başlat",

    // Progress
    progressGenerating: "Dişliler oluşturuluyor, lütfen bekleyin...",
    progressWarning: "⚠️ Bu işlem Fusion 360 modeline göre 15-60 saniye sürebilir.",

    // Modal
    modalClose: "✕",
    
    // Language toggle tooltip
    langToggle: "Switch to English"
  },

  en: {
    // App Header
    appSubtitle: "Parametric Planetary Gear & Herringbone CAD Engine",
    badgeFusion: "Fusion 360",
    badgeVersion: "v1.0 Pro",

    // Tab Labels
    tabMotor: "Motor & Ratio",
    tabGearType: "Gear & Herringbone",
    tabBearings: "Bearings, Pin & Circlip",
    tabHousing: "Carrier & Housing",
    tabTolerances: "3D Print / Tolerance",

    // Tab 1: Motor & Ratio
    tab1Title: "Target Reduction Ratio and Motor Shaft Input",
    labelTargetRatio: "Target Speed Reduction / Torque Multiplication Ratio (i)",
    hintTargetRatio: "e.g. Enter 25 to reduce speed 25×, torque multiplied ~24×.",
    labelStagesCount: "Number of Stages",
    stage1Label: "1 Stage (Ratio: 3:1 ~ 9:1)",
    stage2Label: "2 Stages (Ratio: 9:1 ~ 80:1)",
    stage3Label: "3 Stages (Ratio: 50:1 ~ 500:1)",
    labelMotorPreset: "Motor Mounting Standard",
    motorNema17: "NEMA 17 Stepper (42mm)",
    motorNema23: "NEMA 23 Stepper (57mm)",
    motorNema34: "NEMA 34 Stepper (86mm)",
    motor775: "775 DC Motor (44mm)",
    motor540: "540 / 550 RC Motor (36mm)",
    motorCustom: "Custom / Manual Entry",
    labelShaftDia: "Motor Shaft Diameter (d_motor)",
    labelShaftType: "Motor Shaft Cross-Section Type",
    shaftDCut: "D-Cut Shaft (Single Flat)",
    shaftRound: "Round Shaft (Press-fit / Setscrew)",
    shaftDoubleD: "Double D-Cut Shaft (Symmetric Flats)",
    shaftKeyway: "Keyway Shaft (DIN 6885)",
    labelModule: "Gear Module (m)",
    badgeModuleRec: "Suggested: 1.0mm",
    hintModule: "0.8mm - 1.5mm ideal for 3D printing.",
    labelNumPlanets: "Number of Planet Gears (per Stage)",
    planets3: "3 Planets (120° Symmetry - Most Common)",
    planets4: "4 Planets (90° Symmetry - High Load)",
    planets5: "5 Planets (72° Symmetry - Heavy Duty)",

    // Tab 2: Gear Type
    tab2Title: "Gear Geometry and Herringbone Options",
    labelGearType: "Gear Type Preference",
    herringboneTitle: "★ Herringbone (Double Helical / Chevron)",
    herringboneDesc: "Opposing helices cancel axial thrust entirely. High torque, quiet, and the most stable option for 3D printing.",
    spurTitle: "Spur Gear (Straight Teeth)",
    spurDesc: "Classic straight involute gear. Simplest to manufacture and assemble.",
    labelHelixAngle: "Herringbone Helix Angle (β)",
    hintHelixAngle: "Standard: 25° - 30°. Higher angles improve mesh smoothness.",
    labelFaceWidth: "Face Width (b)",
    labelPressureAngle: "Pressure Angle (α)",
    pa20: "20° (ISO/AGMA Standard)",
    pa25: "25° (3D Print / Heavy Load Root Strength)",
    pa14: "14.5° (Precision / Low Backlash)",

    // Tab 3: Bearings
    tab3Title: "Planet Gear Bearing and Pin Selection",
    labelBearingType: "Planet Bearing Type",
    bearingCustomPin: "Bearingless (Direct Steel Pin / Bronze Bushing)",
    labelPinDia: "Pin / Shaft Diameter (d_pin)",

    // Tab 4: Housing
    tab4Title: "Planet Carrier, Outer Housing & Output Shaft",
    labelGenerateHousing: "Generate Complete Gearbox Housing & Motor Flange",
    hintGenerateHousing: "When unchecked, only the free gear set and carrier are drawn.",
    labelOutputShaftDia: "Output Shaft Diameter",
    labelOutputShaftLen: "Output Shaft Length",
    labelCarrierThick: "Carrier Plate Thickness",

    // Tab 5: Tolerances
    tab5Title: "Manufacturing Method, Backlash & Tolerances",
    labelMfgPreset: "Target Manufacturing Method Preset",
    mfgFdm: "FDM 3D Printer (PLA / PETG / ABS) - Backlash: 0.22mm",
    mfgSla: "Resin / SLA 3D Printer - Backlash: 0.12mm",
    mfgCnc: "CNC Machining / Metal Milling - Backlash: 0.05mm",
    mfgCustom: "Custom Value Entry",
    labelBacklash: "Tooth Profile Clearance (Backlash)",
    labelBearingTolerance: "Bearing / Pin Seat Offset",
    hintBearingTolerance: "+ value enlarges bore (for easy press-fit assembly).",

    // Live Calc Panel
    calcTitle: "📊 Real-Time Gear & Kinematics Synthesis",
    calcBadgeOk: "✓ Assembly Condition Verified",
    calcBadgeWarn: "⚠️ Adjust Ratio or Module",
    metricRatio: "Actual Ratio",
    metricZs: "Sun Tooth Count (Zs)",
    metricZp: "Planet Tooth Count (Zp)",
    metricZr: "Ring Tooth Count (Zr)",
    metricOd: "Housing Outer Dia.",
    metricContact: "Contact Ratio (Overlap)",
    candidateLabel: "Best Matching Tooth Combinations Found:",
    noCandidate: "No valid tooth combination found (change ratio or module)",

    // Footer Buttons
    btnReset: "Reset to Defaults",
    btnGenerate: "🚀 Start 3D Generation in Fusion 360",

    // Progress
    progressGenerating: "Generating gears, please wait...",
    progressWarning: "⚠️ This may take 15-60 seconds depending on the model complexity.",

    // Modal
    modalClose: "✕",
    
    // Language toggle tooltip
    langToggle: "Türkçe'ye Geç"
  }
};
