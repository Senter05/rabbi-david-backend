/* Preserve the original scroll ribbon without a manufactured deadline. */
(()=>{const r=document.querySelector('.floating-ribbon');if(!r)return;const update=()=>r.classList.toggle('visible',window.scrollY>220);window.addEventListener('scroll',update,{passive:true});update();})();
