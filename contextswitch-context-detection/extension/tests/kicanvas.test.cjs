const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function fixture(references = ['R1', 'R10'], confirm = true) {
  const state = {filtered: '', zoomed: false, clicked: []};
  function element(mapping = {}) {
    const attrs = new Set();
    return {
      querySelectorAll: selector => mapping[selector] || [],
      querySelector(selector) { return this.querySelectorAll(selector)[0] || null; },
      getBoundingClientRect: () => ({width: 100, height: 100}),
      hasAttribute: name => attrs.has(name),
      setAttribute: name => attrs.add(name),
      removeAttribute: name => attrs.delete(name),
      scrollIntoView() {}, focus() {}, click() {},
    };
  }
  class Input {}
  Object.defineProperty(Input.prototype, 'value', {set(value) {state.filtered = value;}});
  const input = Object.assign(new Input(), element());
  input.dispatchEvent = event => {
    assert.equal(event.composed, true, 'input events must cross shadow roots');
    assert.equal(event.bubbles, true);
  };
  const zoom = element();
  zoom.setAttribute('disabled');
  zoom.click = () => {state.zoomed = true;};
  const items = references.map(reference => {
    const item = element({'span': [{textContent: reference}]});
    item.click = () => {
      state.clicked.push(reference);
      if (confirm) {item.setAttribute('selected'); zoom.removeAttribute('disabled');}
    };
    return item;
  });
  const filter = element();
  filter.shadowRoot = element({'input': [input]});
  const panel = element();
  panel.shadowRoot = element({'*': [filter], 'kc-ui-menu-item[data-match-text]': items});
  const app = element();
  app.shadowRoot = element({'*': [panel], 'kc-schematic-symbols-panel': [panel],
    'kc-ui-button[name="zoom_to_selection"]': [zoom]});
  const document = element({'*': [app], 'kc-schematic-app': [app]});
  const context = {document, window: {}, HTMLInputElement: Input,
    getComputedStyle: () => ({visibility: 'visible', display: 'block'}),
    Event: class {constructor(type, options) {Object.assign(this, {type}, options);}},
    setTimeout, Date};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../kicanvas.js'), 'utf8'), context);
  return {search: context.window.BeyondTouchKiCanvas.searchComponent, state};
}

test('search crosses nested shadow roots, selects exact reference, and requests zoom', async () => {
  const {search, state} = fixture();
  const result = await search('r 1');
  assert.equal(result.status, 'SUCCESS');
  assert.equal(result.verified, true);
  assert.equal(state.filtered, 'R1');
  assert.deepEqual(state.clicked, ['R1']);
  assert.equal(state.zoomed, true);
});

test('missing and ambiguous components fail without selecting anything', async () => {
  for (const references of [['R10'], ['R1', 'R1']]) {
    const {search, state} = fixture(references);
    assert.equal((await search('R1')).status, 'FAILED');
    assert.deepEqual(state.clicked, []);
    assert.equal(state.zoomed, false);
  }
});

test('malformed references never enter the search box', async () => {
  const {search, state} = fixture();
  assert.equal((await search('R1;alert(1)')).status, 'FAILED');
  assert.equal(state.filtered, '');
});

test('unconfirmed viewer selection never reports success or requests zoom', async () => {
  const {search, state} = fixture(['R1'], false);
  const result = await search('R1');
  assert.equal(result.status, 'UNVERIFIED');
  assert.equal(result.verified, false);
  assert.equal(state.zoomed, false);
});
