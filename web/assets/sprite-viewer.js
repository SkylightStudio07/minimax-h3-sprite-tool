/* Sprite sheet viewer. Opens a finished job (?job=<id>[&source=<key>]) or dropped local files, which never
 * leave the browser. A sheet is cut by its atlas JSON when it has one, otherwise by a grid. A job's
 * transparent frame can also be turned into a breathing loop, which the server adds as a new sheet. */
(() => {
'use strict';
const $ = id => document.getElementById(id);
const {api, node} = StudioUI;
const IMAGE = /\.(png|webp)$/i, JSON_FILE = /\.json$/i;
const DEFAULT_FPS = 8, THUMB = 56, ZOOM_STEP = 1.25, MIN_ZOOM = .1, MAX_ZOOM = 16, KEPT_IMAGES = 3;

const canvas = $('svCanvas'), ctx = canvas.getContext('2d'), stage = $('svStage'), strip = $('svStrip');
const scratch = document.createElement('canvas'), scratchCtx = scratch.getContext('2d');
const loaded = new Map();
let sheets = [], sheet = null, image = null, frames = [], timed = false, jobId = null;
let index = 0, ticket = 0, mode = 'color', zoom = 1, fit = true;
let playing = false, lastTick = 0, carried = 0, thumbs = [], thumbWatch = null;

function status(text) { $('svStatus').textContent = text || ''; $('svStatus').hidden = !text; }

/* ------------------------------------------------------------- frame layout */
function atlasFrames(data) {
  const list = Array.isArray(data.frames) ? data.frames.map(f => [f.filename, f]) : Object.entries(data.frames || {});
  if (!list.length) throw Error('JSON에서 프레임 정보를 찾지 못했습니다.');
  return list.map(([name, f]) => {
    if (f.rotated) throw Error('회전된 프레임이 있는 시트는 볼 수 없습니다.');
    const r = f.frame, full = f.sourceSize || r, offset = f.spriteSourceSize || {x: 0, y: 0};
    return {name, x: r.x, y: r.y, w: r.w, h: r.h, ox: offset.x, oy: offset.y, sw: full.w, sh: full.h, ms: f.duration || 0};
  });
}
function gridFrames() {
  const {columns, rows, count, durationMs} = sheet, w = Math.floor(image.width / columns), h = Math.floor(image.height / rows);
  if (w < 1 || h < 1) throw Error('열·행 수가 시트보다 큽니다.');
  return Array.from({length: Math.min(count, columns * rows)}, (_, i) => ({
    name: '프레임 ' + (i + 1), x: (i % columns) * w, y: Math.floor(i / columns) * h, w, h, ox: 0, oy: 0, sw: w, sh: h,
    ms: durationMs?.length === count ? durationMs[i] : 0,
  }));
}
function guessGrid(target, bitmap) {
  target.columns = Math.min(8, bitmap.width);
  target.rows = Math.max(1, Math.round(bitmap.height / (bitmap.width / target.columns)));
  target.count = target.columns * target.rows;
  target.guessed = true;
}
function frameDelay(frame) { return (frame.ms > 0 ? frame.ms : 1000 / (Number($('svFps').value) || DEFAULT_FPS)) / Number($('svSpeed').value); }

/* ------------------------------------------------------------------ drawing */
function draw() {
  const f = frames[index];
  if (!f) return;
  if (canvas.width !== f.sw || canvas.height !== f.sh) { canvas.width = f.sw; canvas.height = f.sh; applyZoom(); }
  ctx.clearRect(0, 0, f.sw, f.sh);
  if (mode === 'alpha') {
    scratch.width = f.w; scratch.height = f.h;
    scratchCtx.drawImage(image, f.x, f.y, f.w, f.h, 0, 0, f.w, f.h);
    scratchCtx.globalCompositeOperation = 'source-in';
    scratchCtx.fillStyle = '#fff';
    scratchCtx.fillRect(0, 0, f.w, f.h);
    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, f.sw, f.sh);
    ctx.drawImage(scratch, f.ox, f.oy);
  } else ctx.drawImage(image, f.x, f.y, f.w, f.h, f.ox, f.oy, f.w, f.h);
  if (!$('svBreathe').hidden) drawMarks(f);
}
const markValue = id => Number($(id).value);
function drawMarks(f) {
  const neck = markValue('svNeck'), axis = markValue('svAxis'), half = markValue('svHalf');
  ctx.save();
  ctx.lineWidth = Math.max(1, 1.5 / zoom);
  ctx.strokeStyle = '#ff3b6b';
  ctx.beginPath(); ctx.moveTo(0, neck); ctx.lineTo(f.sw, neck); ctx.stroke();
  ctx.strokeStyle = '#19c8ff';
  ctx.beginPath(); ctx.moveTo(axis, 0); ctx.lineTo(axis, f.sh); ctx.stroke();
  ctx.setLineDash([8 / zoom, 6 / zoom]);
  ctx.strokeStyle = '#ffd21f';
  ctx.beginPath();
  for (const x of [axis - half, axis + half]) { ctx.moveTo(x, neck); ctx.lineTo(x, f.sh); }
  ctx.stroke();
  ctx.restore();
}
function updateReadout() {
  const f = frames[index];
  if (!f) return;
  const scrub = $('svScrub'), last = frames.length - 1;
  scrub.value = index + 1;
  scrub.style.setProperty('--fill', (last ? index / last * 100 : 0) + '%');
  $('svCount').textContent = `${index + 1} / ${frames.length}`;
  $('svInfo').textContent = `${f.name} · ${f.sw}×${f.sh} · 시트 위치 ${f.x}, ${f.y}` + (timed ? ` · ${Math.round(f.ms)}ms` : '');
  thumbs.forEach((button, i) => { if ((button.getAttribute('aria-current') === 'true') !== (i === index)) button.setAttribute('aria-current', String(i === index)); });
  const current = thumbs[index];
  if (current) strip.scrollLeft = current.offsetLeft - (strip.clientWidth - current.offsetWidth) / 2;
}
function show(i) { index = (i + frames.length) % frames.length; draw(); updateReadout(); }

/* --------------------------------------------------------------------- zoom */
function fitScale() {
  const style = getComputedStyle(stage), width = stage.clientWidth - parseFloat(style.paddingLeft) * 2, height = stage.clientHeight - parseFloat(style.paddingTop) * 2;
  return Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, width / canvas.width, height / canvas.height));
}
function applyZoom() {
  if (fit) zoom = fitScale();
  canvas.style.width = canvas.width * zoom + 'px';
  canvas.style.height = canvas.height * zoom + 'px';
  canvas.style.imageRendering = zoom >= 2 ? 'pixelated' : 'auto';
  $('svZoom').textContent = Math.round(zoom * 100) + '%';
}
function setZoom(value, anchor) {
  const next = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, value)), box = stage.getBoundingClientRect();
  const x = anchor ? anchor.clientX - box.left : stage.clientWidth / 2, y = anchor ? anchor.clientY - box.top : stage.clientHeight / 2;
  const before = canvas.getBoundingClientRect(), u = (box.left + x - before.left) / before.width, v = (box.top + y - before.top) / before.height;
  fit = false; zoom = next; applyZoom();
  const after = canvas.getBoundingClientRect();
  stage.scrollLeft += after.left + u * after.width - (box.left + x);
  stage.scrollTop += after.top + v * after.height - (box.top + y);
}

