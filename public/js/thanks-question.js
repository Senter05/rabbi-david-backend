document.addEventListener('DOMContentLoaded', function() {
  var form = document.getElementById('replyForm');
  if (!form) return;
  var qEl = document.getElementById('questionText');
  var cEl = document.getElementById('charCount');
  var btn = document.getElementById('submitBtn');
  var msg = document.getElementById('formMsg');
  var sInput = form.querySelector('input[name="session_id"]');
  var sessionId = sInput ? sInput.value : '';

  if (qEl && cEl) {
    qEl.addEventListener('input', function() {
      cEl.textContent = qEl.value.length + ' / 600 characters';
    });
  }

  form.addEventListener('submit', function(e) {
    e.preventDefault();
    var text = qEl.value.trim();
    if (!text) return;
    btn.disabled = true;
    btn.textContent = 'Submitting...';
    fetch('/api/submit-reply-question', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, question: text })
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (data.ok) {
        msg.style.display = 'block';
        msg.style.color = '#166534';
        msg.textContent = '✓ ' + (data.message || 'Your question has been received. Rabbi David will reply within seven days.');
        qEl.disabled = true;
        btn.style.display = 'none';
      } else {
        msg.style.display = 'block';
        msg.style.color = '#991b1b';
        msg.textContent = 'Error: ' + (data.error || 'Could not submit question.');
        btn.disabled = false;
        btn.textContent = 'Submit Your Question';
      }
    })
    .catch(function(err) {
      msg.style.display = 'block';
      msg.style.color = '#991b1b';
      msg.textContent = 'Network error: ' + err.message;
      btn.disabled = false;
      btn.textContent = 'Submit Your Question';
    });
  });
});
