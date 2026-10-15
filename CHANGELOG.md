# Changelog / Değişiklik Günlüğü

All notable changes of the Planetary Gearbox Generator. Versions follow `MAJOR.MINOR.PATCH`.
Projedeki önemli değişiklikler. Her sürüm önce İngilizce, sonra Türkçe.

## [2.9.0]

### 🇬🇧 English

- **Single helical teeth** — a third tooth type besides spur and herringbone (standard and speed-up arrangements):
  quieter and a little stronger than spur (full-face overlap ratio, twice that of a herringbone half), the ring
  housing stays one piece (the stages' teeth twist with their planets, the gaps twist back). The planets' axial forces
  add up on the sun: stage 1's thrust is checked against the motor shaft bearings (NEMA17 ~15 N) with a warning
  (thrust washers, smaller helix angle or herringbone).
- **High contact ratio spur (HCR)** — a fourth tooth type: long teeth (h*a 1.25) and a 17.5° pressure angle, the
  search keeps tooth sets with a contact ratio >= 1.9 on both meshes (typically 2.1–2.7): two tooth pairs carry most of
  the time, nearly as quiet as helical, no axial thrust, as easy to print as spur.
- **User guide** — a "?" button next to the language switch opens a bilingual manual with diagrams: quick start,
  arrangements, the four tooth types (advantages / disadvantages, availability), outputs, the release plunger,
  mounting brackets, expert mode, printing and assembly tips.
- **Tooth types for every arrangement** — single helical now also in the rotating housing (one-piece helical drum),
  HCR also in the Wolfrom (stepped planets with long teeth, contact ratio >= 1.9). Helical / herringbone are not offered
  for the Wolfrom (the stepped planet's two gears mesh different rings) and the cycloidal drive has no teeth.
- **Side bracket fix** — the back plate now ends 1 mm below the output members above the housing (drive collar, arm,
  release flange disc) and stands outside every turning round part too (disc, collar, drum): nothing touches the plate
  or the wall; arms report their free swing angle.
- **Release for flange outputs** — the spring index plunger release now also works with the flange outputs of every
  arrangement: a free flange disc with 6 heat-set inserts turns on the drive collar instead of an arm.
- **No pins cut to length** — every steel dowel is now a standard ISO 8734 length in every arrangement: the Wolfrom
  cage plates grow (<= 3 mm, like the standard cage carrier) until a standard pin spans both tooth sets, the cycloidal
  output plate grows (<= 5 mm) until a standard output pin fits between plate and disc A (it used to need e.g.
  Ø10×29.3 cut down from 30). The parts list still flags any pin that would have to be cut.
- **Cycloidal motion in Fusion** — the discs are jointed to the eccentric hub (they were missing their carrier member,
  so the joint setup stopped and turning the input moved only some parts).
- **3MF plates** — parts keep 8 mm from the plate edge and 10 mm from each other (the 5 mm auto brim no longer runs
  off the plate or merges two parts); only toothed parts and the calibration coupon use the fine layer height,
  housings, covers, flanges and brackets 0.2 mm (about 15 % shorter print time).
- **Logo** — a planetary gear set logo in the app header, the Fusion toolbar icons and the README; the header shows
  the version once.

### 🇹🇷 Türkçe

- **Tek helis diş** — düz ve balıksırtının yanında üçüncü diş tipi (standart düzen ve hız artırıcı): düzden sessiz ve
  biraz daha güçlü (tam genişlikte örtüşme oranı, balıksırtı yarısının iki katı); çember gövdesi tek parça kalır
  (kademelerin dişleri planetleriyle birlikte döner, aradaki boşluklar geri döner). Planetlerin eksenel kuvvetleri
  güneşte toplanır: 1. kademenin itmesi motor mili rulmanlarına karşı (NEMA17 ~15 N) kontrol edilir ve uyarılır (itme
  pulu, daha küçük helis açısı veya balıksırtı).
- **Yüksek temas oranlı düz dişli (HCR)** — dördüncü diş tipi: uzun diş (h*a 1.25) ve 17.5° basınç açısı; arama her
  iki kavramada temas oranı >= 1.9 olan diş setlerini seçer (genelde 2.1–2.7): çoğu an iki diş çifti yük taşır, helise
  yakın sessizlik, hiç eksenel itme yok, baskısı düz dişli kadar kolay.
- **Kullanım kılavuzu** — dil düğmesinin yanındaki "?" butonu görselli, iki dilli bir kılavuz açar: hızlı başlangıç,
  düzenler, dört diş tipi (avantaj / dezavantaj, hangi düzende), çıkışlar, boşa alma pimi, montaj braketleri, uzman
  modu, baskı ve montaj ipuçları.
- **Diş tipleri tüm düzenlerde** — tek helis artık dönen gövdede de (tek parça helisli tambur), HCR Wolfrom'da da
  (uzun dişli kademeli planetler, temas oranı >= 1.9). Wolfrom'da helis / balıksırtı sunulmaz (kademeli planetin iki
  dişlisi farklı çemberlerle kavrar); sikloidalde diş yoktur.
- **Yan braket düzeltmesi** — sırt plakası artık gövdenin üstündeki çıkış parçalarının (tahrik bileziği, kol, boşa alma
  flanş diski) 1 mm altında biter ve dönen tüm yuvarlak parçaların (disk, bilezik, tambur) da dışında durur: plakaya
  veya duvara hiçbir şey değmez; kollar serbest dönüş açısını bildirir.
- **Flanş çıkışlarında boşa alma** — yaylı indeks pimiyle boşa alma artık her düzenin flanş çıkışında da var: kol yerine
  6 ısıl burçlu serbest bir flanş diski tahrik bileziğinde döner.
- **Kısaltılan pim yok** — tüm düzenlerde her çelik pim artık standart ISO 8734 boyunda: Wolfrom'da kafes plakaları
  (standart kafes taşıyıcıdaki gibi <= 3 mm) standart bir pim iki dişli setini geçene kadar, sikloidalde çıkış plakası
  (<= 5 mm) standart çıkış pimi plaka ile A diski arasına sığana kadar kalınlaşır (önce ör. 30'dan kısaltılmış
  Ø10×29.3 gerekiyordu). Parça listesi kesilmesi gereken pimi yine de belirtir.
- **Fusion'da sikloidal hareket** — diskler eksantrik göbeğe eklemlenir (taşıyıcı üyeleri eksikti; eklem kurulumu
  yarıda kalıyor, giriş döndürülünce yalnızca bazı parçalar dönüyordu).
