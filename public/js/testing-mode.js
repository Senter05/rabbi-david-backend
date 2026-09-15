/* Temporary local testing notice; normal pricing remains in the catalogue. */
(()=>{fetch('/api/config').then(r=>r.json()).then(config=>{
if(!config.free_testing)return;
document.body.classList.add('free-testing-mode');
const banner=document.createElement('a');banner.href='quiz.html';banner.textContent='FREE TESTING · Complete reading + your 14-day plan + personal audio · Start here →';
banner.className='free-testing-notice';document.body.prepend(banner);
document.querySelectorAll('.reading-options .option-price').forEach(el=>{el.textContent='Free to test';});
document.querySelectorAll('.reading-options .upgrade-note').forEach(el=>{el.textContent='Included during testing. No payment or second test needed.';});
document.querySelectorAll('[data-testing-copy]').forEach(el=>{el.textContent=el.dataset.testingCopy;});
}).catch(()=>{});})();
