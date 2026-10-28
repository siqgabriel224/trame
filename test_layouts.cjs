const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const { webcrypto, createHash } = require('node:crypto');
const scope = vm.createContext({ crypto: webcrypto, TextEncoder, URLSearchParams, Uint8Array });
vm.runInContext(fs.readFileSync('web/domain.js', 'utf8') + '\nthis.domain = TrameDomain;', scope);
(async () => {
  const image = 'data:image/png;base64,bGF5b3V0';
  const digest = createHash('sha256').update(image).digest('hex');
  const link = '/api/layout?order=o1&item=i1&v=' + digest;
  assert.equal(await scope.domain.sameLayout(link, image), true);
  assert.equal(await scope.domain.sameLayout(image, link), true);
  assert.equal(await scope.domain.sameLayout(link, 'data:image/png;base64,bmV3'), false);
  assert.equal(await scope.domain.sameLayout(link, link), true);
  assert.equal(await scope.domain.sameLayout(undefined, ''), true);
  console.log('PASS: reanexar o mesmo arquivo preserva a aprovação; outro layout exige revisão.');
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