- **3MF tablaları** — parçalar tabla kenarından 8 mm, birbirinden 10 mm uzakta (5 mm otomatik brim artık tabladan
  taşmaz, iki parçayı birleştirmez); ince katman yalnızca dişli parçalarda ve kalibrasyon parçasında, gövde, kapak,
  flanş ve braketler 0.2 mm (baskı süresi ~%15 kısa).
- **Logo** — uygulama başlığında, Fusion araç çubuğu ikonlarında ve README'de planet dişli takımı logosu; başlıkta
  sürüm bilgisi artık bir kez yazar.

## [2.8.0]

### 🇬🇧 English

- **Wolfrom arrangement** (one stage, 50–500:1): stepped planets (two gears in one part) mesh the sun, a fixed ring
  and an output ring with 1–3 teeth more or less; the output ring is a lidded drum (flange screw circle or bolted
  arm) running in a thin-section bearing or, when none is large enough, a greased printed plain bearing. Same module
  and standard centre distances everywhere, every planet turned to its own tooth phase. Efficiency (Müller) and
  back-driving are computed: above ~80:1 the gearbox is usually self-locking (the load is held without power).
- **Cycloidal drive** (one stage, 6–60:1): an eccentric hub on the motor shaft, two cycloid discs 180° apart on
  bearings, steel dowel ring pins half sunk into the housing bore, steel output pins in an output plate with a hub
  running in the cover bearing (flange inserts or arm). Exact disc profile (Lehmann) with running clearance, undercut
  and lobe-tip checks; contact pressure, output pin bending, hole pressure and eccentric bearing life.
