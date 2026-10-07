/* .NET Full Stack Interview Prep — client-side app
   Sections are stored as <template>s inside index.html and rendered on demand.
   No network access or build tooling is needed to browse the site (works from file://). */
(function () {
  'use strict';

  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var esc = function (s) { return String(s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); };

  var META = JSON.parse(document.getElementById('meta').textContent);
  var SECS = META.sections;
  var BY_ID = {};
  SECS.forEach(function (s) { BY_ID[s.id] = s; });
  var ORDER = [];
  META.groups.forEach(function (g) { SECS.filter(function (s) { return s.group === g; }).forEach(function (s) { ORDER.push(s.id); }); });

  var root = document.documentElement;
  var body = document.body;

  /* ---------- storage (always guarded: may be unavailable) ---------- */
  var store = {
    get: function (k, d) { try { var v = localStorage.getItem(k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } },
    set: function (k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* ignore */ } }
  };
  var done = store.get('ip.done', {});
  if (typeof done !== 'object' || done === null) done = {};

  /* ---------- theme ---------- */
  function applyTheme(t) { root.setAttribute('data-theme', t); }
  (function () {
    var t = null;
    try { t = localStorage.getItem('ip.theme'); } catch (e) { /* ignore */ }
    if (t !== 'dark' && t !== 'light') t = window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    applyTheme(t);
  })();
  $('#theme-btn').addEventListener('click', function () {
    var next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    applyTheme(next);
    try { localStorage.setItem('ip.theme', next); } catch (e) { /* ignore */ }
  });

  /* ---------- progress ---------- */
  function progress(s) {
    var n = 0;
    s.trackIds.forEach(function (id) { if (done[id]) n++; });
    return { n: n, total: s.topics, pct: s.topics ? Math.round(100 * n / s.topics) : 0 };
  }
  function updateProgressUI() {
    var sumN = 0, sumT = 0;
    SECS.forEach(function (s) {
      var p = progress(s);
      sumN += p.n; sumT += p.total;
      var a = $('.nav-item[data-id="' + s.id + '"]');
      if (a) {
        $('.nav-pct', a).textContent = p.total ? p.pct + '%' : '';
        $('.nav-bar i', a).style.width = p.pct + '%';
      }
      var c = $('.card[data-id="' + s.id + '"]');
      if (c) {
        $('.bar i', c).style.width = p.pct + '%';
        $('.pct', c).textContent = p.n + ' / ' + p.total + ' topics mastered';
      }
    });
    var pct = sumT ? Math.round(100 * sumN / sumT) : 0;
    var ov = $('#overall');
    if (ov) { $('i', ov).style.width = pct + '%'; $('b', ov).textContent = pct + '%'; }
  }

  /* ---------- sidebar ---------- */
  function buildSidebar() {
    var h = '<a class="nav-home" href="#/" data-nav="home">Home &amp; roadmap</a>';
    META.groups.forEach(function (g) {
      h += '<div class="nav-group">' + esc(g) + '</div>';
      SECS.filter(function (s) { return s.group === g; }).forEach(function (s) {
        h += '<a class="nav-item" href="#/s' + s.id + '" data-id="' + s.id + '"><div class="nav-row"><span class="nav-num">' + s.id +
          '</span><span class="nav-name">' + esc(s.short) + '</span><span class="dot ' + s.prio + '" title="' + META.priority[s.prio] +
          ' priority"></span><span class="nav-pct"></span></div><div class="nav-bar"><i></i></div></a>';
      });
    });
    h += '<div class="legend"><span><i class="dot vh"></i>Very High</span><span><i class="dot h"></i>High</span><span><i class="dot m"></i>Medium</span><span><i class="dot s"></i>Supporting</span></div>';
    $('#sidebar').innerHTML = h;
  }
  function setActiveNav(id) {
    $$('.nav-item').forEach(function (a) { a.classList.toggle('active', a.getAttribute('data-id') === id); });
    var home = $('.nav-home');
    if (home) home.classList.toggle('active', !id);
    var act = $('.nav-item.active');
    if (act) { var sb = $('#sidebar'); var r = act.getBoundingClientRect(), sr = sb.getBoundingClientRect(); if (r.top < sr.top + 40 || r.bottom > sr.bottom - 40) act.scrollIntoView({ block: 'center' }); }
  }

  /* ---------- gallery HTML (home page) ---------- */
  function galleryHTML(images, title) {
    if (!images || !images.length) return '';
    var cards = images.map(function (im, i) {
      return '<figure class="shot" data-i="' + i + '"><button type="button" class="shot-btn" aria-label="Open ' + esc(im.caption) + '"><img loading="lazy" src="' + esc(im.src) + '" alt="' + esc(im.caption) + '"></button><figcaption><span class="k ' + im.kind + '">' + im.kind + '</span> ' + esc(im.caption) + '</figcaption></figure>';
    }).join('');
    return '<h2 class="home-h">' + esc(title) + '</h2><details class="gallery" open><summary>Gallery <span class="count">' + images.length + '</span></summary><div class="shots">' + cards + '</div></details>';
  }

  /* ---------- home ---------- */
  function renderHome() {
    var t = META.totals;
    var stats = { sections: SECS.length, topics: t.topics, qa: t.qa, code: t.code, visuals: t.diagrams + t.shots };
    Object.keys(stats).forEach(function (k) { var el = $('[data-stat="' + k + '"]'); if (el) el.textContent = stats[k].toLocaleString(); });

    var h = '';
    META.groups.forEach(function (g) {
      h += '<div class="grp-title">' + esc(g) + '</div><div class="cards">';
      SECS.filter(function (s) { return s.group === g; }).forEach(function (s) {
        h += '<a class="card" href="#/s' + s.id + '" data-id="' + s.id + '"><div class="card-top"><span class="card-num">' + s.id +
          '</span><span class="chip ' + s.prio + '">' + META.priority[s.prio] + '</span></div><h3>' + esc(s.title) + '</h3><p>' +
          s.topics + ' topics &middot; ' + s.qa + ' Q&amp;As &middot; ' + s.images + ' visuals &middot; ~' + s.minutes + ' min</p>' +
          '<div class="bar"><i></i></div><div class="pct"></div></a>';
      });
      h += '</div>';
    });
    $('#home-sections').innerHTML = h;
    $('#home-visuals').innerHTML = galleryHTML(META.homeImages, 'General reference screenshots');

    var last = store.get('ip.last', null);
    if (last && BY_ID[last]) {
      var r = $('#cta-resume');
      r.hidden = false; r.href = '#/s' + last; r.textContent = 'Resume: ' + BY_ID[last].short;
    }
    updateProgressUI();
  }

  /* ---------- section rendering ---------- */
  var current = null;
  var tocHeads = [];

  function decorateSection(view, s) {
    // "Mastered" checkboxes on tracked headings
    s.trackIds.forEach(function (id) {
      var h = document.getElementById(id);
      if (!h) return;
      var lab = document.createElement('label');
      lab.className = 'done'; lab.title = 'Mark this topic as mastered';
      lab.innerHTML = '<input type="checkbox"> Mastered';
      var cb = lab.firstChild;
      cb.checked = !!done[id];
      h.classList.toggle('is-done', !!done[id]);
      cb.addEventListener('change', function () {
        if (cb.checked) done[id] = 1; else delete done[id];
        store.set('ip.done', done);
        h.classList.toggle('is-done', cb.checked);
        updateProgressUI(); markTocDone();
      });
      h.insertBefore(lab, h.firstChild);
    });

    // on phones, start the diagram gallery collapsed so the content comes first
    var gal = view.querySelector('details.gallery');
    if (gal && window.matchMedia && matchMedia('(max-width: 900px)').matches) gal.open = false;

    // previous / next
    var i = ORDER.indexOf(s.id);
    var prev = ORDER[i - 1] && BY_ID[ORDER[i - 1]], next = ORDER[i + 1] && BY_ID[ORDER[i + 1]];
    var nav = document.createElement('nav');
    nav.className = 'sec-nav'; nav.setAttribute('aria-label', 'Section navigation');
    nav.innerHTML = (prev ? '<a class="prev" href="#/s' + prev.id + '"><small>&larr; Previous</small>' + esc(prev.id + ' · ' + prev.short) + '</a>' : '<span style="flex:1"></span>') +
      (next ? '<a class="next" href="#/s' + next.id + '"><small>Next &rarr;</small>' + esc(next.id + ' · ' + next.short) + '</a>' : '<span style="flex:1"></span>');
    view.querySelector('article').appendChild(nav);
  }

  function buildToc(s) {
    var toc = $('#toc');
    var h = '<h4>On this page</h4>';
    s.toc.forEach(function (t) { h += '<a class="l' + t.l + '" href="#/s' + s.id + '/' + t.id + '" data-id="' + t.id + '">' + esc(t.t) + '</a>'; });
    toc.innerHTML = h;
    toc.hidden = false;
    tocHeads = s.toc.map(function (t) { return document.getElementById(t.id); }).filter(Boolean);
    markTocDone(); spy();
  }
  function markTocDone() {
    $$('#toc a').forEach(function (a) { a.classList.toggle('done-t', !!done[a.getAttribute('data-id')]); });
  }

  var spyTick = false;
  function spy() {
    if (!tocHeads.length) return;
    var active = null;
    for (var i = 0; i < tocHeads.length; i++) { if (tocHeads[i].getBoundingClientRect().top <= 110) active = tocHeads[i]; else break; }
    var id = active ? active.id : null;
    $$('#toc a').forEach(function (a) { a.classList.toggle('active', a.getAttribute('data-id') === id); });
    var act = $('#toc a.active');
    if (act) { var tc = $('#toc'); var r = act.getBoundingClientRect(), tr = tc.getBoundingClientRect(); if (r.top < tr.top + 20 || r.bottom > tr.bottom - 20) act.scrollIntoView({ block: 'nearest' }); }
  }
  window.addEventListener('scroll', function () {
    if (!spyTick) { spyTick = true; requestAnimationFrame(function () { spyTick = false; spy(); $('#to-top').hidden = window.scrollY < 700; }); }
  }, { passive: true });
  $('#to-top').addEventListener('click', jumpTop);

  function jumpTop() {
    try { window.scrollTo({ top: 0, left: 0, behavior: 'instant' }); } catch (e) { window.scrollTo(0, 0); }
  }
  function scrollToId(id) {
    var el = document.getElementById(id);
    if (!el) return false;
    try { el.scrollIntoView({ block: 'start', behavior: 'instant' }); } catch (e) { el.scrollIntoView(true); }
    el.classList.remove('flash'); void el.offsetWidth; el.classList.add('flash');
    return true;
  }

  function showHome() {
    current = null;
    $('#section-view').hidden = true; $('#section-view').innerHTML = '';
    $('#home').hidden = false;
    $('#toc').hidden = true; tocHeads = [];
    body.classList.remove('has-toc');
    document.title = '.NET Full Stack Interview Prep';
    setActiveNav(null);
    jumpTop();
    updateProgressUI();
  }

  function showSection(id, anchor) {
    var s = BY_ID[id];
    var tpl = document.getElementById('tpl-s' + id);
    if (!s || !tpl) { showHome(); return; }
    var view = $('#section-view');
    if (current !== id) {
      view.innerHTML = '';
      view.appendChild(tpl.content.cloneNode(true));
      decorateSection(view, s);
      current = id;
      store.set('ip.last', id);
    }
    $('#home').hidden = true; view.hidden = false;
    body.classList.add('has-toc');
    buildToc(s);
    document.title = s.id + ' · ' + s.title + ' — .NET Interview Prep';
    setActiveNav(id);
    if (!(anchor && scrollToId(decodeURIComponent(anchor)))) jumpTop();
    closeNav();
  }

  function route() {
    var m = (location.hash || '#/').match(/^#\/s(\d{2})(?:\/(.+))?$/);
    if (m) showSection(m[1], m[2]); else showHome();
  }
  window.addEventListener('hashchange', route);

  /* ---------- mobile nav ---------- */
  function closeNav() { body.classList.remove('nav-open'); $('#menu-btn').setAttribute('aria-expanded', 'false'); $('#scrim').hidden = true; }
  $('#menu-btn').addEventListener('click', function () {
    var open = !body.classList.contains('nav-open');
    body.classList.toggle('nav-open', open);
    $('#menu-btn').setAttribute('aria-expanded', String(open));
    $('#scrim').hidden = !open;
  });
  $('#scrim').addEventListener('click', closeNav);

  /* ---------- delegated clicks: copy, Q&A toggles, gallery ---------- */
  function copyText(text, btn) {
    function ok() { btn.textContent = 'Copied'; btn.classList.add('ok'); setTimeout(function () { btn.textContent = 'Copy'; btn.classList.remove('ok'); }, 1400); }
    function fallback() {
      var ta = document.createElement('textarea'); ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
      document.body.appendChild(ta); ta.select();
      try { document.execCommand('copy'); ok(); } catch (e) { btn.textContent = 'Press Ctrl+C'; }
      document.body.removeChild(ta);
    }
    if (navigator.clipboard && window.isSecureContext !== false) navigator.clipboard.writeText(text).then(ok, fallback); else fallback();
  }

  var lbList = [], lbIdx = 0;
  function lbShow() {
    var im = lbList[lbIdx]; if (!im) return;
    var lb = $('#lightbox');
    $('img', lb).src = im.src; $('img', lb).alt = im.caption; $('figcaption', lb).textContent = im.caption + '  (' + (lbIdx + 1) + '/' + lbList.length + ')';
    $$('.lb-nav', lb).forEach(function (b) { b.hidden = lbList.length < 2; });
  }
  function lbOpen(list, i) { lbList = list; lbIdx = i; $('#lightbox').hidden = false; lbShow(); body.style.overflow = 'hidden'; }
  function lbClose() { $('#lightbox').hidden = true; body.style.overflow = ''; }
  function lbStep(d) { lbIdx = (lbIdx + d + lbList.length) % lbList.length; lbShow(); }

  document.addEventListener('click', function (e) {
    var t = e.target;
    var copy = t.closest && t.closest('.copy');
    if (copy) { var code = copy.closest('.codeblock').querySelector('pre code'); copyText(code.textContent, copy); return; }
    var act = t.closest && t.closest('[data-act]');
    if (act) {
      var open = act.getAttribute('data-act') === 'expand-qa';
      $$('#section-view details.callout.q').forEach(function (d) { d.open = open; });
      return;
    }
    var shot = t.closest && t.closest('.shot-btn');
    if (shot) {
      var wrap = shot.closest('.shots');
      var list = $$('.shot img', wrap).map(function (im) { return { src: im.getAttribute('src'), caption: im.alt }; });
      lbOpen(list, $$('.shot', wrap).indexOf(shot.closest('.shot')));
      return;
    }
    if (t.closest && t.closest('.lb-close')) { lbClose(); return; }
    if (t.closest && t.closest('.lb-prev')) { lbStep(-1); return; }
    if (t.closest && t.closest('.lb-next')) { lbStep(1); return; }
    if (t === $('#lightbox')) { lbClose(); return; }
    if (!(t.closest && t.closest('.search'))) hideResults();
  });

  /* ---------- search ---------- */
  var index = null;
  function buildIndex() {
    index = [];
    SECS.forEach(function (s) {
      index.push({ sec: s.id, id: null, title: s.id + ' ' + s.title, text: s.short + ' ' + s.group, tl: (s.id + ' ' + s.title + ' ' + s.short).toLowerCase(), xl: s.group.toLowerCase() });
      var tpl = document.getElementById('tpl-s' + s.id);
      var prose = tpl && tpl.content.querySelector('.prose');
      if (!prose) return;
      var cur = { sec: s.id, id: null, title: s.title, text: '' };
      function push() {
        if (cur.id && (cur.text.trim() || cur.title)) index.push({ sec: cur.sec, id: cur.id, title: cur.title, text: cur.text, tl: cur.title.toLowerCase(), xl: cur.text.toLowerCase() });
      }
      Array.prototype.forEach.call(prose.children, function (el) {
        if (el.tagName === 'H2' || el.tagName === 'H3') {
          push();
          cur = { sec: s.id, id: el.id, title: el.textContent.replace(/#\s*$/, '').trim(), text: '' };
        } else {
          cur.text += ' ' + el.textContent.replace(/\s+/g, ' ');
        }
      });
      push();
    });
  }

  function snippet(text, toks) {
    var low = text.toLowerCase(), pos = -1;
    for (var i = 0; i < toks.length; i++) { var p = low.indexOf(toks[i]); if (p !== -1 && (pos === -1 || p < pos)) pos = p; }
    if (pos === -1) return esc(text.slice(0, 150).trim());
    var start = Math.max(0, pos - 60), end = Math.min(text.length, pos + 120);
    var s = esc(text.slice(start, end).trim());
    toks.forEach(function (t) {
      if (!t) return;
      var re = new RegExp('(' + esc(t).replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'ig');
      s = s.replace(re, '<mark>$1</mark>');
    });
    return (start > 0 ? '… ' : '') + s + (end < text.length ? ' …' : '');
  }

  function doSearch(q) {
    var toks = q.toLowerCase().split(/\s+/).filter(Boolean);
    var box = $('#results');
    if (!toks.length) { hideResults(); return; }
    if (!index) buildIndex();
    var res = [];
    for (var i = 0; i < index.length; i++) {
      var e = index[i], score = 0, ok = true;
      for (var k = 0; k < toks.length; k++) {
        var t = toks[k], inT = e.tl.indexOf(t) !== -1, p = e.xl.indexOf(t);
        if (!inT && p === -1) { ok = false; break; }
        if (inT) score += 10;
        if (p !== -1) { var c = 0; while (p !== -1 && c < 6) { c++; p = e.xl.indexOf(t, p + 1); } score += c; }
      }
      if (ok) res.push({ e: e, score: score + (e.id ? 0 : 4) });
    }
    res.sort(function (a, b) { return b.score - a.score; });
    res = res.slice(0, 20);
    if (!res.length) { box.innerHTML = '<div class="none">No topics match “' + esc(q) + '”.</div>'; box.hidden = false; return; }
    box.innerHTML = res.map(function (r, n) {
      var e = r.e;
      return '<a class="hit' + (n === 0 ? ' sel' : '') + '" role="option" href="#/s' + e.sec + (e.id ? '/' + e.id : '') + '"><div class="hit-top"><span class="hit-sec">' + e.sec + ' · ' + esc(BY_ID[e.sec].short) + '</span><span class="hit-title">' + esc(e.title) + '</span></div>' +
        (e.text ? '<div class="hit-snip">' + snippet(e.text, toks) + '</div>' : '') + '</a>';
    }).join('');
    box.hidden = false;
  }
  function hideResults() { var b = $('#results'); if (b) b.hidden = true; }

  var qInput = $('#q'), qTimer = null;
  qInput.addEventListener('focus', function () { if (!index) setTimeout(buildIndex, 30); if (qInput.value.trim()) doSearch(qInput.value); });
  qInput.addEventListener('input', function () { clearTimeout(qTimer); qTimer = setTimeout(function () { doSearch(qInput.value.trim()); }, 120); });
  qInput.addEventListener('keydown', function (e) {
    var box = $('#results'), items = $$('.hit', box), sel = $('.hit.sel', box);
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault(); if (!items.length) return;
      var i = Math.max(0, items.indexOf(sel)) + (e.key === 'ArrowDown' ? 1 : -1);
      i = (i + items.length) % items.length;
      items.forEach(function (x) { x.classList.remove('sel'); }); items[i].classList.add('sel'); items[i].scrollIntoView({ block: 'nearest' });
    } else if (e.key === 'Enter') {
      if (sel) { e.preventDefault(); location.hash = sel.getAttribute('href'); hideResults(); qInput.blur(); }
    } else if (e.key === 'Escape') { hideResults(); qInput.blur(); }
  });
  $('#results').addEventListener('click', function (e) { if (e.target.closest('.hit')) { hideResults(); qInput.blur(); } });

  document.addEventListener('keydown', function (e) {
    var tag = (document.activeElement && document.activeElement.tagName) || '';
    if (e.key === '/' && !/INPUT|TEXTAREA|SELECT/.test(tag) && !e.ctrlKey && !e.metaKey) { e.preventDefault(); qInput.focus(); qInput.select(); }
    if (!$('#lightbox').hidden) {
      if (e.key === 'Escape') lbClose(); else if (e.key === 'ArrowLeft') lbStep(-1); else if (e.key === 'ArrowRight') lbStep(1);
    }
  });
  var cs = $('#cta-search'); if (cs) cs.addEventListener('click', function () { qInput.focus(); });

  if (window.matchMedia && matchMedia('(max-width: 600px)').matches) qInput.placeholder = 'Search topics…';

  /* ---------- init ---------- */
  buildSidebar();
  renderHome();
  route();
})();
