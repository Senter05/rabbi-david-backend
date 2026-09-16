'use strict';
const api=RabbiAPI.call,esc=RabbiAPI.escape;let state,timer,busy=false,freePreviewRequested=false,toastTimer,toastVersion=0;
const root=document.getElementById('readingRoot');
function say(text){const element=document.getElementById('funnelStatus'),version=++toastVersion;clearTimeout(toastTimer);if(element)element.textContent=text;toastTimer=setTimeout(()=>{if(version===toastVersion&&element)element.textContent='';},4000);}
async function act(fn){if(busy)return;busy=true;try{await fn();}catch(e){say(e.message);}finally{busy=false;}}
const section=(title,text)=>`<section class="pastoral-letter reading-insight"><span class="letter-eyebrow">✦ ${esc(title)}</span><div class="letter-body"><p>${esc(text)}</p></div></section>`;
function paragraphs(text){return String(text??'').split(/\n\s*\n/).filter(Boolean).map(part=>`<p>${esc(part)}</p>`).join('');}
function sourceLink(source){if(!source?.title||!source?.url)return '';let url;try{url=new URL(source.url);if(url.protocol!=='https:')return '';}catch{return '';}return `<p class="reading-source">Source: <a href="${esc(url.href)}" target="_blank" rel="noopener noreferrer">${esc(source.title)} ↗</a></p>`;}
function chapterBody(chapter){
 const parts=String(chapter.text??'').split(/\n\s*\n/).map(part=>part.trim()).filter(Boolean);
 const source=sourceLink(chapter.source);
 if(chapter.presentation!=='guided-four-part-v1'||parts.length!==4)return paragraphs(chapter.text)+source;
 const narrative=parts.map((part,i)=>{
  if(i===3)return `<div class="editorial-reflection"><p>${esc(part)}</p></div>`;
  return `<p class="editorial-para">${esc(part)}</p>`;
 }).join('<div class="editorial-divider" aria-hidden="true"><span>✦</span></div>');
 return `<div class="editorial-flow">${narrative}${source}</div>`;
}
function readingChapters(reading,full){return `<div class="reading-chapters" id="readingChapters"><h2 class="chapters-heading">Explore Your Reading</h2><p class="funnel-note">Open one perspective at a time. Take what is useful at your own pace.</p>${reading.sections.map((chapter,i)=>`<details class="reading-chapter" id="readingChapter${i+1}" data-chapter="${i}"><summary><span class="chapter-number">${String(i+1).padStart(2,'0')}</span><span>${esc(chapter.title)}</span><span class="chapter-toggle" aria-hidden="true">+</span></summary><div class="letter-body">${chapterBody(chapter)}</div></details>`).join('')}</div>`;}