- Both: own assembly steps in the report, AI assistant knows them, verified for clashes, mesh and running clearance
  while turning (tests).
- **Release (spring index plunger)** for every arm output (carrier arm, drum arm of the rotating housing and the
  Wolfrom, cycloid arm; tab 4): the arm turns freely on a drive collar screwed to the output hub / drum lid and a
  GN 617.1 index plunger (rest position, lock nut; thin nut in a pocket under the arm) couples it. Pull the knob and turn
  it a quarter: the arm is disconnected and turns by hand; turn it back and the pin snaps in when the holes line up.
  Plunger size (M10–M20) and radius follow the torque until the printed hole pressure meets the target; a pull solenoid
  can replace the knob later. Wolfrom and cycloid now also check the arm.
- **Expert mode** (materials & strength tab, every arrangement): tooth temperature after the structure of VDI 2736 (power, friction
  greased / dry, speed, housing surface, duty ED, ambient), strength falling with the temperature, fatigue from the
  tooth load cycles over the target life, wear depth and creep of a load held at rest. The design search meets them
  too (a continuously running printed gearbox comes out larger); approximate constants, documented in the report.
  Wolfrom and cycloidal: temperature from their power loss leaving through the housing (dry running lowers their
  efficiency), the same cycle life and creep checks.