/* ----------------------------------------------------------------- playback */
function setPlaying(on) {
  playing = on && frames.length > 1;
  $('svPlay').textContent = playing ? '일시정지' : '재생';
  if (playing) { lastTick = performance.now(); carried = 0; requestAnimationFrame(tick); }
}
function tick(now) {
  if (!playing) return;
  carried += now - lastTick; lastTick = now;
  let moved = false;
  // A hidden tab can come back with a long gap; drop it rather than spinning through the clip.
  if (carried > 2000) carried = 0;
  while (carried >= frameDelay(frames[index])) { carried -= frameDelay(frames[index]); index = (index + 1) % frames.length; moved = true; }
  if (moved) { draw(); updateReadout(); }
  requestAnimationFrame(tick);
}
function step(by) { setPlaying(false); show(index + by); }

/* --------------------------------------------------------------- filmstrip */
function buildStrip() {
  thumbWatch?.disconnect();
  thumbs = frames.map((f, i) => {
    const button = node('button', undefined, 'sv-thumb'), thumb = node('canvas');
    button.type = 'button';
    button.setAttribute('aria-label', `${i + 1}번 프레임`);
    button.setAttribute('aria-current', 'false');
    const scale = Math.min(THUMB / f.sw, THUMB / f.sh);
    thumb.width = Math.max(1, Math.round(f.sw * scale)); thumb.height = Math.max(1, Math.round(f.sh * scale));
    thumb.dataset.bg = 'checker'; thumb.dataset.frame = i;
    button.append(thumb, node('span', String(i + 1)));
    button.onclick = () => { setPlaying(false); show(i); };
    return button;
  });
  strip.replaceChildren(...thumbs);
  strip.hidden = !frames.length;
  // A sheet can hold hundreds of cells, so only paint the ones that scroll into view.
  const source = image, cells = frames;
  thumbWatch = new IntersectionObserver(entries => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;
      thumbWatch.unobserve(entry.target);
      const f = cells[Number(entry.target.dataset.frame)], g = entry.target.getContext('2d'), scale = entry.target.width / f.sw;
      g.drawImage(source, f.x, f.y, f.w, f.h, f.ox * scale, f.oy * scale, f.w * scale, f.h * scale);
    }
  }, {root: strip, rootMargin: '200px'});
  strip.querySelectorAll('canvas').forEach(c => thumbWatch.observe(c));
}

