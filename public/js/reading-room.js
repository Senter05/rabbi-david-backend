/* Private Reading Room Controller — Rabbi David */
(function() {
  'use strict';

  var q = new URLSearchParams(window.location.search);
  var token = (q.get('t') || '').trim();

  // If no token is provided, room is closed immediately
  if (!token) {
    document.body.classList.add('is-closed');
    return;
  }

  // Pre-parse client expiration from base64url token for immediate display
  var exp = 0;
  try {
    var b64 = token.replace(/-/g, '+').replace(/_/g, '/');
    while (b64.length % 4) b64 += '=';
    var raw = atob(b64);
    var parts = raw.split('|');
    if (parts.length >= 2) {
      var expSec = parseInt(parts[1], 10);
      if (!isNaN(expSec) && expSec > 0) {
        exp = expSec * 1000;
      }
    }
  } catch (e) {
    // Malformed token string will be handled by server verification
  }

  if (exp && Date.now() >= exp) {
    document.body.classList.add('is-closed');
    return;
  }

  function showError(msg) {
    var errBox = document.getElementById('offer-error');
    if (!errBox) {
      errBox = document.createElement('div');
      errBox.id = 'offer-error';
      errBox.style.cssText = 'max-width:620px; margin:20px auto 0; background:#fde8e8; border:1px solid #f8b4b4; color:#9b1c1c; border-radius:10px; padding:14px 18px; text-align:center; font-size:15px; font-weight:500;';
      var header = document.querySelector('header');
      if (header) header.appendChild(errBox);
      else document.body.insertBefore(errBox, document.body.firstChild);
    }
    errBox.textContent = msg;
    errBox.style.display = 'block';
    errBox.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function hideError() {
    var errBox = document.getElementById('offer-error');
    if (errBox) errBox.style.display = 'none';
  }

  function applyOwned(ownedList) {
    if (!ownedList || !ownedList.length) return;
    ownedList.forEach(function(id) {
      var targets = document.querySelectorAll(
        '.card[data-book="' + id + '"], .feature[data-book="' + id + '"], .trilogy[data-book="' + id + '"]'
      );
      targets.forEach(function(c) {
        c.classList.add('is-owned');
        var b = c.querySelector('[data-offer-buy]');
        if (b) {
          b.outerHTML = '<div class="owned">✓ Already in your library</div>';
        }
      });
    });
  }

  function setFirstName(name) {
    var displayName = name && name.trim() ? name.trim() : 'friend';
    document.querySelectorAll('[data-first-name]').forEach(function(e) {
      e.textContent = displayName;
    });
  }

  function updateClockDisplay() {
    if (!exp) return;
    try {
      var closeAtEl = document.getElementById('close-at');
      if (closeAtEl) {
        closeAtEl.textContent = new Date(exp).toLocaleString([], {
          weekday: 'long',
          hour: 'numeric',
          minute: '2-digit',
          timeZoneName: 'short'
        });
      }
    } catch (e) {}
  }

  var pad = function(n) { return String(n).padStart(2, '0'); };
  var timerId = null;

  function tick() {
    if (!exp) return;
    var ms = exp - Date.now();
    if (ms <= 0) {
      document.body.classList.add('is-closed');
      return;
    }
    var h = Math.floor(ms / 3600e3),
        m = Math.floor((ms % 3600e3) / 60e3),
        s = Math.floor((ms % 60e3) / 1e3);

    var elH = document.getElementById('c-h'),
        elM = document.getElementById('c-m'),
        elS = document.getElementById('c-s'),
        elBar = document.getElementById('bar-clock');

    if (elH) elH.textContent = pad(h);
    if (elM) elM.textContent = pad(m);
    if (elS) elS.textContent = pad(s);
    if (elBar) elBar.textContent = pad(h) + ':' + pad(m) + ':' + pad(s);

    timerId = setTimeout(tick, 1000);
  }

  // Fetch with retry for Render cold starts (handles 502, 503, 504, network errors)
  function fetchWithRetry(url, options, retriesLeft, delayMs) {
    return fetch(url, options).then(function(res) {
      if (res.status === 410) {
        // Expired or invalid -> hard stop, no retry
        document.body.classList.add('is-closed');
        throw new Error('CLOSED_410');
      }
      if (!res.ok && (res.status === 502 || res.status === 503 || res.status === 504) && retriesLeft > 0) {
        return new Promise(function(resolve) {
          setTimeout(resolve, delayMs);
        }).then(function() {
          return fetchWithRetry(url, options, retriesLeft - 1, delayMs * 1.5);
        });
      }
      return res;
    }).catch(function(err) {
      if (err.message === 'CLOSED_410') throw err;
      if (retriesLeft > 0) {
        return new Promise(function(resolve) {
          setTimeout(resolve, delayMs);
        }).then(function() {
          return fetchWithRetry(url, options, retriesLeft - 1, delayMs * 1.5);
        });
      }
      throw err;
    });
  }

  // Initial countdown kick-off from decoded client expiration
  if (exp) {
    updateClockDisplay();
    tick();
  }

  // Fetch validated data from server
  fetchWithRetry(
    '/api/reading-room-data?t=' + encodeURIComponent(token),
    { headers: { 'X-Requested-With': 'RabbiDavid' } },
    3,
    1500
  ).then(function(res) {
    return res.json();
  }).then(function(data) {
    if (!data || !data.ok || !data.valid) {
      document.body.classList.add('is-closed');
      return;
    }
    if (data.expires_at) {
      exp = data.expires_at;
      updateClockDisplay();
      if (!timerId) tick();
    }
    setFirstName(data.first_name);
    applyOwned(data.owned);
  }).catch(function(err) {
    if (err.message === 'CLOSED_410') {
      document.body.classList.add('is-closed');
    } else {
      console.warn('[READING ROOM] Background sync error:', err);
    }
  });

  // Handle Buy Button Clicks
  document.addEventListener('click', function(e) {
    var btn = e.target.closest('[data-offer-buy]');
    if (!btn) return;
    e.preventDefault();

    hideError();
    var bookId = btn.dataset.offerBuy;
    var originalHtml = btn.innerHTML;

    btn.classList.add('loading');
    btn.style.pointerEvents = 'none';
    btn.textContent = 'Opening secure checkout…';

    fetch('/api/create-offer-checkout', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'RabbiDavid'
      },
      body: JSON.stringify({ book_id: bookId, t: token })
    }).then(function(res) {
      if (res.status === 410) {
        document.body.classList.add('is-closed');
        window.scrollTo({ top: 0, behavior: 'smooth' });
        throw new Error('CLOSED_410');
      }
      if (res.status === 409) {
        return res.json().then(function(d) {
          throw new Error(d.error || 'This book is already in your library.');
        });
      }
      if (!res.ok) {
        return res.json().then(function(d) {
          throw new Error(d.error || 'Payment gateway connection error. Please try again.');
        }).catch(function(innerErr) {
          throw new Error(innerErr.message || 'Payment gateway connection error (HTTP ' + res.status + ').');
        });
      }
      return res.json();
    }).then(function(data) {
      if (data && data.ok && data.checkout_url) {
        window.location.href = data.checkout_url;
      } else {
        throw new Error((data && data.error) || 'Unable to open checkout session.');
      }
    }).catch(function(err) {
      btn.classList.remove('loading');
      btn.style.pointerEvents = '';
      btn.innerHTML = originalHtml;
      if (err.message !== 'CLOSED_410') {
        showError(err.message || 'An error occurred while opening checkout. Please try again.');
      }
    });
  });
})();