- **Mounting bracket for every gearbox type** (standard, rotating housing, Wolfrom, cycloidal) and three kinds: side
  mount (L bracket, axis parallel to the surface; its back plate stands outside the widest part of the gearbox and
  reaches up along the housing, an arm's free swing angle is reported), base stand (legs beside the motor, axis normal to a floor / wall)
  and panel plate (the motor passes through a panel hole). The tie rods always run on into nuts in the bracket shelf.
- Fix: a small first sun (Z13 on a Ø5 shaft) let the planet teeth run on the set-screw collar — the collar top is now
  necked below the planets.

### 🇹🇷 Türkçe

- **Wolfrom düzeni** (tek kademe, 50–500:1): kademeli planetler (tek parçada iki dişli) güneş, sabit çember ve ondan 1–3
  diş farklı çıkış çemberiyle kavrar; çıkış çemberi kapaklı bir tamburdur (flanş vida dairesi veya vidalı kol), ince
  kesitli rulmanda ya da yeterince büyüğü yoksa greslenmiş baskılı kaymalı yatakta döner. Her yerde aynı modül ve
  standart eksen mesafesi; her planet kendi diş fazına çevrilir. Verim (Müller) ve geri sürme hesaplanır: ~80:1 üstünde
  redüktör genelde kendiliğinden kilitlenir (yük elektriksiz tutulur).
- **Sikloidal redüktör** (tek kademe, 6–60:1): motor milinde eksantrik göbek, rulmanlı iki sikloid disk (180°), gövde
  deliğine yarı gömülü çelik halka pimleri, çıkış plakasında çelik çıkış pimleri ve kapak rulmanında dönen göbek (flanş
  burçları veya kol). Tam disk profili (Lehmann) çalışma boşluğuyla; alt kesim ve lob ucu kontrolleri; temas basıncı,
  çıkış pimi eğilmesi, delik ezilmesi ve eksantrik rulman ömrü.
- İkisi de: raporda kendi montaj adımları, AI asistan tanıyor, dönerken çakışma / kavrama / sürtünme testlerle
  doğrulandı.
- **Boşa alma (yaylı indeks pimi)** her kol çıkışında (taşıyıcı kolu, dönen gövde ve Wolfrom tambur kolu, sikloidal
  kol; 4. sekme): kol, çıkış göbeğine / tambur kapağına vidalanan tahrik bileziğinde serbest döner ve bir GN 617.1 indeks
  pimi (dinlenme konumlu, kilit somunlu; kolun altında cepte ince somun) onu bağlar. Topuzu çekip çeyrek tur çevirince
  kol ayrılır ve elle döner; geri çevirince delikler hizalandığında pim kendiliğinden girer. Pim ölçüsü (M10–M20) ve
  yarıçapı, baskı deliği ezilmesi hedefi sağlanana kadar torkla büyür; ileride topuzun yerine çekme solenoidi
  konabilir. Wolfrom ve sikloidalde kol dayanımı da artık hesapta.
- **Uzman modu** (malzeme & dayanım sekmesi, tüm düzenler): VDI 2736 yapısında diş sıcaklığı (güç, gresli / kuru sürtünme, devir,
  gövde yüzeyi, çalışma oranı ED, ortam), sıcaklıkla düşen mukavemet, hedef ömürdeki diş çevrimine göre yorulma,
  aşınma derinliği ve durarak yük tutmada sünme. Tasarım araması bunları da sağlar (sürekli çalışan baskı redüktör
  büyür); katsayılar yaklaşık ve raporda belgeli. Wolfrom ve sikloidalde sıcaklık kayıp gücün gövdeden atılmasıyla
  (kuru çalışmada verim düşer), çevrim ömrü ve sünme aynı.
- **Montaj braketi her redüktör tipinde** (standart, dönen gövde, Wolfrom, sikloidal) ve üç biçimde: yan montaj (L
  braket, eksen yüzeye paralel; sırt plakası redüktörün en geniş yerinin dışında ve gövde boyunca uzanır, kolun
  serbest dönüş açısı bildirilir), ayaklı taban (motorun yanında ayaklar, eksen zemine / duvara dik) ve panel plakası
  (motor panel deliğinden geçer). Bağlantı cıvataları her zaman braket rafındaki somunlara uzanır.
- Düzeltme: küçük ilk güneşte (Ø5 milde Z13) planet dişleri sıkma bileziğinin üstüne sürtüyordu — bileziğin üstü
  planetlerin altında boyunlandı.

## [2.7.0]

### 🇬🇧 English

- **Face load factor K_Hβ** (simplified ISO 6336-1 method C): the load is no longer assumed uniform across the face
  width. Misalignment from the carrier pin hole error (FDM 0.02 mm) and the pin deflection (wind-up of the free cage
  plate, cantilever pin of a single plate), plastic mesh stiffness and running-in. Wide gears no longer gain capacity
  in proportion (45 mm vs 12 mm: ×1.6 instead of ×3.75); printed pins and wide faces are warned about.
- **Profile shift x** (V-zero: sun +x, planet and ring −x, standard centre distances): automatic (one x per gearbox,
  since all stages share the ring gear, chosen per candidate for the strongest weakest stage), none, or manual. The
  ISO 6336-3 root form factor includes x; profiles, CAD and report follow it.
- **Calibration coupon** (tab 5): numbered bearing pockets, pin holes and backlash gear pairs of the selected design;
  enter the best numbers, the tolerances go into the form and are remembered.
- **Print-ready 3MF** with the export: parts on plates (long parts at 45°), per-part walls / infill / layer height;
  with a Creality K1 / K1 Max / K1C / K1 SE profile the file carries the complete printer, process and filament
  settings (Creality Print / OrcaSlicer). Verified: the gate gearbox slices in OrcaSlicer for the K1 Max (4 plates).
- **Mounting bracket** (tab 4): an L bracket under the motor flange (tie rods run on into its shelf, bearing
  pressure checked), screwed to a wall, post or floor.
- The output arm's bed check uses its real outline (hub and rounded tip): a 290 mm arm fits a K1 Max diagonally.

### 🇹🇷 Türkçe

- **Diş genişliği boyunca yük dağılımı K_Hβ** (ISO 6336-1 C yöntemi, sadeleştirilmiş): taşıyıcı pim deliği hatası
  (FDM 0.02 mm) ve pim eğilmesi (kafeste serbest plakanın burulması, tek plakada konsol pim), plastik diş rijitliği ve
  alışma. Geniş dişler artık orantılı kapasite kazanmaz (45 / 12 mm: ×3.75 yerine ×1.6); baskı pim ve geniş diş uyarılır.
- **Profil kaydırma x** (V-sıfır: güneş +x, planet ve çember −x, eksen mesafeleri standart): otomatik (tüm kademeler
  aynı çemberi paylaştığı için redüktör başına tek x, adaya göre en zayıf kademeyi güçlendiren), yok veya elle.
- **Kalibrasyon parçası** (5. sekme): seçili tasarımın numaralı rulman yuvaları, pim delikleri ve diş boşluğu dişli
  çiftleri; en iyi numaralar girilince toleranslar forma yazılır ve hatırlanır.
- **Baskıya hazır 3MF**: parçalar tablalara dizili (uzun parçalar 45°), parça başına duvar / dolgu / katman; Creality
  K1 / K1 Max / K1C / K1 SE profilinde yazıcı, işlem ve filament ayarları da dosyada (Creality Print / OrcaSlicer).
  Doğrulandı: kapı redüktörü OrcaSlicer'da K1 Max için 4 tablada dilimleniyor.
- **Montaj braketi** (4. sekme): motor flanşının altına L braket; bağlantı cıvataları rafa uzar (ezilme hesapta),
  duvara / direğe / zemine vidalanır.
- Kolun tablaya sığma kontrolü gerçek şekliyle (göbek + yuvarlak uç): 290 mm kol K1 Max'e çapraz sığar.

## [2.6.0]

### 🇬🇧 English

- **Up to 5 stages.** 4 and 5 stages for very high ratios (hundreds to tens of thousands :1) or a tight diameter:
  lower stage ratios give larger suns and more planets, so the last stage is stronger in the same diameter. Each
  stage costs ~5–6 % efficiency (4 stages ~78 %, 5 stages ~73 %); the report says so and, above 500:1, that the
  output practically self-locks.
- **Automatic stage count** (tab 1, "Otomatik"): every practical stage count is searched; the smallest suitable
  design wins (a further stage must save > 10 % of the volume, with MAX_OD sizing: add > 10 % strength). When no
  design fits the diameter / length limit or carries the load, the count rises by itself — the status line says
  which counts were tried and why one was chosen. With a fixed count that is too weak for a size limit the search
  suggests more stages.
- **Ratio from the load** (checkbox under the ratio): the lowest ratio that moves load × lever arm with the
  recommended reserve (stepper ×1.5, DC ×1.25) and the stage efficiency; for a winch drum the rope radius of the
  drum found is used (iterated). Works with a fixed or an automatic stage count.
- Requirement solver / AI assistant: up to 5 stages, a further stage is tried when the space is too tight, the
  ranking charges 10 % volume per stage.

### 🇹🇷 Türkçe

- **5 kademeye kadar.** Çok yüksek oranlar (yüzlerce – on binlerce :1) veya dar çap için 4 ve 5 kademe: kademe oranı
  düştükçe güneş büyür, daha çok planet sığar, son kademe aynı çapta daha güçlü olur. Her kademe ~%5–6 verim kaybı
  (4 kademe ~%78, 5 kademe ~%73); rapor bunu ve 500:1 üstünde çıkışın pratikte kendini kilitlediğini söyler.
- **Otomatik kademe sayısı** (1. sekme, "Otomatik"): uygulanabilir her kademe sayısı ayrı aranır, en küçük hacimli
  uygun tasarım seçilir (ek kademe hacmi > %10 küçültmeli; Maks. dış çap modunda dayanımı > %10 artırmalı). Çap / boy
  sınırına sığan ya da yükü taşıyan tasarım yoksa kademe sayısı kendiliğinden artar — durum satırı hangi sayıların
  denendiğini ve neden seçildiğini yazar. Sabit kademe sayısı boyut sınırında yetmezse arama daha çok kademe önerir.
- **Oranı yükten hesapla** (oranın altındaki kutu): yük × kuvvet kolunu önerilen rezervle (step ×1.5, DC ×1.25) ve
  kademe verimiyle kaldıran en düşük oran; vinç tamburunda bulunan tamburun halat yarıçapı kullanılır (yinelenir).
  Sabit veya otomatik kademe sayısıyla çalışır.
- Gereksinim çözücüsü / AI asistan: 5 kademeye kadar; yer dar gelirse bir kademe fazlası denenir, sıralamada her
  kademe %10 hacim sayılır.

## [2.5.0]

### 🇬🇧 English

- Gearbox arrangement (tab 1): **Standard** (housing fixed, carrier output — as before), **Rotating housing**
  (the last carrier is pinned to a fixed base plate, its ring becomes a lidded drum that turns the opposite way,
  i = Zr/Zs for that stage) and **Speed-up** (driven from the output by a crank or a wind rotor, the motor works as
  a generator; generator speed, power and the start-up cogging felt at the input are reported).
- Rotating-housing outputs: drum flange (screw circle on the lid with captive nuts / inserts), drum arm (screwed
  onto the lid) and winch drum (rims, rope anchor hole; the rope radius is the lever arm of the load). The drum turns
  on one ball bearing in its lid, seated on a stub of the fixed carrier's top plate (automatic choice or your own,
  e.g. 608ZZ); herringbone drums are split at the V apex and screwed together. Tie-rod heads sink below the base
  plate. Engineering: star-stage speeds and forces, drum screw bearing pressure, drum bearing side load; kinematics,
  Fusion joints, report, parts list and the AI assistant / requirement solver know the new arrangements.
