const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const elements = new Map();
const location = { origin: 'http://127.0.0.1:18743', search: '' };
const context = vm.createContext({
  location,
  URL,
  URLSearchParams,
  document: {
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, {});
      return elements.get(id);
    },
  },
  fetch: () => new Promise(() => {}),
});
vm.runInContext(fs.readFileSync('web/login.js', 'utf8'), context);
function destination(next) {
  location.search = '?next=' + encodeURIComponent(next);
  return vm.runInContext('destination()', context);
}
for (const next of [
  '//outside.example',
  '///',
  '//[invalid',
  '/\\outside.example',
  '/\t/outside.example',
  'https://outside.example',
  'javascript:alert(1)',
  '/login',
  '/login?next=/',
])
  assert.equal(destination(next), '/', 'Destino não autorizado: ' + JSON.stringify(next));
assert.equal(destination('/?order=demo-1'), '/?order=demo-1');
assert.equal(destination('/print?order=demo-1#details'), '/print?order=demo-1#details');
assert.equal(destination('/%2Foutside.example'), '/%2Foutside.example');
console.log('PASS: login mantém o retorno na origem local e preserva o pedido selecionado.');
