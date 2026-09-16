const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const code=fs.readFileSync(__dirname+'/public/js/quiz-engine.js','utf8');
const settle=()=>new Promise(resolve=>setImmediate(resolve));
function harness({saved=false,fail=false}={}){
 const events={},windowEvents={},nodes=new Map(),calls=[];let radios=[],labels=[];
 const node=id=>({id,disabled:id==='continueBtn',hidden:false,style:{},textContent:'',classList:{add(){},remove(){},toggle(){}},focus(){},scrollIntoView(){},removeAttribute(){},addEventListener(){},closest(){return this},matches(){return false}});
 ['continueBtn','backBtn','questionCard','quizNav','progressWrap','computationScreen','qCounter','qPercent','progressFill','questionTitle','quizError','answerText','readingConsent'].forEach(id=>nodes.set(id,node(id)));
 nodes.get('answerText').value='';nodes.get('readingConsent').checked=false;
 const card=nodes.get('questionCard');let html='';
 Object.defineProperty(card,'innerHTML',{get(){return html},set(value){html=value;radios=[...value.matchAll(/<input type="radio" name="answer" value="([^"]+)"([^>]*)>/g)].map(m=>({value:m[1],checked:m[2].includes('checked'),matches(selector){return selector.includes('input[name="answer"]')},addEventListener(){}}));labels=radios.map(r=>({contains(x){return x===r},classList:{toggle(){}}}));}});
 card.querySelector=()=>radios.find(r=>r.checked)||null;card.querySelectorAll=()=>labels;
 const document={getElementById:id=>nodes.get(id),addEventListener:(type,fn)=>(events[type]??=[]).push(fn),querySelector:()=>radios.find(r=>r.checked),querySelectorAll:selector=>selector==='input[name=answer]'?radios:[],createElement:()=>node('created')};
 let state={started:true,status:'draft',step:0,answers:{name:'Test',...(saved?{goal:'family'}:{})},questions:[{id:'goal',type:'choice',title:'Priority',hint:'Choose one',options:[{value:'family',label:'Family'},{value:'work',label:'Work'}]},{id:'note',type:'text',optional:true,title:'Your situation',hint:'Optional'}]};
 const api=async(endpoint,body)=>{calls.push({endpoint,body});if(endpoint==='save'){if(fail)throw new Error('Connection interrupted');state={...state,answers:body.answers,step:body.step};}return structuredClone(state);};
 const context=vm.createContext({document,window:{addEventListener:(type,fn)=>windowEvents[type]=fn},RabbiAPI:{call:api,escape:value=>String(value??'')},location:{},setTimeout,clearTimeout,setInterval,clearInterval,console});
 vm.runInContext(code,context);
 const dispatch=(type,target)=>{for(const fn of events[type]||[])fn({target,preventDefault(){}})};
 return {nodes,calls,context,windowEvents,async open(){dispatch('DOMContentLoaded');await settle()},choose(value){radios.forEach(r=>r.checked=r.value===value);dispatch('change',radios.find(r=>r.checked));},click(){dispatch('click',{closest:()=>nodes.get('continueBtn')})},replaceButton(){nodes.set('continueBtn',node('continueBtn'));},dispatch};
}
test('Resumed unanswered quiz enables Continue when a radio is selected and saves the value',async()=>{
 const h=harness();await h.open();assert.equal(h.nodes.get('continueBtn').disabled,true);
 h.choose('family');assert.equal(h.nodes.get('continueBtn').disabled,false);
 h.click();await settle();assert.equal(h.calls.filter(c=>c.endpoint==='save').length,1);
 assert.equal(h.calls.find(c=>c.endpoint==='save').body.answers.goal,'family');
 assert.equal(h.nodes.get('continueBtn').disabled,false,'optional blank text can continue');
});
test('Reload with a saved choice is immediately usable',async()=>{
 const h=harness({saved:true});await h.open();assert.equal(h.nodes.get('continueBtn').disabled,false);
});
test('Delegated controls still work after translation replaces the button and wraps its label',async()=>{
 const h=harness();await h.open();h.replaceButton();h.choose('work');
 assert.equal(h.nodes.get('continueBtn').disabled,false);h.click();await settle();
 assert.equal(h.calls.find(c=>c.endpoint==='save').body.answers.goal,'work');
});
test('A failed save retains selection and permits retry',async()=>{
 const h=harness({fail:true});await h.open();h.choose('family');h.click();await settle();
 assert.equal(h.nodes.get('continueBtn').disabled,false);assert.equal(h.nodes.get('quizError').textContent,'Connection interrupted');
});
test('Double taps submit only one save while busy',async()=>{
 const h=harness();await h.open();h.choose('family');h.click();h.click();await settle();
 assert.equal(h.calls.filter(c=>c.endpoint==='save').length,1);
});
test('Browser back-forward cache restoration recomputes the button state',async()=>{
 const h=harness({saved:true});await h.open();h.nodes.get('continueBtn').disabled=true;
 h.windowEvents.pageshow();assert.equal(h.nodes.get('continueBtn').disabled,false);
});
test('Final review waits for consent and responds to its change event',async()=>{
 const h=harness();await h.open();h.choose('family');h.click();await settle();h.click();await settle();
 assert.equal(h.nodes.get('continueBtn').disabled,true);
 const consent=h.nodes.get('readingConsent');consent.checked=true;consent.matches=s=>s.includes('#readingConsent');h.dispatch('change',consent);
 assert.equal(h.nodes.get('continueBtn').disabled,false);
});
