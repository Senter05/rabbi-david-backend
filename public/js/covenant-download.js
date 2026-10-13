/* Covenant private download page: verifies the paid order, then lists books, audios and bonus books. */
(function () {
  const $ = (id) => document.getElementById(id);
  const q = new URLSearchParams(location.search);
  const cs = q.get('session_id') || q.get('checkout_session_id') || '';
  const status = $('dlStatus');
  const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; };

  const bookRow = (b) => {
    const li = el('li', 'dl-item');
    li.appendChild(el('span', 'dl-name', b.title));
    const acts = el('span', 'dl-acts');
    const open = el('a', 'btn btn-alt', 'Read'); open.href = b.url; open.target = '_blank'; open.rel = 'noopener';
    const dl = el('a', 'btn', 'Download'); dl.href = b.download_url;
    acts.append(open, dl); li.appendChild(acts);
    return li;
  };

  const audioRow = (a) => {
    const li = el('li', 'audio-item');
    const h = el('h3', 'audio-title'); h.append(el('span', 'audio-n', String(a.n)), document.createTextNode(a.title));
    const player = el('audio'); player.controls = true; player.preload = 'none'; player.src = a.url;
    player.setAttribute('aria-label', 'Audio ' + a.n + ': ' + a.title);
    player.addEventListener('play', () => document.querySelectorAll('audio').forEach((o) => { if (o !== player) o.pause(); }));
    const dl = el('a', 'audio-dl', 'Download this audio'); dl.href = a.download_url;
    li.append(h, player, dl);
    return li;
  };

  const render = (d) => {
    $('dlTitle').textContent = d.title;
    status.textContent = 'Your payment is confirmed. Everything you bought is below' + (d.email ? ' (order email: ' + d.email + ').' : '.');
    const pdfs = $('dlPdfs'); pdfs.replaceChildren(...d.pdfs.map(bookRow)); $('dlBooks').hidden = false;
    if (d.audios && d.audios.length) {
      $('dlAudioList').replaceChildren(...d.audios.map(audioRow));
      $('dlZip').href = d.zip_url; $('dlAudios').hidden = false;
    }
    if (d.bonus && d.bonus.length) { $('dlBonusList').replaceChildren(...d.bonus.map(bookRow)); $('dlBonus').hidden = false; }
    if (d.book_id === 'covenant_7day') {
      const up = $('dlUpsell'); up.hidden = false;
      const b = up.querySelector('.js-buy'); if (b) b.dataset.prior = cs;
    }
    // Signed links expire: refresh them quietly before they do.
    const ms = Math.max(60, (d.expires_in || 3600) - 300) * 1000;
    const refresh = () => {
      const playing = [...document.querySelectorAll('audio')].some((a) => !a.paused);
      if (playing) setTimeout(refresh, 60000); else load(true);
    };
    setTimeout(refresh, ms);
  };

  let tries = 0;
  const load = async (quiet) => {
    if (!/^cs_(test|live)_[A-Za-z0-9]{10,}$/.test(cs)) {
      status.textContent = 'This link is incomplete. Please open the link in the email we sent you, or contact us and we will help.';
      return;
    }
    try {
      const r = await fetch('/api/covenant/access?session_id=' + encodeURIComponent(cs), { credentials: 'same-origin', headers: { 'X-Requested-With': 'RabbiDavid' } });
      const d = await r.json();
      if (d.verified) return render(d);
    } catch (e) {}
    if (quiet) return;
    if (++tries < 20) { status.textContent = 'Confirming your payment… this takes a few seconds.'; setTimeout(load, 3000); }
    else status.textContent = 'Your payment is still being confirmed. Your books will also arrive by email. If nothing arrives within an hour, please contact us.';
  };
  load();
})();
