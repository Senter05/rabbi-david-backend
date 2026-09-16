'use strict';

(() => {
  const api = RabbiAPI.call;
  const esc = RabbiAPI.escape;
  const $ = id => document.getElementById(id);
  let busy = false;

  function status(text, isError = false, isSuccess = false) {
    const el = $('accountStatus');
    if (!el) return;
    el.textContent = text;
    el.dataset.error = String(isError);
    el.dataset.success = String(isSuccess);
  }

  async function action(fn) {
    if (busy) return;
    busy = true;
    document.querySelectorAll('button').forEach(b => b.disabled = true);
    try {
      await fn();
    } catch (e) {
      status(e.message, true);
    } finally {
      busy = false;
      document.querySelectorAll('button').forEach(b => b.disabled = false);
    }
  }

  function initTabs() {
    const loginBtn = $('tabLoginBtn');
    const regBtn = $('tabRegisterBtn');
    const loginForm = $('loginForm');
    const regForm = $('registerForm');

    if (loginBtn && regBtn) {
      loginBtn.addEventListener('click', () => {
        loginBtn.classList.add('active');
        regBtn.classList.remove('active');
        loginForm.hidden = false;
        regForm.hidden = true;
      });

      regBtn.addEventListener('click', () => {
        regBtn.classList.add('active');
        loginBtn.classList.remove('active');
        loginForm.hidden = true;
        regForm.hidden = false;
      });
    }
  }

  function render(data) {
    const user = data.user;
    const signedIn = Boolean(user);

    $('accountForms').hidden = signedIn;
    $('accountDashboard').hidden = !signedIn;
    $('resetConfirmSection').hidden = true;

    if (!signedIn) {
      $('accountTitle').textContent = 'Welcome to Rabbi David';
      $('accountIntro').textContent = 'Sign in to continue your test, reopen your saved reflections, listen to your audio and download your personal PDF.';
      status('Sign in with your email and password, or create a new account.');
      return;
    }

    // Authenticated Dashboard
    $('accountTitle').textContent = 'Welcome Back, ' + (user.name || 'Friend');
    $('accountIntro').textContent = 'Your saved reflections, progress, personal audio and downloads, all in one place.';
    $('dashUserEmail').textContent = user.email;

    const readings = data.readings || [];
    const listEl = $('accountReadings');

    if (readings.length === 0) {
      listEl.innerHTML = `
        <div class="account-reading" style="text-align:center;padding:32px 20px;">
          <h3>No reflections yet</h3>
          <p style="color:#a49984;margin-bottom:20px;">You have not started a personal reflection under this account yet.</p>
          <a href="quiz.html" class="account-action">Begin Your Personal Test →</a>
        </div>
      `;
    } else {
      listEl.innerHTML = readings.map(r => {
        const isReady = r.status === 'ready';
        const isGenerating = r.status === 'generating';
        const isPersonal = r.tier === 'personal';
        const isReading = r.tier === 'reading';

        const tierLabel = isPersonal ? 'Personal Plan & Audio ($32)' : (isReading ? 'Complete Reading ($7)' : 'Free Opening Reflection');
        const statusLabel = isReady ? 'Ready to Open' : (isGenerating ? 'Preparing Reading…' : 'In Progress (Step ' + (r.step || 1) + ')');

        let actions = '';
        if (isReady) {
          actions += `<button type="button" data-open-reading="${esc(r.id)}">Open My Reading →</button>`;
          actions += `<a href="/api/pdf" class="account-action account-secondary" download>Download Reading (PDF)</a>`;
          if (isPersonal) {
            if (r.has_plan) {
              actions += `<a href="/api/plan-pdf" class="account-action account-secondary" download>Download 14-Day Plan (PDF)</a>`;
            }
            if (r.has_audio && r.audio_url) {
              actions += `<a href="${esc(r.audio_url)}" class="account-action account-secondary" download>Download Audio (MP3)</a>`;
            }
          }
        } else {
          actions += `<button type="button" data-open-reading="${esc(r.id)}">${isGenerating ? 'Check Preparation Progress' : 'Continue Test'} →</button>`;
        }

        let audioPlayer = '';
        if (isPersonal && r.has_audio && r.audio_url) {
          audioPlayer = `
            <div style="margin-top:16px;">
              <p style="font-size:13px;font-weight:600;color:#e2bf61;margin-bottom:6px;">✦ Spoken Audio Reflection</p>
              <audio controls preload="metadata" src="${esc(r.audio_url)}">Your browser does not support audio playback.</audio>
            </div>
          `;
        }

        return `
          <article class="account-reading">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px;">
              <h3>${esc(r.title || 'Your Personal Reading')}</h3>
              <span class="account-badge ${isReady ? 'badge-gold' : ''}">${statusLabel}</span>
            </div>
            <div class="account-reading-meta">
              <span>Tier: <strong>${tierLabel}</strong></span>
            </div>
            ${audioPlayer}
            <div class="account-reading-actions">
              ${actions}
            </div>
          </article>
        `;
      }).join('');

      // Wire up reading open buttons
      listEl.querySelectorAll('[data-open-reading]').forEach(b => {
        b.addEventListener('click', () => action(async () => {
          const res = await api('auth/open', { reading_id: b.dataset.openReading });
          location.href = res.ready ? 'result.html' : 'quiz.html';
        }));
      });
    }

    status('Your account is active.', false, true);
  }

  // Handle URL Reset Token
  const params = new URLSearchParams(location.search);
  const resetToken = params.get('reset_token');

  if (resetToken) {
    $('accountForms').hidden = true;
    $('accountDashboard').hidden = true;
    $('resetConfirmSection').hidden = false;
    status('Please choose your new password.');

    $('resetConfirmForm').addEventListener('submit', e => {
      e.preventDefault();
      const newPassword = $('newPassword').value;
      action(async () => {
        const res = await api('auth/reset-confirm', { token: resetToken, password: newPassword });
        status(res.message || 'Password updated. You can now sign in.', false, true);
        $('resetConfirmSection').hidden = true;
        $('accountForms').hidden = false;
        // Clean URL
        history.replaceState(null, '', location.pathname);
      });
    });
  } else {
    // Normal Flow
    initTabs();

    $('loginForm').addEventListener('submit', e => {
      e.preventDefault();
      action(async () => {
        const email = $('loginEmail').value.trim();
        const password = $('loginPassword').value;
        const res = await api('auth/login', { email, password });
        $('loginPassword').value = '';
        render(res);
      });
    });

    $('registerForm').addEventListener('submit', e => {
      e.preventDefault();
      action(async () => {
        const name = $('regName').value.trim();
        const email = $('regEmail').value.trim();
        const password = $('regPassword').value;
        const res = await api('auth/register', { name, email, password });
        $('regPassword').value = '';
        render(res);
      });
    });

    $('resetRequestForm').addEventListener('submit', e => {
      e.preventDefault();
      action(async () => {
        const email = $('resetEmail').value.trim();
        await api('auth/reset-request', { email });
        status('If this email belongs to an account, recovery instructions have been sent. Check your inbox and spam folder.', false, true);
      });
    });

    $('signOutBtn').addEventListener('click', () => action(async () => {
      await api('auth/logout', {});
      render({ user: null, readings: [] });
      status('You have been signed out.');
    }));

    // Initial load
    action(async () => {
      const data = await api('auth/status');
      render(data);
    });
  }
})();
