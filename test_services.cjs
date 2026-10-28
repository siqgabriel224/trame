const vm = require('node:vm'),
  fs = require('node:fs'),
  assert = require('node:assert/strict');
const context = vm.createContext({});
vm.runInContext(fs.readFileSync('web/domain.js', 'utf8'), context);
const evaluate = (code) => vm.runInContext(code, context);
evaluate('TrameDomain.setThreadPalette(' + fs.readFileSync('web/zenith-colors.json', 'utf8') + ')');
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
// Famílias cadastradas agrupam os tons, sem inventar uma cartela Zenith por código.
for (const color of ['Verde', 'VERDE FOLHA', 'Verde água', 'verde-escuro'])
  assert.equal(evaluate(`TrameDomain.stockColorFamily(${JSON.stringify(color)})`), 'Verde');
for (const code of ['2028', '2075', '2228'])
  assert.equal(
    evaluate(
      `TrameDomain.matchesSupply({category:'Linha',color:'Verde',code:'${code}'},'${code}')`
    ),
    true
  );
assert.equal(evaluate("TrameDomain.matchesSupply({color:'Lilás',code:'0028'},'LILAS')"), true);
assert.equal(evaluate("TrameDomain.matchesSupply({color:'Verde',code:'0028'},'0028')"), true);
assert.equal(
  evaluate("TrameDomain.stockColorHex({color:'Verde',colorHex:'red;display:none'})"),
  '#dce3de'
);
assert.equal(evaluate("TrameDomain.stockColorHex({color:'Verde',colorHex:'#123456'})"), '#dce3de');

const code2228 = evaluate("TrameDomain.threadColor('2228').hex");
assert.equal(evaluate("TrameDomain.stockColorHex({code:'2228',color:'Verde'})"), code2228);
assert.equal(
  evaluate("TrameDomain.stockColorHex({code:'2228',color:'Vermelho',colorHex:'#ff0000'})"),
  code2228
);
assert.notEqual(evaluate("TrameDomain.threadColor('2075').hex"), code2228);
assert.equal(evaluate("TrameDomain.stockColorHex({code:'999999',color:'Verde'})"), '#dce3de');
assert.equal(evaluate("TrameDomain.threadColor('999999')"), null);
assert.equal(
  evaluate("TrameDomain.threadColor('853').hex"),
  evaluate("TrameDomain.threadColor('0853').hex")
);
