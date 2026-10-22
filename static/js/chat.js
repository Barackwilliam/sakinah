// The messages screen: composer, emoji, photo preview, and new messages arriving without a page reload.
// Voice notes, call buttons and the incoming-call card are handled by calls.js, which every page already loads.
(function () {
  const $ = (s, r = document) => r.querySelector(s), $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const body = $('#ch-body'), form = $('#ch-form'), box = $('#ch-box');
  const atEnd = () => !body || body.scrollHeight - body.scrollTop - body.clientHeight < 120;
  const toEnd = (smooth) => { if (body) body.scrollTo({ top: body.scrollHeight, behavior: smooth ? 'smooth' : 'auto' }); };
  toEnd(); addEventListener('load', () => toEnd());

  if (form && box) {
    const fit = () => { box.style.height = 'auto'; box.style.height = Math.min(box.scrollHeight, 120) + 'px'; };
    box.addEventListener('input', fit);
    box.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey && innerWidth > 760) { e.preventDefault(); if (box.value.trim() || $('.ch-file input').files.length) form.requestSubmit ? form.requestSubmit() : form.submit(); }
    });
    form.addEventListener('submit', (e) => { if (!box.value.trim() && !$('.ch-file input').files.length) { e.preventDefault(); box.focus(); } });
    $$('[data-emo]').forEach((b) => b.addEventListener('click', () => { box.value += b.dataset.emo; box.focus(); fit(); $('.ch-emo').open = false; }));
    $$('[data-say]').forEach((b) => b.addEventListener('click', () => { box.value = b.dataset.say; box.focus(); fit(); }));

    // photo: show what is about to be sent, with a way to remove it
    const file = $('.ch-file input');
    file.addEventListener('change', () => {
      $('.ch-prev')?.remove();
      $('.ch-file').classList.toggle('has', !!file.files.length);
      if (!file.files.length) return;
      const row = document.createElement('div'); row.className = 'ch-prev';
      const img = document.createElement('img'); img.src = URL.createObjectURL(file.files[0]); row.appendChild(img);
      const name = document.createElement('span'); name.textContent = file.files[0].name; row.appendChild(name);
      const x = document.createElement('button'); x.type = 'button'; x.textContent = '×'; x.setAttribute('aria-label', 'Ondoa picha');
      x.onclick = () => { file.value = ''; $('.ch-file').classList.remove('has'); row.remove(); };
      row.appendChild(x); form.parentNode.insertBefore(row, form);
    });
    // close the emoji panel when clicking elsewhere
    document.addEventListener('click', (e) => { const d = $('.ch-emo'); if (d && d.open && !d.contains(e.target)) d.open = false; });
  }

  // new messages while the chat is open
  if (body && body.dataset.feed) {
    let last = +body.dataset.last || 0, busy = false;
    const presence = $('#ch-presence');
    const poll = async () => {
      if (!busy && !document.hidden) {
        busy = true;
        try {
          const r = await fetch(`${body.dataset.feed}?after=${last}`, { credentials: 'same-origin', headers: { 'X-Requested-With': 'fetch' } });
          if (r.ok) {
            const j = await r.json(), stick = atEnd();
            if (j.html) {
              const hold = document.createElement('div'); hold.innerHTML = j.html;
              const fresh = $$('[data-voice]', hold);
              const hello = $('.ch-hello', body); if (hello) hello.remove();
              while (hold.firstChild) body.appendChild(hold.firstChild);
              last = j.last; if (stick) toEnd(true);
              fresh.forEach(wire);   // the ones already on the page were wired by calls.js
            }
            if (presence) { presence.classList.toggle('on', !!j.online); if (j.online) presence.textContent = 'Yupo mtandaoni'; }
            if (j.seen) $$('.ch-tick', body).forEach((t) => t.classList.add('seen'));
          }
        } catch (_) {}
        busy = false;
      }
      setTimeout(poll, document.hidden ? 20000 : 6000);
    };
    setTimeout(poll, 4000);
  }

  // voice notes that arrive after the page was built need their player wired up (calls.js does the ones already there)
  const fmt = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
  function wire(v) {
    if (v.dataset.ready) return; v.dataset.ready = '1';
    const a = $('audio', v), t = $('.vtime', v), bar = $('.vwave i', v), dur = +t.dataset.dur || 0;
    t.textContent = fmt(dur);
    $('.vplay', v).addEventListener('click', () => { $$('[data-voice] audio').forEach((o) => { if (o !== a) o.pause(); }); a.paused ? a.play().catch(() => {}) : a.pause(); });
    a.addEventListener('play', () => v.classList.add('on')); a.addEventListener('pause', () => v.classList.remove('on'));
    a.addEventListener('timeupdate', () => { const d = isFinite(a.duration) && a.duration ? a.duration : dur; bar.style.width = (d ? a.currentTime / d * 100 : 0) + '%'; t.textContent = fmt(a.currentTime || 0); });
    a.addEventListener('ended', () => { bar.style.width = '0'; t.textContent = fmt(dur); });
  }
})();
