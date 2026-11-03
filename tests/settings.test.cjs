const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {JSDOM}=require('jsdom');
const source=fs.readFileSync('james/static/settings.js','utf8');
function ui(){
  const dom=new JSDOM('<body><label hidden><select id="settings-section"><option value="/settings/profile">Profil</option></select></label><ol data-aisle-order>'+[1,2,3].map(id=>`<li data-category-id="${id}" draggable="true"><input type="hidden" name="category_order" value="${id}"><label><span>Gruppe ${id}</span></label><button data-move="up" type="button">Up</button><button data-move="down" type="button">Down</button></li>`).join('')+'</ol><p id="aisle-feedback"></p></body>',{runScripts:'outside-only',url:'https://james.test/settings/shopping-views/new'});
  dom.window.eval(source);return dom;
}
test('mobile section selection is progressively enabled without removing fallback navigation',t=>{
  const dom=ui();t.after(()=>dom.window.close());
  assert.equal(dom.window.document.querySelector('label').hidden,false);
  assert.ok(dom.window.document.body.classList.contains('settings-enhanced'));
});
test('aisle move buttons update serialized order, keep focus and announce position',t=>{
  const dom=ui();t.after(()=>dom.window.close());const d=dom.window.document;
  const button=d.querySelector('[data-category-id="2"] [data-move="up"]');button.click();
  assert.deepEqual([...d.querySelectorAll('[name=category_order]')].map(e=>e.value),['2','1','3']);
  assert.equal(d.activeElement,button);assert.match(d.querySelector('#aisle-feedback').textContent,/Position 1 von 3/);
  button.click();assert.deepEqual([...d.querySelectorAll('[name=category_order]')].map(e=>e.value),['2','1','3']);
  d.querySelector('[data-category-id="2"] [data-move="down"]').click();assert.deepEqual([...d.querySelectorAll('[name=category_order]')].map(e=>e.value),['1','2','3']);
});
