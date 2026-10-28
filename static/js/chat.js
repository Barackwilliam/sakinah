// The messages screen: composer, emoji, photo preview, and new messages arriving without a page reload.
// Voice notes, call buttons and the incoming-call card are handled by calls.js, which every page already loads.
(function () {
  const $ = (s, r = document) => r.querySelector(s), $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const body = $('#ch-body'), form = $('#ch-form'), box = $('#ch-box');
  let last = +(body?.dataset.last) || 0, fit = () => {};
  const atEnd = () => !body || body.scrollHeight - body.scrollTop - body.clientHeight < 120;
  const toEnd = (smooth) => { if (body) body.scrollTo({ top: body.scrollHeight, behavior: smooth ? 'smooth' : 'auto' }); };
  toEnd(); addEventListener('load', () => toEnd());

  if (form && box) {
    fit = () => { box.style.height = 'auto'; box.style.height = Math.min(box.scrollHeight, 120) + 'px'; };
    box.addEventListener('input', fit);
    box.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey && innerWidth > 760) { e.preventDefault(); form.requestSubmit ? form.requestSubmit() : form.submit(); }
    });

    // Send over the wire, never by reloading the page: the bubble is on screen before the server has answered.
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const file = $('.ch-file input'), text = box.value.trim();
      if (!text && !file.files.length) return box.focus();
      const fd = new FormData(form);
      const pending = draft(text, file.files[0]);                 // shows at once, greyed, with a little clock
      box.value = ''; fit(); file.value = ''; $('.ch-file').classList.remove('has'); $('.ch-prev')?.remove();
      box.focus(); toEnd(true);
      try {
        const r = await fetch(location.pathname, { method: 'POST', body: fd, credentials: 'same-origin',
                                                   headers: { 'X-Requested-With': 'fetch' } });
        const j = await r.json();
        if (j.ok && j.html) { swap(pending, j.html, j.id); } else { failed(pending, j.error); }
      } catch (_) { failed(pending, 'Ujumbe haukutumwa. Angalia mtandao wako.'); }
    });
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

  // ---- the bubble that appears before the server has answered ----
  function draft(text, photo) {
    const row = document.createElement('div');
    row.className = 'ch-b me ch-wait';                            // the same bubble the server renders, only paler
    const now = new Date().toTimeString().slice(0, 5);
    const clock = '<svg class="ch-tick" viewBox="0 0 24 24"><path fill="currentColor" d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm1 10.6 3.3 2-.8 1.3L11 13.4V6h2z"/></svg>';
    row.innerHTML = `<div class="ch-bb">${photo ? '<span class="ch-img"><img alt=""></span>' : ''}` +
                    `${text ? `<p>${esc(text)}</p>` : ''}<time>${now}${clock}</time></div>`;
    if (photo) $('img', row).src = URL.createObjectURL(photo);
    $('.ch-hello', body)?.remove(); body.appendChild(row);
    return row;
  }
  const esc = (t) => t.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  function swap(pending, html, id) {
    const hold = document.createElement('div'); hold.innerHTML = html;
    const fresh = $$('[data-voice]', hold);
    pending.replaceWith(...hold.childNodes);
    fresh.forEach(wire);
    if (id) last = Math.max(last, id);                            // the poll must not bring it back a second time
    toEnd(true);
  }

  // calls.js records voice notes; this is how it puts the finished one on screen
  window.chatAppend = (html, id) => {
    if (!body) return false;
    const hold = document.createElement('div'); hold.innerHTML = html;
    const fresh = $$('[data-voice]', hold);
    $('.ch-hello', body)?.remove();
    while (hold.firstChild) body.appendChild(hold.firstChild);
    fresh.forEach(wire);
    if (id) last = Math.max(last, id);
    toEnd(true);
    return true;
  };

  function failed(pending, why) {
    pending.classList.remove('ch-wait'); pending.classList.add('ch-fail');
    const note = document.createElement('small'); note.className = 'ch-err'; note.textContent = why || 'Ujumbe haukutumwa.';
    $('.ch-bb', pending).appendChild(note);
  }

  // new messages while the chat is open
  if (body && body.dataset.feed) {
    let busy = false;
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
