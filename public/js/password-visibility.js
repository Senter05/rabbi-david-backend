(() => {
  document.addEventListener('change', event => {
    const toggle = event.target;
    if (!toggle.matches('input[data-show-password]')) return;
    const field = document.getElementById(toggle.dataset.showPassword);
    if (field) field.type = toggle.checked ? 'text' : 'password';
  });
  document.addEventListener('submit', event => {
    event.target.querySelectorAll('input[data-show-password]').forEach(toggle => {
      toggle.checked = false;
      const field = document.getElementById(toggle.dataset.showPassword);
      if (field) field.type = 'password';
    });
  }, true);
})();