- Inter-stage coupling: the next sun is now printed in one piece with the single-plate carrier too (as with the cage
  carrier) — the old printed D-shaft with a fixed 0.5 mm flat could strip under the stage torque. The neck below the
  teeth is checked in torsion.

### 🇹🇷 Türkçe

- Redüktör düzeni (1. sekme): **Standart** (gövde sabit, taşıyıcı çıkışı — eskisi gibi), **Dönen gövde** (son
  kademenin taşıyıcısı sabit tabana pimlenir, çemberi kapaklı bir tambur olur ve ters yönde döner; o kademenin oranı
  Zr/Zs) ve **Hız artırıcı** (kol / mil / flanş krank veya rüzgâr rotoruyla çevrilir, motor jeneratör olur;
  jeneratör devri, gücü ve girişte hissedilen takılma torku raporlanır).
- Dönen gövde çıkışları: tambur flanşı (kapakta tutsak somun / ısıl burçlu vida dairesi), tambur kolu (kapağa
  vidalanır) ve vinç tamburu (kenarlar, halat bağlama deliği; yükün kuvvet kolu halat yarıçapı). Tambur, kapağındaki
  tek rulmanla sabit taşıyıcının üst plakasındaki göbekte döner (otomatik veya elinizdeki rulman, ör. 608ZZ);
  balıksırtı tambur V tepesinden ikiye bölünüp vidalanır. Bağlantı cıvatalarının başları taban plakasına gömülür.
  Hesaplar: yıldız kademe devir ve kuvvetleri, tambur vidalarının delik ezilmesi, tambur rulmanı yan yükü; kinematik,
  Fusion eklemleri, rapor, parça listesi, AI asistan ve gereksinim çözücüsü yeni düzenleri bilir.