function preparing(){return `<section class="reading-preparing" role="status"><div class="reading-constellation" aria-hidden="true"><i></i><i></i><i></i><span>✡</span></div><span class="vessel-tag">ANCIENT JEWISH WISDOM FOR MODERN LIFE</span><h1 class="result-headline">${esc(state.answers.name)}, Your Personal Reading Is Being Prepared</h1><p>We are preparing your reading from the priorities you chose, the words you wrote and the time you have each day.</p><ol class="preparation-steps"><li class="done"><span>✓</span>Your answers are saved</li><li class="active"><span>✦</span>Your individual reading is being prepared</li><li><span>○</span>Ready to explore here when complete</li></ol><p class="funnel-note">${state.generation_progress?`${Number(state.generation_progress.completed)} of ${Number(state.generation_progress.total)} parts prepared. `:""}There is no need to repeat the test. This page updates when your reading is ready.</p></section>`;}
function choices(full,q){const locked=state.preview?.locked_sections||[];return `<section class="paywall-wrapper" id="continueReading"><div class="paywall-overlay"><span class="vessel-tag">YOUR NEXT STEP IS YOUR CHOICE</span><h2 class="paywall-title">${full?'Bring Your Reading Into Everyday Life':'Understand Your Reading. Choose Your Next Step.'}</h2><p class="paywall-desc">${full?'Your complete reading is already yours. If you want help putting it into practice, your personal path builds from these same answers.':'Keep your opening reflection. The complete reading explains more of what your answers suggest. The 14-day plan helps you put those ideas into practice at a pace that suits you.'}</p>${locked.length?`<div class="reading-ahead"><span>Inside the complete reading</span><ul>${locked.map(c=>`<li>✧ ${esc(c.title||c)}</li>`).join('')}</ul></div>`:''}<div class="funnel-offers">${!full?`<article class="reading-option"><span class="option-eyebrow">UNDERSTAND YOUR DIRECTION</span><h3>The Complete Reading</h3><div class="price-tag-big"><span class="price-num">$7</span><span class="price-caption">one-time</span></div><p>Go beyond your opening insight, with the full reflection shaped by your test answers.</p><ul class="offer-benefits"><li>Every section of your personal reading</li><li>Your priorities connected to Jewish wisdom</li><li>A PDF to save and return to</li></ul><button class="btn-unlock" data-tier="reading">Open My Complete Reading →</button><p class="upgrade-note">You can add the plan and audio later for $25.</p></article>`:''}<article class="reading-option personal-option"><span class="option-eyebrow">PUT YOUR INSIGHT INTO PRACTICE</span><h3>Your Own 14-Day Plan & Audio</h3><div class="price-tag-big"><span class="price-num">$${full?'25':'32'}</span><span class="price-caption">${full?'upgrade · $32 total':'one-time'}</span></div><p>A 14-day plan and an individual audio reading, built from <strong>your answers</strong>.</p><ul class="offer-benefits"><li>Your complete written reading and PDF</li><li>Daily actions for ${esc(q('goal').toLowerCase()||'your chosen priority')}</li><li>A pace that fits ${esc(q('time').toLowerCase()||'your available time')}</li><li>Your own audio, reflecting your goals and preferences</li></ul><button class="btn-unlock" data-tier="personal">${full?'Add My Plan & Audio':'Create My Personal Path'} →</button><p class="upgrade-note">${full?'Your $7 reading is credited. Nothing is purchased twice.':'Your saved answers carry forward. No second test.'}</p></article></div><div class="personal-explained"><details><summary>What makes the 14-day plan specific to me?</summary><p>Your goal, available time, preferred pace and practical limitations shape the activities. Each day gives you one action, a reflection question and an adaptation. It is a plan for practising your own priorities, not a generic schedule shared by every reader.</p></details><details><summary>What will my personal audio include?</summary><p>A spoken companion to your individual reading, with selected insights and the first steps in your plan. It uses the authorized Rabbi David voice, generated for your reading, so you can listen as well as read.</p></details></div><p class="email-disclaimer">Preview environment: checkout is not connected. These buttons open a demonstration without charging you. No subscription.</p></div></section>`;}
function answerText(question){const value=state.answers[question.id];return question.options?.find(option=>option.value===value)?.label||value||'Not added';}
function groundedReading(reading){const evidence=Array.isArray(reading.evidence)?reading.evidence:[],first=reading.first_step;return `${evidence.length?`<details class="reading-evidence"><summary>How your answers connect</summary>${evidence.map(item=>`<article><p>${esc(item.interpretation)}</p></article>`).join('')}</details>`:''}${first?.action?`<section class="pastoral-letter first-personal-step"><span class="letter-eyebrow">✦ ONE STEP YOU CAN TRY</span><h2>Something You Can Try Today</h2><p class="first-action">${esc(first.action)}</p>${first.why?`<p><strong>Why this fits your answers:</strong> ${esc(first.why)}</p>`:''}${first.reflection?`<p><strong>A question to reflect on:</strong> ${esc(first.reflection)}</p>`:''}</section>`:''}`;}
function provisionalNotice(){return `<section class="provisional-reading" role="status"><span class="vessel-tag">PROVISIONAL GUIDED REFLECTION</span><h2>Your Individual Reading Is Not Ready Yet</h2><p>The text below is a short guided reflection. Your individual reading has not been completed yet. Your answers are saved, so you can try again without repeating the test.</p><button class="btn-unlock" id="retryPersonalReading">Generate My Personal Reading →</button><p class="funnel-note">Uses the answers and consent you already provided. No payment and no need to take the test again.</p></section>`;}
function restartTest(){const dialog=document.getElementById('offerDialog');dialog.innerHTML=`<h2>Start a New Test?</h2><p>This opens a fresh session in this browser. Your current reading will no longer be the one shown here.</p>${state.status==='ready'?'<p>Download your current reading first if you want to keep a copy.</p><a class="funnel-secondary" href="/api/pdf">Download Current PDF ↓</a>':''}<p>Your saved record is not deleted. You can find it again through your account.</p><div class="restart-actions"><button class="funnel-secondary" id="cancelRestart">Keep My Current Test</button><button class="btn-unlock" id="confirmRestart">Start a New Test</button></div>`;dialog.showModal();document.getElementById('cancelRestart').onclick=()=>dialog.close();document.getElementById('confirmRestart').onclick=()=>act(async()=>{await api('new',{});location.href='quiz.html';});}
function wireReadingActions(){document.getElementById('startNewTest')?.addEventListener('click',restartTest);const retry=document.getElementById('retryPersonalReading');if(retry)retry.disabled=Boolean(state.answer_issues?.length);document.getElementById('retryPersonalReading')?.addEventListener('click',()=>act(async()=>{if(state.answer_issues?.length){say('Please edit the highlighted answers first.');return;}const button=document.getElementById('retryPersonalReading');button.disabled=true;try{state=await api('generate',{consent:true,refresh:true});render();}finally{if(document.getElementById('retryPersonalReading'))document.getElementById('retryPersonalReading').disabled=Boolean(state.answer_issues?.length);}}));}

