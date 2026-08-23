/* FastPDLC — fastpdlc.com
   No dependencies. Everything degrades to a working page if this never loads. */
(function () {
  'use strict';

  /* ── mobile nav ───────────────────────────────────────────────────────── */
  var toggle = document.getElementById('navToggle');
  var links = document.getElementById('navLinks');
  if (toggle && links) {
    toggle.addEventListener('click', function () {
      var open = links.classList.toggle('open');
      toggle.setAttribute('aria-expanded', String(open));
    });
    links.addEventListener('click', function (e) {
      if (e.target.tagName === 'A') {
        links.classList.remove('open');
        toggle.setAttribute('aria-expanded', 'false');
      }
    });
  }

  /* ── copy-to-clipboard ────────────────────────────────────────────────── */
  document.querySelectorAll('.copy-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var src = document.querySelector(btn.dataset.copy);
      if (!src) return;
      var text = src.textContent.trim();

      var done = function () {
        var was = btn.textContent;
        btn.textContent = 'Copied';
        btn.dataset.copied = 'true';
        setTimeout(function () {
          btn.textContent = was;
          delete btn.dataset.copied;
        }, 1600);
      };

      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(done, fallback);
      } else {
        fallback();
      }

      function fallback() {
        var ta = document.createElement('textarea');
        ta.value = text;
        ta.setAttribute('readonly', '');
        ta.style.position = 'fixed';
        ta.style.left = '-9999px';
        document.body.appendChild(ta);
        ta.select();
        try { document.execCommand('copy'); done(); } catch (e) { /* nothing to do */ }
        document.body.removeChild(ta);
      }
    });
  });

  /* ── seamless marquee: duplicate the rail once, animate to -50% ───────── */
  var track = document.getElementById('railTrack');
  if (track && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    var originals = Array.prototype.slice.call(track.children);
    originals.forEach(function (node) {
      var clone = node.cloneNode(true);
      clone.setAttribute('aria-hidden', 'true');
      track.appendChild(clone);
    });
  }

  /* ── scroll reveal ────────────────────────────────────────────────────── */
  var targets = document.querySelectorAll('.reveal');
  if (!('IntersectionObserver' in window)) {
    targets.forEach(function (el) { el.classList.add('in'); });
  } else {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        entry.target.classList.add('in');
        io.unobserve(entry.target);
      });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 });

    targets.forEach(function (el, i) {
      el.style.transitionDelay = (Math.min(i % 4, 3) * 60) + 'ms';
      io.observe(el);
    });
  }

  /* ── signup → lead capture API (the CRM seed) ─────────────────────────── */
  var form = document.getElementById('signupForm');
  var msg = document.getElementById('signupMsg');
  if (form && msg) {
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var email = form.email.value.trim();
      var honeypot = form.company.value;

      msg.className = 'msg';
      if (!email || email.indexOf('@') < 1 || email.indexOf('.', email.indexOf('@')) < 0) {
        msg.textContent = 'That address does not look right.';
        msg.classList.add('err');
        form.email.focus();
        return;
      }

      var btn = form.querySelector('button[type=submit]');
      btn.disabled = true;
      msg.textContent = 'Sending…';

      fetch('/api/subscribe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email, company: honeypot, source: 'landing' })
      })
        .then(function (r) {
          if (!r.ok) throw new Error('HTTP ' + r.status);
          return r.json();
        })
        .then(function () {
          form.reset();
          msg.textContent = "You're on the list. Nothing else required.";
          msg.classList.add('ok');
        })
        .catch(function () {
          msg.textContent = "Couldn't reach the server — try again, or watch the repo on GitHub.";
          msg.classList.add('err');
        })
        .finally(function () { btn.disabled = false; });
    });
  }

  /* ── footer year ──────────────────────────────────────────────────────── */
  var year = document.getElementById('year');
  if (year) year.textContent = String(new Date().getFullYear());
})();
