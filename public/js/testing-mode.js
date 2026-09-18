/* Free access mode notice for complete personal reading and plan */
(()=>{fetch('/api/config').then(r=>r.json()).then(config=>{
if(!config.free_testing)return;
document.body.classList.add('free-testing-mode');
const banner=document.createElement('a');banner.href='quiz.html';banner.textContent='✦ 100% FREE GIFT · Complete reading + 14-day plan PDF + personal audio · Begin here →';
banner.className='free-testing-notice';document.body.prepend(banner);
document.querySelectorAll('.reading-options .option-price').forEach(el=>{el.textContent='Free';});
document.querySelectorAll('.reading-options .upgrade-note').forEach(el=>{el.textContent='Included at no charge. No credit card required.';});
document.querySelectorAll('[data-testing-copy]').forEach(el=>{el.textContent=el.dataset.testingCopy;});
}).catch(()=>{});})();
