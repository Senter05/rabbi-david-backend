/* Product navigation and library discovery. Book previews are full pages. */
(()=>{
 const routes={prayer:'morning-wealth-blessing.html',morning:'morning-wealth-blessing.html',ceo:'torah-ceo-code.html',generational:'generational-wealth.html',legacy:'generational-wealth.html',eliel:'the-torah-decoded.html',rituals:'the-seven-jewish-money-rituals.html',ancient:'the-ancient-wealth-code.html',complete:'the-complete-rabbis-wealth-system.html',hidden:'the-hidden-rules-of-jewish-wealth.html',protection:'the-jewish-wealth-protection-code.html',negotiation:'the-talmud-negotiation-bible.html',codigo:'el-codigo-judio-de-la-riqueza.html',calendario:'el-calendario-judio-de-la-riqueza.html',bundle:'catalog.html'};
 window.openBookModal=key=>location.assign(routes[key]||'catalog.html');
 document.querySelectorAll('[data-open-book]').forEach(link=>{link.href=routes[link.dataset.openBook]||'catalog.html';link.removeAttribute('onclick');link.removeAttribute('data-open-book');});
 document.querySelectorAll('[data-book-target]').forEach(card=>{const href=routes[card.dataset.bookTarget]||'catalog.html';card.addEventListener('click',event=>{if(!event.target.closest('a,button,input'))location.assign(href);});card.setAttribute('tabindex','0');card.addEventListener('keydown',event=>{if(event.target===card&&event.key==='Enter')location.assign(href);});});
 const search=document.getElementById('book-search'),language=document.getElementById('book-language');
 const cards=[...document.querySelectorAll('.library-card')];
 function filter(){let count=0;const needle=(search?.value||'').trim().toLocaleLowerCase();const lang=language?.value||'all';cards.forEach(card=>{card.hidden=!(card.dataset.title.includes(needle)&&(lang==='all'||lang===card.dataset.language));if(!card.hidden)count++;});document.querySelectorAll('.library-category').forEach(group=>{group.hidden=![...group.querySelectorAll('.library-card')].some(card=>!card.hidden);});const status=document.getElementById('book-count');if(status)status.textContent=count+' '+(count===1?'book':'books')+' to explore';const empty=document.getElementById('library-empty');if(empty)empty.hidden=count!==0;}
 search?.addEventListener('input',filter);language?.addEventListener('change',filter);
 // Only publish reviews with verified source, consent and an approved real portrait.
 const feedback=document.querySelector('[data-verified-reviews]');
 if(feedback)fetch('/api/catalog',{credentials:'same-origin'}).then(r=>{if(!r.ok)throw Error();return r.json();}).then(books=>{
  const book=books.find(b=>b.id===feedback.dataset.verifiedReviews);
  const reviews=(book?.reviews||[]).filter(r=>r.verified===true&&r.permissionToPublish===true&&r.name&&r.text&&r.photo&&r.source);
  if(!reviews.length)return;
  const container=document.createElement('div');container.className='verified-reader-grid container';
  reviews.slice(0,5).forEach(review=>{const card=document.createElement('article');card.className='verified-reader-card';const image=document.createElement('img');image.src=review.photo;image.alt=review.name;image.loading='lazy';const heading=document.createElement('h3');heading.textContent=review.name;const text=document.createElement('p');text.textContent=review.text;const badge=document.createElement('small');badge.textContent='Verified reader · Shared with permission';card.append(image,heading,text,badge);container.append(card);});feedback.prepend(container);
 }).catch(()=>{});
})();