let audioProgress=1,audioProgressInterval=null,voiceRequested=false;
let planProgress=1,planProgressInterval=null;

function startAudioProgressTimer(){
 if(audioProgressInterval||typeof setInterval!=='function')return;
 audioProgress=Math.max(audioProgress,1);
 audioProgressInterval=setInterval(()=>{
  if(audioProgress<90){
   audioProgress=Math.min(90,audioProgress+0.65);
  }else if(audioProgress<98){
   audioProgress=Math.min(98,audioProgress+0.15);
  }
  updateAudioProgressBar(Math.round(audioProgress));
 },1000);
}
function stopAudioProgressTimer(){
 if(audioProgressInterval&&typeof clearInterval==='function'){
  clearInterval(audioProgressInterval);
  audioProgressInterval=null;
 }
}
function updateAudioProgressBar(percent){
 const fill=document.getElementById('audioProgressFill');
 const text=document.getElementById('audioProgressPercent');
 const wrap=document.querySelector('.audio-progress-wrap');
 if(wrap)wrap.setAttribute('aria-valuenow',String(percent));
 if(fill)fill.style.width=percent+'%';
 if(text)text.textContent=percent+'%';
}
function audioProgressBar(percent){
 const pct=Math.max(1,Math.min(100,Math.round(percent||audioProgress||1)));
 return `<div class="audio-progress-wrap" role="progressbar" aria-valuenow="${pct}" aria-valuemin="1" aria-valuemax="100" aria-label="Preparing Your Personal Audio with Rabbi David"><div class="audio-progress-header"><div class="audio-progress-pulse" aria-hidden="true"><span>✦</span></div><div class="audio-progress-title-wrap"><h3 class="audio-progress-title">Preparing Your Personal Audio with Rabbi David…</h3><p class="audio-progress-sub">Crafting your personalized audio reading with authentic voice synthesis. This usually takes 2 to 3 minutes.</p></div><span class="audio-progress-percent" id="audioProgressPercent">${pct}%</span></div><div class="audio-progress-bar"><div class="audio-progress-fill" id="audioProgressFill" style="width:${pct}%"><span class="audio-progress-shimmer" aria-hidden="true"></span></div></div><div class="audio-progress-steps"><span class="${pct<=40?'step-active':''}">Synthesizing personal guidance</span><span class="${pct>40&&pct<=85?'step-active':''}">Aligning reflections &amp; plan</span><span class="${pct>85?'step-active':''}">Finalizing master audio</span></div></div>`;
}