/* ----------------------------------------------------------------- loading */
async function fetchImage(target) {
  if (target.file) return createImageBitmap(target.file);
  const response = await fetch(target.url);
  if (!response.ok) throw Error('시트 이미지를 불러오지 못했습니다.');
  return createImageBitmap(await response.blob());
}
async function imageOf(target) {
  if (loaded.has(target)) { const bitmap = loaded.get(target); loaded.delete(target); loaded.set(target, bitmap); return bitmap; }
  const bitmap = await fetchImage(target);
  loaded.set(target, bitmap);
  // Whole sheets are large once decoded, but flipping between a few of them should stay instant.
  for (const [old, data] of loaded) {
    if (loaded.size <= KEPT_IMAGES || old === target || old === sheet) continue;
    data.close(); loaded.delete(old);
  }
  return bitmap;
}
async function atlasOf(target) {
  if (target.atlasData || !target.atlas) return target.atlasData;
  const response = await fetch(target.atlas);
  if (!response.ok) throw Error('시트 JSON을 불러오지 못했습니다.');
  return target.atlasData = await response.json();
}
function layOut() {
  frames = sheet.atlasData ? atlasFrames(sheet.atlasData) : gridFrames();
  timed = frames.every(f => f.ms > 0);
  index = Math.min(index, frames.length - 1);
  $('svScrub').max = frames.length;
  $('svFpsField').hidden = timed;
  buildStrip();
  draw();
  applyZoom();
  updateReadout();
}
async function selectSheet(target) {
  const mine = ++ticket;
  setPlaying(false);
  status('시트를 불러오는 중…');
  try {
    const [bitmap] = await Promise.all([imageOf(target), atlasOf(target)]);
    if (mine !== ticket) return;
    sheet = target; image = bitmap;
    if (!sheet.atlasData && !sheet.columns) guessGrid(sheet, bitmap);
    $('svGrid').hidden = !!sheet.atlasData;
    if (!sheet.atlasData) { $('svColumns').value = sheet.columns; $('svRows').value = sheet.rows; $('svFrames').value = sheet.count; }
    $('svEmpty').hidden = true; canvas.hidden = false; $('svControls').hidden = false;
    $('svBreatheOpen').hidden = !(jobId && sheet.alpha);
    if ($('svBreatheOpen').hidden) closeBreathe();
    layOut();
    status(sheet.guessed ? 'JSON이 없어 칸 수를 추정했습니다. 프레임이 어긋나면 열·행을 맞춰 주세요.' : '');
  } catch (error) { if (mine === ticket) status(error.message); }
}
function useSheets(list, startKey) {
  for (const data of loaded.values()) data.close();
  loaded.clear();
  sheet = null; sheets = list; index = 0;
  const select = $('svSheet');
  select.replaceChildren(...list.map((s, i) => new Option(s.label, i)));
  select.hidden = list.length < 2;
  const start = Math.max(0, list.findIndex(s => s.key === startKey));
  select.value = start;
  return selectSheet(list[start]);
}

