// Calls and voice notes for members: start a call from a chat, ring when someone calls, record and play voice messages.
(function () {
  const $ = (s, r = document) => r.querySelector(s), $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const csrf = () => (document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/) || [])[1] || '';
  const post = (url, body) => fetch(url, { method: 'POST', headers: { 'X-CSRFToken': csrf(), 'X-Requested-With': 'fetch' }, body, credentials: 'same-origin' });
  const toast = (text) => { let t = $('#call-toast'); if (!t) { t = document.createElement('div'); t.id = 'call-toast'; document.body.appendChild(t); }
    t.textContent = text; t.classList.add('show'); clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove('show'), 4500); };

  // ---- a button that is switched off says why instead of doing nothing ----
  document.addEventListener('click', (e) => {
    const b = e.target.closest('[data-why]'); if (b && b.dataset.why) toast(b.dataset.why);
  });

  // ---- start a call from a chat header or a member card ----
  // A call screen is a whole page, so it cannot arrive instantly. The waiting card does, and the microphone
  // is asked for straight away, so the seconds before the screen opens are spent doing the useful part.
  const waiting = (kind) => {
    let w = $('#call-wait');
    if (!w) {
      w = document.createElement('div'); w.id = 'call-wait';
      w.innerHTML = '<div class="cw-card"><span class="cw-ring"></span><svg class="cw-ic"></svg><p></p>' +
                    '<button type="button" class="cw-x">Cancel</button></div>';
      document.body.appendChild(w);
      $('.cw-x', w).addEventListener('click', () => { w.classList.remove('show'); w.dataset.off = '1'; });
    }
    delete w.dataset.off;
    $('.cw-ic', w).innerHTML = `<use href="#${document.getElementById('m-video') ? 'm' : 'i'}-${kind === 'video' ? 'video' : 'phone'}"/>`;
    $('p', w).textContent = kind === 'video' ? 'Starting video call\u2026' : 'Calling\u2026';
    w.classList.add('show');
    return w;
  };

  document.addEventListener('click', async (e) => {
    const b = e.target.closest('[data-call][data-start]'); if (!b) return;
    b.disabled = true;
    const kind = b.dataset.call, w = waiting(kind);
    // warm the microphone/camera up now: the permission prompt and device start are the slowest part of a call
    const warm = navigator.mediaDevices
      ? navigator.mediaDevices.getUserMedia({ audio: true, video: kind === 'video' }).catch(() => null)
      : Promise.resolve(null);
    const fd = new FormData(); fd.append('kind', kind);
    try {
      const r = await post(b.dataset.start, fd), j = await r.json();
      const stream = await warm;
      if (stream) stream.getTracks().forEach((t) => t.stop());   // the call screen opens its own; just prove it works
      if (w.dataset.off) { if (j.ok && j.end) post(j.end, new FormData()); }   // they changed their mind while waiting
      else if (j.ok) location.href = j.url;
      else { w.classList.remove('show'); if (j.premium) { toast(j.error); setTimeout(() => location.href = j.url, 1500); } else toast(j.error || 'The call could not be started.'); }
    } catch (_) { w.classList.remove('show'); toast('No connection. Check your internet and try again.'); }
    b.disabled = false;
  });

  // ---- incoming calls: ask the server every few seconds, ring and show a card ----
  const box = $('#incoming-call');
  if (box) {
    let shown = null, ctx = null, beep = null;
    const ring = (on) => {
      clearInterval(beep); if (navigator.vibrate) navigator.vibrate(on ? [600, 400, 600, 400, 600] : 0);
      if (!on) return;
      try {
        ctx = ctx || new (window.AudioContext || window.webkitAudioContext)();
        const tone = () => { [0, 0.45].forEach((d) => { const o = ctx.createOscillator(), g = ctx.createGain();
          o.frequency.value = 480; g.gain.setValueAtTime(0.0001, ctx.currentTime + d); g.gain.exponentialRampToValueAtTime(0.25, ctx.currentTime + d + 0.03);
          g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + d + 0.38); o.connect(g).connect(ctx.destination); o.start(ctx.currentTime + d); o.stop(ctx.currentTime + d + 0.4); }); };
        tone(); beep = setInterval(tone, 2200);
      } catch (_) {}
    };
    const hide = () => { box.hidden = true; ring(false); document.title = document.title.replace(/^📞 [^|]*\| /, ''); shown = null; };
    const show = (c) => {
      shown = c.id; $('.ic-name', box).textContent = c.name; $('.ic-kind', box).textContent = c.kind === 'video' ? 'Incoming video call…' : 'Incoming voice call…';
      const img = $(".ic-photo", box), letter = $(".ic-letter", box); img.hidden = !c.photo; if (c.photo) img.src = c.photo; letter.hidden = !!c.photo; letter.textContent = (c.name || "?")[0];
      $('.ic-accept', box).href = c.url; $('.ic-accept', box).classList.toggle('video', c.kind === 'video'); box.dataset.decline = c.decline;
      box.hidden = false; ring(true); document.title = '📞 ' + c.name + ' | ' + document.title;
    };
    $('.ic-decline', box).addEventListener('click', () => { post(box.dataset.decline, new FormData()); hide(); });
    const poll = async () => {
      try {
        const r = await fetch(box.dataset.poll, { credentials: 'same-origin', headers: { 'X-Requested-With': 'fetch' } });
        if (r.ok) { const j = await r.json(); if (j.call && j.call.id !== shown) show(j.call); else if (!j.call && shown) hide(); }
      } catch (_) {}
      setTimeout(poll, document.hidden ? 8000 : 3500);
    };
    // browsers only allow sound after the person has touched the page once
    ['click', 'keydown', 'touchstart'].forEach((ev) => addEventListener(ev, () => { try { ctx = ctx || new (window.AudioContext || window.webkitAudioContext)(); ctx.resume(); } catch (_) {} }, { once: true }));
    setTimeout(poll, 1200);
  }

  // ---- voice notes: play ----
  const fmt = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
  $$('[data-voice]').forEach((v) => {
    const a = $('audio', v), t = $('.vtime', v), bar = $('.vwave i', v), dur = +t.dataset.dur || 0;
    t.textContent = fmt(dur);
    $('.vplay', v).addEventListener('click', () => {
      $$('[data-voice] audio').forEach((o) => { if (o !== a) o.pause(); });
      if (a.paused) a.play().catch(() => toast('This voice message could not be played on this device.')); else a.pause();
    });
    a.addEventListener('play', () => v.classList.add('on')); a.addEventListener('pause', () => v.classList.remove('on'));
    a.addEventListener('timeupdate', () => { const d = isFinite(a.duration) && a.duration ? a.duration : dur; bar.style.width = (d ? a.currentTime / d * 100 : 0) + '%'; t.textContent = fmt(a.currentTime || 0); });
    a.addEventListener('ended', () => { bar.style.width = '0'; t.textContent = fmt(dur); });
  });

  // ---- voice notes: record and send ----
  const mic = $('.cmic'), rec = $('.crec');
  if (mic && rec) {
    if (!navigator.mediaDevices || !window.MediaRecorder) { mic.hidden = true; return; }
    const form = mic.form, MAX = 120;
    let recorder = null, chunks = [], started = 0, timer = null, cancelled = false, stream = null;
    const type = ['audio/webm;codecs=opus', 'audio/mp4', 'audio/ogg;codecs=opus', 'audio/webm'].find((t) => MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(t)) || '';
    const stopAll = () => { clearInterval(timer); if (stream) stream.getTracks().forEach((t) => t.stop()); stream = null; rec.hidden = true; form.classList.remove('recording'); };
    const send = async (blob, secs) => {
      const fd = new FormData(); fd.append('csrfmiddlewaretoken', csrf()); fd.append('body', '');
      const ext = (blob.type.includes('mp4') ? 'm4a' : blob.type.includes('ogg') ? 'ogg' : 'webm');
      fd.append('voice', new File([blob], 'voice.' + ext, { type: blob.type.split(';')[0] || 'audio/webm' })); fd.append('duration', Math.round(secs));
      mic.disabled = true;
      try {
        const r = await post(mic.dataset.voiceUrl, fd), j = await r.json();
        if (!j.ok) toast(j.error);
        else if (j.html && window.chatAppend) window.chatAppend(j.html, j.id);   // the chat puts it straight on screen
        else location.reload();                                                  // older page: fall back to a reload
      } catch (_) { toast('The voice note could not be sent. Check your internet.'); }
      mic.disabled = false;
    };
    mic.addEventListener('click', async () => {
      try { stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } }); }
      catch (_) { toast('Allow microphone access in your browser to record a voice note.'); return; }
      chunks = []; cancelled = false; recorder = new MediaRecorder(stream, type ? { mimeType: type, audioBitsPerSecond: 32000 } : undefined);
      recorder.ondataavailable = (e) => e.data.size && chunks.push(e.data);
      recorder.onstop = () => { const secs = (Date.now() - started) / 1000; stopAll(); if (!cancelled && secs >= 1) send(new Blob(chunks, { type: recorder.mimeType || type || 'audio/webm' }), Math.min(secs, MAX)); };
      recorder.start(250); started = Date.now(); rec.hidden = false; form.classList.add('recording');
      timer = setInterval(() => { const s = (Date.now() - started) / 1000; $('.crec-t', rec).textContent = fmt(s); $('.crec-bar i', rec).style.width = Math.min(100, s / MAX * 100) + '%'; if (s >= MAX) recorder.stop(); }, 200);
    });
    $('.crec-send', rec).addEventListener('click', () => recorder && recorder.state === 'recording' && recorder.stop());
    $('.crec-x', rec).addEventListener('click', () => { cancelled = true; if (recorder && recorder.state === 'recording') recorder.stop(); else stopAll(); });
  }
})();
