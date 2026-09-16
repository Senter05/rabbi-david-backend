const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync(__dirname+'/public/js/result-app.js','utf8').replace(/openSavedReading\(\);\s*$/,'');
const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function fixture(overrides={}){return {
 started:true,status:'ready',source:'ai',reading_version:3,tier:'personal',free_testing:false,
 answers:{name:'Reader',goal:'calm',need:'step',experience:'practical',time:'ten'},
 questions:[['goal','calm','Peace at home'],['need','step','One practical step'],['experience','practical','Practical guidance'],['time','ten','Ten minutes']].map(([id,value,label])=>({id,options:[{value,label}]})),
 reading:{title:'A steadier next step',summary:'A short overview.',insight:'Consider what is within your control.',evidence:[{interpretation:'Your preference for a practical step fits a short exercise.'}],first_step:{action:'Write one thing you can do today.',why:'You chose a practical approach.',reflection:'What would make this easier?'},sections:[{title:'Responsibility',text:'One meaningful paragraph.',source:{title:'Pirkei Avot 1:14',url:'https://www.sefaria.org/Pirkei_Avot.1.14'}}]},
 voice:{status:'ready',available:true},intro:{status:'not_requested'},voice_generation_enabled:true,
 plan:[{day:1,title:'This day must stay in the PDF',action:'Daily content must not render here'}],plan_status:'ready',plan_source:'ai',completed_days:[],email:'reader@example.test',owned:[],...overrides};}
function harness(input){
 const root={innerHTML:''};const elements=new Map();const calls=[];let scheduled=0;
 const document={getElementById(id){if(id==='readingRoot')return root;if(!root.innerHTML.includes(`id="${id}"`))return null;if(!elements.has(id))elements.set(id,{listeners:{},addEventListener(type,fn){this.listeners[type]=fn;}});return elements.get(id);},querySelectorAll(){return [];}};
 const context=vm.createContext({document,RabbiAPI:{escape,call:async(endpoint,body)=>{calls.push({endpoint,body});return input;}},URL,clearTimeout(){},setTimeout(){scheduled++;return scheduled;},location:{},console});
 vm.runInContext(source,context);context.input=input;vm.runInContext('state=input;render()',context);
 return {html:root.innerHTML,context,elements,calls,scheduled};
}
test('Personal package leads with playable audio and a single plan PDF; daily content stays off the page',()=>{
 const {html}=harness(fixture());
 assert.ok(html.indexOf('id="personalAudio"')<html.indexOf('id="personalPlan"'));
 assert.ok(html.indexOf('id="personalPlan"')<html.indexOf('Your Starting Point'));
 assert.equal((html.match(/href="\/api\/plan-pdf"/g)||[]).length,1);
 assert.match(html,/<audio controls[^>]+src="\/api\/audio"/);
 assert.doesNotMatch(html,/This day must stay|Daily content|data-day|plan-days|saveRecoveryKey|showInbox|autoplay/);
});
test('Free and reading tiers do not expose premium downloads; prices retain $7/$32/$25',()=>{
 const free=harness(fixture({tier:'free',plan:null,preview:{percent:40}})).html;
 const reading=harness(fixture({tier:'reading',plan:null})).html;
 for(const html of [free,reading])assert.doesNotMatch(html,/id="personalAudio"|href="\/api\/plan-pdf"/);
 assert.match(free,/class="price-num">\$7/);assert.match(free,/class="price-num">\$32/);
 assert.match(reading,/class="price-num">\$25/);assert.match(reading,/\$32 total/);
});
test('Pending plan cannot download or generate audio yet and continues polling',()=>{
 const result=harness(fixture({plan:null,plan_status:'preparing',voice:{status:'not_requested'}}));
 assert.doesNotMatch(result.html,/href="\/api\/plan-pdf"/);
 assert.match(result.html,/id="generateVoice" disabled/);
 assert.match(result.html,/Your plan is being prepared/);assert.ok(result.scheduled>0);
});
test('Audio failure offers support without pretending generation is pending or submitting another task',()=>{
 const result=harness(fixture({voice:{status:'needs_review'},intro:{status:'error'}}));
 assert.match(result.html,/could not be completed yet/);assert.match(result.html,/Get help with my audio/);
 assert.doesNotMatch(result.html,/id="generateVoice"|id="generateWelcome"|Your personal audio is being prepared/);
 assert.equal(result.calls.length,0);
});
test('Guided plans can be retried only before progress and outside active preparation',()=>{
 assert.match(harness(fixture({plan_source:'guided'})).html,/id="retryPlan"/);
 for(const override of [{completed_days:[1]},{plan_status:'preparing'}]){
  const {html}=harness(fixture({plan_source:'guided',...override}));
  assert.doesNotMatch(html,/id="retryPlan"/);assert.match(html,/href="\/api\/plan-pdf"/);
 }
});
test('Optional welcome stays separate with manual play and no automatic request',()=>{
 const result=harness(fixture({intro:{status:'ready',available:true}}));
 assert.match(result.html,/Optional short welcome · ready/);assert.match(result.html,/does not contain the full guidance/);
 assert.match(result.html,/<audio id="welcomeAudio" controls/);assert.doesNotMatch(result.html,/autoplay/);
 assert.equal(result.calls.length,0);
});
test('Details are closed by default, useful next action remains visible, and unsafe text is escaped',()=>{
 const data=fixture();data.reading.first_step.action='<script>bad()</script>';data.answers.name='<img onerror=bad()>';
 const {html}=harness(data);
 assert.doesNotMatch(html,/<details[^>]*\bopen\b|<script>|<img onerror/);
 assert.match(html,/class="first-action">&lt;script&gt;/);
 assert.match(html,/Your priority:<\/strong> Peace at home/);
 assert.doesNotMatch(html,/percentile|IQ score|smarter than/);
});
test('Not-yet-ready and failed readings never expose premium material',()=>{
 for(const status of ['generating','error']){
  const result=harness(fixture({status}));
  assert.doesNotMatch(result.html,/\/api\/audio|\/api\/plan-pdf/);
  if(status==='generating')assert.ok(result.scheduled>0);
  else assert.match(result.html,/id="retryPersonalReading"/);
 }
});
test('Missing media state uses a safe preparation action instead of crashing',()=>{
 assert.match(harness(fixture({voice:undefined,intro:undefined})).html,/id="generateVoice"/);
});

