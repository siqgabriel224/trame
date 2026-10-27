const vm = require('node:vm'),
  fs = require('node:fs'),
  assert = require('node:assert/strict');
const context = vm.createContext({});
vm.runInContext(fs.readFileSync('web/domain.js', 'utf8'), context);
const evaluate = (code) => vm.runInContext(code, context);
for (const query of ['clinica', 'CLÍNICA', 'Bem Viver'])
  assert.equal(
    evaluate(`TrameDomain.matchesClient({name:'Clínica Bem Viver'},${JSON.stringify(query)})`),
    true
  );
for (const query of ['12345678000190', '12.345.678/0001-90', '0001'])
  assert.equal(
    evaluate(
      `TrameDomain.matchesClient({name:'Cliente',document:'12.345.678/0001-90'},${JSON.stringify(query)})`
    ),
    true
  );
assert.equal(
  evaluate(
    "TrameDomain.matchesClient({name:'Cliente',document:'12.345.678/0001-90'},'Outra loja')"
  ),
  false
);
assert.equal(evaluate('TrameDomain.serviceTotal(1500,101)'), 152);
assert.equal(evaluate('TrameDomain.serviceTotal(1500,1,10)'), 12);
assert.equal(evaluate('TrameDomain.quantityInput(1000000)'), '1000');
assert.equal(evaluate('TrameDomain.quantityInput(1234500)'), '1234,5');
console.log(
  'PASS: pesquisa por nome sem acento, CNPJ com ou sem máscara e cálculo de serviços em unidades fracionárias.'
);
