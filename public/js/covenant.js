/* Covenant of Provision: checkout, upsell and Day 1 gift. */
(function () {
  const HEAD = { 'Content-Type': 'application/json', 'X-Requested-With': 'RabbiDavid' };
  const post = async (path, body) => {
    const r = await fetch(path, { method: 'POST', credentials: 'same-origin', headers: HEAD, body: JSON.stringify(body) });
    let d = {}; try { d = await r.json(); } catch (e) {}
    if (!r.ok) throw new Error(d.error || 'Please try again in a minute.');
    return d;
  };
  const showMsg = (el, text) => { if (el) { el.textContent = text; el.hidden = false; } };

  // Buy buttons: data-book = covenant_7day | covenant_complete | covenant_upgrade
  document.querySelectorAll('.js-buy').forEach((btn) => {
    btn.addEventListener('click', async (e) => {
      e.preventDefault();
      if (btn.classList.contains('busy')) return;
      const label = btn.textContent;
      btn.textContent = 'Opening secure checkout…'; btn.classList.add('busy');
      const body = { book_id: btn.dataset.book };
      if (btn.dataset.prior) body.prior_session_id = btn.dataset.prior;
      try {
        const d = await post('/api/create-ebook-checkout', body);
        if (!d.checkout_url) throw new Error('Checkout is not available right now.');
        location.href = d.checkout_url;
      } catch (err) {
        btn.textContent = label; btn.classList.remove('busy');
        showMsg(document.querySelector('.checkout-msg'), err.message || 'Checkout is not available right now. Please try again in a minute.');
      }
    });
  });

  // Day 1 gift
  const form = document.getElementById('leadForm');
  if (form) form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const msg = form.querySelector('.form-msg');
    const email = form.email.value.trim();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { showMsg(msg, 'Please enter a valid email address.'); form.email.focus(); return; }
    const b = form.querySelector('button'); b.disabled = true;
    try {
      const d = await post('/api/lead', { email, name: form.name.value.trim() || 'Friend', source: 'covenant' });
      showMsg(msg, d.message || 'Thank you.'); form.reset();
      if (d.gift_url && !form.querySelector('.gift-open')) { const a = document.createElement('a'); a.className = 'btn btn-alt btn-block gift-open'; a.href = d.gift_url; a.target = '_blank'; a.rel = 'noopener'; a.textContent = 'Open Day 1 now (PDF)'; msg.after(a); }
    } catch (err) { showMsg(msg, err.message); }
    b.disabled = false;
  });

  // Thank-you page: confirm the order, then show the upgrade only to 7-day buyers
  const thanks = document.getElementById('thanks');
  if (thanks) {
    const q = new URLSearchParams(location.search);
    const cs = q.get('checkout_session_id') || '';
    const upsell = document.getElementById('upsell');
    const status = document.getElementById('orderStatus');
    const upBtn = upsell && upsell.querySelector('.js-buy');
    if (upBtn) upBtn.dataset.prior = cs;
    let tries = 0;
    const check = async () => {
      if (!cs) { status.textContent = 'We could not find your order reference. Your files are also sent to the email you used at checkout.'; return; }
      try {
        const r = await fetch('/api/download-verify?session_id=' + encodeURIComponent(cs), { credentials: 'same-origin' });
        const d = await r.json();
        if (d.verified) {
          status.textContent = d.delivery_status === 'sent'
            ? 'Your order is confirmed. We have also emailed your books to ' + d.email + '.'
            : 'Your order is confirmed. Your books will also be emailed to ' + d.email + '.';
          if (upsell && d.book_id === 'covenant_7day') upsell.hidden = false;
          const wrap = document.getElementById('dlLinkWrap'), link = document.getElementById('dlLink');
          if (wrap && link) { link.href = 'download/covenant.html?session_id=' + encodeURIComponent(cs); wrap.hidden = false; }
          return;
        }
      } catch (e) {}
      if (++tries < 20) setTimeout(check, 3000);
      else status.textContent = 'Your payment is being confirmed. Your books will arrive by email; if not within an hour, contact us.';
    };
    check();
  }

  // Sticky bar on mobile: after the hero, hidden over the offers
  const sticky = document.querySelector('.sticky-buy'), hero = document.querySelector('.hero'), buy = document.querySelector('#offers');
  if (sticky && hero && buy && 'IntersectionObserver' in window) {
    let heroGone = false, buyIn = false;
    const upd = () => sticky.classList.toggle('on', heroGone && !buyIn);
    new IntersectionObserver(([en]) => { heroGone = !en.isIntersecting; upd(); }).observe(hero);
    new IntersectionObserver(([en]) => { buyIn = en.isIntersecting; upd(); }).observe(buy);
  }
})();