- Kademe arası bağlantı: bir sonraki güneş artık tek plaka taşıyıcıda da taşıyıcıyla tek parça basılır (kafes
  taşıyıcıdaki gibi) — eski, düzlüğü sabit 0.5 mm olan baskı D-mil kademe torkunda sıyrılabiliyordu. Dişlerin
  altındaki boyun burulmaya göre kontrol edilir.

## [2.4.0]

### 🇬🇧 English

- Tooth depth coefficient h*a (0.75–1.30, default 1.0) on the gear tab: addendum h*a·m, dedendum (h*a + 0.157)·m,
  ring tips / roots alike. Geometry, CAD profiles, housing, contact ratio and tip thickness follow it; the root
  bending check is corrected with the ISO 6336-3 form × stress factor ratio (load at the actual tip). Topped or too
  thin (FDM) tips of long teeth are reported.
- Optional application load (tab 1): kg / N with its lever arm (arm output: the arm length) or a torque in Nm. The
  app answers "✓ suitable / ⚠ marginal / ✗ not suitable" — motor × ratio × efficiency against the load with a
  reserve (stepper 1.5, other 1.25), gearbox strength, output bearing side load (s0) and shaft bending — and says
  what to change (ratio, motor torque, lever arm, size). The requirement solver searches enough output torque for
  the load; the AI assistant passes a stated load and otherwise asks for it once (optional).