/* -------------------------------------------------------------- local files */
const stemOf = name => name.replace(/\.[^.]+$/, '').toLowerCase();
async function readEntry(entry, out) {
  if (entry.isFile) { out.push(await new Promise((ok, no) => entry.file(ok, no))); return; }
  const reader = entry.createReader();
  for (;;) {
    const batch = await new Promise((ok, no) => reader.readEntries(ok, no));
    if (!batch.length) return;
    for (const child of batch) await readEntry(child, out);
  }
}
async function openFiles(files) {
  const atlases = new Map();
  for (const file of files.filter(f => JSON_FILE.test(f.name))) {
    try {
      const data = JSON.parse(await file.text());
      if (!data.frames) continue;
      atlases.set(stemOf(file.name), data);
      if (data.meta?.image) atlases.set(stemOf(data.meta.image), data);
    } catch { /* A file that is not an atlas just leaves its image on the grid. */ }
  }
  const list = files.filter(f => IMAGE.test(f.name)).sort((a, b) => a.name.localeCompare(b.name, undefined, {numeric: true}))
    .map(file => ({label: file.name, file, atlasData: atlases.get(stemOf(file.name))}));
  if (!list.length) { status('PNG 또는 WEBP 시트를 넣어 주세요.'); return; }
  $('svTitle').textContent = list.length === 1 ? list[0].label : `시트 ${list.length}개`;
  await useSheets(list);
}

/* ------------------------------------------------------------ breathing loop */
function closeBreathe() {
  $('svBreathe').hidden = true;
  stage.classList.remove('is-marking');
  if (frames.length) draw();
}
// Only a starting point: a held weapon pulls these off, which is why the lines can be dragged.
function guessMarks(f) {
  scratch.width = f.w; scratch.height = f.h;
  scratchCtx.drawImage(image, f.x, f.y, f.w, f.h, 0, 0, f.w, f.h);
  const data = scratchCtx.getImageData(0, 0, f.w, f.h).data;
  let top = f.h, bottom = 0, left = f.w, right = 0;
  for (let y = 0; y < f.h; y++) for (let x = 0; x < f.w; x++) {
    if (data[(y * f.w + x) * 4 + 3] < 128) continue;
    top = Math.min(top, y); bottom = Math.max(bottom, y); left = Math.min(left, x); right = Math.max(right, x);
  }
  if (bottom <= top) return null;
  const band = [top + (bottom - top) * .22, top + (bottom - top) * .5];
  let sum = 0, weight = 0;
  for (let y = Math.round(band[0]); y < band[1]; y++) for (let x = 0; x < f.w; x++) if (data[(y * f.w + x) * 4 + 3] >= 128) { sum += x; weight++; }
  return {neck: Math.round(top + (bottom - top) * .2) + f.oy, axis: Math.round(weight ? sum / weight : (left + right) / 2) + f.ox, half: Math.max(2, Math.round((bottom - top) * .13))};
}
$('svBreatheOpen').onclick = () => {
  if (!$('svBreathe').hidden) { closeBreathe(); return; }
  setPlaying(false);
  const f = frames[index], marks = guessMarks(f);
  if (!marks) { status('이 프레임에는 보이는 캐릭터가 없습니다.'); return; }
  $('svNeck').max = f.sh - 1; $('svAxis').max = f.sw - 1; $('svHalf').max = Math.floor(f.sw / 2);
  $('svNeck').value = marks.neck; $('svAxis').value = marks.axis; $('svHalf').value = marks.half;
  $('svBreathe').hidden = false;
  stage.classList.add('is-marking');
  status('');
  draw();
};
$('svBreatheClose').onclick = closeBreathe;
for (const id of ['svNeck', 'svAxis', 'svHalf']) $(id).oninput = draw;
$('svBreathe').onsubmit = async event => {
  event.preventDefault();
  const button = $('svBreatheMake');
  button.disabled = true;
  status('숨쉬기 루프를 만드는 중…');
  try {
    const made = await api('/api/jobs/' + encodeURIComponent(jobId) + '/breathe', {source: sheet.key, frame: index, neck: markValue('svNeck'), axis: markValue('svAxis'), half: markValue('svHalf'), frameCount: markValue('svBreatheCount'), fps: markValue('svBreatheFps')});
    const data = await api('/api/jobs/' + encodeURIComponent(jobId) + '/sheets');
    closeBreathe();
    await useSheets(data.sheets, made.key);
    setPlaying(true);
    status('숨쉬기 루프를 시트 목록에 추가했습니다.');
  } catch (error) { status(error.message); }
  button.disabled = false;
};

