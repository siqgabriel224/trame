const vm = require('node:vm'),
  fs = require('node:fs'),
  assert = require('node:assert/strict');
const ctx = vm.createContext({ Intl });
vm.runInContext(fs.readFileSync('web/domain.js', 'utf8'), ctx);
vm.runInContext(fs.readFileSync('web/operations.js', 'utf8'), ctx);
const run = (code) => vm.runInContext(code, ctx);
run(
  "var planned = {tasks:[{id:'finish',sector:'Acabamento'},{id:'cut',sector:'Corte'},{id:'sew',sector:'Costura'}]}"
);
assert.equal(run("TrameDomain.productionTasks(planned).map(t=>t.id).join(',')"), 'cut,sew,finish');
assert.equal(run("planned.tasks.map(t=>t.id).join(',')"), 'finish,cut,sew');
assert.equal(run("TrameDomain.sizeGroups().map(g=>g.rows.length).join(',')"), '5,5');
assert.equal(
  run(
    "TrameDomain.sizeGroups({M:12,'Feminino PP':3,'Sob medida':2}).flatMap(g=>g.rows).reduce((n,[,qty])=>n+qty,0)"
  ),
  15
);
for (const query of ['21', '0021', 'OS-0021', 'pedido 21', '#21']) {
  assert.equal(
    run(`TrameDomain.matchesOrder({kind:'order',osNumber:21},${JSON.stringify(query)})`),
    true
  );
  assert.equal(
    run(`TrameDomain.matchesOrder({kind:'order',osNumber:121},${JSON.stringify(query)})`),
    false
  );
}
assert.equal(
  run("TrameDomain.productionSectors({techniques:[{type:'Bordado'},{type:'DTF'}]}).join(',')"),
  'Separação,Corte,Costura,Bordado,DTF,Acabamento,Revisão,Expedição'
);
assert.equal(run("parseQuantity('10,500')"), 10500);
assert.equal(run("parseQuantity('0,001')+parseQuantity('10,250')"), 10251);
for (const value of ['-1', '1,1234', '1.000,00', 'abc'])
  assert.throws(() => run(`parseQuantity(${JSON.stringify(value)})`));
run("var state={reservations:[{stockId:'s',qtyMilli:4250,stage:'Reservado'}]}");
assert.equal(run("stockValues({id:'s',openingMilli:10500,movements:[]}).available"), 6250);
run("state.reservations[0].stage='Consumido'");
assert.equal(run("stockValues({id:'s',openingMilli:10500,movements:[]}).onHand"), 6250);
assert.equal(run("stockValues({id:'s',openingMilli:10500,movements:[]}).reserved"), 0);
assert.equal(
  run(
    "installmentBalance({payments:[{amountCents:5000,installmentId:'p'},{amountCents:20000},{amountCents:3000,installmentId:'p',voided:true}]},{id:'p',amountCents:17950})"
  ),
  12950
);
assert.equal(
  run(
    'deliveredSizes({deliveryBaseline:{M:1},deliveries:[{sizes:{M:3}},{sizes:{M:2},voided:true}]}).M'
  ),
  4
);
console.log(
  'PASS: quantidades em milésimos, reserva/consumo sem baixa duplicada, parcelas vinculadas e entregas parciais.'
);