function startPlanProgressTimer(){
 if(planProgressInterval||typeof setInterval!=='function')return;
 planProgress=Math.max(planProgress,1);
 planProgressInterval=setInterval(()=>{
  if(planProgress<90){
   planProgress=Math.min(90,planProgress+2.6);
  }else if(planProgress<98){
   planProgress=Math.min(98,planProgress+0.4);
  }
  updatePlanProgressBar(Math.round(planProgress));
 },1000);
}
function stopPlanProgressTimer(){
 if(planProgressInterval&&typeof clearInterval==='function'){
  clearInterval(planProgressInterval);
  planProgressInterval=null;
 }
}
function updatePlanProgressBar(percent){
 const fill=document.getElementById('planProgressFill');
 const text=document.getElementById('planProgressPercent');
 const wrap=document.querySelector('.plan-progress-wrap');
 if(wrap)wrap.setAttribute('aria-valuenow',String(percent));
 if(fill)fill.style.width=percent+'%';
 if(text)text.textContent=percent+'%';
}
function planProgressBar(percent){
 const pct=Math.max(1,Math.min(100,Math.round(percent||planProgress||1)));
 return `<div class="plan-progress-wrap" role="progressbar" aria-valuenow="${pct}" aria-valuemin="1" aria-valuemax="100" aria-label="Preparing Your Personal 14-Day Plan"><div class="plan-progress-header"><div class="plan-progress-pulse" aria-hidden="true"><span>✦</span></div><div class="plan-progress-title-wrap"><h3 class="plan-progress-title">Preparing Your Personal 14-Day Plan…</h3><p class="plan-progress-sub">Structuring your customized daily practices, reflections, and printable PDF. This usually takes under 1 minute.</p></div><span class="plan-progress-percent" id="planProgressPercent">${pct}%</span></div><div class="plan-progress-bar"><div class="plan-progress-fill" id="planProgressFill" style="width:${pct}%"><span class="plan-progress-shimmer" aria-hidden="true"></span></div></div><div class="plan-progress-steps"><span class="${pct<=40?'step-active':''}">Tailoring daily practices</span><span class="${pct>40&&pct<=85?'step-active':''}">Structuring 14-day sequence</span><span class="${pct>85?'step-active':''}">Generating PDF document</span></div></div><p role="status" class="funnel-note" style="margin-top:10px;">Your plan is being prepared. The download will appear here when ready.</p>`;
}

function ensureVoiceTriggered(){
 if(state.tier==='personal'&&state.status==='ready'&&state.plan&&state.voice_generation_enabled){
  if((!state.voice||state.voice.status==='not_requested')&&!voiceRequested){
   voiceRequested=true;
   startAudioProgressTimer();
   api('voice',{}).then(next=>{
    if(next?.voice?.status==='not_requested'){
     next={...next,voice:{...next?.voice,status:'queued'}};
    }
    state=next;
    renderPreserving();
   }).catch(e=>{
    say(e.message);
   });
  }
 }
}

