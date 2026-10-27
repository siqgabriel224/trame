'use strict';

const TrameCnpj = (() => {
  function bind({ form, button, message, dialog, endpoint, saveLabel }) {
    const fields = ['name', 'tradeName', 'phone', 'email', 'address'];
    let generation = 0;
    const normalize = (value) => value.replace(/[.\s/-]/g, '').toUpperCase();

    function reset() {
      generation += 1;
      message.textContent = '';
      button.disabled = false;
      button.textContent = 'Consultar CNPJ';
    }

    button.onclick = async () => {
      const document = normalize(form.elements.document.value);
      if (!/^[0-9A-Z]{12}[0-9]{2}$/.test(document)) {
        message.textContent = 'Digite um CNPJ completo. Para CPF, preencha os dados manualmente.';
        return;
      }
      const request = ++generation;
      const before = Object.fromEntries(fields.map((key) => [key, form.elements[key].value]));
      button.disabled = true;
      button.textContent = 'Consultando…';
      message.textContent = 'Buscando os dados públicos da empresa…';
      try {
        const result = await TrameAccess.request(endpoint, { cnpj: document });
        if (request !== generation) return;
        if (normalize(form.elements.document.value) !== document) {
          message.textContent = 'O CNPJ foi alterado durante a consulta. Consulte novamente.';
          return;
        }
        const missing = [];
        let edited = false;
        const labels = {
          name: 'razão social',
          tradeName: 'nome fantasia',
          phone: 'telefone',
          email: 'e-mail',
          address: 'endereço',
        };
        for (const key of fields) {
          if (form.elements[key].value !== before[key]) {
            edited = true;
            continue;
          }
          if (result.company[key]) form.elements[key].value = result.company[key];
          else missing.push(labels[key]);
        }
        form.elements.document.value = result.company.document;
        message.textContent = `Dados consultados na ${result.source}.${result.status ? ' Situação: ' + result.status + '.' : ''} Revise e clique em ${saveLabel}.`;
        if (missing.length)
          message.textContent += ` A fonte não informou ${missing.join(', ')}; esses campos foram mantidos como estavam.`;
        if (edited)
          message.textContent += ' Os campos editados durante a consulta foram preservados.';
      } catch (error) {
        if (request === generation) message.textContent = error.message;
      } finally {
        if (request === generation) {
          button.disabled = false;
          button.textContent = 'Consultar CNPJ';
        }
      }
    };

    dialog.addEventListener('close', reset);
    return {
      reset,
      dispose() {
        reset();
        dialog.removeEventListener('close', reset);
      },
    };
  }
  return { bind };
})();

const TrameCompany = TrameCnpj.bind({
  form: document.getElementById('companyForm'),
  button: document.getElementById('lookupCompany'),
  message: document.getElementById('companyLookupMessage'),
  dialog: document.getElementById('companyDialog'),
  endpoint: '/api/company/cnpj',
  saveLabel: 'Salvar empresa',
});

TrameCompany.editing = false;
TrameCompany.lock = () => {
  TrameCompany.reset();
  TrameCompany.editing = false;
  document.getElementById('companyFields').disabled = true;
  document.getElementById('saveCompany').hidden = true;
  document.getElementById('editCompany').hidden = false;
  document.getElementById('companyCancel').textContent = 'Fechar';
  document.getElementById('companyEditState').textContent =
    'Somente leitura. Use o lápis para solicitar a edição.';
};
if (document.getElementById('editCompany')) {
  document.getElementById('editCompany').onclick = () =>
    document.getElementById('companyEditDialog').showModal();
  document.getElementById('confirmCompanyEdit').onclick = () => {
    document.getElementById('companyEditDialog').close();
    TrameCompany.editing = true;
    document.getElementById('companyFields').disabled = false;
    document.getElementById('saveCompany').hidden = false;
    document.getElementById('editCompany').hidden = true;
    document.getElementById('companyCancel').textContent = 'Cancelar';
    document.getElementById('companyEditState').textContent =
      'Edição liberada. Revise os dados e salve para aplicar.';
  };
  document.getElementById('companyDialog').addEventListener('close', TrameCompany.lock);
}
