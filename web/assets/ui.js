/* Sprite Lab UI runtime. Load synchronously in <head> so the theme applies before first paint.
 * - Theme: light by default, stored in localStorage['sprite-theme'].
 *   Every same-origin document (embedded iframes, other tabs) follows changes through the `storage` event,
 *   so parent pages never need to reach into an iframe to restyle it.
 * - [data-theme-toggle] buttons toggle the theme and get aria-pressed / label sync.
 * - .ui-range inputs get a --fill custom property for the WebKit track fill.
 */
(function () {
  'use strict';
  var KEY = 'sprite-theme';
  var root = document.documentElement;

  function read() {
    try { return localStorage.getItem(KEY) === 'dark' ? 'dark' : 'light'; } catch (error) { return 'light'; }
  }

  function apply(theme) {
    root.dataset.theme = theme;
    var buttons = document.querySelectorAll('[data-theme-toggle]');
    for (var i = 0; i < buttons.length; i++) {
      var button = buttons[i];
      button.setAttribute('aria-pressed', String(theme === 'dark'));
      button.setAttribute('aria-label', theme === 'dark' ? '라이트 모드로 전환' : '다크 모드로 전환');
      button.title = button.getAttribute('aria-label');
    }
    document.dispatchEvent(new CustomEvent('themechange', { detail: { theme: theme } }));
  }

  // Colour transitions would animate every surface through grey during a switch; suspend them for two frames.
  function switchTheme(theme) {
    root.classList.add('ui-theme-switching');
    apply(theme);
    requestAnimationFrame(function () { requestAnimationFrame(function () { root.classList.remove('ui-theme-switching'); }); });
  }

  function set(theme) {
    theme = theme === 'dark' ? 'dark' : 'light';
    try { localStorage.setItem(KEY, theme); } catch (error) { /* private mode: theme still applies to this page */ }
    switchTheme(theme);
  }

  root.dataset.theme = read();

  window.addEventListener('storage', function (event) {
    if (event.key === KEY) switchTheme(read());
  });

  function fillRange(input) {
    var min = Number(input.min || 0), max = Number(input.max || 100), value = Number(input.value);
    input.style.setProperty('--fill', (max > min ? ((value - min) / (max - min)) * 100 : 0) + '%');
  }

  document.addEventListener('input', function (event) {
    if (event.target.classList && event.target.classList.contains('ui-range')) fillRange(event.target);
  });

  document.addEventListener('click', function (event) {
    var toggle = event.target.closest && event.target.closest('[data-theme-toggle]');
    if (toggle) set(root.dataset.theme === 'dark' ? 'light' : 'dark');
  });

  function init() {
    apply(root.dataset.theme);
    var ranges = document.querySelectorAll('.ui-range');
    for (var i = 0; i < ranges.length; i++) fillRange(ranges[i]);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();

  window.SpriteUI = {
    theme: { get: function () { return root.dataset.theme; }, set: set, toggle: function () { set(root.dataset.theme === 'dark' ? 'light' : 'dark'); } },
    fillRange: fillRange
  };
})();
