const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const result = {
  company: {
    document: '19.131.243/0001-97',
    name: 'OFICINA EXEMPLO',
    tradeName: 'Oficina',
    phone: '(11) 3333-4444',
    email: '',
    address: 'Rua Exemplo, 100',
  },
  source: 'BrasilAPI',
  status: 'ATIVA',
};
function setup(request, client = false, protectedCompany = false) {
  const elements = Object.fromEntries(
    [
      'name',
      'tradeName',
      'document',
      'phone',
      'email',
      'address',
      'website',
      'whatsapp',
      'responsible',
    ].map((key) => [key, { value: '' }])
  );
  elements.document.value = '19131243000197';
  const form = { elements };
  const button = {};
  const message = {};
  const dialog = {
    addEventListener(event, callback) {
      this[event] = callback;
    },
    removeEventListener(event, callback) {
      if (this[event] === callback) delete this[event];
    },
  };
  const controls = {
    companyFields: {},
    saveCompany: {},
    editCompany: {},
    companyCancel: {},
    companyEditState: {},
    confirmCompanyEdit: {},
    companyEditDialog: {
      open: false,
      showModal() {
        this.open = true;
      },
      close() {
        this.open = false;
      },
    },
  };
  const context = vm.createContext({
    document: {
      getElementById: (id) =>
        ({
          companyForm: form,
          lookupCompany: button,
          companyLookupMessage: message,
          companyDialog: dialog,
        })[id] || (protectedCompany ? controls[id] : undefined),
    },
    TrameAccess: { request },
    clientBindings: {
      form,
      button,
      message,
      dialog,
      endpoint: '/api/clients/cnpj',
      saveLabel: 'Salvar',
    },
  });
  vm.runInContext(fs.readFileSync('web/company.js', 'utf8'), context);
  const binding = vm.runInContext(
    client ? 'TrameCnpj.bind(clientBindings)' : 'TrameCompany',
    context
  );
  return { elements, button, message, dialog, binding, controls };
}
async function main() {
  let calls = 0;
  const success = setup(async (path, data) => {
    calls++;
    assert.equal(path, '/api/company/cnpj');
    assert.equal(data.cnpj, '19131243000197');
    return result;
  });
  success.elements.email.value = 'contato@example.com';
  success.elements.website.value = 'https://example.com';
  await success.button.onclick();
  assert.equal(success.elements.name.value, 'OFICINA EXEMPLO');
  assert.equal(success.elements.email.value, 'contato@example.com');
  assert.equal(success.elements.website.value, 'https://example.com');
  assert.match(success.message.textContent, /Revise e clique em Salvar/);
  assert.match(success.message.textContent, /e-mail/);
  assert.equal(calls, 1);

  const offline = setup(async () => {
    throw Error('Sem conexão');
  });
  offline.elements.name.value = 'Nome manual';
  await offline.button.onclick();
  assert.equal(offline.elements.name.value, 'Nome manual');
  assert.equal(offline.message.textContent, 'Sem conexão');
  assert.equal(offline.button.disabled, false);

  let resolve;
  const stale = setup(
    () =>
      new Promise((done) => {
        resolve = done;
      })
  );
  const pending = stale.button.onclick();
  stale.elements.document.value = '00000000000191';
  resolve(result);
  await pending;
  assert.equal(stale.elements.name.value, '');
  assert.match(stale.message.textContent, /CNPJ foi alterado/);

  const editing = setup(
    () =>
      new Promise((done) => {
        resolve = done;
      })
  );
  const inProgress = editing.button.onclick();
  editing.elements.phone.value = 'Telefone manual';
  resolve(result);
  await inProgress;
  assert.equal(editing.elements.phone.value, 'Telefone manual');
  assert.equal(editing.elements.name.value, 'OFICINA EXEMPLO');

  const closed = setup(
    () =>
      new Promise((done) => {
        resolve = done;
      })
  );
  const closing = closed.button.onclick();
  closed.dialog.close();
  resolve(result);
  await closing;
  assert.equal(closed.elements.name.value, '');
  assert.equal(closed.message.textContent, '');

  const client = setup(async (path) => {
    assert.equal(path, '/api/clients/cnpj');
    return result;
  }, true);
  client.elements.whatsapp.value = 'WhatsApp informado manualmente';
  client.elements.responsible.value = 'Contato do cliente';
  await client.button.onclick();
  assert.equal(client.elements.name.value, result.company.name);
  assert.equal(client.elements.tradeName.value, result.company.tradeName);
  assert.equal(client.elements.whatsapp.value, 'WhatsApp informado manualmente');
  assert.equal(client.elements.responsible.value, 'Contato do cliente');
  assert.match(client.message.textContent, /clique em Salvar\./);

  const replaced = setup(
    () =>
      new Promise((done) => {
        resolve = done;
      }),
    true
  );
  const replacing = replaced.button.onclick();
  replaced.binding.dispose();
  resolve(result);
  await replacing;
  assert.equal(replaced.elements.name.value, '');
  assert.equal(replaced.message.textContent, '');
  const protectedForm = setup(async () => result, false, true);
  protectedForm.binding.lock();
  assert.equal(protectedForm.controls.companyFields.disabled, true);
  assert.equal(protectedForm.controls.saveCompany.hidden, true);
  protectedForm.controls.editCompany.onclick();
  assert.equal(protectedForm.controls.companyEditDialog.open, true);
  assert.equal(protectedForm.binding.editing, false);
  protectedForm.controls.companyEditDialog.close();
  assert.equal(protectedForm.controls.companyFields.disabled, true);
  protectedForm.controls.editCompany.onclick();
  protectedForm.controls.confirmCompanyEdit.onclick();
  assert.equal(protectedForm.binding.editing, true);
  assert.equal(protectedForm.controls.companyFields.disabled, false);
  protectedForm.dialog.close();
  assert.equal(protectedForm.binding.editing, false);
  assert.equal(protectedForm.controls.companyFields.disabled, true);
  console.log(
    'PASS: consulta sem salvamento automático, falhas preservam dados e respostas antigas não sobrescrevem edições.'
  );
}
main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
