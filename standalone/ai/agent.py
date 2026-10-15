# -*- coding: utf-8 -*-
"""
AI tasarım asistanı: kullanıcının yazdığı ihtiyacı (devir, tork, ölçü, yazıcı...) Gemini'ye anlatır;
model hesap yapmaz, uygulamanın kendi motorunu araç olarak çağırır:

  solve_requirements   gereksinimden tasarım (core.requirements.solve)
  evaluate_design      bir tasarımı/formu değiştirip yeniden boyutlandırma (core.design.design)
  get_current_design   formdaki mevcut ayarlar
  propose_design       sonucu kullanıcıya "Forma uygula" kartı olarak sunar

Her konuşma turu arka plan iş parçacığında çalışır (Fusion'un ana iş parçacığı bloklanmaz); arayüz
`poll` ile adımları ve sonucu okur.
"""
from __future__ import annotations

import json
import logging
import threading
import time
import traceback
import uuid
from typing import Callable, Dict, List, Optional

from core.bearing_catalog import BEARING_CATALOG
from core.design import design
from core.materials import MATERIALS
from core.motor_catalog import MOTOR_CATALOG
from core.requirements import load_summary, solve

from . import gemini

log = logging.getLogger(__name__)

MAX_ROUNDS = 8
HISTORY_TURNS = 6
SHAFT_TYPES = ["ROUND", "D_CUT", "DOUBLE_D", "KEYWAY"]
OUTPUT_TYPES = ["FLANGE", "SHAFT_PRINTED", "SHAFT_STEEL", "ARM", "DRUM_FLANGE", "DRUM_ARM", "DRUM_WINCH"]


def _num(desc: str) -> Dict:
    return {"type": "number", "description": desc}


def _int(desc: str) -> Dict:
    return {"type": "integer", "description": desc}


def _enum(values: List[str], desc: str) -> Dict:
    return {"type": "string", "enum": values, "description": desc}