/* ------------------------------------------------------------------- inputs */
$('svPlay').onclick = () => setPlaying(!playing);
$('svPrev').onclick = () => step(-1);
$('svNext').onclick = () => step(1);
$('svFirst').onclick = () => { setPlaying(false); show(0); };
$('svLast').onclick = () => { setPlaying(false); show(frames.length - 1); };
$('svScrub').oninput = event => { setPlaying(false); show(Number(event.target.value) - 1); };
$('svSheet').onchange = event => { event.target.blur(); selectSheet(sheets[Number(event.target.value)]); };
$('svSpeed').onchange = event => event.target.blur();
$('svZoomIn').onclick = () => setZoom(zoom * ZOOM_STEP);
$('svZoomOut').onclick = () => setZoom(zoom / ZOOM_STEP);
$('svFit').onclick = () => { fit = true; applyZoom(); };
$('svActual').onclick = () => setZoom(1);
$('svOpen').onclick = () => $('svFiles').click();
$('svFiles').onchange = event => { openFiles([...event.target.files]); event.target.value = ''; };

for (const [group, apply] of [['svBg', b => { canvas.dataset.bg = b.dataset.bg; }], ['svMode', b => { mode = b.dataset.mode; draw(); }]]) {
  $(group).querySelectorAll('button').forEach(button => button.onclick = () => {
    $(group).querySelectorAll('button').forEach(other => other.setAttribute('aria-pressed', String(other === button)));
    apply(button);
  });
}

for (const [id, field, min] of [['svColumns', 'columns', 1], ['svRows', 'rows', 1], ['svFrames', 'count', 1]]) {
  $(id).onchange = event => {
    const value = Number(event.target.value);
    if (!Number.isInteger(value) || value < min) { event.target.value = sheet[field]; return; }
    sheet[field] = value; sheet.guessed = false;
    // Editing the grid means the saved per-frame timing no longer lines up.
    sheet.durationMs = null;
    if (field !== 'count') { sheet.count = sheet.columns * sheet.rows; $('svFrames').value = sheet.count; }
    try { layOut(); status(''); } catch (error) { status(error.message); }
  };
}

// A mouse click must not leave focus on a button, or Space would press it again instead of playing.
document.addEventListener('mousedown', event => { if (event.target.closest('button')) event.preventDefault(); });
document.addEventListener('keydown', event => {
  if (!frames.length || event.ctrlKey || event.metaKey || event.altKey || event.target.closest('input,select,textarea')) return;
  if (event.key === ' ' && event.target.closest('button')) return;
  const actions = {ArrowLeft: () => step(-1), ArrowRight: () => step(1), ' ': () => setPlaying(!playing), Home: () => { setPlaying(false); show(0); }, End: () => { setPlaying(false); show(frames.length - 1); }};
  if (!actions[event.key]) return;
  event.preventDefault();
  actions[event.key]();
});

