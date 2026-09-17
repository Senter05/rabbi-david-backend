/* Ebook Checkout Handler — Rabbi David */
(function() {
    async function handleEbookClick(e) {
        const btn = e.target.closest('[data-buy-ebook]');
        if (!btn) return;
        e.preventDefault();
        
        const bookId = btn.getAttribute('data-buy-ebook');
        if (!bookId) return;

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
