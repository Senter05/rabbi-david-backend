'use strict';
let quizState, busy=false, review=false;
const api=RabbiAPI.call, esc=RabbiAPI.escape, $=id=>document.getElementById(id);
function notify(message){let el=$('quizError');if(!el){el=document.createElement('p');el.id='quizError';el.setAttribute('role','alert');$('questionCard').append(el);}el.textContent=message;}
function syncContinueState(){
 const button=$('continueBtn');if(!button)return;
 let allowed=false;
 if(quizState?.started&&!['ready','generating'].includes(quizState.status)){
  const q=quizState.questions?.[quizState.step||0];
  if(review)allowed=Boolean($('readingConsent')?.checked);
  else if(q?.type==='choice'){
   const selected=$('questionCard').querySelector('input[name="answer"]:checked');
   allowed=Boolean(selected&&q.options.some(option=>option.value===selected.value));
  }else if(q?.type==='text')allowed=Boolean(q.optional||$('answerText')?.value.trim());
 }
 button.disabled=busy||!allowed;
}
function syncAnswerSelection(){
 const card=$('questionCard');if(!card)return;
 const selected=card.querySelector('input[name="answer"]:checked');
 card.querySelectorAll('label.q-option').forEach(label=>label.classList.toggle('selected',Boolean(selected&&label.contains(selected))));
 syncContinueState();
}
async function action(fn){if(busy)return;busy=true;syncContinueState();try{await fn();}catch(e){notify(e.message);}finally{busy=false;syncContinueState();}}
function display(){if(!quizState.started)return identity();if(quizState.status==='ready'){location.href='result.html';return;}if(quizState.status==='generating')return loading();$('computationScreen').classList.remove('active');$('questionCard').hidden=false;$('quizNav').hidden=false;$('progressWrap').hidden=false;const questions=quizState.questions,index=quizState.step||0;if(index>=questions.length)return summary();review=false;const q=questions[index];$('qCounter').textContent=`Question ${index+1} of ${questions.length}`;const pct=Math.round(index/questions.length*100);$('qPercent').textContent=pct+'%';$('progressFill').style.width=pct+'%';$('backBtn').style.display=index?'inline-block':'none';$('continueBtn').textContent=index===questions.length-1?'Review My Answers →':'Continue →';$('questionCard').innerHTML=`<div class="q-eyebrow">✦ A question for ${esc(quizState.answers.name)}</div><h2 class="q-title" id="questionTitle" tabindex="-1">${esc(q.title)}</h2><p class="q-helper">${esc(q.hint)}</p>`+(q.type==='choice'?`<fieldset class="q-options" aria-labelledby="questionTitle">${q.options.map(o=>`<label class="q-option ${quizState.answers[q.id]===o.value?'selected':''}"><input type="radio" name="answer" value="${esc(o.value)}" ${quizState.answers[q.id]===o.value?'checked':''}><span class="opt-text">${esc(o.label)}</span></label>`).join('')}</fieldset>`:`<label class="sr-only" for="answerText">${esc(q.title)}</label><textarea class="q-textarea" id="answerText" maxlength="1200" aria-describedby="optionalWritingHint" placeholder="Share your situation, challenges, what you want to transform, and any context you would like Rabbi David to understand...">${esc(quizState.answers[q.id]||'')}</textarea><p id="optionalWritingHint" class="email-disclaimer">✦ <strong>Important:</strong> The more detail and context you provide about your situation and life, the more personalized, profound, and accurate Rabbi David's reading will be. You may also leave this blank and continue.</p>`);syncAnswerSelection();$('questionTitle').focus({preventScroll:true});$('progressWrap').scrollIntoView({block:'start',behavior:'instant'});}
function identity(){
  $('quizNav').hidden=true;
  $('progressWrap').hidden=true;
  if(quizState.logged_in_user){
    $('questionCard').innerHTML=`<div class="email-card"><div class="email-rabbi-thumb"><img src="assets/rabbi-david-clean.webp" alt="Rabbi David"></div><span class="q-eyebrow">✦ Ancient Jewish Wisdom for Modern Life</span><h2 class="email-headline">Welcome Back, ${esc(quizState.logged_in_user.name||'Friend')}</h2><p class="email-sub">You are signed in as <strong>${esc(quizState.logged_in_user.email)}</strong>. Each account is limited to one personal reading.</p><a class="email-btn" style="display:inline-block;text-decoration:none;text-align:center;box-sizing:border-box;" href="result.html">View My Personal Reading →</a><p class="email-disclaimer" style="margin-top:14px;"><a href="account.html" style="color:#e2bf61;font-weight:600;">← Return to My Account</a></p></div>`;
    return;
  }
  $('questionCard').innerHTML=`<div class="email-card"><div class="email-rabbi-thumb"><img src="assets/rabbi-david-clean.webp" alt="Rabbi David"></div><span class="q-eyebrow">✦ Ancient Jewish Wisdom for Modern Life</span><h2 class="email-headline">A Reading That Begins With You</h2><p class="email-sub">Create an account so you can return to your reading. Then answer 11–12 short questions about what matters to you.</p><form id="enrollForm"><label for="firstName">Your first name <span>(required)</span></label><input class="email-input" id="firstName" name="name" autocomplete="given-name" maxlength="60" required placeholder="Your first name"><label for="startEmail">Your email <span>(required)</span></label><input class="email-input" type="email" id="startEmail" name="email" autocomplete="email" maxlength="254" required placeholder="you@example.com"><label for="startPassword">Create account password <span>(at least 8 characters)</span></label><input class="email-input" type="password" id="startPassword" name="password" autocomplete="new-password" minlength="8" maxlength="128" required placeholder="Min. 8 characters"><label class="password-visibility"><input type="checkbox" data-show-password="startPassword" aria-controls="startPassword"> Show password</label><label class="funnel-check"><input type="checkbox" id="marketing">Send me reflection reminders and occasional book recommendations. Optional.</label><p class="email-disclaimer" style="margin-top:4px;">Already have an account? <a href="account.html" style="color:#e2bf61;font-weight:600;">Sign in to your account here →</a></p><p class="email-disclaimer">Your reading is prepared with the personal guidance of Rabbi David. Share only what feels comfortable. <a href="privacy.html">Privacy</a></p><button class="email-btn" type="submit">Begin My Free Reading →</button><p class="email-disclaimer">Your complete personal reading, 14-day plan PDF and personal audio are 100% free. No payment or credit card required.<br>Sign in anytime to continue where you left off.</p></form></div>`;$('enrollForm').addEventListener('submit',e=>{e.preventDefault();action(async()=>{quizState=await api('enroll',{name:$('firstName').value.trim(),email:$('startEmail').value.trim(),password:$('startPassword').value,marketing:$('marketing').checked});display();});});
}
async function saveNext(){if(review){if(!$('readingConsent').checked)return notify('Please confirm that we may prepare your reading from your answers.');quizState=await api('generate',{consent:true});return display();}const q=quizState.questions[quizState.step||0],answers={...quizState.answers};const value=q.type==='choice'?document.querySelector('input[name=answer]:checked')?.value:$('answerText').value.trim();if(!value&&!q.optional)return notify('Please choose an answer to continue.');if(q.type==='text'&&value&&(value.match(/\p{L}[\p{L}'’-]*/gu)||[]).length<2)return notify('Please write a short sentence with at least two words, or leave this optional answer blank.');answers[q.id]=value||'';if(q.id==='goal'&&answers.goal!==quizState.answers.goal){delete answers.focus;delete answers.personal_detail;}if(q.id==='obstacle'&&value!=='cost')delete answers.no_cost;quizState=await api('save',{answers,step:(quizState.step||0)+1});display();$('progressWrap').scrollIntoView({block:'start',behavior:'instant'});}
function summary(){review=true;$('backBtn').style.display='inline-block';$('qCounter').textContent=quizState.status==='error'?'Reading Needs Attention':'Your answers are ready';$('qPercent').textContent=quizState.status==='error'?'Paused':'100%';$('progressFill').style.width=quizState.status==='error'?'0%':'100%';$('continueBtn').textContent='Prepare My Complete Reading →';const hasError=quizState.status==='error';const errHtml=hasError?`<div class="quiz-error-banner" role="alert" style="background:#241616;border:1px solid #e05252;border-radius:12px;padding:20px;margin-bottom:24px;text-align:left;"><h3 style="color:#ff6b6b;margin:0 0 8px;font-size:18px;">⚠️ Reading Preparation Could Not Complete</h3><p style="color:#f3dede;margin:0 0 10px;font-size:15px;line-height:1.5;">${esc(quizState.error||'We could not complete your reading at this time.')}</p><div style="display:flex;gap:12px;flex-wrap:wrap;"><button class="btn-continue" id="retryGenerateTop" style="padding:10px 20px;font-size:14px;">Retry Personal Reading →</button><button class="btn-back" id="guidedFallbackTop" style="padding:10px 20px;font-size:14px;">Open Curated Reading Immediately →</button></div></div>`:'';$('questionCard').innerHTML=errHtml+`<span class="q-eyebrow">✦ Your words shape your reading</span><h2 class="q-title">Does This Sound Like You?</h2><p class="q-helper">Review your answers before we prepare your reading. If something no longer feels right, select it to make a change.</p><div class="funnel-review">${quizState.questions.map((q,i)=>`<button class="q-option" data-edit="${i}"><span><strong>${esc(q.title)}</strong><br>${esc(q.options?.find(o=>o.value===quizState.answers[q.id])?.label||quizState.answers[q.id]||'Not added')}</span><span aria-hidden="true">✎</span></button>`).join('')}</div>${!quizState.followup?'<button class="btn-back" id="deeperQuestion">Add one optional personal question →</button><p class="email-disclaimer">Rabbi David will consider the answers you shared to offer one relevant reflection. Adding it is optional.</p>':''}<label class="funnel-check"><input type="checkbox" id="readingConsent" ${hasError||quizState.consent_at?'checked':''}>I agree to use my answers for a personal reading prepared with the guidance of Rabbi David.</label><p class="email-disclaimer">Inspired by Jewish wisdom, with attention to the life you described. Your reading offers reflection and practical ideas; it does not promise financial results.</p>`;$('retryGenerateTop')?.addEventListener('click',()=>action(async()=>{if(!$('readingConsent').checked)return notify('Please confirm use of your answers first.');quizState=await api('generate',{consent:true,refresh:true});display();}));
$('guidedFallbackTop')?.addEventListener('click',()=>action(async()=>{if(!$('readingConsent').checked)return notify('Please confirm use of your answers first.');quizState=await api('generate',{consent:true,guided:true});display();}));document.querySelectorAll('[data-edit]').forEach(b=>b.addEventListener('click',()=>action(async()=>{quizState=await api('save',{answers:quizState.answers,step:Number(b.dataset.edit)});display();})));$('deeperQuestion')?.addEventListener('click',()=>action(async()=>{$('deeperQuestion').textContent='Preparing your question…';quizState=await api('followup',{consent:true});display();}));syncContinueState();}
let readingPoll, readingProgressTimer, readingProgressStarted;
function loading(){
  $('questionCard').hidden=true;$('quizNav').hidden=true;$('progressWrap').hidden=true;
  const screen=$('computationScreen');screen.classList.add('active');
  if(!$('readingGenerationProgress')){
    const box=document.createElement('div');box.id='readingGenerationProgress';
    box.style.cssText='max-width:594px;margin:24px auto;text-align:center;color:#f3d063';
    box.innerHTML='<div style="font-size:32px;font-weight:700" id="readingGenerationPercent">1%</div><progress id="readingGenerationBar" max="100" value="1" aria-label="Reading preparation progress" style="width:100%;height:12px;accent-color:#d4af37"></progress><p id="readingGenerationStatus" role="status" style="font-size:16px;line-height:1.6">Preparing the first part of your reading.</p>';
    screen.querySelector('.comp-sub').after(box);
  }
  if(!readingProgressStarted)readingProgressStarted=quizState.generation_started_at?quizState.generation_started_at*1000:Date.now();
  clearTimeout(readingPoll);clearInterval(readingProgressTimer);
  const tick=()=>{
    const seconds=(Date.now()-readingProgressStarted)/1000;
    const completed=quizState.generation_progress?.completed||0,total=quizState.generation_progress?.total||5;
    const percent=Math.max(1,Math.min(95,Math.round(completed/total*100)));
    $('readingGenerationStatus').textContent=completed+' of '+total+' parts prepared. Your answers are saved.';
    $('readingGenerationPercent').textContent=percent+'%';$('readingGenerationBar').value=percent;
    if(seconds>=60)$('readingGenerationStatus').textContent+=' Preparation is taking a little longer; you can return here later.';
  };
  tick();readingProgressTimer=setInterval(tick,250);
  const poll=async()=>{
    try{
      const next=await api('state');quizState=next;
      if(next.status==='generating'){readingPoll=setTimeout(poll,1000);return;}
      clearInterval(readingProgressTimer);readingProgressStarted=null;
      if(next.status==='ready'){
        $('readingGenerationPercent').textContent='100%';$('readingGenerationBar').value=100;
        $('readingGenerationStatus').textContent='Your reading is ready. Opening it now…';
        readingPoll=setTimeout(()=>{location.href='result.html';},350);return;
      }
      display();if(next.status==='error')notify(next.error);
    }catch(error){
      clearInterval(readingProgressTimer);
      $('readingGenerationStatus').textContent='Connection interrupted. Your answers are saved. Reconnecting…';
      readingPoll=setTimeout(poll,3000);
    }
  };
  readingPoll=setTimeout(poll,1000);
}

// Delegation survives translated labels or replaced button contents.
document.addEventListener('change',event=>{if(event.target.matches?.('input[name="answer"], #readingConsent'))syncAnswerSelection();});
document.addEventListener('input',event=>{if(event.target.matches?.('#answerText'))syncContinueState();});
document.addEventListener('click',event=>{
 const button=event.target.closest?.('#continueBtn, #backBtn');
 if(!button||button.disabled||busy)return;
 event.preventDefault();
 if(button.id==='continueBtn')action(saveNext);
 else action(async()=>{quizState=await api('save',{answers:quizState.answers,step:Math.max(0,quizState.step-1)});display();});
});
window.addEventListener('pageshow',()=>syncContinueState());
document.addEventListener('DOMContentLoaded',()=>{$('continueBtn').removeAttribute('onclick');$('backBtn').removeAttribute('onclick');openQuiz();});

async function openQuiz(){
 try{
  quizState=await api('state');
  if(!quizState.started){
    try{
      const auth=await api('auth/status');
      if(auth?.user) quizState.logged_in_user=auth.user;
    }catch(_){}
  }
  display();
 }
 catch(error){$('quizNav').hidden=true;$('progressWrap').hidden=true;$('questionCard').innerHTML=`<h2 class="q-title">Continue Your Reading</h2><p role="alert">${esc(error.message)}</p><button class="email-btn" id="retryQuizLoad">Try Again</button><p><a href="contact.html">Contact support</a></p>`;$('retryQuizLoad').addEventListener('click',openQuiz);}
}