test('Structured teaching renders four labelled blocks with an escaped example and one source',()=>{
 const data=fixture();data.reading.sections[0].presentation='guided-four-part-v1';
 data.reading.sections[0].text='A teaching.\n\n<script>unsafe()</script>\n\nOne choice.\n\nWhat could you try?';
 const {html}=harness(data);
 for(const label of ['The teaching','An everyday example','A choice you can try','Pause and reflect'])assert.ok(html.includes(`<h3>${label}</h3>`));
 assert.match(html,/&lt;script&gt;unsafe\(\)&lt;\/script&gt;/);assert.doesNotMatch(html,/<script>/);
 assert.equal((html.match(/Source: <a/g)||[]).length,1);
 assert.doesNotMatch(html,/<details[^>]*\bopen\b/);
});

test('Legacy text and incomplete excerpts are not assigned invented teaching roles',()=>{
 for(const presentation of [undefined,'guided-four-part-v1']){
  const data=fixture();data.reading.sections[0].presentation=presentation;
  const {html}=harness(data);
  assert.match(html,/<p>One meaningful paragraph\.<\/p>/);
  assert.doesNotMatch(html,/<h3>The teaching<\/h3>/);
 }
});
test('Only an explicit prepare action submits a voice request',async()=>{
 const result=harness(fixture({voice:{status:'not_requested'}}));
 assert.equal(result.calls.length,0);
 result.elements.get('generateVoice').listeners.click();
 await new Promise(resolve=>setImmediate(resolve));
 assert.deepEqual(JSON.parse(JSON.stringify(result.calls)),[{endpoint:'voice',body:{}}]);
});