function render(){
 clearTimeout(timer);
 if(!state.started){location.href='quiz.html';return;}
 if(state.answer_issues?.length){root.innerHTML=`<section class="provisional-reading"><h1 class="result-headline">A Fresh Start for a Clearer Reading</h1><p>We could not prepare a reliable reading from this test. Start a new test and use a short, clear sentence for any written answers. Optional writing can be left blank.</p></section><div class="restart-actions"><button class="btn-unlock" id="startNewTest">Start a New Test</button></div>`;wireReadingActions();return;}
 if(state.status!=='ready'){root.innerHTML=(state.status==='generating'?preparing():`<section class="provisional-reading"><h1 class="result-headline">${state.status==='error'?'Your Reading Could Not Be Completed Yet':'Your Path Is Waiting'}</h1><p>${esc(state.error||'Your answers are saved. Continue where you left off.')}</p>${state.status==='error'?'<button class="btn-unlock" id="retryPersonalReading">Try My Personal Reading Again →</button>':'<a class="btn-unlock" href="quiz.html">Return to My Test →</a>'}</section>`);wireReadingActions();if(state.status==='generating')poll();return;}
 ensureVoiceTriggered();
 if(state.free_testing&&state.source==='ai'&&!freePreviewRequested){freePreviewRequested=true;api('free-preview',{}).then(next=>{state=next;renderPreserving();}).catch(error=>say(error.message));}
 const r=state.reading,p=state.tier==='personal',full=state.free_testing||state.tier!=='free',individual=state.source==='ai',q=id=>state.questions.find(q=>q.id===id)?.options?.find(o=>o.value===state.answers[id])?.label||'';
 root.innerHTML=`${state.free_testing?'<div class="free-testing-banner"><strong>Free testing</strong><span>Complete reading, your 14-day plan and personal audio are included. No payment required.</span></div>':''}<div class="reading-topline"><span class="cert-badge">✦ ${!individual?'PROVISIONAL GUIDED REFLECTION':state.free_testing?'FREE COMPLETE READING':full?'YOUR COMPLETE READING':'YOUR FREE OPENING READING'}</span><a href="/api/pdf" class="reading-save">Save PDF ↓</a></div>${!individual?provisionalNotice():state.reading_version!==3?'<section class="reading-update"><h2>Bring Your Reading Up to Date</h2><p>Prepare an updated reading with source references and practical steps. Your existing answers will be used.</p><button class="funnel-secondary" id="retryPersonalReading">Prepare My Updated Reading →</button></section>':''}<div class="result-hero reading-personal-hero"><div class="reading-byline"><img src="assets/rabbi-david-clean.webp" alt="Rabbi David"><span>${individual?'Prepared from the answers shared by':'A guided starting point for'} <strong>${esc(state.answers.name)}</strong></span></div><h1 class="result-headline">${esc(r.title)}</h1><div class="reading-context"><span>✦ ${esc(q('goal'))}</span><span>☀ ${esc(q('time'))}</span></div></div>
 ${individual&&p?personal():''}<section class="reading-at-glance"><h2>Your Starting Point</h2><ul><li><strong>Your priority:</strong> ${esc(q('goal'))}</li><li><strong>Your focus:</strong> ${esc(q('focus')||q('need'))}</li><li><strong>Your reflection approach:</strong> ${esc(q('experience'))}</li></ul><p class="starting-insight"><strong>${individual?'An idea to consider:':'A provisional reflection:'}</strong> ${esc(r.insight)}</p></section><details class="reading-overview"><summary>Overview of your reading</summary>${paragraphs(r.summary)}</details>${individual?groundedReading(r):''}
 <nav class="reading-nav" aria-label="Your personal space"><a href="#readingChapters">Your reading</a>${p&&individual?'<a href="#personalAudio">Your audio</a><a href="#personalPlan">14-Day Plan</a>':individual&&!state.free_testing?'<a href="#continueReading">Continue your path</a>':''}<a href="#delivery">My account</a></nav>
 ${individual&&!full&&state.preview?.percent?`<div class="reading-access"><span>Your opening ${Number(state.preview.percent)}% is unlocked</span><span>The rest is available with your complete reading</span><div class="reading-access-track" aria-hidden="true"><i style="width:${Math.min(100,Math.max(0,Number(state.preview.percent)))}%"></i></div></div>`:''}${readingChapters(r,full)}
 ${individual&&!p&&!state.free_testing?choices(full,q):''}
 ${individual?recommendation():''}
 <section class="delivery-card compact-access" id="delivery"><p>Your reading is saved. Use your account to return on another device.</p><div class="media-links"><a href="account.html">My account →</a><a href="help.html">Help signing in →</a></div><details class="delivery-settings"><summary>Email preferences</summary><form id="contactForm"><label for="deliveryEmail">Your email</label><input class="q-input-text" type="email" id="deliveryEmail" value="${esc(state.email)}" required><label class="funnel-check"><input id="marketing" type="checkbox" ${state.marketing?'checked':''}>Send me reflection reminders and occasional book recommendations.</label><button class="funnel-secondary" type="submit">Save Preferences</button></form></details></section>
 <details class="reading-method"><summary>About your reading and how it is prepared</summary><p class="funnel-note">A personal reflection inspired by Jewish wisdom, prepared with the guidance of Rabbi David. Practices invite reflection and everyday action; financial outcomes are not guaranteed.</p></details><div class="restart-actions"><button type="button" class="funnel-secondary" id="startNewTest">Start a New Test</button></div><div class="funnel-links"><a href="privacy.html">Privacy</a><a href="index.html">Home</a></div>`;
 wire();
 const isPlanBusy=state.tier==='personal'&&(state.plan_status==='preparing'||!state.plan);
 const isVoiceBusy=state.tier==='personal'&&(['queued','submitting','processing','download_pending'].includes(state.voice?.status)||voiceRequested||(!state.voice||state.voice.status==='not_requested'));
 if(isPlanBusy)startPlanProgressTimer();
 else stopPlanProgressTimer();
 if(isVoiceBusy&&state.voice?.status!=='ready')startAudioProgressTimer();
 else if(state.voice?.status==='ready')stopAudioProgressTimer();
 if(state.plan_status==='preparing'||isVoiceBusy||isPlanBusy){
  poll();
 }
}
function audioStatus(media,label){
 const failed=['needs_review','error','failed'].includes(media.status);
 if(failed)return `<p role="status">${esc(media.error||`Your ${label} could not be completed yet. Your written reading is available.`)}</p><a class="funnel-secondary" href="contact.html">Get help with my audio →</a>`;
 return `<p role="status">Your ${label} is being prepared. You can leave and return; it will appear here when ready.</p>`;
}
function personal(){
 const voice=state.voice||{status:'not_requested'};
 const canRetryPlan=state.plan_source==='guided'&&!state.completed_days?.length&&state.plan_status!=='preparing';
 const isGenerating=['queued','submitting','processing','download_pending'].includes(voice.status)||(voiceRequested&&voice.status==='not_requested');

 let audioContent='';
 if(voice.available||voice.status==='ready'){
  audioContent=`<audio controls preload="metadata" src="/api/audio" aria-label="Your personal reading audio"></audio><div class="media-links"><a href="/api/audio" download="personal-reading.mp3">Download audio ↓</a><a href="/api/transcript">Read transcript</a></div>`;
 }else if(['needs_review','error','failed'].includes(voice.status)){
  audioContent=audioStatus(voice,'personal audio');
 }else if(isGenerating){
  audioContent=audioProgressBar();
 }else if(voice.status==='not_requested'){
  if(!state.plan){
   audioContent=`<button class="btn-unlock" id="generateVoice" disabled style="display:none;">Preparing Your Personal Audio…</button>${audioProgressBar()}`;
  }else if(!state.voice_generation_enabled){
   audioContent=`<p class="funnel-note">Audio preparation is currently unavailable. Your PDF is still accessible.</p>`;
  }else{
   audioContent=audioProgressBar();
  }
 }else{
  audioContent=audioStatus(voice,'personal audio');
 }

 let planContent='';
 if(state.plan){
  planContent=`<a class="btn-unlock" href="/api/plan-pdf" target="_blank" rel="noopener">Download 14-Day Plan →</a>`;
 }else if(['error','needs_review'].includes(state.plan_status)){
  planContent=`<p role="status">Your plan could not be completed yet. Your reading is saved.</p><a class="funnel-secondary" href="contact.html">Get help with my plan →</a>`;
 }else{
  planContent=planProgressBar();
 }

 return `<section class="personal-media" id="personalAudio"><span class="letter-eyebrow">LISTEN FIRST</span><h2>Your Personal Audio</h2><p>A spoken companion to your reading. Listen when you are ready.</p>${audioContent}</section><section class="plan-download" id="personalPlan"><h2>Your 14-Day Plan</h2><p>All fourteen days in one PDF. Save it to your phone or print it and follow at your own pace.</p>${planContent}${state.plan_source==='guided'?`<p class="funnel-note">${state.plan_status==='preparing'?'Your detailed plan is being prepared. You can download the guided edition meanwhile.':'Your PDF is a guided edition based on your chosen priority.'}</p>${canRetryPlan?'<button class="funnel-secondary" id="retryPlan">Prepare My Detailed Plan</button>':''}`:''}</section>`;
}
function recommendation(){const rec=state.recommendation;if(!rec?.book)return '';const b=rec.book;return `<section class="cross-sell-box"><div class="cross-sell-cover"><img src="${esc(b.cover)}" alt="${esc(b.title)}"></div><div><span class="vessel-tag">A COMPANION TO YOUR READING</span><h2>${esc(b.title)}</h2><p>${esc(rec.reason)}</p><p>${esc(b.author)} · ${b.pages} pages</p><a class="funnel-secondary" href="${esc(b.detailPage||'catalog.html')}">Explore This Book →</a><button class="funnel-secondary" id="alreadyOwn" data-book="${esc(b.id)}">I Already Own This Book</button></div></section>`;}
function wire(){wireReadingActions();document.getElementById('retryPlan')?.addEventListener('click',()=>act(async()=>{state=await api('plan-retry',{consent:true});render();}));document.querySelectorAll('[data-tier]').forEach(b=>b.addEventListener('click',()=>offer(b.dataset.tier)));document.getElementById('generateVoice')?.addEventListener('click',()=>act(async()=>{state=await api('voice',{});render();}));document.getElementById('alreadyOwn')?.addEventListener('click',e=>act(async()=>{state=await api('owned',{owned:[...state.owned,e.target.dataset.book]});render();}));document.getElementById('contactForm')?.addEventListener('submit',e=>{e.preventDefault();act(async()=>{state=await api('contact',{email:document.getElementById('deliveryEmail').value,marketing:document.getElementById('marketing').checked});say('Your preferences are saved.');});});}
function offer(tier){
 if(state.free_testing){
  const d=document.getElementById('offerDialog');d.innerHTML=`<button id="closeOffer" class="funnel-secondary">Close ✕</button><span class="vessel-tag">LOCAL PREVIEW · NO CHARGE</span><h2>${tier==='reading'?'Your Complete Reading':'Your Personal Path'}</h2><p>${tier==='reading'?'$7 — full written reflection and PDF.':state.tier==='reading'?'$25 upgrade — $32 total, including your existing reading.':'$32 total — reading, personal 14-day plan and audio.'}</p><p>Your answers are already saved. You will not repeat the test. Payments are not connected.</p><button id="confirmOffer" class="btn-unlock">Open This Preview →</button>`;d.showModal();document.getElementById('closeOffer').onclick=()=>d.close();document.getElementById('confirmOffer').onclick=()=>act(async()=>{state=await api('demo-tier',{tier});d.close();render();});
 }else{
  act(async()=>{
   say('Connecting to secure checkout…');
   const res=await api('create-checkout-session',{tier});
   if(res.checkout_url){
    window.location.href=res.checkout_url;
   }else{
    throw new Error('Checkout session could not be created. Please try again.');
   }
  });
 }
}
function updateSignature(value){return JSON.stringify([value.generation_progress,value.status,value.revision,value.tier,value.reading,value.plan_status,value.plan_source,value.plan,value.voice?.status,value.voice?.available,value.voice?.error,value.free_testing]);}
function renderPreserving(){
 const delivery=document.getElementById('delivery');
 const focus=document.activeElement,focusId=focus?.id;
 const selection=focus&&'selectionStart' in focus?[focus.selectionStart,focus.selectionEnd]:null;
 const opened=[...root.querySelectorAll('details[open]')].map(el=>el.querySelector('summary')?.textContent);
 const audios=[...root.querySelectorAll('audio')];
 const scroll=typeof window!=='undefined'&&window.scrollY?window.scrollY:0;
 render();
 const nextDelivery=document.getElementById('delivery');
 if(delivery&&nextDelivery)nextDelivery.replaceWith(delivery);
 root.querySelectorAll('details').forEach(el=>{if(opened.includes(el.querySelector('summary')?.textContent))el.open=true;});
 for(const audio of audios){const next=[...root.querySelectorAll('audio')].find(el=>el.getAttribute('src')===audio.getAttribute('src'));if(next)next.replaceWith(audio);}
 const nextFocus=focusId&&document.getElementById(focusId);
 if(nextFocus){nextFocus.focus({preventScroll:true});if(selection&&nextFocus.setSelectionRange){try{nextFocus.setSelectionRange(...selection);}catch{}}}
 if(typeof window!=='undefined'&&typeof window.scrollTo==='function')window.scrollTo({top:scroll,behavior:'instant'});
}
function poll(){clearTimeout(timer);timer=setTimeout(async()=>{try{const previous=updateSignature(state),next=await api('state');if(busy){poll();return;}const wasPlanGenerating=!state.plan||state.plan_status==='preparing';const isPlanNowReady=Boolean(next?.plan&&next?.plan_status!=='preparing');if(wasPlanGenerating&&isPlanNowReady){stopPlanProgressTimer();planProgress=100;updatePlanProgressBar(100);}const wasGenerating=['queued','submitting','processing','download_pending'].includes(state?.voice?.status)||voiceRequested||(!state?.voice||state?.voice?.status==='not_requested');const isNowReady=next?.voice?.status==='ready'||next?.voice?.available;if(wasGenerating&&isNowReady){stopAudioProgressTimer();audioProgress=100;updateAudioProgressBar(100);await new Promise(res=>setTimeout(res,400));state=next;renderPreserving();return;}state=next;if(updateSignature(next)!==previous)renderPreserving();else poll();}catch(e){say('Connection interrupted. Your answers are saved. Reconnecting…');poll();}},2500);}

async function openSavedReading(){
 try{
  if(typeof window!=='undefined'&&window.location?.search){
   const urlParams=new URLSearchParams(window.location.search);
   const checkoutSessionId=urlParams.get('checkout_session_id');
   if(checkoutSessionId){
    try{
     const verifyResp=await fetch(`/api/checkout-verify?checkout_session_id=${encodeURIComponent(checkoutSessionId)}`,{
      headers:{'X-Requested-With':'RabbiDavid'}
     });
     if(verifyResp.ok){
      const vData=await verifyResp.json();
      if(vData.unlocked){
       window.history.replaceState({},document.title,window.location.pathname);
      }
     }
    }catch(e){console.warn('Verification check:',e);}
   }
  }
  state=await api('state');
  render();
 }catch(error){root.innerHTML=`<section class="provisional-reading"><h1 class="result-headline">Your Saved Reading Is Waiting</h1><p role="alert">${esc(error.message)}</p><button class="btn-unlock" id="retryInitialLoad">Try Again</button><p><a href="contact.html">Contact support</a></p></section>`;document.getElementById('retryInitialLoad').addEventListener('click',openSavedReading);}
}
openSavedReading();
