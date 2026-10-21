// The call screen: camera/microphone, the WebRTC connection between the two members, and the controls.
// The server only relays the connection details (offer, answer, network candidates); sound and video go browser to browser.
(function () {
  const el = document.getElementById('call'), $ = (id) => document.getElementById(id);
  const D = el.dataset, video = D.kind === 'video', isCaller = D.caller === '1';
  const ice = JSON.parse(document.getElementById('ice').textContent || '[]');
  const csrf = () => (document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/) || [])[1] || '';
  const post = (url, body) => fetch(url, { method: 'POST', credentials: 'same-origin', keepalive: true,
    headers: { 'X-CSRFToken': csrf(), 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : '{}' });
  const status = (t) => { $('status').textContent = t; };

  let pc = null, local = null, lastSignal = 0, done = false, started = null, tick = null, pollTimer = null, connected = false;
  let pendingIce = [], outbox = [], flushTimer = null, facing = 'user';

  const send = (kind, data) => { outbox.push({ kind, data }); clearTimeout(flushTimer); flushTimer = setTimeout(flush, kind === 'ice' ? 120 : 0); };
  const flush = () => { if (!outbox.length) return; const items = outbox; outbox = []; post(D.signal, items).catch(() => { outbox = items.concat(outbox); }); };

  const leave = (text, ms = 1800) => {
    if (done) return; done = true; clearInterval(tick); clearTimeout(pollTimer);
    status(text); el.classList.add('over');
    if (pc) pc.close(); if (local) local.getTracks().forEach((t) => t.stop());
    setTimeout(() => { location.href = D.back; }, ms);
  };
  const hangup = () => { if (!done) { post(D.end); leave('Call ended', 900); } };

  const startTimer = (from = 0) => {
    if (started) return; started = Date.now() - from * 1000; $('timer').hidden = false; el.classList.add('live');
    const show = () => { const s = Math.floor((Date.now() - started) / 1000); $('timer').textContent = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`; };
    show(); tick = setInterval(show, 1000);
  };

  async function media() {
    try {
      local = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
        video: video ? { facingMode: facing, width: { ideal: 1280 }, height: { ideal: 720 } } : false });
    } catch (e) {
      if (video) { // no camera (or refused): fall back to a voice-only connection rather than failing the call
        try { local = await navigator.mediaDevices.getUserMedia({ audio: true }); el.classList.add('nocam'); } catch (_) {}
      }
      if (!local) { post(D.end); leave('Allow microphone access to make calls', 3500); return false; }
    }
    if (video) { $('self').srcObject = local; }
    if (video && navigator.mediaDevices.enumerateDevices) {
      const cams = (await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === 'videoinput');
      if (cams.length > 1 && $('flip')) $('flip').hidden = false;
    }
    return true;
  }

  function connect() {
    pc = new RTCPeerConnection({ iceServers: ice, iceCandidatePoolSize: 2 });
    local.getTracks().forEach((t) => pc.addTrack(t, local));
    pc.onicecandidate = (e) => { if (e.candidate) send('ice', e.candidate.toJSON()); };
    pc.ontrack = (e) => {
      const s = e.streams[0];
      if (video && e.track.kind === 'video') { $('remote').srcObject = s; el.classList.add('has-video'); }
      $('remote-audio').srcObject = s; $('remote-audio').play().catch(() => {});
    };
    pc.onconnectionstatechange = () => {
      const st = pc.connectionState;
      if (st === 'connected') { connected = true; status(video ? '' : 'Connected'); startTimer(); el.classList.add('connected'); }
      if (st === 'disconnected') status('Reconnecting…');
      if (st === 'failed') { post(D.end); leave('The connection failed. Check your internet and try again.', 3500); }
    };
  }

  async function handle(sig) {
    const data = JSON.parse(sig.data);
    if (sig.kind === 'offer' && !isCaller) {
      await pc.setRemoteDescription(data); await addPendingIce();
      const ans = await pc.createAnswer(); await pc.setLocalDescription(ans); send('answer', pc.localDescription.toJSON());
    } else if (sig.kind === 'answer' && isCaller && pc.signalingState === 'have-local-offer') {
      await pc.setRemoteDescription(data); await addPendingIce();
    } else if (sig.kind === 'ice') {
      if (pc && pc.remoteDescription) { try { await pc.addIceCandidate(data); } catch (_) {} } else pendingIce.push(data);
    }
  }
  async function addPendingIce() { for (const c of pendingIce.splice(0)) { try { await pc.addIceCandidate(c); } catch (_) {} } }

  let offered = false;
  async function poll() {
    if (done) return;
    try {
      const r = await fetch(`${D.state}?after=${lastSignal}`, { credentials: 'same-origin' });
      if (r.ok) {
        const j = await r.json();
        if (['declined', 'ended', 'missed', 'cancelled'].includes(j.status)) {
          return leave({ declined: 'Call declined', missed: 'No answer', cancelled: 'Call cancelled', ended: 'Call ended' }[j.status]);
        }
        if (isCaller && j.status === 'accepted' && !offered) {
          offered = true; status('Connecting…'); connect();
          const offer = await pc.createOffer(); await pc.setLocalDescription(offer); send('offer', pc.localDescription.toJSON());
        }
        if (isCaller && j.status === 'ringing') status('Ringing…');
        for (const s of j.signals) { lastSignal = Math.max(lastSignal, s.id); if (pc) await handle(s); }
      }
    } catch (_) { if (!connected) status('Waiting for the network…'); }
    pollTimer = setTimeout(poll, connected ? 2500 : 700);
  }

  // controls
  $('hangup').addEventListener('click', hangup);
  $('mute').addEventListener('click', (e) => {
    const b = e.currentTarget, off = b.getAttribute('aria-pressed') !== 'true';
    local && local.getAudioTracks().forEach((t) => { t.enabled = !off; }); b.setAttribute('aria-pressed', off); b.classList.toggle('active', off);
  });
  if ($('cam')) $('cam').addEventListener('click', (e) => {
    const b = e.currentTarget, off = b.getAttribute('aria-pressed') !== 'true';
    local && local.getVideoTracks().forEach((t) => { t.enabled = !off; }); b.setAttribute('aria-pressed', off); b.classList.toggle('active', off); el.classList.toggle('selfoff', off);
  });
  if ($('flip')) $('flip').addEventListener('click', async () => {
    facing = facing === 'user' ? 'environment' : 'user';
    try {
      const s = await navigator.mediaDevices.getUserMedia({ video: { facingMode: facing } }), track = s.getVideoTracks()[0];
      const sender = pc && pc.getSenders().find((x) => x.track && x.track.kind === 'video'); if (sender) await sender.replaceTrack(track);
      local.getVideoTracks().forEach((t) => { local.removeTrack(t); t.stop(); }); local.addTrack(track); $('self').srcObject = local;
    } catch (_) {}
  });
  addEventListener('pagehide', () => { if (!done) post(D.end); });   // closing the tab hangs up (keepalive lets the request finish)

  (async function boot() {
    if (!window.RTCPeerConnection || !navigator.mediaDevices) { post(D.end); return leave('This browser does not support calls. Please use Chrome, Safari or Firefox.', 4000); }
    if (!(await media())) return;
    if (!isCaller) {
      const r = await post(D.accept);
      if (!r.ok) return leave('This call has ended', 1500);
      status('Connecting…'); connect();
    }
    poll();
  })();
})();