def _requirement_props() -> Dict:
    mats = ["AUTO"] + list(MATERIALS.keys())
    bearings = ["AUTO"] + [c for c in BEARING_CATALOG if c != "CUSTOM_PIN"]
    return {
        "motor_preset": _enum(list(MOTOR_CATALOG.keys()), "Motor preset (NEMA17/23/34 are steppers, e.g. 17HS4401 = "
                                                          "NEMA17); CUSTOM when the motor is not in the list."),
        "motor_torque": _num("Motor torque the gearbox must carry, Nm (stepper: holding torque, e.g. 17HS4401 = 0.4). "
                             "Leave empty to use the preset."),
        "motor_speed": _num("Motor speed, rpm. For a stepper: the highest speed you want to run it at "
                            "(default 300 — stepper torque falls above that)."),
        "motor_shaft_dia": _num("Motor shaft diameter, mm."),
        "motor_shaft_type": _enum(SHAFT_TYPES, "Motor shaft type (D_CUT = one flat)."),
        "free_speed": {"type": "boolean", "description": "Motor speed is set by a driver (steppers, servos, VFD): the "
                       "engine then chooses the ratio for the required output speed. Default: true for steppers."},
        "output_speed": _num("Required OUTPUT speed in rpm. Convert motions yourself: e.g. 180° in 30 s = 0.5 rev in "
                             "0.5 min = 1 rpm; 90° in 10 s = 0.25 rev in 1/6 min = 1.5 rpm. ALWAYS give this when the "
                             "user describes a speed or a motion time; the engine derives the ratio."),
        "ratio": _num("ONLY when the user explicitly states a ratio (e.g. '50:1'). Never compute it yourself."),
        "ratio_tol": _num("Allowed ratio deviation, percent (default 3)."),
        "min_output_torque": _num("Minimum output torque the application needs, Nm — only if the user gives it or "
                                  "a load you can convert exactly (force × lever)."),
        "max_od": _num("Space limit across the axis: maximum outer diameter incl. bolt lugs, mm (e.g. a 25 × 28 cm "
                       "space with the axis along 28 cm → 250). 0 = no limit."),
        "max_length": _num("Space limit along the axis, mm (e.g. 280). 0 = no limit."),
        "length_includes_motor": {"type": "boolean", "description": "max_length is the whole space incl. the motor "
                                  "body (default true: the motor length is subtracted)."},
        "motor_length": _num("Motor body length behind the flange, mm (17HS4401: 40). Leave empty for the preset."),
        "printer": {"type": "string", "description": "The user's 3D printer model, e.g. 'Creality K1 Max', 'Bambu Lab "
                    "P1S', 'Ender 3 V3' — the engine knows their beds."},
        "bed_x": _num("Print bed X, mm (only if the printer is unknown to the engine)."),
        "bed_y": _num("Print bed Y, mm."),
        "bed_z": _num("Print height Z, mm."),
        "fit_bed": {"type": "boolean", "description": "Every printed part must fit the print bed (default true)."},
        "gear_material": _enum(mats, "Gear material; AUTO tries PLA then PA-CF. Use the user's filament (e.g. PETG)."),
        "struct_material": _enum(mats, "Carrier/housing material; AUTO = same as the gears."),
        "planet_bearing": _enum(bearings, "Planet bearing the user already has (e.g. 608ZZ); AUTO = engine chooses."),
        "pin_type": _enum(["STEEL", "PRINTED"], "Planet pins: STEEL dowels (strongest, default) or PRINTED."),
        "carrier_type": _enum(["CAGE", "SINGLE"], "CAGE (two plates + pins, no circlips, default) or SINGLE "
                                                  "(one plate + printed snap circlips)."),
        "herringbone": {"type": "boolean", "description": "Herringbone gears (quieter, stronger; default true)."},
        "expert_mode": {"type": "boolean", "description": "Expert checks (every arrangement): tooth temperature "
                                                          "(VDI 2736 structure), load-cycle life, wear, creep. Use when the "
                                                          "user mentions continuous duty, heat, hours of operation, dry "
                                                          "running or holding a load for long."},
        "ambient_temp": _num("Expert mode: ambient temperature, C (default 23)."),
        "duty_pct": _num("Expert mode: share of the time the gearbox runs, % (default 100)."),
        "lubrication": _enum(["GREASE", "DRY"], "Expert mode: greased (default) or dry running."),
        "hold_hours": _num("Expert mode: hours a load is held at rest (creep), 0 = none."),
        "declutch": {"type": "boolean", "description": "ARM output of the standard arrangement only: the arm turns "
                                                       "freely on a drive collar, one removable steel release pin "
                                                       "couples it (gate opened by hand in a power cut)."},
        "arrangement": _enum(["CARRIER", "RING", "SPEED_UP", "WOLFROM", "CYCLOID"],
                             "WOLFROM = one stepped-planet stage, 50-500:1, output ring as a lidded drum (DRUM_FLANGE / "
                             "DRUM_ARM), low efficiency, mostly self-locking. CYCLOID = eccentric + two cycloid discs + "
                             "steel ring pins, 6-60:1, very stiff, almost no backlash, output FLANGE / ARM, turns "
                             "backwards. "
                             "CARRIER = standard reducer, housing fixed, carrier "
                                                              "output (default). RING = rotating housing: the last "
                                                              "carrier is fixed and the drum (ring) turns, opposite "
                                                              "direction — for a wheel hub, winch drum, turntable, or an "
                                                              "arm / gate bolted onto a large drum. SPEED_UP = driven "
                                                              "from the output (crank, wind rotor), the motor is a "
                                                              "generator (form only, the solver treats it as a reducer)."),
        "output_type": _enum(OUTPUT_TYPES, "Output member. CARRIER: FLANGE hub, SHAFT_PRINTED, SHAFT_STEEL socket, ARM "
                                           "(lever). RING: DRUM_FLANGE (screw circle on the drum lid), DRUM_ARM (arm "
                                           "screwed onto the lid), DRUM_WINCH (rimmed rope drum)."),
        "rope_dia": _num("Winch rope / cord diameter, mm (DRUM_WINCH)."),
        "output_shaft_dia": _num("Output shaft diameter for shaft outputs, mm — ONLY if the user gives it; otherwise "
                                 "leave it empty and the engine sizes the shaft for the torque."),
        "output_shaft_len": _num("Output shaft length above the cover, mm."),
        "hub_fastener": _enum(["NUT", "INSERT"], "Screws into the output flange/arm hub: captive M3 nuts in side "
                                                 "pockets (default) or heat-set inserts."),
        "arm_shape": _enum(["FLAT", "ROUND"], "Output arm section."),
        "arm_length": _num("Arm length from the axis to the tip hole, mm."),
        "arm_width": _num("Flat arm width or round arm diameter, mm — ONLY if the user gives it; otherwise leave it "
                          "empty and the engine sizes the arm for the torque."),
        "arm_thickness": _num("Flat arm thickness, mm — only if the user gives it."),
        "load_value": _num("Application load the gearbox has to move — ONLY if the user states it (a weight or force "
                           "at the arm tip / on the rope, or a torque). Never guess it. The engine then checks whether "
                           "the design is suitable (torque with a reserve, gearbox strength, output bearing / shaft "
                           "side load) and the solver searches enough output torque."),
        "load_unit": _enum(["KG", "N", "NM"], "Unit of load_value: KG for a weight / a force given in kg (\"10 kg\"), "
                                              "N for a force, NM for a torque at the output."),
        "load_radius": _num("Lever arm of the load force, mm: pulley / drum / wheel radius or the distance from the "
                            "axis. Leave empty for an arm output (the arm length is used), a winch drum (its rope "
                            "radius is used) or when load_unit is NM."),
        "addendum_coef": _num("Tooth depth (addendum) coefficient h_a*, default 1.0 (standard). 0.8 = stub teeth: "
                              "stronger roots, less sensitive to print errors, lower contact ratio. 1.1–1.25 = long "
                              "teeth: smoother, quieter, more load sharing, but weaker roots and thin / pointed tips "
                              "(hard to print with FDM). ONLY if the user asks about tooth depth."),
        "profile_shift": {"type": "string", "description": "Profile shift: AUTO (default: balanced root strength, no "
                                                          "narrow small-sun roots), NONE (x = 0) or a number = the "
                                                          "sun's x of every stage (planet / ring -x)."},
        "num_planets": _int("Planets per stage; 0 = automatic per stage (recommended)."),
        "stages_count": _int("Number of stages 1–5 (0 = automatic: the engine searches each count and adds stages "
                             "when the diameter / length limit or the load needs them)."),
        "face_width": _num("Gear face width, mm (0 = automatic from the length budget)."),
        "app_factor": _num("Application factor K_A: 1.0 smooth, 1.25 light shocks (default), 1.5 moderate, 1.75 heavy."),
        "target_sf": _num("Target safety for tooth root / structure (default 1.4)."),
        "prefer": _enum(["small", "strong", "short"], "small = smallest gearbox (default); strong = the user gives the "
                        "SPACE available and/or asks for the strongest/most powerful drive: fill the space, maximise "
                        "torque; short = shortest."),
    }


