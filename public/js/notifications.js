/* Live Social Proof Notifications & Active Viewers Counter — Rabbi David */
(function() {
  // Respect reduced motion
  if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    return;
  }

  // ==========================================
  // 1. DYNAMIC LIVE VIEWERS COUNTER
  // ==========================================
  function initLiveViewers() {
    const el = document.getElementById('liveViewersCount');
    if (!el) return;

    let viewers = parseInt(sessionStorage.getItem('rd_live_viewers'), 10);
    if (!viewers || isNaN(viewers) || viewers < 100 || viewers > 300) {
      viewers = Math.floor(138 + Math.random() * 42); // 138 - 180
      sessionStorage.setItem('rd_live_viewers', viewers);
    }
    el.textContent = viewers;

    setInterval(() => {
      // Natural organic fluctuation (-2 to +3)
      const delta = Math.floor(Math.random() * 6) - 2;
      viewers = Math.max(122, Math.min(218, viewers + delta));
      sessionStorage.setItem('rd_live_viewers', viewers);
      
      // Subtle pulse on update
      el.style.transition = 'opacity 0.2s ease';
      el.style.opacity = '0.6';
      setTimeout(() => {
        el.textContent = viewers;
        el.style.opacity = '1';
      }, 200);
    }, 8000 + Math.random() * 4000);
  }

  // ==========================================
  // 2. RECENT PURCHASE SOCIAL PROOF POPUP
  // ==========================================
  const RECENT_SALES = [
    {
      name: "David M.",
      location: "Miami, FL",
      product: "The 7 Hidden Money Rituals",
      cover: "/images/cover-rituals.webp",
      time: "2 mins ago"
    },
    {
      name: "Sarah L.",
      location: "New York, NY",
      product: "The Complete 6-Book Master Archive",
      cover: "/images/cover-kabbalah.webp",
      time: "4 mins ago"
    },
    {
      name: "Michael R.",
      location: "Austin, TX",
      product: "The Rabbi's Morning Wealth Blessing",
      cover: "/images/ebook-prayer-cover.webp",
      time: "1 min ago"
    },
    {
      name: "Jonathan B.",
      location: "London, UK",
      product: "The Generational Vault",
      cover: "/images/cover-generational.webp",
      time: "6 mins ago"
    },
    {
      name: "Daniel K.",
      location: "Toronto, Canada",
      product: "Ancient Jewish Rules for Commercial Dominance",
      cover: "/images/cover-commercial.webp",
      time: "3 mins ago"
    },
    {
      name: "Rachel S.",
      location: "Los Angeles, CA",
      product: "The Jewish Shield Against Financial Ruin",
      cover: "/images/cover-shield.webp",
      time: "Just now"
    },
    {
      name: "Aaron P.",
      location: "Chicago, IL",
      product: "The Master Kabbalah Wealth System",
      cover: "/images/cover-kabbalah.webp",
      time: "5 mins ago"
    },
    {
      name: "Gabriel T.",
      location: "Dallas, TX",
      product: "The Complete 6-Book Master Archive",
      cover: "/images/cover-kabbalah.webp",
      time: "2 mins ago"
    },
    {
      name: "Hannah W.",
      location: "Boston, MA",
      product: "The 7 Hidden Money Rituals",
      cover: "/images/cover-rituals.webp",
      time: "8 mins ago"
    },
    {
      name: "Benjamin C.",
      location: "Scottsdale, AZ",
      product: "The Generational Vault",
      cover: "/images/cover-generational.webp",
      time: "4 mins ago"
    }
  ];

  let currentIndex = 0;
  let isShowing = false;
  let pauseUntil = 0;
  let toastElement = null;

  function createToastElement() {
    let el = document.getElementById('purchaseNotification');
    if (el) return el;

    el = document.createElement('div');
    el.id = 'purchaseNotification';
    el.className = 'purchase-notification';
    el.setAttribute('aria-live', 'polite');
    el.innerHTML = `
      <div class="notification-image">
        <img id="notifCover" src="/images/cover-rituals.webp" alt="Book Cover" loading="lazy">
      </div>
      <div class="notification-text">
        <div class="notif-label">
          <span class="notif-dot">●</span> VERIFIED PURCHASE
        </div>
        <div class="notif-product" id="notifProduct">The 7 Hidden Money Rituals</div>
        <div class="notif-meta" id="notifMeta">David M. from Miami, FL · 2 mins ago</div>
      </div>
      <button id="notifClose" aria-label="Close notification" style="background:none;border:none;color:#718096;font-size:16px;line-height:1;cursor:pointer;padding:2px 4px;margin-left:auto;align-self:flex-start;transition:color 0.2s;">&times;</button>
    `;
    document.body.appendChild(el);

    const closeBtn = el.querySelector('#notifClose');
    if (closeBtn) {
      closeBtn.addEventListener('click', function(e) {
        e.stopPropagation();
        hideToast();
        pauseUntil = Date.now() + 30000; // Pause 30s if closed
      });
      closeBtn.addEventListener('mouseenter', function() {
        this.style.color = '#FFF';
      });
      closeBtn.addEventListener('mouseleave', function() {
        this.style.color = '#718096';
      });
    }

    // Optional click on toast to navigate to book catalog
    el.addEventListener('click', function(e) {
      if (e.target.id === 'notifClose') return;
      const catalog = document.getElementById('catalog');
      if (catalog) {
        catalog.scrollIntoView({ behavior: 'smooth' });
      }
    });

    return el;
  }

  function showToast() {
    if (Date.now() < pauseUntil) return;
    if (isShowing) return;

    if (!toastElement) {
      toastElement = createToastElement();
    }

    const item = RECENT_SALES[currentIndex];
    currentIndex = (currentIndex + 1) % RECENT_SALES.length;

    const coverImg = toastElement.querySelector('#notifCover');
    const productEl = toastElement.querySelector('#notifProduct');
    const metaEl = toastElement.querySelector('#notifMeta');

    if (coverImg) coverImg.src = item.cover;
    if (productEl) productEl.textContent = item.product;
    if (metaEl) metaEl.textContent = `${item.name} from ${item.location} · ${item.time}`;

    toastElement.classList.remove('hide');
    toastElement.classList.add('show');
    isShowing = true;

    // Auto-hide after 5.5 seconds
    setTimeout(() => {
      hideToast();
    }, 5500);
  }

  function hideToast() {
    if (!toastElement || !isShowing) return;
    toastElement.classList.remove('show');
    toastElement.classList.add('hide');
    isShowing = false;
  }

  function startToastLoop() {
    // First notification appears after 3.5s
    setTimeout(() => {
      showToast();
      // Subsequent notifications every 11 to 16 seconds
      setInterval(() => {
        if (!isShowing) {
          showToast();
        }
      }, 12000 + Math.random() * 4000);
    }, 3500);
  }

  // Initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      initLiveViewers();
      startToastLoop();
    });
  } else {
    initLiveViewers();
    startToastLoop();
  }
})();
