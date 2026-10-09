/* Private Reading Room Controller — Rabbi David */
(function() {
  'use strict';

  var q = new URLSearchParams(window.location.search);
  var token = (q.get('t') || '').trim();

  if (!token && document.body) {
    token = (document.body.getAttribute('data-token') || '').trim();
  }

  if (!token) {
    var pathMatch = window.location.pathname.match(/\/(?:for|go|gift)\/([A-Za-z0-9_\-]+)/);
    if (pathMatch) {
      token = pathMatch[1].trim();
    }
  }

  // If no token is provided, room is closed immediately
  if (!token) {
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

  function setFirstName(name) {
    var displayName = name && name.trim() ? name.trim() : 'friend';
    document.querySelectorAll('[data-first-name]').forEach(function(e) {
      e.textContent = displayName;
    });
  }

  var pad = function(n) { return String(n).padStart(2, '0'); };
  var timerEnd = 0;

  var bodyExpires = document.body ? document.body.getAttribute('data-expires') : null;
  if (bodyExpires) {
    var parsed = parseInt(bodyExpires, 10);
    if (parsed && !isNaN(parsed)) {
      timerEnd = parsed;
    }
  }

  function updateClockDisplay() {
    if (!timerEnd) return;
    var ms = timerEnd - Date.now();
    if (ms <= 0) {
      document.body.classList.add('is-closed');
      var elH = document.getElementById('c-h'),
          elM = document.getElementById('c-m'),
          elS = document.getElementById('c-s'),
          elBar = document.getElementById('bar-clock');
      if (elH) elH.textContent = '00';
      if (elM) elM.textContent = '00';
      if (elS) elS.textContent = '00';
      if (elBar) elBar.textContent = '00:00:00';
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

    setTimeout(updateClockDisplay, 1000);
  }

  if (timerEnd > 0) {
    updateClockDisplay();
  }

  // Load real reading room data if timer not pre-populated
  fetch('/api/reading-room-data?t=' + encodeURIComponent(token))
    .then(function(r) {
      if (r.status === 410) {
        document.body.classList.add('is-closed');
        throw new Error('Offer expired');
      }
      return r.json();
    })
    .then(function(data) {
      if (!data.valid) {
        document.body.classList.add('is-closed');
        return;
      }
      if (data.first_name) {
        setFirstName(data.first_name);
      }
      if (data.expires_at && !timerEnd) {
        timerEnd = data.expires_at;
        updateClockDisplay();
      }
    })
    .catch(function(err) {
      console.warn('Reading room data check:', err.message);
    });

  // Load real reply slots count from Supabase/SQLite
  function loadReplySlots() {
    fetch('/api/reply-slots')
      .then(function(r) { return r.json(); })
      .then(function(data) {
        var badge = document.getElementById('reply-slots-badge');
        if (!badge) return;
        if (data && data.remaining > 0 && data.active !== false) {
          badge.className = 'reply-badge';
          badge.innerHTML = '<span id="slots-count">' + data.remaining + '</span> of 50 personal replies left';
        } else {
          badge.className = 'reply-badge closed';
          badge.textContent = 'The 50 personal replies have been given';
        }
      })
      .catch(function(err) {
        console.warn('Reply slots check error:', err);
      });
  }
  loadReplySlots();

  // Buy buttons
  document.querySelectorAll('[data-offer-buy]').forEach(function(btn) {
    btn.addEventListener('click', function(e) {
      e.preventDefault();
      hideError();
      var bookId = btn.getAttribute('data-offer-buy');
      var originalText = btn.textContent;
      btn.textContent = 'Preparing checkout...';
      btn.classList.add('loading');

      fetch('/api/create-offer-checkout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ t: token, book_id: bookId })
      })
      .then(function(res) {
        return res.json().then(function(data) {
          if (!res.ok) {
            throw new Error(data.error || 'Failed to initiate checkout');
          }
          return data;
        });
      })
      .then(function(data) {
        if (data.checkout_url) {
          window.location.href = data.checkout_url;
        } else {
          throw new Error('No checkout URL received');
        }
      })
      .catch(function(err) {
        btn.textContent = originalText;
        btn.classList.remove('loading');
        showError(err.message || 'Payment initiation failed. Please try again.');
      });
    });
  });

})();