def _design_props() -> Dict:
    props = {k: v for k, v in _requirement_props().items() if k not in (
        "output_speed", "ratio", "fit_bed", "prefer", "ratio_tol", "herringbone", "free_speed", "printer",
        "length_includes_motor", "motor_length", "planet_bearing")}
    props.update({
        "base": {"type": "string", "description": "Solution id to start from (e.g. 'R1.S1') or 'current' for the form."},
        "bearing_type": {"type": "string", "description": "Planet bearing code (e.g. 608ZZ) or AUTO."},
        "target_ratio": _num("Target ratio."),
        "is_herringbone": {"type": "boolean", "description": "Herringbone gears."},
        "sizing_mode": _enum(["AUTO", "MAX_OD", "MANUAL"], "AUTO = smallest housing meeting the strength targets, "
                                                           "MAX_OD = strongest within max_od, MANUAL = given module."),
        "module": _num("Module for MANUAL sizing, mm."),
        "out_hub": {"type": "string", "description": "Output hub bearing code (e.g. 6812ZZ) or AUTO."},
        "pin_type": _enum(["STEEL", "PRINTED"], "Planet pins: steel dowels (recommended) or printed."),
        "helix_angle": _num("Herringbone helix angle, degrees."),
        "ratio_from_load": {"type": "boolean", "description": "Use the lowest ratio that moves the application load "
                                                              "(load_value / load_radius) with the recommended reserve "
                                                              "instead of target_ratio."},
        "drive_torque": _num("SPEED_UP only: torque turning the output member (crank / rotor), Nm."),
        "drive_speed": _num("SPEED_UP only: speed of the output member (crank / rotor), rpm."),
    })
    return props


TOOLS = [
    {"name": "solve_requirements",
     "description": "Design a planetary gearbox from requirements. Derives the ratio and stage count, checks the motor, "
                    "searches face width / planet count / material within the size and print-bed limits and returns ranked "
                    "solutions (ids like R1.S1) with diagnostics. All numbers come from the engineering engine.",
     "parameters": {"type": "object", "properties": _requirement_props()}},
    {"name": "evaluate_design",
     "description": "Re-size a design with changed parameters (e.g. stronger material, larger diameter, lower safety target, "
                    "other output type). Starts from a solution id or the current form; returns up to 3 candidates (ids "
                    "like E1.1) with capacity, safety and warnings.",
     "parameters": {"type": "object", "properties": _design_props(), "required": ["base"]}},
    {"name": "get_current_design",
     "description": "Returns the parameters currently set in the application's form and the selected candidate."},
    {"name": "propose_design",
     "description": "Present a solution to the user as a card with 'Apply to form' / 'Apply and generate 3D' buttons. "
                    "Call it for the recommended design (and at most 2 alternatives) before the final answer.",
     "parameters": {"type": "object", "properties": {
         "solution_id": {"type": "string", "description": "Id returned by solve_requirements or evaluate_design."},
         "title": {"type": "string", "description": "Short title, e.g. 'Recommended: PA-CF, Ø245 × 210 mm'."},
         "summary": {"type": "string", "description": "1–3 sentences: why this design, what to watch out for."}},
         "required": ["solution_id", "title"]}},
]


