const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const read=path=>fs.readFileSync(__dirname+'/'+path,'utf8');
const script=read('public/js/password-visibility.js');
function setup(){
 const fields=new Map(),listeners=new Map();
 const document={getElementById:id=>fields.get(id)||null,addEventListener(type,handler,capture){listeners.set(type,{handler,capture});}};
 vm.runInNewContext(script,{document});
 function field(id){const value={id,type:'password',value:'Synthetic test value'};fields.set(id,value);return value;}
 function toggle(id){return {checked:false,dataset:{showPassword:id},matches:selector=>selector==='input[data-show-password]'};}
 return {field,toggle,listeners,change(target){listeners.get('change').handler({target});},submit(toggles){listeners.get('submit').handler({target:{querySelectorAll(selector){assert.equal(selector,'input[data-show-password]');return toggles;}}});}};
}
test('Every account and quiz password starts hidden with one labelled, unchecked linked control',()=>{
 const pages=[['public/account.html',['loginPassword','regPassword','newPassword']],['public/js/quiz-engine.js',['startPassword']]];
 for(const [path,expected] of pages){
  const markup=read(path),inputs=[...markup.matchAll(/<input\b[^>]*>/g)].map(match=>match[0]);
  const passwords=inputs.filter(tag=>/type="password"/.test(tag));
  assert.equal(passwords.length,expected.length);
  for(const id of expected){
   assert.equal(passwords.filter(tag=>tag.includes(`id="${id}"`)).length,1);
   const toggles=inputs.filter(tag=>tag.includes(`data-show-password="${id}"`));
   assert.equal(toggles.length,1);assert.match(toggles[0],/type="checkbox"/);
   assert.ok(toggles[0].includes(`aria-controls="${id}"`));assert.doesNotMatch(toggles[0],/\bchecked\b/);
   assert.match(markup,new RegExp(`<label class="password-visibility"><input[^>]*data-show-password="${id}"[^>]*> Show password</label>`));
  }
 }
 for(const page of ['public/account.html','public/quiz.html'])assert.match(read(page),/<script src="js\/password-visibility.js"><\/script>/);
});
test('Showing and hiding changes only the target type, never its value',()=>{
 const h=setup(),field=h.field('first'),other=h.field('second'),toggle=h.toggle('first');
 const original=field.value;
 toggle.checked=true;h.change(toggle);
 assert.equal(field.type,'text');assert.equal(field.value,original);assert.equal(other.type,'password');
 toggle.checked=false;h.change(toggle);
 assert.equal(field.type,'password');assert.equal(field.value,original);
});
test('Delegated controls work when inserted after the script, including a re-rendered field',()=>{
 const h=setup(),toggle=h.toggle('later');
 const first=h.field('later');toggle.checked=true;h.change(toggle);assert.equal(first.type,'text');
 const replacement=h.field('later');h.change(toggle);assert.equal(replacement.type,'text');
 toggle.checked=false;h.change(toggle);assert.equal(replacement.type,'password');
});
test('Submitting hides every password in that form but preserves another form and all values',()=>{
 const h=setup(),a=h.field('a'),b=h.field('b'),outside=h.field('outside');
 const toggles=['a','b','outside'].map(id=>h.toggle(id));
 for(const toggle of toggles){toggle.checked=true;h.change(toggle);}
 const originals=[a.value,b.value,outside.value];h.submit(toggles.slice(0,2));
 assert.deepEqual([a.type,b.type,outside.type],['password','password','text']);
 assert.deepEqual(toggles.map(toggle=>toggle.checked),[false,false,true]);
 assert.deepEqual([a.value,b.value,outside.value],originals);
 assert.equal(h.listeners.get('submit').capture,true);
});
test('Unrelated checkbox changes have no effect on password fields',()=>{
 const h=setup(),field=h.field('a');
 h.change({checked:true,dataset:{},matches:()=>false});
 assert.equal(field.type,'password');
});
test('A removed target is ignored safely for changes and submission',()=>{
 const h=setup(),toggle=h.toggle('missing');toggle.checked=true;
 assert.doesNotThrow(()=>h.change(toggle));assert.doesNotThrow(()=>h.submit([toggle]));
 assert.equal(toggle.checked,false);
});
