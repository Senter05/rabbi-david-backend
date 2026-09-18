/* Ebook Checkout Handler — Rabbi David */
(function() {
    const DIRECT_STRIPE_LINKS = {
        'morning': 'https://buy.stripe.com/bJe28tdoG0HU4OS3hNawo0m',
        'rituals': 'https://buy.stripe.com/9B6aEZacubmy3KOf0vawo0n',
        'complete': 'https://buy.stripe.com/8x200lfwO76i2GK9Gbawo0o',
        'legacy': 'https://buy.stripe.com/eVq00lacu3U6chk19Fawo0p',
        'ceo': 'https://buy.stripe.com/eVqbJ3bgy62e1CG05Bawo0q',
        'protection': 'https://buy.stripe.com/aFa6oJ70i76i3KOg4zawo0r',
        'bundle_all': 'https://buy.stripe.com/4gM8wR0BUcqCeps4lRawo0s'
    };

    async function handleEbookClick(e) {
        const btn = e.target.closest('[data-buy-ebook]');
        if (!btn) return;
        e.preventDefault();
        
        const bookId = btn.getAttribute('data-buy-ebook');
        const hrefUrl = btn.getAttribute('href');
        const directUrl = (bookId && DIRECT_STRIPE_LINKS[bookId]) || (hrefUrl && hrefUrl.startsWith('https://buy.stripe.com/') ? hrefUrl : null);
        if (directUrl) {
            btn.innerHTML = '<span class="spinner-mini"></span> Opening Stripe...';
            btn.style.opacity = '0.75';
            btn.style.pointerEvents = 'none';
            window.location.href = directUrl;
            return;
        }

        const originalText = btn.innerHTML;
        btn.innerHTML = '<span class="spinner-mini"></span> Connecting to Stripe...';
        btn.style.opacity = '0.75';
        btn.style.pointerEvents = 'none';

        try {
            const res = await fetch('/api/create-ebook-checkout', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'RabbiDavid'
                },
                body: JSON.stringify({ book_id: bookId })
            });
            const data = await res.json();
            if (data.ok && data.checkout_url) {
                window.location.href = data.checkout_url;
            } else {
                // If backend is in preview or error, fallback to detail page or alert
                const targetUrl = btn.getAttribute('href');
                if (targetUrl && targetUrl !== '#' && !targetUrl.startsWith('javascript:')) {
                    window.location.href = targetUrl;
                } else {
                    alert(data.error || 'Payment gateway connection error. Please try again.');
                    btn.innerHTML = originalText;
                    btn.style.opacity = '1';
                    btn.style.pointerEvents = 'auto';
                }
            }
        } catch (err) {
            console.warn('[EBOOK CHECKOUT]', err);
            const targetUrl = btn.getAttribute('href');
            if (targetUrl && targetUrl !== '#' && !targetUrl.startsWith('javascript:')) {
                window.location.href = targetUrl;
            } else {
                alert('Unable to reach payment service. Please try again in a moment.');
                btn.innerHTML = originalText;
                btn.style.opacity = '1';
                btn.style.pointerEvents = 'auto';
            }
        }
    }

    document.addEventListener('DOMContentLoaded', () => {
        document.body.addEventListener('click', handleEbookClick);
    });
})();
