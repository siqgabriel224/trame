const assert = require('node:assert/strict'),
  vm = require('node:vm'),
  fs = require('node:fs');
const sandbox = { fetch: () => new Promise(() => {}), URLSearchParams, console };
vm.createContext(sandbox);
vm.runInContext(
  fs.readFileSync('web/access.js', 'utf8') + '\nthis.changes=TrameAccess.changes;',
  sandbox
);
const before = {
  orders: [
    { id: 'a', client: 'Um' },
    { id: 'b', client: 'Dois' },
  ],
  clients: [],
  employees: [],
  stock: [],
  reservations: [],
  company: {},
  warningDays: 3,
};
const after = structuredClone(before);
after.orders[0].client = 'Alterado';
let result = sandbox.changes(before, after);
assert.equal(result.length, 1);
assert.equal(result[0].id, 'a');
assert.equal(result[0].before.client, 'Um');
assert.equal(result[0].after.client, 'Alterado');
assert.equal(before.orders[0].client, 'Um');
const newState = structuredClone(before);
newState.clients.push({ id: 'c', name: 'Cliente' });
result = sandbox.changes(before, newState);
assert.equal(result[0].before, null);
assert.equal(result[0].key, 'clients');
assert.equal(sandbox.changes(before, structuredClone(before)).length, 0);
assert.throws(() => sandbox.changes(before, { ...before, orders: [] }), /excluir/);
console.log(
  'PASS: alterações enviam apenas entidades editadas, preservam a base de comparação e impedem exclusões.'
);