### 🇹🇷 Türkçe

- Diş yüksekliği katsayısı h*a (0.75–1.30, varsayılan 1.0, 2. sekme): diş başı h*a·m, diş dibi (h*a + 0.157)·m,
  çember dişli de aynı oranda. Geometri, CAD profilleri, gövde, kavrama oranı ve uç kalınlığı buna göre değişir;
  diş dibi hesabı ISO 6336-3 form × gerilme faktörü oranıyla düzeltilir (yük gerçek uçta). Uzun dişlerde kırpılan
  veya FDM için çok ince kalan uçlar uyarı olarak bildirilir.
- İsteğe bağlı uygulama yükü (1. sekme): kuvvet kolu ile kg / N (kol çıkışında kol boyu) veya doğrudan Nm. Program
  "✓ Uygun / ⚠ Sınırda / ✗ Uygun değil" diye cevaplar — motor × oran × verim, rezervle (step 1.5, diğer 1.25) yüke
  karşı, redüktör dayanımı, çıkış rulmanı yan yükü (s0) ve mil eğilmesi — ve neyin değişmesi gerektiğini (oran,
  motor torku, kuvvet kolu, boyut) yazar. Gereksinim çözücüsü yüke yetecek çıkış torkunu arar; AI asistan verilen
  yükü kullanır, verilmemişse bir kez (isteğe bağlı) sorar.

## [2.3.0]

### 🇬🇧 English

- Output hub: the side-loaded M3 nuts are part of the assembly (BOM, Fusion components); the pocket cut can no
  longer leave loose fragments (invalid face merge fixed, booleans never modify their inputs).
- The arm / flange face always clears the stationary tie-rod heads, rod ends and top nuts by 1 mm; short housings
  that fall between two standard screw lengths get a rod cut to length (not 205 mm).
- A candidate's safety factor and ✓ now include every check of the report (a fixed output shaft, a manually chosen
  hub, the arm section); when such a part is the limit, the form says which setting to change.
- Search: robust on slow / busy machines, much faster for high-torque requests, explains why there is no solution;
  applying an AI / solver proposal always selects exactly the proposed tooth set.
- Lightening holes keep spokes between them (6-planet carriers stayed in one piece only by luck before).
- Fusion: Stop / Run of the add-in loads updated files (no Fusion restart needed).

### 🇹🇷 Türkçe

- Çıkış göbeği: yandan takılan M3 somunlar montajda (BOM ve Fusion bileşeni olarak); yuva kesimi artık kopuk
  parça/çıkıntı bırakmıyor (geçersiz yüz birleştirme düzeltildi, boolean işlemler girdileri değiştirmiyor).
- Kol / flanş yüzü sabit cıvata başlarının, saplama uçlarının ve üst somunların her zaman 1 mm üstünden geçer;
  iki standart cıvata boyu arasında kalan kısa gövdelere boyuna kesilmiş saplama verilir (205 mm değil).
- Adayın emniyet katsayısı ve ✓ işareti raporun tüm kontrollerini içerir (sabit çıkış mili, elle seçilen göbek,
  kol kesiti); sınırlayan böyle bir parçaysa form hangi ayarın değişeceğini söyler.
- Arama: yavaş/meşgul bilgisayarda da güvenilir, yüksek torkta çok daha hızlı, çözüm yoksa nedenini açıklar;
  AI/çözücü önerisini uygulamak tam olarak önerilen diş kombinasyonunu seçer.
- Hafifletme delikleri arasında her zaman kol kalır (6 planetli taşıyıcılarda delikler birleşebiliyordu).
- Fusion: eklentiyi Durdur/Çalıştır yapmak güncellenmiş dosyaları yükler (Fusion'ı kapatmak gerekmez).
