document.addEventListener('click', function(e) {
  var btn = e.target.closest('.btn-mark-answered');
  if (!btn) return;
  var id = btn.getAttribute('data-id');
  var key = btn.getAttribute('data-key');
  if (!id || !key) return;
  if (!confirm('Mark question as answered?')) return;
  btn.disabled = true;
  fetch('/api/admin/mark-answered', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id: id, key: key })
  })
  .then(function(r) { return r.json(); })
  .then(function(d) {
    if (d.ok) location.reload();
    else { alert('Error: ' + d.error); btn.disabled = false; }
  })
  .catch(function(err) { alert('Error: ' + err.message); btn.disabled = false; });
});
