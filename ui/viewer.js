/**
 * 3D Assembly Viewer (standalone mode only).
 * Renders the OpenCascade tessellation sent by the Python backend with three.js (r128, local copy).
 * Z-up CAD convention, exploded view, group visibility, see-through housing, hover labels.
 */
(function () {
  'use strict';

  const VENDOR = ['vendor/three.min.js', 'vendor/OrbitControls.js'];
  let loadPromise = null;

  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = src;
      s.onload = resolve;
      s.onerror = () => reject(new Error('Script load failed: ' + src));
      document.head.appendChild(s);
    });
  }

  function loadThree() {
    if (!loadPromise) {
      loadPromise = VENDOR.reduce((p, src) => p.then(() => loadScript(src)), Promise.resolve());
    }
    return loadPromise;
  }

  async function b64ToBuffer(b64) {
    const res = await fetch('data:application/octet-stream;base64,' + b64);
    return res.arrayBuffer();
  }

  const state = {
    container: null, renderer: null, scene: null, camera: null, controls: null,
    root: null, grid: null, instances: [], groups: {}, unit: 10, explode: 0, explodeTarget: 0,
    housingAlpha: 1, edges: true, hovered: null, tooltip: null, raycaster: null, pointer: null,
    needsPick: false, bbox: null, clip: null, section: false,
    theta: 0, playing: false, speed: 1.2, dragging: null, onAngle: null, outputFactor: 0,
  };

  function init(container) {
    return loadThree().then(() => {
      if (state.renderer) return;
      const THREE = window.THREE;
      state.container = container;
      const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
      renderer.outputEncoding = THREE.sRGBEncoding;
      renderer.localClippingEnabled = true;
      state.clip = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);   // keeps y >= 0 (front half removed)
      container.appendChild(renderer.domElement);
      state.renderer = renderer;

      const scene = new THREE.Scene();
      state.scene = scene;
      const camera = new THREE.PerspectiveCamera(35, 1, 0.1, 10000);
      camera.up.set(0, 0, 1);
      camera.position.set(180, -220, 160);
      state.camera = camera;

      scene.add(new THREE.HemisphereLight(0xdfe8f5, 0x1a2230, 0.85));
      const key = new THREE.DirectionalLight(0xffffff, 0.85);
      key.position.set(1, -1.2, 1.6);
      scene.add(key);
      const fill = new THREE.DirectionalLight(0x9fc4ff, 0.35);
      fill.position.set(-1.4, 1, 0.4);
      scene.add(fill);
      const rim = new THREE.DirectionalLight(0xffffff, 0.25);
      rim.position.set(0, 1, -1);
      scene.add(rim);

      state.root = new THREE.Group();
      scene.add(state.root);

      const controls = new THREE.OrbitControls(camera, renderer.domElement);
      controls.enableDamping = true;
      controls.dampingFactor = 0.12;
      controls.screenSpacePanning = true;
      state.controls = controls;

      state.raycaster = new THREE.Raycaster();
      state.pointer = new THREE.Vector2();
      state.tooltip = document.createElement('div');
      state.tooltip.className = 'viewer-tooltip';
      container.appendChild(state.tooltip);
      renderer.domElement.addEventListener('pointermove', (e) => {
        const r = renderer.domElement.getBoundingClientRect();
        state.pointer.x = ((e.clientX - r.left) / r.width) * 2 - 1;
        state.pointer.y = -((e.clientY - r.top) / r.height) * 2 + 1;
        state.tooltip.style.left = (e.clientX - r.left + 14) + 'px';
        state.tooltip.style.top = (e.clientY - r.top + 12) + 'px';
        state.needsPick = e.buttons === 0;
      });
      renderer.domElement.addEventListener('pointerleave', () => setHover(null));
      // Shift + sürükle: giriş milini döndür (dişliler birlikte döner)
      renderer.domElement.addEventListener('pointerdown', (e) => {
        if (!e.shiftKey) return;
        state.dragging = { x: e.clientX, theta: state.theta };
        state.controls.enabled = false;
        renderer.domElement.setPointerCapture(e.pointerId);
      });
      renderer.domElement.addEventListener('pointermove', (e) => {
        if (!state.dragging) return;
        setAngle(state.dragging.theta + (e.clientX - state.dragging.x) * 0.02);
      });
      const endDrag = () => { if (state.dragging) { state.dragging = null; state.controls.enabled = true; } };
      renderer.domElement.addEventListener('pointerup', endDrag);
      renderer.domElement.addEventListener('pointercancel', endDrag);

      new ResizeObserver(resize).observe(container);
      resize();
      animate();
    });
  }

  function resize() {
    if (!state.renderer) return;
    const w = Math.max(10, state.container.clientWidth);
    const h = Math.max(10, state.container.clientHeight);
    state.renderer.setSize(w, h, false);
    state.renderer.domElement.style.width = w + 'px';
    state.renderer.domElement.style.height = h + 'px';
    state.camera.aspect = w / h;
    state.camera.updateProjectionMatrix();
  }

  let lastT = performance.now();
  function animate() {
    requestAnimationFrame(animate);
    const now = performance.now();
    if (state.playing) setAngle(state.theta + state.speed * (now - lastT) / 1000);
    lastT = now;
    if (Math.abs(state.explode - state.explodeTarget) > 1e-4) {
      state.explode += (state.explodeTarget - state.explode) * 0.18;
      applyExplode();
    }
    state.controls.update();
    if (state.needsPick) {
      state.needsPick = false;
      pick();
    }
    state.renderer.render(state.scene, state.camera);
  }

  function clear() {
    const root = state.root;
    if (!root) return;
    const disposed = new Set();
    root.traverse((o) => {
      if (o.geometry && !disposed.has(o.geometry)) { o.geometry.dispose(); disposed.add(o.geometry); }
      if (o.material && !disposed.has(o.material)) { o.material.dispose(); disposed.add(o.material); }
    });
    while (root.children.length) root.remove(root.children[0]);
    if (state.grid) { state.scene.remove(state.grid); state.grid = null; }
    state.instances = [];
    state.groups = {};
    setHover(null);
  }

  async function load(data) {
    const THREE = window.THREE;
    clear();
    const geoms = {};
    const edgeGeoms = {};
    for (const [key, proto] of Object.entries(data.protos)) {
      const pos = new Float32Array(await b64ToBuffer(proto.positions));
      const idx = new Uint32Array(await b64ToBuffer(proto.indices));
      const g = new THREE.BufferGeometry();
      g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
      g.setIndex(new THREE.BufferAttribute(idx, 1));
      g.computeVertexNormals();
      g.computeBoundingSphere();
      geoms[key] = g;
      edgeGeoms[key] = new THREE.EdgesGeometry(g, 28);
    }
    const edgeMat = new THREE.LineBasicMaterial({ color: 0x0b1018, transparent: true, opacity: 0.55 });
    const [x0, y0, z0, x1, y1, z1] = data.bbox;
    const diag = Math.hypot(x1 - x0, y1 - y0, z1 - z0);
    state.unit = Math.max(4, diag * 0.12);
    state.bbox = data.bbox;

    for (const inst of data.instances) {
      const material = new THREE.MeshStandardMaterial({
        color: new THREE.Color(inst.color).convertSRGBToLinear(),
        metalness: 0.25, roughness: 0.48, side: THREE.DoubleSide,
        polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1,
        clippingPlanes: state.section ? [state.clip] : [],
      });
      const mesh = new THREE.Mesh(geoms[inst.proto], material);
      const edges = new THREE.LineSegments(edgeGeoms[inst.proto], edgeMat);
      edges.visible = state.edges;
      const holder = new THREE.Group();
      holder.add(mesh);
      holder.add(edges);
      if (inst.matrix) {
        holder.matrixAutoUpdate = false;
        holder.matrix.fromArray(inst.matrix);
      }
      const kin = new THREE.Group();
      kin.matrixAutoUpdate = false;
      kin.add(holder);
      const outer = new THREE.Group();
      outer.add(kin);
      state.root.add(outer);
      const rec = { outer, kin, mesh, edges, material, info: inst, baseColor: material.color.clone() };
      mesh.userData.rec = rec;
      state.instances.push(rec);
      (state.groups[inst.group] = state.groups[inst.group] || []).push(rec);
    }

    const size = Math.max(x1 - x0, y1 - y0) * 1.8;
    const grid = new THREE.GridHelper(Math.ceil(size / 10) * 10, Math.ceil(size / 10),
                                      0x2a3a50, 0x1a2433);
    grid.rotation.x = Math.PI / 2;
    grid.position.set((x0 + x1) / 2, (y0 + y1) / 2, z0 - 0.5);
    state.grid = grid;
    state.scene.add(grid);

    state.outputFactor = data.output_factor || 0;
    applyExplode();
    applyMotion();
    setHousingOpacity(state.housingAlpha);
    fit('iso');
  }

  // Kinematik: M = Rz(a·θ) · T(c) · Rz(b·θ) · T(-c)   (a: ana eksen / yörünge, b: planet öz dönüşü)
  function applyMotion() {
    const THREE = window.THREE;
    const m1 = new THREE.Matrix4(), m2 = new THREE.Matrix4(), m3 = new THREE.Matrix4(), m4 = new THREE.Matrix4();
    for (const rec of state.instances) {
      const mo = rec.info.motion || { a: 0, b: 0, cx: 0, cy: 0 };
      m1.makeRotationZ(mo.a * state.theta);
      if (mo.b) {
        m2.makeTranslation(mo.cx, mo.cy, 0);
        m3.makeRotationZ(mo.b * state.theta);
        m4.makeTranslation(-mo.cx, -mo.cy, 0);
        m1.multiply(m2).multiply(m3).multiply(m4);
      }
      rec.kin.matrix.copy(m1);
      rec.kin.matrixWorldNeedsUpdate = true;
    }
  }

  function setAngle(theta) {
    state.theta = theta;
    if (state.instances.length) applyMotion();
    if (state.onAngle) state.onAngle(theta, theta * state.outputFactor);
  }

  function setPlaying(on) { state.playing = on; }
  function setSpeed(v) { state.speed = v; }
  function onAngle(cb) { state.onAngle = cb; }

  function applyExplode() {
    const f = state.explode * state.unit;
    for (const rec of state.instances) {
      const e = rec.info.explode || [0, 0, 0];
      rec.outer.position.set(e[0] * f, e[1] * f, e[2] * f);
    }
  }

  function setExplode(t) {
    state.explodeTarget = Math.max(0, Math.min(1.5, t));
  }

  function setGroupVisible(group, visible) {
    (state.groups[group] || []).forEach((rec) => { rec.outer.visible = visible; });
  }

  function setHousingOpacity(alpha) {
    state.housingAlpha = alpha;
    (state.groups.housing || []).forEach((rec) => {
      rec.material.transparent = alpha < 0.999;
      rec.material.opacity = alpha;
      rec.material.depthWrite = alpha >= 0.999;
      rec.edges.material.opacity = alpha < 0.999 ? 0.25 : 0.55;
      rec.material.needsUpdate = true;
    });
  }

  function setSection(on) {
    state.section = on;
    state.instances.forEach((rec) => {
      rec.material.clippingPlanes = on ? [state.clip] : [];
      rec.material.needsUpdate = true;
      rec.edges.material.clippingPlanes = on ? [state.clip] : [];
      rec.edges.material.needsUpdate = true;
    });
  }

  function setEdges(on) {
    state.edges = on;
    state.instances.forEach((rec) => { rec.edges.visible = on; });
  }

  function fit(view) {
    const THREE = window.THREE;
    if (!state.bbox) return;
    // fit to the final (target) explode state, not to an animation frame
    const current = state.explode;
    state.explode = state.explodeTarget;
    applyExplode();
    const box = new THREE.Box3();
    state.instances.forEach((rec) => { if (rec.outer.visible) box.expandByObject(rec.outer); });
    state.explode = current;
    applyExplode();
    if (box.isEmpty()) return;
    const center = box.getCenter(new THREE.Vector3());
    const radius = box.getSize(new THREE.Vector3()).length() * 0.5;
    const dist = radius / Math.sin((state.camera.fov * Math.PI) / 360) * 1.05;
    const dirs = { iso: [1, -1.15, 0.85], bottom: [0.9, -1.1, -0.9], top: [0, -0.001, 1], front: [0, -1, 0.0001], side: [1, 0, 0.0001] };
    const d = new THREE.Vector3(...(dirs[view] || dirs.iso)).normalize();
    state.camera.position.copy(center).addScaledVector(d, dist);
    state.camera.near = Math.max(0.1, dist / 200);
    state.camera.far = dist * 20;
    state.camera.updateProjectionMatrix();
    state.controls.target.copy(center);
    state.controls.update();
  }

  function setHover(rec) {
    if (state.hovered === rec) return;
    if (state.hovered) {
      state.hovered.material.emissive.setHex(0x000000);
    }
    state.hovered = rec;
    if (rec) {
      rec.material.emissive.setHex(0x16324a);
      state.tooltip.textContent = rec.info.name + ' · ' + rec.info.group_label;
      state.tooltip.style.display = 'block';
    } else if (state.tooltip) {
      state.tooltip.style.display = 'none';
    }
  }

  function pick() {
    if (!state.instances.length) return;
    state.raycaster.setFromCamera(state.pointer, state.camera);
    const meshes = state.instances.filter((r) => r.outer.visible && !(r.material.transparent && r.material.opacity < 0.5))
      .map((r) => r.mesh);
    const hit = state.raycaster.intersectObjects(meshes, false)[0];
    setHover(hit ? hit.object.userData.rec : null);
  }

  function screenshot() {
    return state.renderer ? state.renderer.domElement.toDataURL('image/png') : null;
  }

  window.GearViewer = { init, load, clear, setExplode, setGroupVisible, setHousingOpacity, setEdges, setSection, fit,
                        screenshot, setAngle, setPlaying, setSpeed, onAngle,
                        getAngle: () => state.theta, isPlaying: () => state.playing };
})();
