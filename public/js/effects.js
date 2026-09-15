/* ============================================
   SCROLL ANIMATIONS, PARALLAX, 3D BOOK EFFECT
   ============================================ */

(function () {

  /* ---- Scroll Animations (IntersectionObserver) ---- */
  const reduceMotion=matchMedia('(prefers-reduced-motion: reduce)').matches;
  document.documentElement.classList.add('rd-effects');
  const animatedElements = document.querySelectorAll('.fade-up, .fade-in, .scale-in');

  if ('IntersectionObserver' in window && !reduceMotion) {
    const observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
          observer.unobserve(entry.target);
        }
      });
    }, {
      threshold: 0.15,
      rootMargin: '0px 0px -40px 0px'
    });

    animatedElements.forEach(function (el) {
      observer.observe(el);
    });
  } else {
    // Fallback: show all
    animatedElements.forEach(function (el) {
      el.classList.add('visible');
    });
  }

  /* ---- Counter-Up Animation for Social Proof ---- */
  const counterElements = document.querySelectorAll('[data-count]');

  if (counterElements.length) {
    const counterObserver = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          animateCounter(entry.target);
          counterObserver.unobserve(entry.target);
        }
      });
    }, { threshold: 0.5 });

    counterElements.forEach(function (el) {
      counterObserver.observe(el);
    });
  }

  function animateCounter(el) {
    const target = parseFloat(el.dataset.count);
    const suffix = el.dataset.suffix || '';
    const prefix = el.dataset.prefix || '';
    const isDecimal = target % 1 !== 0;
    const duration = 2000;
    const startTime = performance.now();

    function update(currentTime) {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      // Ease out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      const value = eased * target;

      if (isDecimal) {
        el.textContent = prefix + value.toFixed(1) + suffix;
      } else {
        el.textContent = prefix + Math.floor(value).toLocaleString() + suffix;
      }

      if (progress < 1) {
        requestAnimationFrame(update);
      }
    }

    requestAnimationFrame(update);
  }

  /* ---- Navbar Shadow on Scroll ---- */
  const navbar = document.querySelector('.site-header');
  if (navbar) {
    window.addEventListener('scroll', function () {
      if (window.scrollY > 50) {
        navbar.classList.add('scrolled');
      } else {
        navbar.classList.remove('scrolled');
      }
    });
  }

  /* ---- Hamburger Menu Toggle ---- */
  const hamburger = document.querySelector('.hamburger');
  const mobileMenu = document.querySelector('.mobile-menu');

  if (hamburger && mobileMenu) {
    hamburger.addEventListener('click', function () {
      hamburger.classList.toggle('active');
      mobileMenu.classList.toggle('open');
    });

    // Close on link click
    mobileMenu.querySelectorAll('a').forEach(function (link) {
      link.addEventListener('click', function () {
        hamburger.classList.remove('active');
        mobileMenu.classList.remove('open');
      });
    });
  }

  /* ---- 3D Book Tilt Effect ---- */
  const book3D = document.querySelector('.product-image-3d');
  if (book3D && window.innerWidth > 768 && !reduceMotion) {
    const wrapper = book3D.closest('.product-image-wrapper');

    if(wrapper)wrapper.addEventListener('mousemove', function (e) {
      const rect = wrapper.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const centerX = rect.width / 2;
      const centerY = rect.height / 2;

      const rotateY = ((x - centerX) / centerX) * 8;
      const rotateX = ((centerY - y) / centerY) * 8;

      book3D.style.transform = `rotateX(${rotateX}deg) rotateY(${rotateY}deg)`;
    });

    if(wrapper)wrapper.addEventListener('mouseleave', function () {
      book3D.style.transition = 'transform 0.5s ease';
      book3D.style.transform = 'rotateX(0deg) rotateY(0deg)';
      setTimeout(function () {
        book3D.style.transition = 'transform 0.1s ease';
      }, 500);
    });
  }

  /* ---- CTA Button Pulse ---- */
  const pulseButtons = document.querySelectorAll('.btn-pulse');
  // Pulse is handled by CSS animation, nothing extra needed here

  /* ---- Smooth Scroll for Anchor Links ---- */
  document.querySelectorAll('a[href^="#"]').forEach(function (anchor) {
    anchor.addEventListener('click', function (e) {
      const hash=this.getAttribute('href');
      if(!hash||hash==='#')return;
      const target = document.getElementById(decodeURIComponent(hash.slice(1)));
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: reduceMotion?'auto':'smooth', block: 'start' });
      }
    });
  });

})();