def _system_prompt() -> str:
    motors = "; ".join(f"{c}: {m['name']} ~{m.get('torque_nm', '?')} Nm @ {m.get('speed_rpm', '?')} rpm, "
                       f"shaft Ø{m['default_shaft_dia']} {m['default_shaft_type']}" for c, m in MOTOR_CATALOG.items())
    mats = "; ".join(f"{c}: {m['name']} (bending allow. {m['sigma_F']} MPa, contact {m['sigma_H']} MPa)"
                     for c, m in MATERIALS.items() if m.get("printed", True))
    return f"""You are the design assistant inside "Planetary Gearbox Generator", a desktop app (also a Fusion 360 add-in)
that designs 3D-printable planetary gearboxes with a full engineering check (ISO 6336-style tooth bending and contact,
bearing life, pins, shafts, output hub) and then generates the CAD model, STL files, an engineering report and a parts list.
Many users are not engineers: explain simply, but be precise and honest.

HOW TO WORK
1. Read the request and extract: motor (preset or custom torque/speed/shaft), required output speed (convert motions:
   180° in 30 s = 1 rpm), required output torque, the available SPACE (diameter across the axis, length along it,
   including the motor), output type (flange, shaft or a lever arm with its length), material, printer, parts the user
   already has (e.g. 608ZZ bearings, no circlips → cage carrier). Pass output_speed — do NOT compute or pass a ratio
   unless the user states one. For steppers the engine picks the ratio: the motor speed is set by the driver.
   If something essential is missing (no speed or ratio, no idea of the motor) ask ONE short question; otherwise assume
   sensible defaults and say so. Never invent loads or arm sizes; the engine sizes the arm and reports the force it
   can hold.
   APPLICATION LOAD (optional, but it decides "suitable / not suitable"): when the user states what the gearbox has to
   move — a weight or force at the arm tip or on a rope/drum ("10 kg", "20 N"), or a torque — pass load_value +
   load_unit (+ load_radius for a pulley / drum / wheel; for an arm output the arm length is used). The engine then
   reports a verdict (load_check: ok / low = marginal / fail / incomplete) with the reason and what to change; quote
   it plainly ("✓ Uygun" / "⚠ Sınırda" / "✗ Uygun değil" + why). When the application obviously moves something
   (door, gate, lid, arm, winch, lift, conveyor, wheel) and the user did NOT state the load, still design it, and end
   your answer with ONE short optional question, e.g. "İsterseniz kolun ucundaki en büyük yükü (kg) yazın; tasarımın bu
   yükü çekip çekemeyeceğini kontrol edeyim." Do not block the design on this question and do not ask it again once
   the user answered or declined.
   Dimensions the user gives for the installation space are an envelope to FILL, not a size to shrink to: when the user
   gives the space and asks for a strong / the strongest / most powerful drive, use prefer="strong".
   Always pass the printer model (e.g. "Creality K1 Max") or its bed size, so parts are checked against the right bed.
2. Call solve_requirements. Never invent dimensions, capacities or safety factors — every number you state must come
   from a tool result.
3. If the result is infeasible or only partially meets the needs, explore at most 2–3 meaningful variations with
   evaluate_design or solve_requirements (e.g. PA-CF instead of PLA, larger diameter, a slightly lower safety target
   such as 1.25–1.3 when the application is gentle, fewer stages, a different output) and compare them.
4. Call propose_design for the best solution (and at most 2 alternatives). A design that does not meet the strength
   targets may only be proposed as "not recommended" with the gap stated clearly.
5. Answer briefly in the user's language (Turkish if they write Turkish): what you understood, the recommended design
   (ratio, output speed and torque, continuous capacity, outer diameter × length, material, output hub/bearings),
   important warnings (motor shaft, print bed, assembly), then what to do next ("Forma uygula" / "Uygula ve 3D oluştur"
   buttons on the card). Use short bullet points; no long essays. Do not repeat raw JSON.

DOMAIN NOTES
- One planetary stage gives ~3:1 to ~9:1; up to 5 stages share one ring gear. More planets share the load but fit only
  at lower stage ratios, so more stages (lower stage ratios) can make the last stage stronger in the same diameter;
  each stage costs ~5–6 % efficiency (4 stages ~78 %, 5 ~73 %), length and parts. Leave stages_count 0 (automatic)
  unless the user fixes it: the engine adds stages only when the space or the load needs them. Herringbone teeth are quieter and stronger (default).
- Printed plastic gears are limited mainly by tooth root bending and surface pressure of the last stage. PA-CF (carbon
  nylon) is the strongest common printable material; PETG/ABS are weaker than PLA in this model.
- Capacity ('max_output_torque') is the continuous output torque at the safety targets; 'margin' >= 1 means all targets
  are met. K_A 1.25 suits stepper/robotic drives with light shocks; a door or lid that hits end stops is 1.25–1.5.
- Load check: the needed torque is force × lever (10 kg at 29 cm = 98 N × 0.29 m = 28.4 Nm). The drive should deliver
  about 1.5× that with a stepper (pull-out torque falls with speed, a stepper short of torque loses steps), 1.25×
  otherwise. The solver already searches that much output torque when a load is given.
- Tooth depth (addendum coefficient, default 1.0): stub teeth (0.8) are stronger at the root and tolerate print errors
  but mesh with a lower contact ratio; long teeth (1.1–1.25) mesh more smoothly but have weaker roots and thin tips.
- A thin motor shaft (e.g. Ø5 mm) cannot transmit high torque; recommend a motor with a thicker shaft or a coupling.
- Steppers (NEMA17 17HS4401: 0.4 Nm holding, 42×42×40 mm; NEMA23 ~1–2 Nm) keep their torque best below ~300 rpm.
  For the strongest output at a given output speed the engine raises the ratio until the housing can no longer carry the
  full motor torque, and reports the driver current limit that would allow a higher ratio.
- The planet count is chosen per stage automatically (more planets at lower stage ratios = more torque).
- The output flange / arm hub uses captive M3 nuts in side pockets (no screws into bare plastic).
- ARRANGEMENTS. CARRIER (standard): ring = fixed housing, carrier output, i = 1 + Zr/Zs per stage. RING (rotating
  housing): the last stage is a "star" stage — its carrier is pinned to a fixed base plate, the ring is a drum with a
  lid that turns on one ball bearing seated on the fixed carrier; i = Zr/Zs for that stage (one less) and the output
  turns the opposite way. Suggest RING when the user wants a wheel hub, a winch / rope drum, a turntable, a conveyor
  drum, or an arm / gate bolted onto a large rotating face; it may come out ~20 % larger for the same torque (the
  tooth forces of a star stage are higher). SPEED_UP: a standard gearbox driven from the output (hand crank, wind
  rotor) with the motor as a generator; generator speed = input speed × ratio; keep ratios ≤ 30:1 (friction and the
  motor's cogging torque grow by the ratio at the input) — set it up via evaluate_design with drive_torque /
  drive_speed, the solver does not design speed-ups.
- WOLFROM (stepped planets: the sun and a fixed ring drive one gear of each planet, its second gear drives an output
  ring with 1-3 teeth more or less): 50-500:1 in ONE short stage, the output ring turns as a lidded drum. Efficiency is
  only 15-60 % and above ~80:1 it is usually self-locking (holds the load without power, cannot be back-driven - say so).
  CYCLOID (cycloidal drive): 6-60:1 in one stage, no teeth, shock-proof and nearly backlash-free (robot joints,
  turntables, camera heads), ~80 % efficient, needs steel dowel pins and grease, output turns backwards. Both ignore the
  stage count, herringbone, carrier type and profile shift; use evaluate_design (solve_requirements does not design them).
- Inter-stage suns are printed in one piece with the previous carrier (no D-shaft between stages).
- Long arms that do not fit the bed: the engine says whether they fit diagonally; otherwise suggest a split arm.
- Parts must fit the user's print bed (given in the form); oversize housings or arms need a bigger printer or splitting.
- Motor presets: {motors}.
- Printable materials: {mats}."""


