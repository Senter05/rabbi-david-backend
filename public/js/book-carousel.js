'use strict';
globalThis.RabbiBookCarousel=(()=>{
 let catalogPromise,dispose=()=>{},selectedId,savedPause;
 const esc=RabbiAPI.escape;
 function catalog(){return catalogPromise??=(RabbiAPI.call('catalog').then(items=>{
  if(!Array.isArray(items))throw new Error('Catalog unavailable');
  return items.filter(book=>book.active!==false&&book.id&&book.title);
 }).catch(error=>{catalogPromise=null;throw error;}));}
 function localPath(value,fallback){return typeof value==='string'&&/^(?:\/?[a-zA-Z0-9_-]+\/)*[a-zA-Z0-9_.-]+$/.test(value)?value:fallback;}
 function mount(root,recommendation,onOwned){
  dispose();if(!root)return;
  const restoreId=selectedId;
  const motion=matchMedia('(prefers-reduced-motion: reduce)');
  let books=recommendation?.book?[recommendation.book]:[],index=0,timer,dead=false,paused=savedPause??motion.matches,hover=false,focused=false,start=null,suppressUntil=0;
  const slide=root.querySelector('.book-library-slide'),count=root.querySelector('[data-library-count]'),pause=root.querySelector('[data-library="pause"]');
  const listeners=[];
  const listen=(target,event,fn)=>{target.addEventListener(event,fn);listeners.push(()=>target.removeEventListener(event,fn));};
  function schedule(){clearTimeout(timer);if(root.isConnected!==false&&!dead&&!paused&&!hover&&!focused&&!document.hidden&&books.length>1)timer=setTimeout(()=>{move(1,false);},3000);}
  function draw(direction=0){
   const book=books[index];if(!book)return;
   selectedId=book.id;
   const reason=book.id===recommendation?.book?.id?recommendation.reason:book.description||book.subtitle||'';
   slide.innerHTML=`<a class="library-cover" href="${esc(localPath(book.detailPage,'catalog.html'))}" aria-label="View ${esc(book.title)}"><img draggable="false" src="${esc(localPath(book.cover,''))}" alt="${esc(book.title)}"></a><div class="library-book-copy"><h2>${esc(book.title)}</h2><p>${esc(reason)}</p><p class="library-book-meta">${esc(book.author||'')}${book.pages?' · '+esc(book.pages)+' pages':''}</p><a class="funnel-secondary" href="${esc(localPath(book.detailPage,'catalog.html'))}">View This Book →</a><button type="button" class="funnel-secondary" data-library="owned">I Already Own This Book</button></div>`;
   count.textContent=`${index+1} / ${books.length}`;
   root.querySelectorAll('[data-library="previous"],[data-library="next"]').forEach(button=>button.disabled=books.length<2);
   if(direction&&!motion.matches&&slide.animate)slide.animate([{opacity:0,transform:`translateX(${direction>0?'32':'-32'}px)`},{opacity:1,transform:'translateX(0)'}],{duration:320,easing:'ease-out'});
   schedule();
  }
  function setPaused(value){paused=value;savedPause=value;pause.textContent=paused?'Play':'Pause';pause.setAttribute('aria-label',paused?'Start automatic book rotation':'Pause automatic book rotation');schedule();}
  function move(direction,manual=true){if(!books.length)return;if(manual)setPaused(true);index=(index+direction+books.length)%books.length;draw(direction);}
  listen(root,'click',event=>{
   if(Date.now()<suppressUntil){event.preventDefault();return;}
   const control=event.target.closest('[data-library]');if(!control)return;
   if(control.dataset.library==='previous')move(-1);
   if(control.dataset.library==='next')move(1);
   if(control.dataset.library==='pause')setPaused(!paused);
   if(control.dataset.library==='owned'&&books[index]){setPaused(true);onOwned(books[index].id);}
  });
  listen(root,'pointerdown',event=>{if(event.isPrimary===false||event.button>0)return;start={x:event.clientX,y:event.clientY};clearTimeout(timer);});
  listen(root,'dragstart',event=>event.preventDefault());
  listen(root,'pointerup',event=>{if(!start)return;const dx=event.clientX-start.x,dy=event.clientY-start.y;start=null;if(Math.abs(dx)>45&&Math.abs(dx)>Math.abs(dy)*1.4){suppressUntil=Date.now()+400;move(dx<0?1:-1);}else schedule();});
  listen(root,'pointercancel',()=>{start=null;schedule();});
  listen(root,'mouseenter',()=>{hover=true;clearTimeout(timer);});
  listen(root,'mouseleave',()=>{hover=false;start=null;schedule();});
  listen(root,'focusin',()=>{focused=true;clearTimeout(timer);});
  listen(root,'focusout',event=>{if(!root.contains(event.relatedTarget)){focused=false;schedule();}});
  listen(document,'visibilitychange',schedule);
  listen(motion,'change',()=>{if(motion.matches)setPaused(true);});
  dispose=()=>{dead=true;clearTimeout(timer);listeners.forEach(remove=>remove());};
  setPaused(paused);draw();
  catalog().then(items=>{
   if(dead)return;
   const preferred=items.find(book=>book.id===recommendation?.book?.id);
   books=preferred?[preferred,...items.filter(book=>book.id!==preferred.id)]:items;
   index=Math.max(0,books.findIndex(book=>book.id===(restoreId||selectedId)));
   if(books.length)draw();else{slide.innerHTML='<p>The library is available through the link below.</p>';setPaused(true);}
  }).catch(()=>{if(!dead&&!books.length){slide.innerHTML='<p>Open the library to explore our books.</p>';setPaused(true);}});
 }
 return {mount};
})();
