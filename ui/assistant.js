/**
 * AI Tasarım Asistanı sekmesi (Gemini) + AI'sız gereksinim çözücü.
 * Python tarafı: Api.ai_send / ai_poll (arka plan işi), solve_requirements, ai_settings_*.
 * Öneri kartları "Forma uygula" ile formu doldurur ve önerilen diş kombinasyonunu seçer.
 */
(function () {
  'use strict';

  let aiJob = null;
  let aiTimer = null;
  let aiSettings = null;
  let pendingTurn = null;          // {bubble, stepsEl, seen}

  const $ = (id) => document.getElementById(id);

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  /* Minimal, safe Markdown: escape first, then **bold**, `code`, bullet and numbered lists, paragraphs */
  function mdLite(text) {
    const lines = esc(text).split(/\r?\n/);
    let html = '';
    let list = null;
    const inline = (s) => s.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/`([^`]+)`/g, '<code>$1</code>');
    const close = () => { if (list) { html += `</${list}>`; list = null; } };
    lines.forEach(line => {
      const b = line.match(/^\s*[-*•]\s+(.*)$/);
      const n = line.match(/^\s*\d+[.)]\s+(.*)$/);
      if (b || n) {
        const kind = b ? 'ul' : 'ol';
        if (list !== kind) { close(); html += `<${kind}>`; list = kind; }
        html += `<li>${inline((b || n)[1])}</li>`;
      } else if (/^\s*#{1,4}\s+/.test(line)) {
        close();
        html += `<div class="ai-h">${inline(line.replace(/^\s*#{1,4}\s+/, ''))}</div>`;
      } else if (line.trim() === '') {
        close();
      } else {
        close();
        html += `<p>${inline(line)}</p>`;
      }
    });
    close();
    return html;
  }

  function scrollLog() {
    const log = $('ai_log');
    log.scrollTop = log.scrollHeight;
  }

  function bubble(role, html) {
    const b = el('div', `ai-msg ai-${role}`);
    b.innerHTML = html;
    $('ai_log').appendChild(b);
    scrollLog();
    return b;
  }

  function formState() {
    const f = collectParams();
    const cand = currentCandidates && currentCandidates[selectedCandidateIndex];
    if (cand) f._candidate = cand.label;
    return f;
  }

  /* ── settings ─────────────────────────────────────────────────────────── */
  function renderChip() {
    const chip = $('ai_chip');
    if (!chip) return;
    if (!aiSettings || !aiSettings.has_key) {
      chip.textContent = tr('aiNoKey', 'anahtar yok');
      chip.className = 'ai-chip ai-chip-off';
      return;
    }
    const model = aiSettings.model && aiSettings.model !== 'auto' ? aiSettings.model : tr('aiAutoShort', 'otomatik model');
    chip.textContent = `Gemini · ${model}`;
    chip.className = 'ai-chip ai-chip-on';
  }

  function fillModelSelect(models, current) {
    const sel = $('ai_model');
    const keep = current || sel.value || 'auto';
    sel.innerHTML = '';
    const auto = el('option', '', tr('aiModelAuto', 'Otomatik — hesabınızdaki en güçlü model'));
    auto.value = 'auto';
    sel.appendChild(auto);
    (models || []).forEach(m => {
      const o = el('option', '', m.name && m.name !== m.id ? `${m.name} (${m.id})` : m.id);
      o.value = m.id;
      sel.appendChild(o);
    });
    if (keep && ![...sel.options].some(o => o.value === keep)) {
      const o = el('option', '', keep);
      o.value = keep;
      sel.appendChild(o);
    }
    sel.value = keep;
  }

  async function loadSettings() {
    try {
      aiSettings = await Host.call('ai_settings_get');
    } catch (e) {
      aiSettings = null;
    }
    renderChip();
    if (aiSettings) {
      fillModelSelect(aiSettings.models, aiSettings.model);
      $('ai_key_status').textContent = aiSettings.has_key
        ? `${tr('aiKeySaved', 'Kayıtlı anahtar')}: ${aiSettings.key_hint}${aiSettings.protected ? ' · ' + tr('aiKeyProtected', 'Windows ile şifreli') : ''}`
        : tr('aiKeyNone', 'Henüz anahtar girilmedi.');
    }
  }

  function openSettings() {
    loadSettings();
    $('ai_settings_overlay').classList.add('active');
    setTimeout(() => $('ai_key').focus(), 50);
  }

  async function saveKey() {
    const v = $('ai_key').value.trim();
    if (!v) return;
    const r = await Host.call('ai_settings_set', { api_key: v, model: $('ai_model').value || 'auto' });
    $('ai_key').value = '';
    if (!r || !r.success) {
      $('ai_key_status').textContent = `${tr('errorPrefix', 'Hata')}: ${r ? r.error : '?'}`;
      return;
    }
    aiSettings = r;
    await loadSettings();
    listModels();
  }

  async function clearKey() {
    aiSettings = await Host.call('ai_settings_set', { api_key: '', clear_key: true });
    await loadSettings();
  }

  async function listModels() {
    $('ai_model_status').textContent = tr('aiLoadingModels', 'Modeller alınıyor…');
    const r = await Host.call('ai_list_models');
    if (!r || !r.success) {
      $('ai_model_status').textContent = `${tr('errorPrefix', 'Hata')}: ${r ? r.error : '?'}`;
      return;
    }
    fillModelSelect(r.models, $('ai_model').value);
    $('ai_model_status').textContent = `${r.models.length} ${tr('aiModelsFound', 'model')} · ${tr('aiAutoPick', 'otomatik seçim')}: ${r.auto || '-'}`;
  }

  async function testConnection() {
    $('ai_model_status').textContent = tr('aiTesting', 'Bağlantı deneniyor…');
    const r = await Host.call('ai_test');
    $('ai_model_status').textContent = r && r.success
      ? `✓ ${r.model} · ${r.seconds} s`
      : `✗ ${r ? r.error : '?'}`;
  }

  async function modelChanged() {
    aiSettings = await Host.call('ai_settings_set', { model: $('ai_model').value || 'auto' });
    renderChip();
  }

  /* ── chat ─────────────────────────────────────────────────────────────── */
  function setBusy(on) {
    $('ai_send').disabled = on;
    $('ai_input').disabled = on;
    $('ai_send').textContent = on ? tr('aiWorking', 'Çalışıyor…') : tr('aiSend', 'Gönder');
  }

  async function send(textArg) {
    const text = (textArg != null ? textArg : $('ai_input').value).trim();
    if (!text || aiJob) return;
    if (!aiSettings || !aiSettings.has_key) {
      bubble('note', esc(tr('aiNeedKey', 'Önce ⚙ Ayarlar\'dan Gemini API anahtarınızı girin. Anahtar olmadan aşağıdaki "Gereksinim formu" ile de çözüm alabilirsiniz.')));
      openSettings();
      return;
    }
    $('ai_input').value = '';
    bubble('user', esc(text).replace(/\n/g, '<br>'));
    const b = bubble('assistant', '');
    const steps = el('div', 'ai-steps');
    b.appendChild(steps);
    pendingTurn = { bubble: b, stepsEl: steps, seen: 0 };
    setBusy(true);
    let r;
    try {
      r = await Host.call('ai_send', text, formState());
    } catch (e) {
      r = { success: false, error: e.message || String(e) };
    }
    if (!r || !r.success) {
      finishTurn({ status: 'error', error: r ? r.error : '?' });
      return;
    }
    aiJob = r.job;
    aiTimer = setInterval(poll, 800);
  }

  async function poll() {
    if (!aiJob) return;
    let st;
    try {
      st = await Host.call('ai_poll', aiJob);
    } catch (e) {
      return;
    }
    if (!st || !pendingTurn) return;
    const steps = st.steps || [];
    for (let i = pendingTurn.seen; i < steps.length; i++) {
      const s = steps[i];
      const row = el('div', `ai-step ai-step-${s.kind}`, s.text);
      pendingTurn.stepsEl.appendChild(row);
    }
    pendingTurn.seen = steps.length;
    scrollLog();
    if (st.status !== 'running') finishTurn(st);
  }

  function finishTurn(st) {
    if (aiTimer) clearInterval(aiTimer);
    aiTimer = null;
    aiJob = null;
    setBusy(false);
    const turn = pendingTurn;
    pendingTurn = null;
    if (!turn) return;
    turn.stepsEl.classList.add('ai-steps-done');
    if (st.status === 'error') {
      const e = el('div', 'ai-error');
      e.textContent = `${tr('errorPrefix', 'Hata')}: ${st.error}`;
      turn.bubble.appendChild(e);
    } else {
      const body = el('div', 'ai-text');
      body.innerHTML = mdLite(st.reply || '');
      turn.bubble.appendChild(body);
      (st.proposals || []).forEach(p => turn.bubble.appendChild(proposalCard(p)));
      if (st.model) turn.bubble.appendChild(el('div', 'ai-meta', `${st.model} · ${st.elapsed} s`));
    }
    scrollLog();
  }

  /* ── proposals ────────────────────────────────────────────────────────── */
  function metricRows(m, out) {
    const rows = [
      [tr('sumRatio', 'Oran'), m.ratio != null ? `${m.ratio} : 1` : null],
      [tr('aiOutSpeed', 'Çıkış devri'), m.output_speed != null ? `${m.output_speed} rpm` : null],
      [tr('sumOutTorque', 'Çıkış torku'), m.output_torque != null ? `${m.output_torque} Nm` : null],
      [tr('sumMaxTorque', 'Sürekli kapasite'), m.max_output_torque != null ? `${m.max_output_torque} Nm` : null],
      [tr('metricSafety', 'Emniyet Marjı'), m.margin != null ? `${m.margin}` : null],
      [tr('aiSize', 'Ölçü'), m.outer_diameter != null ? `Ø${m.outer_diameter} × ${m.overall_length} mm` : null],
      [tr('aiMaterial', 'Malzeme'), m.material],
      [tr('aiGearing', 'Dişli'), m.module != null ? `m${m.module} · Zr${m.z_ring} · ${m.num_planets} planet · b ${m.face_width} mm` : null],
      [tr('metricOutHub', 'Çıkış Göbeği'), out ? `${out.type} · Ø${out.hub_d} · ${out.bearing}` : null],
      [tr('metricBed', 'Tablaya Sığma'), m.bed_ok === false ? tr('bedNo', '✗ büyük') : tr('bedYes', '✓ sığar')],
    ];
    return rows.filter(r => r[1] != null && r[1] !== undefined);
  }

  function proposalCard(p) {
    const card = el('div', `ai-card${p.recommended ? '' : ' ai-card-weak'}`);
    const head = el('div', 'ai-card-head');
    head.appendChild(el('span', 'ai-card-title', p.title || p.id));
    head.appendChild(el('span', `ai-tag ${p.recommended ? 'ai-tag-ok' : 'ai-tag-bad'}`,
      p.recommended ? tr('aiRecommended', 'önerilen') : tr('aiNotRecommended', 'hedefleri karşılamıyor')));
    card.appendChild(head);
    if (p.summary) card.appendChild(el('div', 'ai-card-summary', p.summary));
    const grid = el('div', 'ai-card-grid');
    metricRows(p.metrics || {}, p.output).forEach(([k, v]) => {
      grid.appendChild(el('span', 'ai-k', k));
      grid.appendChild(el('span', 'ai-v', v));
    });
    card.appendChild(grid);
    const lc = p.load_check || (p.metrics && p.metrics.load_check);
    if (lc) {
      const lv = el('div', `load-verdict ${lc.status}`, lc.text);
      card.appendChild(lv);
    }
    if (p.warnings && p.warnings.length) {
      const det = el('details', 'ai-card-warn');
      det.appendChild(el('summary', '', `${tr('sideWarnings', 'Uyarılar')} (${p.warnings.length})`));
      const ul = el('ul', 'warning-list');
      p.warnings.forEach(w => ul.appendChild(el('li', '', w)));
      det.appendChild(ul);
      card.appendChild(det);
    }
    const act = el('div', 'ai-card-actions');
    const apply = el('button', 'btn btn-secondary btn-sm', tr('aiApply', 'Forma uygula'));
    apply.addEventListener('click', () => applyProposal(p.payload, false));
    const gen = el('button', 'btn btn-primary btn-sm', tr('aiApplyGenerate', 'Uygula ve 3D oluştur'));
    gen.addEventListener('click', () => applyProposal(p.payload, true));
    act.appendChild(apply);
    act.appendChild(gen);
    card.appendChild(act);
    return card;
  }

  function setField(id, value) {
    const e = document.getElementById(id);
    if (!e || value === undefined || value === null) return;
    if (e.type === 'checkbox') e.checked = !!value;
    else if (e.tagName === 'SELECT') {
      const v = String(value);
      const num = parseFloat(v);
      // numeric options ("1.0" vs 1) must match by value, not by text
      const match = [...e.options].find(o => o.value === v || (!isNaN(num) && parseFloat(o.value) === num
        && /^[\d.]+$/.test(o.value)));
      if (match) {
        e.value = match.value;
      } else {
        const o = document.createElement('option');
        o.value = v;
        o.textContent = v;
        e.appendChild(o);
        e.value = v;
      }
    } else e.value = value;
  }

  /* Fill the whole form from an engine payload, then re-run the design and pick the proposed tooth set */
  function applyProposal(payload, generate) {
    if (!payload) return;
    const skip = new Set(['stages', 'total_ratio', 'lang', 'od_limit', 'action', 'is_herringbone', 'profile_shift']);
    Object.keys(payload).forEach(k => { if (!skip.has(k)) setField(k, payload[k]); });
    const herring = !!payload.is_herringbone;
    document.querySelectorAll('input[name="gear_type"]').forEach(r => {
      r.checked = (r.value === 'HERRINGBONE') === herring;
      const card = r.closest('.radio-card');
      if (card) card.classList.toggle('selected', r.checked);
    });
    if (payload.bed_x) setField('bed_preset', 'CUSTOM');
    const rfl = $('ratio_from_load');                   // the proposal's ratio is kept as it is
    if (rfl) rfl.checked = false;
    const ps = payload.profile_shift;                   // a number is a manual shift of the sun
    if (ps !== undefined && ps !== null && ps !== '' && !isNaN(Number(ps))) {
      setField('profile_shift', 'CUSTOM');
      setField('profile_shift_x', Number(ps));
    } else setField('profile_shift', ps ? String(ps).toUpperCase() : 'AUTO');
    const stages = payload.stages || [];
    window.pendingApply = {
      sig: stages.map(s => `${s.z_sun}/${s.z_planet}/${s.z_ring}`).join('|') + `@${payload.module}`,
      generate: !!generate,
      // the engine lists this exact tooth set first (the plain search may rank or time it out)
      pin: { stages: stages.map(s => ({ z_sun: s.z_sun, z_planet: s.z_planet, z_ring: s.z_ring,
                                        num_planets: s.num_planets })), module: payload.module },
    };
    updateVisibility();
    recalculateKinematics && recalculateKinematics();
    requestDesign();
    const first = document.querySelector('.tab-btn[data-tab="tab-power"]');
    if (first && !generate) first.click();
  }

  /* ── offline requirement solver ───────────────────────────────────────── */
  function initRequirementForm(catalogs) {
    const mSel = $('rq_motor_preset');
    if (mSel && !mSel.options.length) {
      const src = document.getElementById('motor_preset');
      [...src.options].forEach(o => { const c = o.cloneNode(true); mSel.appendChild(c); });
      mSel.value = src.value;
      const fillMotor = () => {
        const m = (window.MOTOR_PRESETS || {})[mSel.value] || MOTOR_PRESETS[mSel.value];
        if (!m) return;
        if (m.torque != null) $('rq_motor_torque').value = m.torque;
        if (m.speed != null) $('rq_motor_speed').value = m.speed;
        if (m.shaft_dia != null) $('rq_motor_shaft_dia').value = m.shaft_dia;
      };
      mSel.addEventListener('change', fillMotor);
      fillMotor();
    }
    const matSel = $('rq_gear_material');
    if (matSel && catalogs && catalogs.materials && matSel.options.length <= 1) {
      catalogs.materials.filter(m => m.printed).forEach(m => {
        const o = el('option', '', m.name);
        o.value = m.code;
        matSel.appendChild(o);
      });
    }
  }

  async function solveOffline() {
    const num = (id) => parseFloat($(id).value) || 0;
    const f = collectParams();
    const req = {
      motor_preset: $('rq_motor_preset').value, motor_torque: num('rq_motor_torque'), motor_speed: num('rq_motor_speed'),
      motor_shaft_dia: num('rq_motor_shaft_dia'), motor_shaft_type: f.motor_shaft_type,
      output_speed: num('rq_output_speed'), ratio: num('rq_ratio'), min_output_torque: num('rq_min_output_torque'),
      max_od: num('rq_max_od'), max_length: num('rq_max_length'), gear_material: $('rq_gear_material').value,
      output_type: $('rq_output_type').value, prefer: $('rq_prefer').value, herringbone: f.is_herringbone,
      // a winch drum is a rotating-housing output; flange / arm become the drum flange / drum arm there
      arrangement: $('rq_output_type').value === 'DRUM_WINCH' ? 'RING' : $('rq_arrangement').value,
      rope_dia: f.rope_dia,
      arm_shape: f.arm_shape, arm_length: f.arm_length,          // arm section: sized for the torque by the solver
      load_value: num('rq_load_value'), load_unit: $('rq_load_unit').value, load_radius: num('rq_load_radius'),
      addendum_coef: f.addendum_coef,
      bed_x: f.bed_x, bed_y: f.bed_y, bed_z: f.bed_z, app_factor: f.app_factor,
      target_sf: f.target_sf, fit_bed: f.fit_bed, hub_fastener: f.hub_fastener, carrier_type: f.carrier_type,
      pin_type: f.pin_type, planet_bearing: f.bearing_type, length_includes_motor: $('rq_len_motor').checked,
      lang: currentLang,
    };
    const btn = $('rq_solve');
    btn.disabled = true;
    btn.textContent = tr('aiWorking', 'Çalışıyor…');
    const b = bubble('assistant', `<div class="ai-steps"><div class="ai-step ai-step-tool">${esc(tr('rqSolving', 'Gereksinimler çözülüyor (AI kullanılmadan)…'))}</div></div>`);
    let r;
    try {
      r = await Host.call('solve_requirements', req);
    } catch (e) {
      r = { success: false, error: e.message || String(e) };
    }
    btn.disabled = false;
    btn.textContent = tr('rqSolve', 'Çöz');
    if (!r || !r.success) {
      b.appendChild(el('div', 'ai-error', `${tr('errorPrefix', 'Hata')}: ${r ? r.error : '?'}`));
      return;
    }
    const d = r.derived || {};
    const lines = [];
    if (d.ratio) lines.push(`**${tr('sumRatio', 'Oran')}:** ${d.ratio}:1 · ${d.stages || '?'} ${tr('stageWord', 'kademe')} · η ${d.efficiency}`);
    if (d.output_torque_nominal != null) lines.push(`**${tr('sumOutTorque', 'Çıkış torku')}:** ${d.output_torque_nominal} Nm @ ${d.output_speed} rpm`);
    (r.diagnostics || []).forEach(x => lines.push(`- ${x.severity === 'error' ? '⛔' : x.severity === 'warn' ? '⚠' : 'ℹ'} ${x.text}`));
    const body = el('div', 'ai-text');
    body.innerHTML = mdLite(lines.join('\n'));
    b.appendChild(body);
    (r.solutions || []).forEach(s => b.appendChild(proposalCard({
      id: s.id, title: `${s.id}: ${s.label}`, summary: '', recommended: s.recommended,
      metrics: s, output: s.output, warnings: s.warnings, payload: s.payload,
    })));
    b.appendChild(el('div', 'ai-meta', `${tr('rqOffline', 'AI kullanılmadı')} · ${r.elapsed} s`));
    scrollLog();
  }

  /* ── init ─────────────────────────────────────────────────────────────── */
  window.initAssistant = function () {
    const tab = $('tab-ai');
    if (!tab || tab.dataset.ready) return;
    tab.dataset.ready = '1';
    // the chat needs the room of the live summary card while the AI tab is open
    document.querySelectorAll('.tab-btn').forEach(b => b.addEventListener('click', () => {
      document.body.classList.toggle('ai-active', b.getAttribute('data-tab') === 'tab-ai');
    }));
    $('ai_send').addEventListener('click', () => send());
    $('ai_input').addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); send(); }
    });
    document.querySelectorAll('#ai_examples .ai-example').forEach(b => b.addEventListener('click', () => {
      $('ai_input').value = b.textContent;
      $('ai_input').focus();
    }));
    $('ai_new').addEventListener('click', async () => {
      if (aiJob) return;
      await Host.call('ai_reset');
      $('ai_log').innerHTML = '';
    });
    $('ai_settings_btn').addEventListener('click', openSettings);
    $('ai_settings_close').addEventListener('click', () => $('ai_settings_overlay').classList.remove('active'));
    $('ai_settings_overlay').addEventListener('click', (e) => {
      if (e.target === $('ai_settings_overlay')) $('ai_settings_overlay').classList.remove('active');
    });
    $('ai_key_save').addEventListener('click', saveKey);
    $('ai_key').addEventListener('keydown', (e) => { if (e.key === 'Enter') saveKey(); });
    $('ai_key_clear').addEventListener('click', clearKey);
    $('ai_models_load').addEventListener('click', listModels);
    $('ai_test').addEventListener('click', testConnection);
    $('ai_model').addEventListener('change', modelChanged);
    $('rq_solve').addEventListener('click', solveOffline);
    // the solver form must not trigger the main design engine (it lives inside the form wrapper)
    ['input', 'change'].forEach(ev => tab.addEventListener(ev, (e) => e.stopPropagation()));
    Host.call('get_catalogs').then(cat => initRequirementForm(cat)).catch(() => initRequirementForm(null));
    loadSettings();
  };
})();
