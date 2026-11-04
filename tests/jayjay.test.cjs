const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {JSDOM} = require('jsdom');
const id = '12345678-1234-4234-8234-123456789abc';
const transcript = (saved=true) => `<div><button data-jayjay-history aria-expanded="false">Verlauf</button><nav id="jayjay-history" hidden>Ältere Chats</nav><a data-jayjay-nav href="/jayjay?new=1">Neuer Chat</a><div data-jayjay-thread>Antwort</div><form data-jayjay-form data-saved="${saved}"><input name="conversation_id" value="${id}"><input name="request_id" value="request"><textarea name="message" required></textarea><button type="submit">Senden</button></form></div>`;
const response = (changed=false,owner='alice',saved=true) => ({ok:true,status:200,redirected:false,headers:{get:()=> 'application/json'},json:async()=>({owner,html:transcript(saved),changed,saved,conversation_id:id,active_url:saved?'/jayjay?panel=1&conversation='+id:'/jayjay?panel=1&new=1'})});
const tick = () => new Promise(resolve=>setImmediate(resolve));
function ui(fetch,canRefresh=true, pageOwner='alice') {
 const dom=new JSDOM(`<body data-offline-owner="alice"><a id="jayjay-launcher"></a><dialog id="jayjay-dialog"><button id="jayjay-close"></button><button id="jayjay-expand"></button><div id="jayjay-content"></div><p id="jayjay-status"></p><button id="jayjay-reload" hidden></button><button id="jayjay-refresh" hidden></button></dialog><form action="/logout"></form><main></main></body>`,{url:'https://james.test/shopping',runScripts:'outside-only'});
 const w=dom.window,d=w.document,q=s=>d.querySelector(s);
 q('dialog').showModal=function(){this.setAttribute('open','');};
 q('dialog').close=function(){this.removeAttribute('open');this.dispatchEvent(new w.Event('close'));};
 w.fetch=fetch;w.confirm=()=>true;w.JamesPage={canRefresh:()=>canRefresh,refresh:async()=>{w.refreshCalls=(w.refreshCalls||0)+1;return pageOwner==='alice';}};
 w.eval(fs.readFileSync('james/static/jayjay.js','utf8'));
 return {w,d,q,open:()=>q('#jayjay-launcher').click(),submit:()=>q('[data-jayjay-form]').dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true})),close:()=>w.close()};
}

test('closing and reopening preserves the transcript and draft without another request',async()=>{
 let calls=0;const p=ui(async()=>{calls++;return response();});p.open();await tick();p.q('textarea').value='Entwurf';
 p.q('#jayjay-close').click();p.open();await tick();assert.equal(calls,1);assert.equal(p.q('textarea').value,'Entwurf');
 assert.ok(!Object.values(p.w.sessionStorage).includes('Entwurf'));p.close();
});
test('pending and ambiguous writes cannot be submitted twice; reload is read-only',async()=>{
 let calls=0,reject;const p=ui(async()=>{calls++;if(calls===2)return new Promise((_,r)=>reject=r);return response();});
 p.open();await tick();p.q('textarea').value='Kaffee';p.submit();p.submit();assert.equal(calls,2);assert.equal(p.q('textarea').readOnly,true);
 reject(new Error('network'));await tick();p.submit();assert.equal(calls,2);assert.match(p.q('#jayjay-status').textContent,/Verlauf neu laden/);
 p.q('#jayjay-reload').click();await tick();assert.equal(calls,3);assert.equal(p.q('textarea').value,'Kaffee');p.close();
});
test('logout and account change discard pending responses',async()=>{
 for(const method of ['logout','storage']){let resolve;const p=ui(()=>new Promise(r=>resolve=r));p.open();
 if(method==='logout')p.q('form[action="/logout"]').dispatchEvent(new p.w.Event('submit'));
 else p.w.dispatchEvent(new p.w.StorageEvent('storage',{key:'james-offline-v1',newValue:JSON.stringify({owner:'bob'})}));
 resolve(response());await tick();assert.equal(p.q('#jayjay-content').innerHTML,'');assert.equal(p.q('dialog').open,false);p.close();}
});
test('foreign response is never rendered',async()=>{const p=ui(async()=>response(false,'bob'));p.open();await tick();assert.equal(p.q('#jayjay-content').innerHTML,'');p.close();});
test('saved changes respect unfinished app edits and refresh only when possible',async()=>{
 for(const allowed of [false,true]){let calls=0;const p=ui(async()=>response(++calls>1),allowed);p.open();await tick();p.submit();await tick();assert.equal(p.q('#jayjay-refresh').hidden,allowed);assert.equal(p.w.refreshCalls||0,allowed?1:0);p.close();}
});
test('history and expansion work with accessible state; navigation preserves per-chat drafts',async()=>{
 let calls=0;const p=ui(async()=>response(false,'alice',++calls!==2));p.open();await tick();p.q('textarea').value='Entwurf im bestehenden Chat';
 p.q('[data-jayjay-history]').click();assert.equal(p.q('#jayjay-history').hidden,false);assert.equal(p.q('[data-jayjay-history]').getAttribute('aria-expanded'),'true');
 p.q('#jayjay-expand').click();assert.equal(p.q('dialog').classList.contains('jayjay--expanded'),true);
 p.q('[data-jayjay-nav]').click();await tick();assert.equal(p.q('textarea').value,'');
 const a=p.d.createElement('a');a.href='/jayjay?conversation='+id;a.dataset.jayjayNav='';p.q('#jayjay-content').append(a);a.click();await tick();assert.equal(p.q('textarea').value,'Entwurf im bestehenden Chat');p.close();
});
test('new drafts reload via a read-only new-chat URL, never an unpersisted conversation',async()=>{
 const urls=[];const p=ui(async url=>{urls.push(url);return response(false,'alice',false);});p.open();await tick();p.q('#jayjay-reload').click();await tick();assert.equal(urls[1],'/jayjay?panel=1&new=1');p.close();
});
