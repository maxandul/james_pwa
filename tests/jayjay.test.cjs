const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function ui(fetch, canRefresh = true, pageOwner = 'alice') {
  const nodes = new Map();
  function element() {
    return {listeners:{},hidden:true,open:false,innerHTML:'',textContent:'',scrollHeight:100,
      addEventListener(name,fn) {this.listeners[name]=fn;},setAttribute(name,value){this[name]=value;},
      replaceChildren(){this.innerHTML='';this.cleared=true;},focus(){this.focused=true;},
      querySelector(){return null;},showModal(){this.open=true;},
      close(){this.open=false;this.listeners.close?.();}};
  }
  for (const name of ['#jayjay-launcher','#jayjay-dialog','#jayjay-content','#jayjay-status','#jayjay-reload','#jayjay-refresh','#jayjay-close','logout','main']) nodes.set(name,element());
  const document = {body:{dataset:{offlineOwner:'alice'}},querySelector:name=>nodes.get(name),querySelectorAll:()=>[nodes.get('logout')]};
  const storage = new Map(), listeners = {};
  const window = {location:{pathname:'/shopping',href:'https://james.test/shopping',reload(){}},
    JamesPage:{canRefresh:()=>canRefresh,refresh:async()=>{window.refreshCalls=(window.refreshCalls||0)+1; const accepted=pageOwner==='alice'; if(accepted)nodes.get('main').replaceChildren(); return accepted;}},addEventListener(name,fn){listeners[name]=fn;},dispatchEvent(){},confirm:()=>false};
  vm.runInNewContext(fs.readFileSync('james/static/jayjay.js','utf8'),{document,window,navigator:{onLine:true},fetch,
    sessionStorage:{setItem:(k,v)=>storage.set(k,v),getItem:k=>storage.get(k)},AbortController,Event,FormData:class {},
    DOMParser:class {parseFromString(){return {body:{dataset:{offlineOwner:pageOwner}},querySelector:()=>({childNodes:[]})};}}});
  return {nodes,listeners,storage,window,open:()=>nodes.get('#jayjay-launcher').listeners.click({preventDefault(){}}),
    submit:()=>nodes.get('#jayjay-content').listeners.submit({target:{matches:()=>true,querySelector:()=>({disabled:false})},preventDefault(){}})};
}
const response = (changed=false,owner='alice') => ({ok:true,redirected:false,headers:{get:()=> 'application/json'},json:async()=>({owner,html:'private transcript',changed})});
const tick = () => new Promise(resolve=>setImmediate(resolve));

test('closing and reopening preserves the loaded conversation without another request',async()=>{
  let calls=0;const p=ui(async()=>{calls++;return response();});p.open();await tick();
  p.nodes.get('#jayjay-close').listeners.click();p.open();await tick();
  assert.equal(calls,1);assert.equal(p.nodes.get('#jayjay-content').innerHTML,'private transcript');
  assert.ok([...p.storage.values()].every(v=>v==='0'||v==='1'));
});
test('a second send during a pending request is ignored and a failed send is never automatically retried',async()=>{
  let calls=0,reject;const p=ui(async()=>{calls++;if(calls===1)return response();return new Promise((_,r)=>reject=r);});
  p.open();await tick();p.submit();p.submit();assert.equal(calls,2);
  reject(new Error('network'));await tick();assert.equal(calls,2);
  assert.match(p.nodes.get('#jayjay-status').textContent,/nicht automatisch/);
  assert.equal(p.nodes.get('#jayjay-reload').hidden,false);
});
test('logout discards a late response and clears private content',async()=>{
  let resolve;const p=ui(()=>new Promise(r=>resolve=r));p.open();
  p.nodes.get('logout').listeners.submit();resolve(response());await tick();
  assert.equal(p.nodes.get('#jayjay-content').innerHTML,'');assert.equal(p.nodes.get('#jayjay-dialog').open,false);
});
test('an account change in another tab discards a pending response',async()=>{
  let resolve;const p=ui(()=>new Promise(r=>resolve=r));p.open();
  p.listeners.storage({key:'james-offline-v1',newValue:JSON.stringify({owner:'bob'})});resolve(response());await tick();
  assert.equal(p.nodes.get('#jayjay-content').innerHTML,'');
});
test('a response for a different person is never displayed',async()=>{
  const p=ui(async()=>response(false,'bob'));p.open();await tick();assert.equal(p.nodes.get('#jayjay-content').innerHTML,'');
});
test('saved actions do not overwrite an unfinished edit in the app',async()=>{
  let calls=0;const p=ui(async()=>{calls++;return response(calls>1);},false);p.open();await tick();p.submit();await tick();
  assert.equal(p.nodes.get('#jayjay-refresh').hidden,false);assert.notEqual(p.nodes.get('main').cleared,true);assert.equal(calls,2);
});
test('saved actions refresh the current list when there are no unfinished edits',async()=>{
  let calls=0;const p=ui(async()=>{calls++;return calls===3 ? {ok:true,redirected:false,text:async()=>'<main>updated</main>'} : response(calls===2);});
  p.open();await tick();p.submit();await tick();
  assert.equal(calls,2);assert.equal(p.window.refreshCalls,1);assert.equal(p.nodes.get('main').cleared,true);
});
test('a list response belonging to another signed-in person is discarded',async()=>{
  let calls=0;const p=ui(async()=>{calls++;return calls===3 ? {ok:true,redirected:false,text:async()=>'<main>private</main>'} : response(calls===2);},true,'bob');
  p.open();await tick();p.submit();await tick();
  assert.equal(calls,2);assert.equal(p.window.refreshCalls,1);assert.equal(p.nodes.get('#jayjay-refresh').hidden,false);assert.notEqual(p.nodes.get('main').cleared,true);
});
