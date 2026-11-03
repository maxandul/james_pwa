const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {JSDOM} = require('jsdom');
const script = fs.readFileSync('james/static/app.js','utf8');
const tick = () => new Promise(resolve=>setImmediate(resolve));
const response = (html, extra={}) => ({ok:true,redirected:false,url:'https://james.test/?view=all&layout=compact&undo=4',text:async()=>html,...extra});
function html({owner='alice',version=1,ids=[1,2,3],undo=false}={}) {
  return `<body data-offline-owner="${owner}"><main data-list-page="main.home"><div id="offline-banner" hidden></div><div data-preserve="article-toolbar"><input id="search" name="q"></div>${undo?'<div class="notice">Gespeichert.</div><div class="undo"><form method="post" action="/activity/4/undo"><input name="version" value="2"><button type="submit">Rückgängig</button></form></div>':''}${ids.map(id=>`<article data-item-id="${id}"><h3>Artikel ${id} v${version}</h3><form method="post" action="/items/${id}/action"><input name="csrf_token" value="csrf"><input name="request_id" value="request-${id}"><input name="version" value="${version}"><input name="action" value="replenish"><button type="submit">Nachkaufen</button></form><details id="details-${id}"><summary>Details</summary><form method="post" action="/items/${id}/action"><input name="action" value="extra"><input name="version" value="${version}"><input name="quantity" value="1"><button type="submit">Ergänzen</button></form></details></article>`).join('')}</main><div id="action-feedback" hidden></div></body>`;
}
function ui(fetch) {
  const dom = new JSDOM(html(),{url:'https://james.test/',runScripts:'outside-only'});
  const w=dom.window, d=w.document;
  w.fetch=fetch; w.CSS={escape:s=>String(s)};
  w.setInterval=()=>0;
  let y=400;
  Object.defineProperty(w,'scrollY',{get:()=>y});
  w.scrollTo=({top})=>{y=top;};
  w.HTMLElement.prototype.getBoundingClientRect=function(){const index=[...d.querySelectorAll('[data-item-id]')].indexOf(this);return {top:200+index*300-y,bottom:500+index*300-y};};
  w.eval(script);
  function form(id=1,index=0) {return d.querySelectorAll(`[data-item-id="${id}"] form`)[index];}
  function submit(f=form()) {f.dispatchEvent(new w.SubmitEvent('submit',{bubbles:true,cancelable:true,submitter:f.querySelector('button')}));}
  function edit(id=2,value='7') {const input=form(id,1).querySelector('[name=quantity]'); input.value=value; input.dispatchEvent(new w.Event('input',{bubbles:true})); return input;}
  return {w,d,dom,form,submit,edit,scroll:()=>y,close:()=>w.close()};
}
test('list mutation retains position, posts CSRF/idempotency fields and offers enhanced undo',async t=>{
  let calls=[];
  const p=ui(async(url,options)=>{calls.push([url,options]);return response(html({version:2,undo:true}));});t.after(p.close);
  p.submit(); await tick();
  assert.equal(calls.length,1);assert.equal(calls[0][1].body.get('csrf_token'),'csrf');assert.equal(calls[0][1].body.get('request_id'),'request-1');
  assert.equal(p.scroll(),400);assert.match(p.d.querySelector('h3').textContent,/v2/);
  assert.ok(p.d.querySelector('#action-feedback form[action="/activity/4/undo"]'));
  assert.equal(p.w.location.search.includes('undo='),false);
  p.submit(p.d.querySelector('#action-feedback form'));await tick();assert.equal(calls.length,2);
});
test('an edit in the same article survives another action with its original version',async t=>{
  const p=ui(async()=>response(html({version:2})));t.after(p.close);
  const input=p.edit(1,'7');p.d.querySelector('#details-1').open=true;
  p.submit();await tick();
  assert.equal(p.form(1,1).querySelector('[name=quantity]'),input);
  assert.equal(input.value,'7');assert.equal(p.form(1,1).querySelector('[name=version]').value,'1');
  assert.equal(p.form(1).querySelector('[name=version]').value,'2');assert.equal(p.d.querySelector('#details-1').open,true);
});
test('background refresh that finishes after a write cannot restore stale data',async t=>{
  let finishRead;
  const p=ui(async(url,options)=>options.method==='POST'?response(html({version:2})):new Promise(resolve=>{finishRead=resolve;}));t.after(p.close);
  const pending=p.w.JamesPage.refresh();p.submit();await tick();
  finishRead(response(html({version:1})));await pending;
  assert.match(p.d.querySelector('h3').textContent,/v2/);
});
test('starting an edit during a background read discards the response',async t=>{
  let finish;
  const p=ui(()=>new Promise(resolve=>{finish=resolve;}));t.after(p.close);
  const pending=p.w.JamesPage.refresh();const input=p.edit();finish(response(html({version:2})));await pending;
  assert.equal(p.form(2,1).querySelector('[name=quantity]'),input);assert.match(p.d.querySelector('h3').textContent,/v1/);
});
test('a response from another household is never inserted',async t=>{
  const p=ui(async()=>response(html({owner:'bob',version:99})));t.after(p.close);
  p.submit();await tick();assert.match(p.d.querySelector('h3').textContent,/v1/);
  assert.match(p.d.querySelector('[role=alert]').textContent,/aktualisiere/);
});
test('missing draft destinations leave the existing DOM intact before any replacement',async t=>{
  const p=ui(async()=>response(html({version:2,ids:[1,2]})));t.after(p.close);
  const a=p.edit(2), b=p.edit(3);
  p.submit();await tick();assert.equal(a.isConnected,true);assert.equal(b.isConnected,true);assert.equal(p.d.querySelectorAll('[data-item-id]').length,3);
});
test('a lost confirmation is not retried and keeps the original request id',async t=>{
  let calls=0;
  const p=ui(async()=>{calls++;throw Error('network');});t.after(p.close);
  p.submit();await tick();await tick();assert.equal(calls,1);
  assert.equal(p.form().querySelector('[name=request_id]').value,'request-1');assert.equal(p.form().querySelector('button').disabled,false);
  assert.match(p.d.querySelector('[role=alert]').textContent,/Bestätigung fehlt/);
});
test('conflicts preserve entered quantities and display the server error beside the form',async t=>{
  const p=ui(async()=>response('<main><p>Die Daten wurden inzwischen geändert.</p></main>',{ok:false}));t.after(p.close);
  const input=p.edit(1,'8');p.submit(p.form(1,1));await tick();
  assert.equal(input.value,'8');assert.equal(input.disabled,false);assert.match(p.d.querySelector('[role=alert]').textContent,/inzwischen geändert/);
});

test('removing the acted-on row keeps its next neighbour in place and reachable',async t=>{
  const p=ui(async()=>response(html({version:2,ids:[2,3]})));t.after(p.close);
  p.form().querySelector('button').focus();p.submit();await tick();
  assert.equal(p.scroll(),100);assert.equal(p.d.activeElement.closest('[data-item-id]').dataset.itemId,'2');
});