class Job:
    def __init__(self, jid: str):
        self.id = jid
        self.status = "running"
        self.steps: List[Dict] = []
        self.reply = ""
        self.proposals: List[Dict] = []
        self.error = ""
        self.model = ""
        self.started = time.time()

    def snapshot(self) -> Dict:
        return {"success": True, "job": self.id, "status": self.status, "steps": list(self.steps),
                "reply": self.reply, "proposals": list(self.proposals), "error": self.error, "model": self.model,
                "elapsed": round(time.time() - self.started, 1)}


class Assistant:
    """Konuşma geçmişi + iş kuyruğu. Api nesnesi başına bir tane."""

    def __init__(self, settings_provider: Callable[[], Dict], client_factory: Callable[[str, str], "gemini.GeminiClient"],
                 model_resolver: Callable[[], List[str]]):
        self._settings = settings_provider
        self._client_factory = client_factory
        self._models = model_resolver
        self.history: List[Dict] = []
        self.solutions: Dict[str, Dict] = {}
        self.jobs: Dict[str, Job] = {}
        self._counter = {"R": 0, "E": 0}
        self._form: Dict = {}

    # ── public ────────────────────────────────────────────────────────────────
    def busy(self) -> bool:
        return any(j.status == "running" for j in self.jobs.values())

    def reset(self) -> bool:
        if self.busy():
            return False
        self.history.clear()
        self.solutions.clear()
        self._counter = {"R": 0, "E": 0}
        return True

    def send(self, message: str, form_state: Optional[Dict], lang: str) -> Job:
        if self.busy():
            raise RuntimeError("Önceki istek hâlâ sürüyor." if lang != "en" else "The previous request is still running.")
        job = Job(uuid.uuid4().hex[:12])
        self.jobs[job.id] = job
        for old in [k for k, j in self.jobs.items() if j.status != "running" and time.time() - j.started > 3600]:
            self.jobs.pop(old, None)
        t = threading.Thread(target=self._run, args=(job, str(message or ""), dict(form_state or {}), lang),
                             name="pgb-ai", daemon=True)
        t.start()
        return job

    def poll(self, jid: str) -> Dict:
        job = self.jobs.get(jid)
        if job is None:
            return {"success": False, "error": "unknown job"}
        return job.snapshot()

    # ── worker ────────────────────────────────────────────────────────────────
    def _step(self, job: Job, kind: str, text: str) -> None:
        job.steps.append({"kind": kind, "text": text, "t": round(time.time() - job.started, 1)})

    def _run(self, job: Job, message: str, form: Dict, lang: str) -> None:
        tr = lang != "en"
        try:
            self._form = form
            key = self._settings().get("api_key")
            if not key:
                raise gemini.GeminiError("Gemini API anahtarı girilmemiş (AI Asistan → Ayarlar)." if tr
                                         else "No Gemini API key (AI Assistant → Settings).")
            candidates = self._models()
            if not candidates:
                raise gemini.GeminiError("Kullanılabilir Gemini modeli bulunamadı." if tr else "No Gemini model available.")
            start_len = len(self.history)
            self.history.append({"role": "user", "parts": [{"text": message}]})
            try:
                self._converse(job, key, candidates, tr)
            except Exception:
                del self.history[start_len:]            # yarım kalan turu geçmişe bırakma
                raise
            self._trim()
            job.status = "done"
        except gemini.GeminiError as e:
            job.error = str(e)
            job.status = "error"
        except Exception as e:  # pragma: no cover - beklenmeyen hata
            log.error("AI asistan hatası: %s", traceback.format_exc())
            job.error = f"{type(e).__name__}: {e}"
            job.status = "error"

    def _converse(self, job: Job, key: str, models: List[str], tr: bool) -> None:
        system = _system_prompt()
        tools = [dict(t, parameters=gemini.to_openapi(t["parameters"])) if "parameters" in t else dict(t)
                 for t in TOOLS]
        model_idx = 0
        client = self._client_factory(key, models[0])
        job.model = models[0]
        for rnd in range(MAX_ROUNDS + 1):
            mode = "AUTO" if rnd < MAX_ROUNDS else "NONE"
            self._step(job, "think", (f"{client.model} düşünüyor…" if tr else f"{client.model} is thinking…"))
            try:
                res = client.generate(self.history, system, tools, mode)
            except gemini.GeminiError as e:
                # otomatik model seçimi: kota/erişim yoksa sıradaki en güçlü modele geç
                if (e.quota or e.status in (403, 404)) and model_idx + 1 < len(models) and \
                        self._settings().get("model", "auto") == "auto":
                    model_idx += 1
                    self._step(job, "info", (f"{client.model} kullanılamıyor ({e.status}); {models[model_idx]} deneniyor."
                                             if tr else f"{client.model} unavailable ({e.status}); trying {models[model_idx]}."))
                    client = self._client_factory(key, models[model_idx])
                    job.model = client.model
                    continue
                raise
            content = res["content"]
            self.history.append(content)
            calls = gemini.function_calls(content)
            if not calls:
                job.reply = gemini.text_of(content).strip() or ("(boş yanıt)" if tr else "(empty answer)")
                return
            responses = []
            for call in calls:
                name = call.get("name", "")
                args = call.get("args") or {}
                out = self._execute(job, name, args, tr)
                part = {"functionResponse": {"name": name, "response": out}}
                if call.get("id"):
                    part["functionResponse"]["id"] = call["id"]
                responses.append(part)
            self.history.append({"role": "user", "parts": responses})
        job.reply = job.reply or ("Asistan yanıtı tamamlayamadı." if tr else "The assistant could not finish.")

    def _trim(self) -> None:
        """Son HISTORY_TURNS kullanıcı mesajından eskisini at (araç çağrısı/yanıt çiftleri bölünmez)."""
        starts = [i for i, c in enumerate(self.history)
                  if c.get("role") == "user" and any("text" in p for p in c.get("parts", []))]
        if len(starts) > HISTORY_TURNS:
            del self.history[:starts[-HISTORY_TURNS]]

    # ── tools ─────────────────────────────────────────────────────────────────
    def _execute(self, job: Job, name: str, args: Dict, tr: bool) -> Dict:
        try:
            if name == "solve_requirements":
                return self._tool_solve(job, args, tr)
            if name == "evaluate_design":
                return self._tool_evaluate(job, args, tr)
            if name == "get_current_design":
                self._step(job, "tool", "Formdaki mevcut ayarlar okundu." if tr else "Read the current form settings.")
                return self._form_summary()
            if name == "propose_design":
                return self._tool_propose(job, args, tr)
            return {"error": f"unknown tool {name}"}
        except Exception as e:
            log.error("AI aracı %s hatası: %s", name, traceback.format_exc())
            self._step(job, "error", f"{name}: {e}")
            return {"error": str(e)}

    def _defaults(self) -> Dict:
        f = self._form
        out = {"lang": f.get("lang", "tr")}
        for k in ("bed_x", "bed_y", "bed_z"):
            if f.get(k):
                out[k] = f[k]
        return out

    def _tool_solve(self, job: Job, args: Dict, tr: bool) -> Dict:
        req = dict(self._defaults(), **{k: v for k, v in args.items() if v is not None})
        desc = []
        if req.get("output_speed"):
            desc.append(f"{req.get('motor_speed', '?')}→{req['output_speed']} rpm")
        elif req.get("ratio"):
            desc.append(f"{req['ratio']}:1")
        if req.get("min_output_torque"):
            desc.append(f"≥{req['min_output_torque']} Nm")
        if req.get("load_value"):
            desc.append(("yük " if tr else "load ") + f"{req['load_value']} {str(req.get('load_unit') or 'KG').lower()}")
        if req.get("max_od") or req.get("max_length"):
            desc.append(f"Ø{req.get('max_od') or '–'}×{req.get('max_length') or '–'} mm")
        self._step(job, "tool", ("Gereksinimler çözülüyor: " if tr else "Solving requirements: ") + ", ".join(desc))
        res = solve(req)
        self._counter["R"] += 1
        prefix = f"R{self._counter['R']}."
        sols = []
        for s in res["solutions"]:
            sid = prefix + s["id"]
            self.solutions[sid] = dict(s, id=sid)
            sols.append(self._compact(sid, s))
        best = sols[0] if sols else None
        if best:
            self._step(job, "result", "→ " + self._line(best, tr))
        else:
            self._step(job, "result", "→ çözüm yok" if tr else "→ no solution")
        return {"status": res["status"], "derived": res["derived"],
                "diagnostics": [f"[{d['severity']}] {d['text']}" for d in res["diagnostics"]], "solutions": sols}

    def _tool_evaluate(self, job: Job, args: Dict, tr: bool) -> Dict:
        base_id = str(args.get("base") or "current")
        if base_id in self.solutions:
            base = dict(self.solutions[base_id]["payload"])
        else:
            base = dict(self._form)
        over = {k: v for k, v in args.items() if k != "base" and v is not None}
        if "herringbone" in over:
            over["is_herringbone"] = over.pop("herringbone")
        if "gear_material" in over and "struct_material" not in over:
            over["struct_material"] = over["gear_material"]
        payload = dict(base, **over)
        for k in ("stages", "total_ratio"):
            payload.pop(k, None)
        payload.setdefault("lang", self._form.get("lang", "tr"))
        self._step(job, "tool", ("Tasarım deneniyor: " if tr else "Trying design: ") +
                   ", ".join(f"{k}={v}" for k, v in over.items()))
        res = design(payload, max_results=3)
        self._counter["E"] += 1
        out = []
        for i, c in enumerate(res["candidates"], 1):
            sid = f"E{self._counter['E']}.{i}"
            e = c["engineering"]
            sol = {"id": sid, "recommended": c["feasible"], "label": c["label"], "material": payload.get("gear_material"),
                   "num_planets": payload.get("num_planets"), "face_width": payload.get("face_width"),
                   "stages": len(c["stages"]), "ratio": c["total_ratio"], "module": c["module"], "z_ring": c["z_ring"],
                   "outer_diameter": c["outer_diameter"], "overall_length": c.get("overall_length"),
                   "output_speed": round(e["output_speed"], 3), "output_torque": round(e["output_torque"], 1),
                   "max_output_torque": round(e["max_output_torque"], 1), "margin": c["margin"],
                   "limiting": e["limiting"]["label"] if e["limiting"] else "", "bed_ok": c.get("bed_ok", True),
                   "output": {"type": c["output"]["type"], "bearing": c["output"]["bearing"], "hub_d": c["output"]["hub_d"],
                              **({"drum_od": round(c["output"]["drum_od"], 1)} if c["output"].get("drum") else {})},
                   "arrangement": str(payload.get("arrangement") or "CARRIER").upper(),
                   "speedup": (e.get("speedup") or {}).get("text"),
                   "load_check": load_summary(c.get("load")),
                   "feasible": c["feasible"], "issues": c["issues"], "warnings": [],
                   "payload": self._fixed_payload(payload, c)}
            self.solutions[sid] = sol
            out.append(self._compact(sid, sol))
        if out:
            self._step(job, "result", "→ " + self._line(out[0], tr))
        res_out = {"candidates": out, "note": "margin >= 1 means all strength targets met" if out else "no candidate"}
        if res.get("auto"):                      # automatic stage count / ratio from the load: what was chosen and why
            res_out["auto"] = res["auto"]["note"]
        if not out and res.get("hint"):
            res_out["hint"] = res["hint"]
        return res_out

    @staticmethod
    def _fixed_payload(payload: Dict, c: Dict) -> Dict:
        """A candidate as a form payload: an automatic stage count / ratio from the load become the values found."""
        out = dict(payload, total_ratio=c["total_ratio"], stages=c["stages"], module=c["module"],
                   stages_count=len(c["stages"]))
        if out.pop("ratio_from_load", False):
            out["target_ratio"] = c["total_ratio"]
        return out

    def _tool_propose(self, job: Job, args: Dict, tr: bool) -> Dict:
        sid = str(args.get("solution_id", ""))
        sol = self.solutions.get(sid)
        if not sol:
            return {"error": f"unknown solution id {sid}"}
        if any(p["id"] == sid for p in job.proposals):
            return {"ok": True}
        card = {"id": sid, "title": str(args.get("title") or sol.get("label", sid)),
                "summary": str(args.get("summary") or ""), "recommended": bool(sol.get("recommended", sol.get("feasible"))),
                "metrics": {k: sol.get(k) for k in ("ratio", "output_speed", "output_torque", "max_output_torque",
                                                    "margin", "outer_diameter", "overall_length", "material",
                                                    "num_planets", "face_width", "module", "z_ring", "bed_ok",
                                                    "limiting")},
                "load_check": sol.get("load_check"),
                "output": sol.get("output"), "warnings": sol.get("warnings", [])[:6], "payload": sol["payload"]}
        job.proposals.append(card)
        self._step(job, "tool", ("Öneri hazırlandı: " if tr else "Proposal ready: ") + card["title"])
        return {"ok": True}

    # ── helpers ───────────────────────────────────────────────────────────────
    @staticmethod
    def _compact(sid: str, s: Dict) -> Dict:
        keys = ("recommended", "material", "num_planets", "face_width", "stages", "ratio", "module", "z_ring",
                "outer_diameter", "overall_length", "output_speed", "output_torque", "max_output_torque", "margin",
                "limiting", "bed_ok", "output", "load_check", "arrangement", "speedup")
        out = {"id": sid}
        out.update({k: s.get(k) for k in keys})
        out["warnings"] = (s.get("warnings") or [])[:5]
        return out

    @staticmethod
    def _line(s: Dict, tr: bool) -> str:
        cap = s.get("max_output_torque")
        txt = (f"{s.get('ratio')}:1 · Ø{s.get('outer_diameter')}×{s.get('overall_length')} mm · "
               f"{s.get('material')} · {'kapasite' if tr else 'capacity'} {cap} Nm · S {s.get('margin')}")
        return txt + ("" if s.get("recommended") else (" · yetersiz" if tr else " · insufficient"))

    def _form_summary(self) -> Dict:
        f = self._form
        keys = ("target_ratio", "stages_count", "num_planets", "sizing_mode", "max_od", "max_length", "is_herringbone",
                "face_width", "motor_preset", "motor_torque", "motor_speed", "motor_shaft_dia", "motor_shaft_type",
                "gear_material", "struct_material", "output_type", "out_hub", "arm_shape", "arm_length", "arm_width",
                "arm_thickness", "load_value", "load_unit", "load_radius", "addendum_coef", "app_factor", "target_sf",
                "bed_x", "bed_y", "bed_z")
        out = {k: f.get(k) for k in keys if k in f}
        if f.get("_candidate"):
            out["selected_candidate"] = f["_candidate"]
        return out


def compact_json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
