/* 리깅 스튜디오 presentation layer, loaded after the editor and its modules:
 * - Photoshop-style brush cursor: a ring at the real brush size × zoom, size flash on [ ] or the slider
 * - layer thumbnails in the layer list, eye state for hidden layers
 * - icon for the expression module's paint tool, mobile panel toggle
 * Relies on the editor globals (canvas, tool, space, panning, readonly, parts, $, setTool, drawLayerList). */
(function () {
  'use strict';
  const BRUSH_TOOLS = new Set(['restore', 'source_restore', 'erase', 'paint']);
  const ring = document.createElement('div'), tag = document.createElement('div');
  ring.className = 'brush-cursor'; ring.hidden = true;
  tag.className = 'brush-size-tag';
  document.body.append(ring, tag);
  let pointer = null, inside = false, tagTimer = 0;

  const brushOn = () => !readonly && BRUSH_TOOLS.has(tool) && !space && !panning && !document.body.classList.contains('bone-editing');
  const diameter = () => Number($('size').value) * canvas.getBoundingClientRect().width / canvas.width;

  function drawCursor() {
    const show = inside && pointer && brushOn() && !pointer.altKey;
    ring.hidden = !show;
    document.body.classList.toggle('brush-cursor-on', show);
    if (!show) return;
    const size = Math.max(4, diameter());
    ring.style.width = ring.style.height = size + 'px';
    ring.style.transform = `translate(${pointer.x - size / 2}px, ${pointer.y - size / 2}px)`;
    ring.dataset.tool = tool;
  }
  function flashSize() {
    if (!pointer || !inside) return;
    tag.textContent = $('size').value + 'px';
    tag.style.transform = `translate(${pointer.x + Math.max(4, diameter()) / 2 + 8}px, ${pointer.y - 10}px)`;
    tag.classList.add('is-on');
    clearTimeout(tagTimer); tagTimer = setTimeout(() => tag.classList.remove('is-on'), 700);
  }
  const track = event => { pointer = { x: event.clientX, y: event.clientY, altKey: event.altKey }; };
  canvas.addEventListener('pointerenter', event => { inside = true; track(event); drawCursor(); });
  canvas.addEventListener('pointermove', event => { inside = true; track(event); drawCursor(); });
  canvas.addEventListener('pointerleave', () => { inside = false; drawCursor(); });
  $('scroll').addEventListener('scroll', () => { if (!inside) return; drawCursor(); }, { passive: true });
  $('scroll').addEventListener('wheel', () => requestAnimationFrame(drawCursor), { passive: true });
  $('size').addEventListener('input', () => { drawCursor(); flashSize(); });
  for (const type of ['keydown', 'keyup']) {
    document.addEventListener(type, event => {
      if (pointer) pointer.altKey = event.altKey;
      // The editor handles [ ] / Space first; read its result on the next frame.
      requestAnimationFrame(() => { drawCursor(); if (type === 'keydown' && (event.key === '[' || event.key === ']')) flashSize(); });
    });
  }
  const baseSetTool = setTool;
  setTool = function (...args) { baseSetTool.apply(this, args); drawCursor(); };

  /* layer thumbnails + hidden state */
  function decorateLayers() {
    const byKey = new Map(parts.map(part => [part.key, part]));
    for (const row of document.querySelectorAll('#layers .layer')) {
      const part = byKey.get(row.dataset.layerKey);
      if (!part) continue;
      row.classList.toggle('is-hidden', !part.visible);
      let thumb = row.querySelector('.layer-thumb');
      if (!thumb) { thumb = document.createElement('canvas'); thumb.className = 'layer-thumb'; thumb.width = thumb.height = 68; row.querySelector('input')?.after(thumb); }
      const context = thumb.getContext('2d'), scale = Math.min(68 / part.width, 68 / part.height);
      context.clearRect(0, 0, 68, 68);
      try { context.drawImage(part.canvas, (68 - part.width * scale) / 2, (68 - part.height * scale) / 2, part.width * scale, part.height * scale); } catch (error) { /* part not drawn yet */ }
    }
  }
  const baseDrawLayerList = drawLayerList;
  drawLayerList = function (...args) { baseDrawLayerList.apply(this, args); decorateLayers(); };
  // Strokes change a layer's pixels without rebuilding the list; refresh thumbnails when a stroke ends.
  canvas.addEventListener('pointerup', () => requestAnimationFrame(decorateLayers));
  $('layers').addEventListener('click', event => { if (event.target.matches('input[type=checkbox]')) requestAnimationFrame(decorateLayers); });

  /* the expression module adds its paint tool as text; give it the rail look */
  const paint = $('paintTool');
  if (paint) paint.innerHTML = '<svg class="ei" viewBox="0 0 24 24" aria-hidden="true"><path d="M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z"/><path d="m15 5 4 4"/></svg><span>그리기</span><kbd>P</kbd>';
  if (paint) paint.setAttribute('aria-label', '색상 브러시 (P)');

  /* narrow screens: the panel floats over the canvas and can be collapsed */
  const toggle = $('panelToggle');
  if (toggle) toggle.onclick = () => { const collapsed = document.body.classList.toggle('panel-collapsed'); toggle.setAttribute('aria-expanded', String(!collapsed)); };
  if (matchMedia('(max-width: 860px)').matches) { document.body.classList.add('panel-collapsed'); toggle?.setAttribute('aria-expanded', 'false'); }
})();
