const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const scannerSource = fs.readFileSync(path.join(__dirname, '../james/static/scanner.js'), 'utf8');

function setup({supported = true, media, detect} = {}) {
  const elements = {};
  for (const id of ['scan-form','barcode-input','barcode-video','camera-preview','camera-start','camera-stop','camera-status']) {
    elements[id] = {listeners:{}, hidden:false, disabled:false, value:'',
      addEventListener(name, fn) {this.listeners[name] = fn;}};
  }
  let stopped = 0, submissions = 0, mediaCalls = 0;
  const stream = {getTracks:() => [{stop:() => {stopped += 1;}}]};
  elements['barcode-video'].play = async () => {};
  elements['barcode-video'].pause = () => {};
  elements['scan-form'].requestSubmit = () => {submissions += 1;};
  const document = {listeners:{}, visibilityState:'visible', querySelector:selector => elements[selector.slice(1)],
    addEventListener(name, fn) {this.listeners[name] = fn;}};
  const window = {listeners:{}, isSecureContext:true, setTimeout:() => 1, clearTimeout:() => {},
    addEventListener(name, fn) {this.listeners[name] = fn;}};
  class Detector {
    static async getSupportedFormats() {return ['ean_13'];}
    async detect() {return detect ? detect() : [];}
  }
  if (supported) window.BarcodeDetector = Detector;
  const navigator = {mediaDevices:{getUserMedia:async () => {mediaCalls += 1;return media ? media() : stream;}}};
  vm.runInNewContext(scannerSource, {window,document,navigator,BarcodeDetector:Detector,Error});
  return {elements,window,document,stream,stats:() => ({stopped,submissions,mediaCalls})};
}
const settle = () => new Promise(resolve => setImmediate(resolve));

test('unsupported camera leaves manual entry available and never requests media', () => {
  const state = setup({supported:false});
  assert.equal(state.elements['camera-start'].hidden,true);
  assert.match(state.elements['camera-status'].textContent,/Nummer eingeben/);
  assert.equal(state.stats().mediaCalls,0);
});

test('camera requires a gesture, submits exactly once, then releases all tracks', async () => {
  const state = setup({detect:async () => [{rawValue:'4006381333931',format:'ean_13'}]});
  assert.equal(state.stats().mediaCalls,0);
  await state.elements['camera-start'].listeners.click();
  await settle();
  assert.deepEqual(state.stats(),{stopped:1,submissions:1,mediaCalls:1});
  assert.equal(state.elements['barcode-video'].srcObject,null);
  assert.equal(state.elements['barcode-input'].value,'4006381333931');
});

test('cancelling pending permission stops a camera that resolves later', async () => {
  let resolveMedia;
  const pending = new Promise(resolve => {resolveMedia=resolve;});
  const state = setup({media:() => pending});
  const starting = state.elements['camera-start'].listeners.click();
  await settle();
  state.elements['camera-stop'].listeners.click();
  resolveMedia(state.stream);
  await starting;
  assert.equal(state.stats().stopped,1);
  assert.equal(state.stats().submissions,0);
});

test('backgrounding stops camera and ignores a late detection result', async () => {
  let resolveDetection;
  const pending = new Promise(resolve => {resolveDetection=resolve;});
  const state = setup({detect:() => pending});
  await state.elements['camera-start'].listeners.click();
  state.document.visibilityState='hidden';
  state.document.listeners.visibilitychange();
  resolveDetection([{rawValue:'4006381333931',format:'ean_13'}]);
  await settle();
  assert.equal(state.stats().stopped,1);
  assert.equal(state.stats().submissions,0);
});

test('named catalogue submit action survives disabling the clicked button', () => {
  const source = fs.readFileSync(path.join(__dirname,'../james/static/app.js'),'utf8');
  const button = {name:'lookup',value:'1',disabled:false};
  const fields=[];
  const form={listeners:{}, querySelectorAll:selector => selector.startsWith('button') ? [button] : [],
    appendChild:field => fields.push(field), addEventListener(name,fn) {this.listeners[name]=fn;}};
  const document={querySelector:selector => selector==='#offline-banner' ? {} : null,
    querySelectorAll:selector => selector.includes('button') ? [button] : [form],
    addEventListener() {}, createElement:() => ({setAttribute() {}})};
  const window={location:{pathname:'/join'},addEventListener() {}};
  vm.runInNewContext(source,{document,window,navigator:{onLine:true}});
  form.listeners.submit({submitter:button,preventDefault() {throw Error('unexpected cancellation');}});
  assert.equal(button.disabled,true);
  assert.equal(fields.length,1);
  assert.equal(fields[0].name,'lookup');
  assert.equal(fields[0].value,'1');
});
