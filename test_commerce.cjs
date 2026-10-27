const vm = require('node:vm');
const fs = require('node:fs');
const assert = require('node:assert/strict');
const context = vm.createContext({
  Intl,
  total: (i) => Object.values(i.sizes).reduce((s, n) => s + n, 0),
});
vm.runInContext(fs.readFileSync('web/domain.js', 'utf8'), context);
vm.runInContext(fs.readFileSync('web/commerce.js', 'utf8'), context);
const run = (code) => vm.runInContext(code, context);
assert.equal(run("parseMoney('35,90')"), 3590);
assert.equal(run("parseMoney('1.234,56')"), 123456);
assert.equal(run("parseMoney('0,10')+parseMoney('0,20')"), 30);
assert.equal(run("parseMoney('1.000')"), 100000);
assert.equal(run("parseMoney('35.90')"), 3590);
for (const value of ['-1', '1,234', 'abc', '2,3,4', 'Infinity'])
  assert.throws(() => run(`parseMoney(${JSON.stringify(value)})`));
assert.equal(
  run(
    "itemFinancial({sizes:{P:10,M:20,G:10},unitPriceCents:3590,techniques:[{type:'Bordado',unitCents:500,setupCents:2500},{type:'Silk',unitCents:300,setupCents:1000},{type:'DTF',unitCents:750,setupCents:0}]}).total"
  ),
  209100
);
assert.equal(
  run(
    'financial({items:[{sizes:{M:3},unitPriceCents:10}],payments:[{amountCents:10}],discountCents:0}).status'
  ),
  'Parcialmente pago'
);
assert.equal(
  run('financial({items:[{sizes:{M:3},unitPriceCents:10}],payments:[{amountCents:30}]}).status'),
  'Pago'
);
assert.equal(
  run(
    'financial({items:[{sizes:{M:3},unitPriceCents:10}],payments:[{amountCents:30,voided:true}]}).status'
  ),
  'Não pago'
);
console.log(
  'PASS: conversão monetária, centavos exatos, técnicas combinadas e três situações de pagamento.'
);
