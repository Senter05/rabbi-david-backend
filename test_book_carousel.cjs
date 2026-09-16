const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');
const code=fs.readFileSync(__dirname+'/public/js/book-carousel.js','utf8');
const settle=()=>new Promise(r=>setImmediate(r));
function setup({reduced=false,fail=false}={}){
 const events=new Map(),timers=new Map();let number=0;
 function target(){return {addEventListener(t,fn){events.set(this.key+t,fn)},removeEventListener(t){events.delete(this.key+t)},key:String(number++)};}
 const root=target(),doc=target(),motion=target();doc.hidden=false;motion.matches=reduced;
 const slide={innerHTML:'',animate(frames){this.frames=frames}},count={},pause={setAttribute(){}};
 root.querySelector=s=>s.includes('slide')?slide:s.includes('count')?count:pause;root.querySelectorAll=()=>[];root.contains=()=>false;
 const books=['one','two','three'].map(id=>({id,title:id,cover:'/images/'+id+'.webp',detailPage:id+'.html',description:'About '+id}));
 const ctx=vm.createContext({RabbiAPI:{escape:s=>String(s??'').replace(/</g,'&lt;'),call:()=>fail?Promise.reject(Error()):Promise.resolve(books)},document:doc,matchMedia:()=>motion,setTimeout(fn,ms){const id=number++;timers.set(id,{fn,ms});return id},clearTimeout:id=>timers.delete(id),Date,console});
 vm.runInContext(code,ctx);let owned;
 ctx.RabbiBookCarousel.mount(root,{book:books[0],reason:'Chosen for you'},id=>owned=id);
 const emit=(name,event={})=>events.get(root.key+name)?.(event);
 return {slide,count,pause,timers,ctx,root,emit,get owned(){return owned},click(action){emit('click',{target:{closest:()=>({dataset:{library:action}})},preventDefault(){}})}};
}
test('Loads catalog, starts with recommendation, advances every three seconds and wraps',async()=>{
 const h=setup();await settle();assert.equal(h.count.textContent,'1 / 3');
 for(const expected of ['2 / 3','3 / 3','1 / 3']){const timer=[...h.timers.values()][0];assert.equal(timer.ms,3000);timer.fn();assert.equal(h.count.textContent,expected);}
 assert.equal(h.slide.frames[0].transform,'translateX(32px)');
});
test('Manual arrows stop autoplay and ownership tracks the visible book',async()=>{
 const h=setup();await settle();h.click('next');assert.equal(h.count.textContent,'2 / 3');assert.equal(h.timers.size,0);
 h.click('owned');assert.equal(h.owned,'two');h.click('previous');assert.equal(h.count.textContent,'1 / 3');
});
test('Swipes change direction; vertical scrolling does not change the book',async()=>{
 const h=setup();await settle();h.emit('pointerdown',{clientX:150,clientY:100});h.emit('pointerup',{clientX:30,clientY:110});assert.equal(h.count.textContent,'2 / 3');
 h.emit('pointerdown',{clientX:30,clientY:100});h.emit('pointerup',{clientX:150,clientY:110});assert.equal(h.count.textContent,'1 / 3');
 h.emit('pointerdown',{clientX:30,clientY:100});h.emit('pointerup',{clientX:50,clientY:240});assert.equal(h.count.textContent,'1 / 3');
});
test('Reduced motion does not start rotation; failed catalog retains the initial book',async()=>{
 const h=setup({reduced:true});await settle();assert.equal(h.timers.size,0);assert.equal(h.pause.textContent,'Play');
 const failed=setup({fail:true});await settle();assert.match(failed.slide.innerHTML,/Chosen for you/);
});
test('Remount cleans the old timer and keeps the selected book',async()=>{
 const h=setup();await settle();h.click('next');h.ctx.RabbiBookCarousel.mount(h.root,null,()=>{});await settle();assert.equal(h.count.textContent,'2 / 3');assert.equal(h.timers.size,0);
});
