/* Product facts only; final values remain readable without JavaScript. */
(()=>{
const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
const nodes=document.querySelectorAll('[data-product-count]');
const animate=node=>{
  const target=Number(node.dataset.productCount);
  const prefix=node.dataset.prefix||'';
  const suffix=node.dataset.suffix||'';
  if(!Number.isFinite(target)||reduced){
    if(Number.isFinite(target)) node.textContent=prefix+target.toLocaleString()+suffix;
    return;
  }
  if(target===0){
    node.textContent=prefix+'0'+suffix;
    return;
  }
  const start=performance.now();
  const tick=now=>{
    const fraction=Math.min(1,(now-start)/1200);
    const val=Math.round(target*(1-(1-fraction)**3));
    node.textContent=prefix+val.toLocaleString()+suffix;
    if(fraction<1)requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
};
if('IntersectionObserver' in window&&!reduced){const observer=new IntersectionObserver(entries=>{entries.forEach(entry=>{if(entry.isIntersecting){animate(entry.target);observer.unobserve(entry.target);}});},{threshold:.6});nodes.forEach(node=>observer.observe(node));}
const film=document.querySelector('#covenant-video');
if(film&&(film.getAttribute('src')||film.querySelector('source[src]'))){
const card=film.closest('.covenant-film'),toggle=card.querySelector('.covenant-video-toggle');
let inView=false,pausedByVisitor=reduced;
film.hidden=false;card.classList.add('has-video');film.controls=false;film.muted=true;film.defaultMuted=true;film.loop=true;film.playsInline=true;film.autoplay=!reduced;
if(toggle)toggle.hidden=false;
const label=()=>{if(toggle)toggle.textContent=film.paused?'Play video':'Pause video';};
const sync=()=>{if(inView&&!document.hidden&&!pausedByVisitor){film.play().catch(label);}else film.pause();label();};
film.addEventListener('play',label);film.addEventListener('pause',label);
toggle?.addEventListener('click',()=>{pausedByVisitor=!film.paused;sync();});
document.addEventListener('visibilitychange',sync);
if('IntersectionObserver' in window){new IntersectionObserver(entries=>{inView=entries[0].isIntersecting;sync();},{threshold:.15}).observe(film);}else{inView=true;sync();}
film.addEventListener('error',()=>{film.hidden=true;card.classList.remove('has-video');if(toggle)toggle.hidden=true;});
}
})();