stage.addEventListener('wheel', event => {
  if (!frames.length || !event.ctrlKey) return;
  event.preventDefault();
  setZoom(zoom * (event.deltaY < 0 ? ZOOM_STEP : 1 / ZOOM_STEP), event);
}, {passive: false});
let pan = null, marking = null;
function framePoint(event) {
  const box = canvas.getBoundingClientRect();
  return {x: (event.clientX - box.left) / box.width * canvas.width, y: (event.clientY - box.top) / box.height * canvas.height};
}
function nearestMark(event) {
  const p = framePoint(event), reach = 12 / (canvas.getBoundingClientRect().width / canvas.width);
  const axis = markValue('svAxis'), half = markValue('svHalf');
  const lines = [['neck', Math.abs(p.y - markValue('svNeck'))], ['axis', Math.abs(p.x - axis)], ['left', Math.abs(p.x - (axis - half))], ['right', Math.abs(p.x - (axis + half))]];
  const [name, distance] = lines.sort((a, b) => a[1] - b[1])[0];
  return distance <= reach ? name : null;
}
function moveMark(event) {
  const p = framePoint(event), clamp = (value, low, high) => Math.round(Math.max(low, Math.min(high, value)));
  if (marking === 'neck') $('svNeck').value = clamp(p.y, 0, canvas.height - 1);
  else if (marking === 'axis') $('svAxis').value = clamp(p.x, 0, canvas.width - 1);
  else $('svHalf').value = clamp(Math.abs(p.x - markValue('svAxis')), 2, Math.floor(canvas.width / 2));
  draw();
}
stage.addEventListener('pointerdown', event => {
  if (!frames.length) return;
  marking = $('svBreathe').hidden ? null : nearestMark(event);
  if (marking) { stage.setPointerCapture(event.pointerId); return; }
  pan = {x: event.clientX, y: event.clientY, left: stage.scrollLeft, top: stage.scrollTop};
  stage.setPointerCapture(event.pointerId);
  stage.classList.add('is-panning');
});
stage.addEventListener('pointermove', event => {
  if (marking) { moveMark(event); return; }
  if (!pan) return;
  stage.scrollLeft = pan.left - (event.clientX - pan.x);
  stage.scrollTop = pan.top - (event.clientY - pan.y);
});
for (const type of ['pointerup', 'pointercancel']) stage.addEventListener(type, () => { pan = null; marking = null; stage.classList.remove('is-panning'); });
new ResizeObserver(() => { if (fit && frames.length) applyZoom(); }).observe(stage);

let dragDepth = 0;
const dragsFiles = event => [...(event.dataTransfer?.types || [])].includes('Files');
document.addEventListener('dragenter', event => { if (dragsFiles(event)) { dragDepth++; $('svDrop').hidden = false; } });
document.addEventListener('dragleave', event => { if (dragsFiles(event) && --dragDepth <= 0) { dragDepth = 0; $('svDrop').hidden = true; } });
document.addEventListener('dragover', event => { if (dragsFiles(event)) event.preventDefault(); });
document.addEventListener('drop', async event => {
  if (!dragsFiles(event)) return;
  event.preventDefault();
  dragDepth = 0; $('svDrop').hidden = true;
  // DataTransfer is emptied once this handler yields, so take the entries before the first await.
  const entries = [...event.dataTransfer.items].map(item => item.webkitGetAsEntry?.()).filter(Boolean);
  const direct = [...event.dataTransfer.files], files = [];
  try {
    if (entries.length) for (const entry of entries) await readEntry(entry, files);
    await openFiles(entries.length ? files : direct);
  } catch (error) { status(error.message); }
});

/* ------------------------------------------------------------------ startup */
(async () => {
  const params = new URLSearchParams(location.search), job = params.get('job');
  if (!job) return;
  jobId = job;
  $('svBack').href = '/#/jobs/' + encodeURIComponent(job);
  $('svBack').textContent = '결과로 돌아가기';
  try {
    const data = await api('/api/jobs/' + encodeURIComponent(job) + '/sheets');
    $('svTitle').textContent = data.title;
    document.title = data.title + ' · 스프라이트 뷰어';
    if (!data.sheets.length) { status('이 결과에는 볼 수 있는 시트가 없습니다.'); return; }
    await useSheets(data.sheets, params.get('source'));
  } catch (error) { status(error.message); }
})();
})();
