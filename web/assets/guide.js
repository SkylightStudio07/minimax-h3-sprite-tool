(function () {
  'use strict';
  var params = new URLSearchParams(location.search);
  var embedded = params.get('embed') === '1' && window.top !== window;
  var cards = Array.prototype.slice.call(document.querySelectorAll('.g-card'));
  var sections = Array.prototype.slice.call(document.querySelectorAll('.g-sec'));
  var links = Array.prototype.slice.call(document.querySelectorAll('.g-toc a'));
  var toc = document.getElementById('guideToc');
  var compact = window.matchMedia('(max-width: 860px)');

  if (embedded) document.documentElement.classList.add('g-embed');
  // Inside the app frame, links that leave the guide must replace the app, not nest it.
  document.querySelectorAll('a[href]').forEach(function (a) {
    if (embedded && a.getAttribute('href').charAt(0) !== '#') a.target = '_top';
  });

  function syncToc() { toc.open = !compact.matches; }
  syncToc();
  compact.addEventListener('change', syncToc);
  links.forEach(function (a) {
    a.addEventListener('click', function () { if (compact.matches) toc.open = false; });
  });

  function mark(id) {
    var card = id && document.getElementById(id);
    var sectionId = card ? (card.closest('.g-sec') || card).id : '';
    links.forEach(function (a) {
      var target = a.getAttribute('href').slice(1);
      a.classList.toggle('is-current', target === id);
      if (a.classList.contains('g-toc__top')) a.parentNode.classList.toggle('is-open', target === sectionId);
    });
  }
  var observer = new IntersectionObserver(function (entries) {
    var visible = entries.filter(function (e) { return e.isIntersecting; })
      .sort(function (a, b) { return a.boundingClientRect.top - b.boundingClientRect.top; })[0];
    if (visible) mark(visible.target.id);
  }, { rootMargin: '-80px 0px -70% 0px' });
  cards.forEach(function (card) { observer.observe(card); });
  mark(location.hash.slice(1) || cards[0].id);

  var empty = document.getElementById('guideEmpty');
  document.getElementById('guideSearch').addEventListener('input', function (event) {
    var query = event.target.value.trim().toLowerCase();
    var shown = 0;
    cards.forEach(function (card) {
      var hit = !query || card.textContent.toLowerCase().indexOf(query) !== -1;
      if (hit) { card.removeAttribute('data-g-hidden'); shown += 1; } else card.setAttribute('data-g-hidden', '');
    });
    sections.forEach(function (section) {
      if (section.querySelector('.g-card:not([data-g-hidden])')) section.removeAttribute('data-g-hidden');
      else section.setAttribute('data-g-hidden', '');
    });
    empty.hidden = shown !== 0;
  });
})();
