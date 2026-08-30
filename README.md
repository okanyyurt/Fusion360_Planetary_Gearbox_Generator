# Autodesk Fusion 360 - Parametric Planetary Gearbox Generator
### *Parametrik Planet Redüktör Tasarımcısı (Spur & Herringbone / Balıksırtı)*

[![Autodesk Fusion 360](https://img.shields.io/badge/Autodesk-Fusion%20360-orange.svg?logo=autodesk)](https://www.autodesk.com/products/fusion-360)
[![Python 3.x](https://img.shields.io/badge/Python-3.x-blue.svg?logo=python)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Bilingual: EN / TR](https://img.shields.io/badge/Language-English%20%7C%20T%C3%BCrk%C3%A7e-brightgreen.svg)]()

[🇬🇧 English](#-english) | [🇹🇷 Türkçe](#-türkçe)

---

# 🇬🇧 English

## Overview
**Planetary Gearbox Generator** is a professional Autodesk Fusion 360 Add-In designed to automatically synthesize, calculate, and 3D-model ready-to-manufacture, multi-stage planetary gearboxes. 

Simply specify your **motor shaft diameter**, **target reduction/torque ratio**, and **number of stages**, and the script will synthesize the optimal gear train kinematics and model the complete 3D assembly directly inside Fusion 360.

---

## 🌟 Key Features & Engineering Capabilities

1. **Smart Kinematic Synthesis Engine:**
   - Automatically satisfies the **coaxiality condition**:
     $$Z_{\text{ring}} = Z_{\text{sun}} + 2 \cdot Z_{\text{planet}}$$
   - Enforces the **equal planet spacing assembly condition**:
     $$(Z_{\text{sun}} + Z_{\text{ring}}) \pmod N = 0$$
   - Evaluates adjacent planet tip-to-tip clearance to prevent physical collisions.

2. **Herringbone (Double Helical) & Spur Gears:**
   - **Herringbone (Balıksırtı):** Opposing helix angles cancel axial thrust forces completely, offering smooth, quiet, and high-torque transmission—ideal for 3D printed and CNC-machined gearboxes.
   - **High-Performance Adaptive Spline:** Involute profiles are modeled using smooth closed `SketchFittedSplines` for 10–30× faster CAD regeneration without locking up Fusion 360.

3. **Multi-Stage Power Transmission:**
   - Supports **1, 2, or 3 stages** (ratios from 3:1 up to 500:1).
   - Generates unified continuous ring gear housings with inter-stage carrier-to-sun couplings.

4. **Bearings & Pin Shaft Library:**
   - Standard ball bearing presets: `688ZZ`, `608ZZ`, `684ZZ`, `623ZZ`, `MR105`, `MR117`, `MR128`.
   - Bearingless option: Direct steel pins or bronze bushings with custom diameters.

5. **Motor Interface Presets & Shaft Profiles:**
   - Standard flange mounting: **NEMA 17, NEMA 23, NEMA 34, 775 DC Motor, 540/550 RC Motors, or Custom**.
   - Shaft bore geometries: **Round (Press-fit/Setscrew), D-Cut (Single Flat), Double D-Cut, and Keyway (DIN 6885)**.

6. **Manufacturing Presets & Backlash Management:**
   - Pre-configured clearance offsets for **FDM 3D Printing (0.22mm)**, **SLA Resin (0.12mm)**, and **CNC Metal Milling (0.05mm with high-precision curve generation)**.

7. **Modern Dual-Language Web UI:**
   - Built-in live calculation panel, interactive SVG modal diagrams, and one-click **TR / EN language switching**.

---

## 🚀 Installation & Usage in Fusion 360

### Step 1: Copy to Fusion 360 Add-Ins Folder
Open the Fusion 360 Add-Ins directory:
- **Windows:** Press `Win + R`, paste the following and press Enter:
  ```text
  %appdata%\Autodesk\Autodesk Fusion 360\API\AddIns
  ```
- **macOS:**
  ```text
  ~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns
  ```
Clone or copy this repository folder into that directory:
```bash
cd "%appdata%\Autodesk\Autodesk Fusion 360\API\AddIns"
git clone https://github.com/okanyyurt/Fusion360_Planetary_Gearbox_Generator.git PlanetaryGearboxGenerator
```

### Step 2: Run in Autodesk Fusion 360
1. Launch **Autodesk Fusion 360**.
2. Go to **UTILITIES** > **Scripts and Add-Ins** (`Shift + S`).
3. Under the **Add-Ins** tab, find **PlanetaryGearboxGenerator**.
4. Select it and click **Run**.
5. The dark-themed control palette will appear. Configure your parameters and click **"🚀 Start 3D Generation in Fusion 360"**!

---

## 📁 Repository Structure

```
PlanetaryGearboxGenerator/
├── PlanetaryGearboxGenerator.manifest    # Fusion 360 Add-In descriptor
├── PlanetaryGearboxGenerator.py          # Main entry point & Fusion HTML palette bridge
├── test_generator.py                     # Kinematics & profile geometry verification suite
├── core/
│   ├── kinematics.py                     # Tooth synthesis engine & assembly rule validator
│   ├── tooth_profile.py                  # Involute profile & herringbone helix calculator
│   ├── bearing_catalog.py                # Bearing dimensions (608, 688, MR series)
│   └── motor_catalog.py                  # Motor flange & shaft standards (NEMA, DC, RC)
├── cad/
│   ├── gear_builder.py                   # 3D B-Rep Sun, Planet & Ring gear builder (Spline)
│   ├── carrier_builder.py                # Planet carrier cage, pins & output shaft builder
│   ├── housing_builder.py                # Motor mounting plate & enclosure builder
│   └── assembly_manager.py               # Hierarchical multi-stage assembly orchestrator
└── ui/
    ├── index.html                        # HTML5 UI with bilingual data attributes
    ├── style.css                         # Dark engineering UI theme & progress animations
    ├── app.js                            # UI state, live kinematics calculator & event handler
    ├── i18n.js                           # English & Turkish translation dictionary
    └── assets/                           # Explanatory SVG diagrams & visual popups
        ├── assembly_condition.svg
        ├── backlash_clearance.svg
        ├── bearing_assembly.svg
        ├── herringbone_vs_spur.svg
        ├── multistage_carrier.svg
        └── shaft_types.svg
```

---

# 🇹🇷 Türkçe

## Genel Bakış
**Parametrik Planet Redüktör Tasarımcısı**, Autodesk Fusion 360 içerisinde **motor şaftı, hedef redüksiyon/tork oranı, kademe sayısı, yataklama tipi ve balıksırtı (herringbone) dişli geometrisini** alarak üretime hazır, tam montajlı planet redüktörler modelleyen profesyonel bir CAD eklentisidir.

---

## 🌟 Özellikler ve Mühendislik Kabiliyetleri

1. **Akıllı Kinematik Sentez Motoru:**
   - **Eş eksenlilik şartını** otomatik hesaplar:
     $$Z_{\text{çember}} = Z_{\text{güneş}} + 2 \cdot Z_{\text{planet}}$$
   - **Eşit açılı planet montaj kuralını** denetler:
     $$(Z_{\text{güneş}} + Z_{\text{çember}}) \pmod N = 0$$
   - Planet dişlilerin birbirine temas etmesini önleyen emniyet boşluğunu (clearance) kontrol eder.

2. **Balıksırtı (Herringbone / Çavuş) ve Düz Dişli:**
   - **Balıksırtı:** V şekilli zıt helis açıları ile eksenel kuvvetleri tamamen sıfırlar; sessiz, yüksek torklu ve 3D baskıda eksenel kaymayı önleyen ideal yapı sunar.
   - **Performans Odaklı Adaptif Spline:** Diş profilleri tek parça kapalı spline olarak çizilir, Fusion 360'ın donmasını engeller ve 10–30 kat daha hızlı çizim yapar.

3. **Çok Kademeli (Multi-Stage) Güç Aktarımı:**
   - **1, 2 veya 3 kademe** desteği (3:1'den 500:1'e kadar oranlar).
   - Kademeler arası taşıyıcı-güneş dişli akupleleri ve yekpare ortak çember dişli gövdesi sentezler.

4. **Rulman ve Mil Kütüphanesi:**
   - Hazır bilyalı rulmanlar: `688ZZ`, `608ZZ`, `684ZZ`, `623ZZ`, `MR105`, `MR117`, `MR128`.
   - Rulmansız seçenek: Doğrudan çelik pim veya bronz burç çapı belirleme.

5. **Motor Arayüzü Şablonları:**
   - Motor flanşları: **NEMA 17, NEMA 23, NEMA 34, 775 DC Motor, 540/550 RC Motor veya Özel**.
   - Şaft delikleri: **Yuvarlak (Pres-geçme/Setskur), D-Şaft (Tek düzlük), Çift D-Şaft ve Kamalı (DIN 6885)**.

6. **3D Baskı / CNC Tolerans ve Backlash Yönetimi:**
   - **FDM 3D Yazıcı (0.22mm)**, **SLA Reçine (0.12mm)** ve **CNC Metal İşleme (0.05mm + yüksek hassasiyet)** için hazır tolerans profilleri.

7. **Modern İki Dilli Arayüz (TR / EN):**
   - Canlı kinematik hesaplama kartı, teknik SVG yardım şemaları ve tek tıkla **Türkçe / İngilizce** geçişi.

---

## 🚀 Kurulum ve Çalıştırma

### Adım 1: Eklenti Klasörünü Kopyalama
Fusion 360 Add-Ins klasörünü açın:
- **Windows:** `Win + R` tuşlarına basıp aşağıdaki adresi yapıştırın ve Enter'a basın:
  ```text
  %appdata%\Autodesk\Autodesk Fusion 360\API\AddIns
  ```
- **macOS:**
  ```text
  ~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns
  ```

Bu depoyu bu dizin içerisine klonlayın veya kopyalayın:
```bash
cd "%appdata%\Autodesk\Autodesk Fusion 360\API\AddIns"
git clone https://github.com/okanyyurt/Fusion360_Planetary_Gearbox_Generator.git PlanetaryGearboxGenerator
```

### Adım 2: Fusion 360 İçinde Çalıştırma
1. **Autodesk Fusion 360**'ı açın.
2. Üst menüden **UTILITIES (Araçlar)** > **Scripts and Add-Ins** (`Shift + S`) penceresini açın.
3. **Add-Ins** sekmesine geçin.
4. Listede **PlanetaryGearboxGenerator** eklentisini seçip **Run (Çalıştır)** butonuna tıklayın.
5. Açılan modern arayüzden parametrelerinizi seçip **"🚀 Fusion 360'ta 3D Çizimi Başlat"** butonuna basın.

---

## 🧪 Matematiksel ve Geometrik Testler
Tüm kinematik denklemleri ve dişli geometrisi doğrulama testlerini yerel olarak çalıştırmak için:
```bash
python test_generator.py
```

---

## 📄 Lisans / License
Bu proje [MIT Lisansı](LICENSE) altında sunulmaktadır.
This project is licensed under the terms of the [MIT License](LICENSE).
