'use strict';
const sectors = [
  'Separação',
  'Corte',
  'Costura',
  'Bordado',
  'Silk',
  'DTF',
  'Acabamento',
  'Revisão',
  'Expedição',
];
const contactFields = [
  'responsible',
  'document',
  'phone',
  'whatsapp',
  'email',
  'instagram',
  'website',
  'otherContact',
  'address',
];
const specFields = {
  Bordado: [
    ['points', 'Quantidade de pontos'],
    ['matrix', 'Arquivo / código da matriz'],
    ['threads', 'Cores e códigos das linhas'],
  ],
  Silk: [
    ['screens', 'Quantidade / código das telas'],
    ['inkColors', 'Cores e tipos das tintas'],
  ],
  DTF: [
    ['width', 'Largura (cm)'],
    ['height', 'Altura (cm)'],
    ['film', 'Filme / referência'],
    ['temperature', 'Temperatura de aplicação (°C)'],
    ['seconds', 'Tempo de aplicação (segundos)'],
    ['pressure', 'Pressão / instruções'],
  ],
};
let opsSubmit = null,
  opsLookup = null,
  queueSearch = '',
  queueEmployee = '',
  queueStage = 'active',
  approvalFile = '',
  approvalReading = false;
const inputField = (label, name, value = '', type = 'text', extra = '') =>
  `<label>${esc(label)}<input name="${name}" type="${type}" value="${esc(value)}" ${extra}></label>`;
const textField = (label, name, value = '') =>
  `<label class="full">${esc(label)}<textarea name="${name}" rows="2" maxlength="3000">${esc(value)}</textarea></label>`;
const option = (value, label, selected) =>
  `<option value="${esc(value)}" ${String(value) === String(selected) ? 'selected' : ''}>${esc(label)}</option>`;
const selectField = (label, name, options) =>
  `<label>${esc(label)}<select name="${name}">${options}</select></label>`;
const formatQuantity = (n) =>
  new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 3 }).format(n / 1000);
function parseQuantity(v) {
  const s = String(v).trim().replace(',', '.');
  if (!/^\d+(\.\d{1,3})?$/.test(s))
    throw Error('Use quantidade com até três casas decimais, sem separador de milhares.');
  const [a, b = ''] = s.split('.');
  const n = Number(a) * 1000 + Number(b.padEnd(3, '0'));
  if (!Number.isSafeInteger(n) || n > 1000000000) throw Error('Quantidade acima do limite.');
  return n;
}
const deliveredSizes = TrameDomain.delivered;
const stockValues = (s) => TrameDomain.stock(state, s);
const installmentBalance = TrameDomain.installmentBalance;
function installmentStatus(o, p) {
  if (p.cancelled) return 'Cancelada';
  const b = installmentBalance(o, p);
  return b === 0
    ? 'Paga'
    : p.due < today()
      ? 'Vencida'
      : b < p.amountCents
        ? 'Parcialmente paga'
        : 'A vencer';
}
function opsForm(title, html, handler) {
  opsLookup?.dispose();
  opsLookup = null;
  $('#opsTitle').textContent = title;
  $('#opsFields').innerHTML = html;
  opsSubmit = handler;
  $('#opsForm .modal-actions .primary').hidden = !handler;
  $('#opsForm .modal-actions .primary').textContent = 'Salvar';
  $('#opsDialog').showModal();
}
function openOpsOrder(id) {
  if ($('#opsDialog').open) $('#opsDialog').close();
  openDetail(id);
}
function renderOperationsView() {
  $('#sideCount').textContent = state.orders.filter(
    (o) => o.kind !== 'quote' && !o.archived && !done(o)
  ).length;
  $('#quoteCount').textContent = state.orders.filter(
    (o) => o.kind === 'quote' && !o.archived
  ).length;
  const custom = !['orders', 'quotes'].includes(view);
  for (const s of ['.heading', '#stats', '#financeSummary', '.board']) $(s).hidden = custom;
  $('#opsWorkspace').hidden = !custom;
  $$('.sidebar .nav').forEach((b) => b.classList.toggle('active', b.dataset.view === view));
  if (!custom) return false;
  const titles = {
    clients: ['Clientes', 'Contatos reutilizáveis, com histórico de pedidos.'],
    queue: ['Produção', 'Etapas, funcionários, quantidades e prazos por setor.'],
    stock: ['Estoque e reservas', 'Disponível = saldo físico menos reservas ativas.'],
    billing: ['Cobranças', 'Parcelas previstas, recebimentos e vencimentos.'],
    employees: ['Funcionários', 'Cadastre as pessoas que executam as etapas.'],
  };
  const [title, subtitle] = titles[view];
  let content = '';
  if (view === 'clients')
    content = `<button class="primary" data-action="new-client">＋ Cadastrar cliente</button><div class="ops-cards">${(state.clients || []).map((c) => `<article class="ops-card"><div class="section-heading"><h3>${esc(c.name)}</h3><span class="badge">${c.active === false ? 'Inativo' : 'Ativo'}</span></div><p>${esc(c.responsible || 'Sem responsável informado')}</p><p class="notes">${esc([c.phone, c.whatsapp, c.email].filter(Boolean).join(' · '))}</p><div class="detail-actions"><button class="secondary" data-action="edit-client" data-id="${esc(c.id)}">Editar cadastro</button><button class="secondary" data-action="client-history" data-id="${esc(c.id)}">Histórico de pedidos</button></div></article>`).join('') || '<p class="ops-empty">Cadastre um cliente para reutilizar seus contatos em pedidos e orçamentos.</p>'}</div>`;
  if (view === 'employees')
    content = `<button class="primary" data-action="new-employee">＋ Cadastrar funcionário</button><div class="ops-cards">${(state.employees || []).map((e) => `<article class="ops-card"><h3>${esc(e.name)}</h3><p>${esc(e.sector)} · ${e.active === false ? 'Inativo' : 'Ativo'}</p><button class="secondary" data-action="edit-employee" data-id="${esc(e.id)}">Editar funcionário</button></article>`).join('') || '<p class="ops-empty">Cadastre as pessoas para atribuir e concluir etapas de produção.</p>'}</div>`;
  if (view === 'queue') content = productionBoard();
  if (view === 'stock')
    content = `<div class="ops-toolbar"><button class="primary" data-action="new-stock">＋ Cadastrar material</button><button class="secondary" data-action="new-reservation">＋ Reservar para pedido</button></div><div class="ops-cards">${
      (state.stock || [])
        .map((s) => {
          const v = stockValues(s);
          return `<article class="ops-card"><div class="section-heading"><h3>${esc(s.name)}</h3><span class="badge ${v.available < (s.minimumMilli || 0) ? 'late' : 'good'}">${s.active === false ? 'Inativo' : v.available < (s.minimumMilli || 0) ? 'Abaixo do mínimo' : 'Disponível'}</span></div><div class="stock-numbers"><div><small>Físico</small><b>${formatQuantity(v.onHand)} ${esc(s.unit)}</b></div><div><small>Reservado</small><b>${formatQuantity(v.reserved)}</b></div><div><small>Livre</small><b>${formatQuantity(v.available)}</b></div></div><div class="detail-actions"><button class="secondary" data-action="stock-move" data-id="${esc(s.id)}">Entrada / saída</button><button class="secondary" data-action="edit-stock" data-id="${esc(s.id)}">Editar material</button><button class="secondary" data-action="stock-history" data-id="${esc(s.id)}">Histórico</button></div></article>`;
        })
        .join('') ||
      '<p class="ops-empty">Cadastre materiais com unidade, saldo inicial e estoque mínimo.</p>'
    }</div><h2 class="ops-subtitle">Reservas dos pedidos</h2>${reservationMarkup((state.reservations || []).filter((r) => r.stage === 'Reservado'))}`;
  if (view === 'billing') {
    const rows = state.orders
      .filter((o) => o.kind !== 'quote' && !o.archived)
      .flatMap((o) =>
        (o.installments || [])
          .filter((p) => !p.cancelled)
          .map((p) => ({ o, p, b: installmentBalance(o, p) }))
      )
      .sort((a, b) => a.p.due.localeCompare(b.p.due));
    const overdue = rows.filter((r) => r.p.due < today()).reduce((n, r) => n + r.b, 0),
      planned = rows.reduce((n, r) => n + r.b, 0);
    content = `<div class="finance-summary"><div><small>PARCELAS PENDENTES</small><strong>${brl(planned)}</strong></div><div><small>VALOR VENCIDO</small><strong>${brl(overdue)}</strong></div></div><div class="ops-cards">${rows.map(({ o, p, b }) => `<article class="ops-card"><div class="section-heading"><h3>${esc(p.label)} · ${brl(p.amountCents)}</h3><span class="badge ${b === 0 ? 'good' : p.due < today() ? 'late' : 'pending'}">${installmentStatus(o, p)}</span></div><p>${esc(o.client)} · ${docLabel(o)}</p><p>Vencimento: ${new Date(p.due + 'T12:00:00').toLocaleDateString('pt-BR')} · Saldo: ${brl(b)}</p><div class="detail-actions"><button class="primary" data-action="receive-part" data-id="${esc(o.id)}" data-item="${esc(p.id)}" ${b === 0 ? 'disabled' : ''}>Registrar recebimento</button><button class="secondary" data-action="open-order" data-id="${esc(o.id)}">Abrir pedido</button></div></article>`).join('') || '<p class="ops-empty">Programe as parcelas nos detalhes dos pedidos. Recebimentos existentes continuam preservados.</p>'}</div>`;
  }
  $('#opsWorkspace').innerHTML = `<div class="ops-heading"><h1>${title}</h1></div>${content}`;
  bindOperationButtons($('#opsWorkspace'));
  if (view === 'queue') {
    $('#queueSearch').oninput = (e) => {
      queueSearch = e.target.value;
      $('#productionOrders').innerHTML = productionOrders();
      bindOperationButtons($('#productionOrders'));
    };
    $('#queueStage').onchange = (e) => {
      queueStage = e.target.value;
      render();
    };
    $('#queueEmployee').onchange = (e) => {
      queueEmployee = e.target.value;
      render();
    };
  }
  return true;
}
function productionTaskRow(o, i, t) {
  const employee = state.employees.find((e) => e.id === t.employeeId);
  const signed = t.signature;
  const blocked = o.archived || !i.approved || !employee || o.kind === 'quote';
  return `<div class="production-step ${signed ? 'is-signed' : ''}"><div><strong>${esc(t.sector)}</strong><small>${esc(employee?.name || 'Defina o responsável')} · ${t.qty} peças · prazo ${dateLabel(t.due)}</small>${signed ? `<p class="signature-record">✓ ${esc(signed.name)} · ${dateLabel(signed.date)}<small>Registrado por ${esc(signed.recordedBy.name)} · ${esc(signed.source)}</small></p>` : t.stage === 'Concluído' ? '<small class="unsigned-warning">Concluída anteriormente · assinatura não registrada</small>' : !i.approved ? '<small>Layout pendente · início bloqueado</small>' : ''}</div><div class="step-actions"><span class="badge ${signed ? 'good' : 'pending'}">${signed ? 'Assinada' : esc(t.stage)}</span>${signed ? '' : `${t.stage !== 'Concluído' ? `<button class="secondary" data-action="edit-task" data-item="${esc(i.id)}" data-id="${esc(t.id)}" ${o.archived ? 'disabled' : ''}>${employee ? 'Editar etapa' : 'Definir responsável'}</button>${t.stage === 'Pendente' ? `<button class="secondary" data-action="start-task" data-item="${esc(i.id)}" data-id="${esc(t.id)}" ${blocked ? 'disabled' : ''}>Iniciar</button>` : ''}` : ''}<button class="primary" data-action="sign-task" data-item="${esc(i.id)}" data-id="${esc(t.id)}" ${blocked ? 'disabled' : ''}>${t.stage === 'Concluído' ? 'Registrar assinatura' : 'Concluir e assinar'}</button>`}</div></div>`;
}
function productionBoard() {
  return `<p class="form-note">Abra o pedido, defina os responsáveis e registre a execução de cada etapa da OS. As etapas assinadas ficam preservadas.</p><div class="ops-toolbar"><label class="production-search">Localizar pedido<input type="search" id="queueSearch" value="${esc(queueSearch)}" placeholder="Número do pedido ou cliente"></label><label>Exibir<select id="queueStage">${option('active', 'Pedidos em aberto', queueStage)}${option('done', 'Pedidos entregues', queueStage)}${option('all', 'Todos os pedidos', queueStage)}</select></label><label>Responsável<select id="queueEmployee">${option('', 'Todos os responsáveis', queueEmployee)}${state.employees.map((e) => option(e.id, e.name, queueEmployee)).join('')}</select></label></div><div id="productionOrders" class="production-orders">${productionOrders()}</div>`;
}
function productionOrders() {
  const number = TrameDomain.orderNumberQuery(queueSearch);
  const orders = state.orders
    .filter((o) => o.kind !== 'quote' && (number !== null || !o.archived))
    .filter(
      (o) => number !== null || queueStage === 'all' || (queueStage === 'done' ? done(o) : !done(o))
    )
    .filter((o) => TrameDomain.matchesOrder(o, queueSearch))
    .filter(
      (o) =>
        !queueEmployee || o.items.some((i) => i.tasks?.some((t) => t.employeeId === queueEmployee))
    )
    .sort((a, b) => a.due.localeCompare(b.due));
  return (
    orders
      .map((o) => {
        const tasks = o.items.flatMap((i) => i.tasks || []),
          signed = tasks.filter((t) => t.signature).length;
        return `<article class="production-order"><div class="section-heading"><div><span class="eyebrow">${docLabel(o)}${o.archived ? ' · ARQUIVADO' : ''}</span><h2>${esc(o.client)}</h2><p>${esc(o.description)} · entrega ${dateLabel(o.due)}</p></div><div class="detail-actions"><button class="secondary" data-action="open-order" data-id="${esc(o.id)}">Abrir OS</button><button class="secondary" data-action="edit-order" data-id="${esc(o.id)}" ${o.archived ? 'disabled' : ''}>Editar pedido</button><a class="secondary" target="_blank" rel="noopener" href="/print?id=${encodeURIComponent(o.id)}&type=os">Imprimir OS</a></div></div><p class="hint">${tasks.length ? `${signed} de ${tasks.length} etapas assinadas` : 'Etapas ainda não preparadas'}</p><details class="production-steps" ${number !== null || orders.length === 1 ? 'open' : ''}><summary>Ver etapas e responsáveis · ${signed}/${tasks.length} assinadas</summary>${o.items
          .map(
            (i, index) =>
              `<section class="production-model"><h3>Modelo ${index + 1} · ${esc(i.type)} · ${total(i)} peças</h3>${
                TrameDomain.productionTasks(i)
                  .map((t) => productionTaskRow(o, i, t))
                  .join('') || '<p class="hint">Prepare as etapas para acompanhar este modelo.</p>'
              }<button class="secondary" data-action="new-task" data-item="${esc(i.id)}" ${o.archived ? 'disabled' : ''}>＋ Etapa complementar</button></section>`
          )
          .join(
            ''
          )}<button class="secondary" data-action="prepare-production" data-id="${esc(o.id)}" ${o.archived || !o.items.length || done(o) ? 'disabled' : ''}>Preparar etapas da OS</button><p class="hint">Inclui separação, corte, costura, técnicas do modelo, acabamento, revisão e expedição. Etapas existentes são mantidas.</p></details></article>`;
      })
      .join('') ||
    '<p class="ops-empty">Nenhum pedido encontrado. Busque pelo número ou altere o filtro de situação.</p>'
  );
}
async function prepareProduction(orderId) {
  const n = clone(),
    o = n.orders.find((o) => o.id === orderId);
  let added = false;
  for (const i of o.items) {
    i.tasks ||= [];
    for (const sector of TrameDomain.productionSectors(i)) {
      if (i.tasks.some((t) => t.sector === sector)) continue;
      added = true;
      i.tasks.push({
        id: uid(),
        sector,
        employeeId: '',
        due: o.due,
        qty: total(i),
        stage: 'Pendente',
        notes: '',
      });
    }
  }
  if (!added) return toast('As etapas da OS já estão preparadas.');
  if (await save(n)) toast('Etapas da OS preparadas. Defina os responsáveis para começar.');
}
function signTask(itemId, taskId) {
  const { o, i } = findItem(itemId),
    task = i.tasks.find((t) => t.id === taskId);
  const employee = state.employees.find((e) => e.id === task.employeeId);
  if (!employee || !i.approved || o.archived)
    return toast('Defina o responsável e aprove o layout antes de registrar a execução.', true);
  const user = TrameAccess.session.user;
  if (user.role !== 'admin' && user.employeeId !== employee.id)
    return toast(
      'Entre com o acesso do responsável pela etapa ou peça ao administrador para registrar a OS assinada.',
      true
    );
  opsForm(
    `Assinar etapa · ${docLabel(o)}`,
    `<p class="form-note">${esc(o.client)} · ${esc(i.type)} · <b>${esc(task.sector)}</b> · ${task.qty} peças</p><p>${user.role === 'admin' ? 'Registre o nome e a data conforme a etapa assinada pelo responsável na OS.' : 'Confirme a execução desta etapa com seu nome.'}</p><div class="form-grid">${inputField('Responsável pela execução', 'executor', employee.name, 'text', 'readonly')}${inputField('Data da execução', 'date', task.completedAt || today(), 'date', `required max="${today()}"`)}${inputField('Digite o nome do responsável para confirmar', 'signatureName', '', 'text', 'required maxlength="200" autocomplete="off"')}<label class="check full"><input type="checkbox" name="confirmed" required> Confirmo que esta etapa foi executada pelo responsável informado.</label></div><p class="hint">O registro guardará também a conta ${esc(user.name)} e o horário. Depois de assinada, a etapa não poderá ser sobrescrita.</p>`,
    async (f) => {
      const n = clone(),
        { i } = findItem(itemId, n),
        t = i.tasks.find((t) => t.id === taskId);
      t.stage = 'Concluído';
      t.signature = {
        name: f.elements.signatureName.value.trim(),
        date: f.elements.date.value,
        confirmed: f.elements.confirmed.checked,
      };
      if (i.stage === 'Aguardando') i.stage = 'Em produção';
      if (i.stage !== 'Entregue' && i.tasks.every((t) => t.signature)) i.stage = 'Pronto';
      return save(n);
    }
  );
  $('#opsForm .modal-actions .primary').textContent = 'Concluir e registrar assinatura';
}
function openClient(id = null) {
  const c = state.clients.find((c) => c.id === id) || {},
    labels = {
      responsible: 'Responsável pelo cliente',
      document: 'CPF / CNPJ',
      phone: 'Telefone',
      whatsapp: 'WhatsApp',
      email: 'E-mail',
      instagram: 'Instagram',
      website: 'Site',
      otherContact: 'Outros contatos',
      address: 'Endereço',
    };
  opsForm(
    id ? 'Editar cliente' : 'Cadastrar cliente',
    `<div class="company-lookup">${inputField('CPF / CNPJ', 'document', c.document || '', 'text', 'maxlength="30" placeholder="00.000.000/0000-00"')}<button type="button" class="secondary" id="lookupClient">Consultar CNPJ</button></div>
    <p class="form-note">Consulta online de dados públicos. Revise antes de salvar o cliente. CPF é preenchido manualmente.</p>
    <p id="clientLookupMessage" class="form-note" role="status" aria-live="polite"></p>
    <div class="form-grid">${inputField('Cliente / empresa', 'name', c.name || '', 'text', 'required maxlength="200"')}${inputField('Nome fantasia', 'tradeName', c.tradeName || '', 'text', 'maxlength="200"')}${selectField('Situação', 'active', option('true', 'Ativo', c.active !== false) + option('false', 'Inativo', c.active === false ? 'false' : ''))}${contactFields
      .filter((k) => k !== 'document')
      .map((k) =>
        inputField(labels[k], k, c[k] || '', k === 'email' ? 'email' : 'text', 'maxlength="1000"')
      )
      .join('')}${textField('Observações', 'notes', c.notes || '')}</div>`,
    async (f) => {
      const n = clone();
      let row = n.clients.find((c) => c.id === id);
      if (!row) {
        row = { id: uid() };
        n.clients.push(row);
      }
      ['name', 'tradeName', ...contactFields, 'notes'].forEach(
        (k) => (row[k] = f.elements[k].value.trim())
      );
      row.active = f.elements.active.value === 'true';
      return save(n);
    }
  );
  opsLookup = TrameCnpj.bind({
    form: $('#opsForm'),
    button: $('#lookupClient'),
    message: $('#clientLookupMessage'),
    dialog: $('#opsDialog'),
    endpoint: '/api/clients/cnpj',
    saveLabel: 'Salvar',
  });
}
function clientHistory(id) {
  const c = state.clients.find((c) => c.id === id),
    orders = state.orders.filter(
      (o) =>
        o.clientId === id ||
        (!o.clientId && o.client.toLocaleLowerCase() === c.name.toLocaleLowerCase())
    );
  opsForm(
    'Histórico · ' + c.name,
    orders
      .map(
        (o) =>
          `<article class="ops-card"><h3>${docLabel(o)} · ${esc(o.description)}</h3><p>${dateLabel(o.entry)} · ${brl(financial(o).total)} · ${stage(o)}</p><button type="button" class="secondary" data-action="open-order" data-id="${esc(o.id)}">Abrir documento</button></article>`
      )
      .join('') ||
      '<p class="notes">Nenhum pedido vinculado. Selecione este cliente ao cadastrar ou editar o pedido.</p>',
    null
  );
  bindOperationButtons($('#opsFields'));
}
function populateClientSelector(o) {
  const f = $('#orderForm');
  let label = $('#clientSelector');
  if (!label) {
    label = document.createElement('label');
    label.id = 'clientSelector';
    label.className = 'full';
    f.querySelector('.form-grid').prepend(label);
  }
  label.innerHTML = `Cliente cadastrado<select name="clientId">${
    option('', 'Preencher manualmente', o.clientId || '') +
    (state.clients || [])
      .filter((c) => c.active !== false || c.id === o.clientId)
      .map((c) => option(c.id, c.name, o.clientId || ''))
      .join('')
  }</select>`;
  f.elements.clientId.onchange = () => {
    const c = state.clients.find((c) => c.id === f.elements.clientId.value);
    if (c) {
      f.elements.client.value = c.name;
      contactFields.forEach((k) => (f.elements[k].value = c[k] || ''));
    }
  };
}
function openEmployee(id = null) {
  const e = state.employees.find((e) => e.id === id) || {};
  opsForm(
    id ? 'Editar funcionário' : 'Cadastrar funcionário',
    `<div class="form-grid">${inputField('Nome', 'name', e.name || '', 'text', 'required maxlength="150"')}${selectField('Setor principal', 'sector', sectors.map((s) => option(s, s, e.sector)).join(''))}${selectField('Situação', 'active', option('true', 'Ativo', e.active !== false ? 'true' : '') + option('false', 'Inativo', e.active === false ? 'false' : ''))}</div>`,
    async (f) => {
      const n = clone();
      let row = n.employees.find((e) => e.id === id);
      if (!row) {
        row = { id: uid() };
        n.employees.push(row);
      }
      row.name = f.elements.name.value.trim();
      row.sector = f.elements.sector.value;
      row.active = f.elements.active.value === 'true';
      return save(n);
    }
  );
}
function itemOptions(selected) {
  return state.orders
    .filter((o) => !o.archived && o.kind !== 'quote')
    .flatMap((o) =>
      o.items.map((i) => option(i.id, `${docLabel(o)} · ${o.client} · ${i.type}`, selected))
    )
    .join('');
}
function findItem(id, data = state) {
  for (const o of data.orders) {
    const i = o.items.find((i) => i.id === id);
    if (i) return { o, i };
  }
  throw Error('Modelo não encontrado.');
}
function openTask(itemId = null, taskId = null) {
  const ref = itemId ? findItem(itemId) : null,
    t = ref?.i.tasks?.find((t) => t.id === taskId) || {};
  if (!itemOptions(itemId)) {
    toast('Adicione um modelo a um pedido antes de criar etapas.', true);
    return;
  }
  if (t.signature)
    return toast(
      'Esta etapa já foi assinada. Cadastre uma etapa complementar, se necessário.',
      true
    );
  if (t.stage === 'Concluído') return signTask(itemId, taskId);
  opsForm(
    taskId ? 'Atualizar etapa' : 'Criar etapa',
    `<div class="form-grid">${selectField('Modelo do pedido', 'itemId', itemOptions(itemId))}${selectField('Setor', 'sector', sectors.map((s) => option(s, s, t.sector)).join(''))}${selectField(
      'Funcionário responsável',
      'employeeId',
      option('', 'A definir', t.employeeId) +
        (state.employees || [])
          .filter((e) => e.active !== false || e.id === t.employeeId)
          .map((e) => option(e.id, e.name, t.employeeId))
          .join('')
    )}${inputField('Prazo da etapa', 'due', t.due || ref?.o.due || today(), 'date', 'required')}${inputField('Quantidade de peças', 'qty', t.qty || (ref && total(ref.i)) || 1, 'number', 'required min="1" step="1"')}${selectField('Andamento da etapa', 'stage', ['Pendente', 'Em andamento'].map((s) => option(s, s, t.stage || 'Pendente')).join(''))}${textField('Instruções / observações', 'notes', t.notes || '')}</div><p class="form-note">Defina quem executará esta etapa. Depois, use Concluir e assinar para registrar o trabalho realizado. O início exige layout aprovado.</p>`,
    async (f) => {
      const n = clone(),
        ref = findItem(f.elements.itemId.value, n);
      let task = ref.i.tasks.find((t) => t.id === taskId);
      if (!task) {
        task = { id: uid() };
        ref.i.tasks.push(task);
      }
      task.sector = f.elements.sector.value;
      task.employeeId = f.elements.employeeId.value;
      task.due = f.elements.due.value;
      task.qty = Number(f.elements.qty.value);
      task.stage = f.elements.stage.value;
      task.notes = f.elements.notes.value.trim();
      task.completedAt = '';
      if (task.stage !== 'Pendente' && ref.i.stage === 'Aguardando') ref.i.stage = 'Em produção';
      return save(n);
    }
  );
  if (taskId) $('#opsForm').elements.itemId.disabled = true;
}
function openStock(id = null) {
  const s = state.stock.find((s) => s.id === id) || {};
  opsForm(
    id ? 'Editar material' : 'Cadastrar material',
    `<div class="form-grid">${inputField('Material', 'name', s.name || '', 'text', 'required maxlength="200"')}${inputField('Unidade (m, un, kg…)', 'unit', s.unit || 'un', 'text', `required maxlength="20" ${id ? 'readonly' : ''}`)}${inputField('Saldo inicial', 'opening', moneyQuantity(s.openingMilli), 'text', `required inputmode="decimal" ${id ? 'readonly' : ''}`)}${inputField('Estoque mínimo', 'minimum', moneyQuantity(s.minimumMilli), 'text', 'required inputmode="decimal"')}${selectField('Situação', 'active', option('true', 'Ativo', s.active !== false ? 'true' : '') + option('false', 'Inativo', s.active === false ? 'false' : ''))}${textField('Observações', 'notes', s.notes || '')}</div><p class="form-note">Quantidades aceitam até três casas decimais, sem separador de milhares. Ajuste saldos posteriores por entrada/saída.</p>`,
    async (f) => {
      const n = clone();
      let row = n.stock.find((s) => s.id === id);
      if (!row) {
        row = {
          id: uid(),
          openingMilli: parseQuantity(f.elements.opening.value),
          unit: f.elements.unit.value.trim(),
          movements: [],
        };
        n.stock.push(row);
      }
      row.name = f.elements.name.value.trim();
      row.minimumMilli = parseQuantity(f.elements.minimum.value);
      row.notes = f.elements.notes.value.trim();
      row.active = f.elements.active.value === 'true';
      return save(n);
    }
  );
}
const moneyQuantity = (n) => ((n || 0) / 1000).toFixed(3).replace('.', ',');
function stockMove(id) {
  const s = state.stock.find((s) => s.id === id);
  opsForm(
    'Movimentar · ' + s.name,
    `<div class="form-grid">${selectField('Movimentação', 'kind', option('Entrada', 'Entrada', 'Entrada') + option('Saída', 'Saída', ''))}${inputField('Quantidade em ' + s.unit, 'qty', '1', 'text', 'required inputmode="decimal"')}${inputField('Data', 'date', today(), 'date', 'required')}${inputField('Motivo', 'reason', '', 'text', 'required maxlength="1000"')}</div>`,
    async (f) => {
      const n = clone();
      n.stock
        .find((s) => s.id === id)
        .movements.push({
          id: uid(),
          kind: f.elements.kind.value,
          qtyMilli: parseQuantity(f.elements.qty.value),
          date: f.elements.date.value,
          reason: f.elements.reason.value.trim(),
        });
      return save(n);
    }
  );
}
function stockHistory(id) {
  const s = state.stock.find((s) => s.id === id);
  opsForm(
    'Histórico · ' + s.name,
    `<p class="notes">Saldo inicial: ${formatQuantity(s.openingMilli)} ${esc(s.unit)}</p>${s.movements.map((m) => `<p>${dateLabel(m.date)} · ${esc(m.kind)} · ${formatQuantity(m.qtyMilli)} ${esc(s.unit)} · ${esc(m.reason)}</p>`).join('')}${reservationMarkup(state.reservations.filter((r) => r.stockId === id))}`,
    null
  );
  bindOperationButtons($('#opsFields'));
}
function openReservation(itemId = null) {
  const stocks = state.stock.filter((s) => s.active !== false);
  if (!stocks.length || !itemOptions(itemId)) {
    toast('Cadastre materiais e modelos de pedidos para reservar.', true);
    return;
  }
  opsForm(
    'Reservar material',
    `<div class="form-grid">${selectField('Modelo do pedido', 'itemId', itemOptions(itemId))}${selectField('Material', 'stockId', stocks.map((s) => option(s.id, `${s.name} · livre ${formatQuantity(stockValues(s).available)} ${s.unit}`, '')).join(''))}${inputField('Quantidade a reservar', 'qty', '1', 'text', 'required inputmode="decimal"')}${inputField('Data', 'date', today(), 'date', 'required')}${textField('Observação', 'note', '')}</div><p class="form-note">Reservar reduz o disponível. Consumir reduz o saldo físico; liberar devolve a disponibilidade sem consumir.</p>`,
    async (f) => {
      const n = clone(),
        ref = findItem(f.elements.itemId.value, n);
      n.reservations.push({
        id: uid(),
        stockId: f.elements.stockId.value,
        itemId: ref.i.id,
        orderId: ref.o.id,
        qtyMilli: parseQuantity(f.elements.qty.value),
        date: f.elements.date.value,
        note: f.elements.note.value.trim(),
        stage: 'Reservado',
      });
      return save(n);
    }
  );
}
function reservationMarkup(rows) {
  return (
    rows
      .map((r) => {
        const s = state.stock.find((s) => s.id === r.stockId),
          o = state.orders.find((o) => o.id === r.orderId);
        return `<article class="ops-card"><div class="section-heading"><h3>${esc(s?.name || 'Material')} · ${formatQuantity(r.qtyMilli)} ${esc(s?.unit || '')}</h3><span class="badge">${esc(r.stage)}</span></div><p>${o ? docLabel(o) : ''} · ${esc(o?.client || '')} · ${esc(r.note || '')}</p>${r.stage === 'Reservado' ? `<div class="detail-actions"><button class="secondary" data-action="consume-reservation" data-id="${esc(r.id)}">Consumir material</button><button class="secondary" data-action="release-reservation" data-id="${esc(r.id)}">Liberar reserva</button></div>` : ''}</article>`;
      })
      .join('') || '<p class="notes">Nenhuma reserva nesta visualização.</p>'
  );
}
function openInstallments(orderId) {
  const o = state.orders.find((o) => o.id === orderId),
    unallocated = (o.payments || [])
      .filter((p) => !p.voided && !p.installmentId)
      .reduce((n, p) => n + p.amountCents, 0),
    available =
      financial(o).total -
      unallocated -
      (o.installments || []).filter((p) => !p.cancelled).reduce((n, p) => n + p.amountCents, 0);
  if (available <= 0) {
    toast('Todo o valor disponível já foi recebido ou programado em parcelas.', true);
    return;
  }
  opsForm(
    'Programar parcelas · ' + docLabel(o),
    `<p class="form-note">Valor ainda não programado: ${brl(available)}. Recebimentos anteriores sem parcela já foram descontados.</p><div class="form-grid">${inputField('Valor total a programar (R$)', 'amount', moneyInput(available), 'text', 'required inputmode="decimal"')}${inputField('Quantidade de parcelas', 'count', 1, 'number', 'required min="1" max="24" step="1"')}${inputField('Primeiro vencimento', 'due', o.due, 'date', 'required')}${inputField('Intervalo entre parcelas (dias)', 'interval', 30, 'number', 'required min="1" max="365" step="1"')}</div>`,
    async (f) => {
      const n = clone(),
        order = n.orders.find((x) => x.id === orderId),
        amount = parseMoney(f.elements.amount.value),
        count = Number(f.elements.count.value),
        interval = Number(f.elements.interval.value);
      if (!Number.isInteger(count) || count < 1 || count > 24 || amount < count)
        throw Error('Confira a quantidade de parcelas e o valor.');
      const base = Math.floor(amount / count),
        remainder = amount % count;
      for (let k = 0; k < count; k++) {
        const d = new Date(f.elements.due.value + 'T12:00:00');
        d.setDate(d.getDate() + k * interval);
        const due = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
        order.installments.push({
          id: uid(),
          label: `Parcela ${k + 1}/${count}`,
          due,
          amountCents: base + (k === count - 1 ? remainder : 0),
          cancelled: false,
        });
      }
      return save(n);
    }
  );
}
function editInstallment(orderId, partId) {
  const o = state.orders.find((o) => o.id === orderId),
    p = o.installments.find((p) => p.id === partId);
  opsForm(
    'Editar parcela',
    `<div class="form-grid">${inputField('Identificação', 'label', p.label, 'text', 'required maxlength="150"')}${inputField('Vencimento', 'due', p.due, 'date', 'required')}${inputField('Valor da parcela (R$)', 'amount', moneyInput(p.amountCents), 'text', 'required inputmode="decimal"')}${selectField('Situação', 'cancelled', option('false', 'Ativa', p.cancelled ? '' : 'false') + option('true', 'Cancelada', p.cancelled ? 'true' : ''))}</div><p class="form-note">Uma parcela com recebimentos válidos não pode ser cancelada. O histórico permanece preservado.</p>`,
    async (f) => {
      const n = clone(),
        p = n.orders.find((o) => o.id === orderId).installments.find((p) => p.id === partId);
      p.label = f.elements.label.value.trim();
      p.due = f.elements.due.value;
      p.amountCents = parseMoney(f.elements.amount.value);
      p.cancelled = f.elements.cancelled.value === 'true';
      return save(n);
    }
  );
}
function setupPaymentParts(o, partId = '') {
  const f = $('#paymentForm');
  let label = $('#paymentPartLabel');
  if (!label) {
    label = document.createElement('label');
    label.id = 'paymentPartLabel';
    label.className = 'full';
    f.querySelector('.form-grid').prepend(label);
  }
  const parts = (o.installments || []).filter((p) => !p.cancelled && installmentBalance(o, p) > 0);
  label.innerHTML = `Parcela<select name="installmentId" ${parts.length ? 'required' : ''}>${parts.length ? option('', 'Selecione a parcela', partId) : option('', 'Sem parcela programada', '')}${parts.map((p) => option(p.id, `${p.label} · saldo ${brl(installmentBalance(o, p))} · ${dateLabel(p.due)}`, partId)).join('')}</select>`;
  f.elements.installmentId.onchange = () => {
    const p = parts.find((p) => p.id === f.elements.installmentId.value);
    if (p) f.elements.amount.value = moneyInput(installmentBalance(o, p));
  };
  if (partId) {
    f.elements.installmentId.value = partId;
    const p = parts.find((p) => p.id === partId);
    if (p) f.elements.amount.value = moneyInput(installmentBalance(o, p));
  }
}
function receivePart(orderId, partId) {
  openDetail(orderId);
  $('#addPayment').click();
  setupPaymentParts(
    state.orders.find((o) => o.id === orderId),
    partId
  );
}
function openDelivery(itemId) {
  const { o, i } = findItem(itemId),
    d = deliveredSizes(i);
  opsForm(
    'Entregar por tamanho · ' + i.type,
    `<p class="form-note">${docLabel(o)} · ${esc(o.client)}. O modelo precisa estar pronto e com layout aprovado.</p><div class="sizes">${Object.entries(
      i.sizes
    )
      .filter(([, n]) => n > 0)
      .map(
        ([s, n]) =>
          `<label>${esc(s)}<input type="number" data-delivery-size="${esc(s)}" min="0" max="${n - (d[s] || 0)}" value="0" step="1"><small>Faltam ${n - (d[s] || 0)}</small></label>`
      )
      .join(
        ''
      )}</div><div class="form-grid">${inputField('Data da entrega', 'date', today(), 'date', 'required')}${inputField('Recebido por', 'receiver', o.responsible || '', 'text', 'required maxlength="150"')}${textField('Observações', 'notes', '')}</div>`,
    async (f) => {
      const n = clone(),
        ref = findItem(itemId, n);
      ref.i.deliveries.push({
        id: uid(),
        date: f.elements.date.value,
        receiver: f.elements.receiver.value.trim(),
        notes: f.elements.notes.value.trim(),
        sizes: Object.fromEntries(
          $$('[data-delivery-size]').map((e) => [e.dataset.deliverySize, Number(e.value || 0)])
        ),
        voided: false,
      });
      const delivered = deliveredSizes(ref.i);
      if (Object.entries(ref.i.sizes).every(([s, n]) => (delivered[s] || 0) === n))
        ref.i.stage = 'Entregue';
      return save(n);
    }
  );
}
function voidDelivery(itemId, deliveryId) {
  opsForm(
    'Anular entrega',
    textField('Motivo', 'reason', '') +
      '<p class="form-note">A entrega ficará no histórico. Isto corrige o registro e não registra devolução física ou reposição de estoque.</p>',
    async (f) => {
      const reason = f.elements.reason.value.trim();
      if (!reason) throw Error('Informe o motivo.');
      const n = clone(),
        { i } = findItem(itemId, n);
      const d = i.deliveries.find((d) => d.id === deliveryId);
      d.voided = true;
      d.voidReason = reason;
      if (i.stage === 'Entregue') i.stage = 'Pronto';
      return save(n);
    }
  );
}
function populateTechnicalFields(i) {
  for (const name of techniqueNames) {
    const t = techniquesOf(i || {}).find((t) => t.type === name);
    const body = $(`[data-description="${name}"]`).closest('.tech-grid');
    body.insertAdjacentHTML(
      'beforeend',
      specFields[name]
        .map(
          ([k, label]) =>
            `<label>${esc(label)}<input data-spec="${name}:${k}" value="${esc(t?.specs?.[k] || '')}" maxlength="500"></label>`
        )
        .join('')
    );
  }
}
function readTechnicalFields(name) {
  return Object.fromEntries(
    specFields[name].map(([k]) => [k, $(`[data-spec="${name}:${k}"]`)?.value.trim() || ''])
  );
}
function technicalMarkup(i) {
  return techniquesOf(i)
    .map((t) => {
      const entries = (specFields[t.type] || []).filter(([k]) => t.specs?.[k]);
      return entries.length
        ? `<div class="technical-spec"><b>Ficha técnica · ${esc(t.type)}</b>${entries.map(([k, label]) => `<p>${esc(label)}: ${esc(t.specs[k])}</p>`).join('')}</div>`
        : '';
    })
    .join('');
}
async function readImage(file) {
  if (!file) return '';
  if (file.size > 5 * 1024 * 1024 || !['image/png', 'image/jpeg', 'image/webp'].includes(file.type))
    throw Error('Use uma imagem PNG, JPEG ou WebP de até 5 MB.');
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(r.result);
    r.onerror = () => reject(Error('Falha ao ler o comprovante.'));
    r.readAsDataURL(file);
  });
}
function openApproval(itemId) {
  const { o, i } = findItem(itemId);
  approvalFile = '';
  approvalReading = false;
  opsForm(
    'Registrar aprovação do layout',
    `<p class="form-note">${docLabel(o)} · ${esc(i.type)} · versão ${i.layoutVersion || 1}. Registre a confirmação efetiva do cliente.</p><div class="form-grid">${inputField('Nome de quem aprovou', 'name', o.responsible || '', 'text', 'required maxlength="150"')}${inputField('Data da aprovação', 'date', today(), 'date', 'required')}${selectField('Canal da aprovação', 'channel', ['WhatsApp', 'E-mail', 'Presencial', 'Telefone', 'Outro'].map((s) => option(s, s, 'WhatsApp')).join(''))}${textField('Evidência / referência da conversa', 'note', '')}<label class="full">Comprovante opcional (imagem até 5 MB)<input id="evidenceFile" type="file" accept="image/png,image/jpeg,image/webp"></label></div>`,
    async (f) => {
      if (approvalReading) throw Error('Aguarde a leitura do comprovante.');
      const n = clone(),
        { i } = findItem(itemId, n);
      i.approved = true;
      i.approvalEvidence = {
        name: f.elements.name.value.trim(),
        date: f.elements.date.value,
        channel: f.elements.channel.value,
        note: f.elements.note.value.trim(),
        attachment: approvalFile,
        fileName: $('#evidenceFile').files[0]?.name || '',
      };
      return save(n);
    }
  );
  $('#evidenceFile').onchange = async (e) => {
    approvalReading = true;
    try {
      approvalFile = await readImage(e.target.files[0]);
    } catch (err) {
      approvalFile = '';
      e.target.value = '';
      toast(err.message, true);
    } finally {
      approvalReading = false;
    }
  };
}
function detailOperations(o) {
  const parts = o.installments || [];
  return `<section class="operations-detail"><h2>Operação do pedido</h2>${o.kind !== 'quote' ? `<div class="section-heading"><h3>Parcelas e vencimentos</h3><button class="secondary" data-action="new-installments" data-id="${esc(o.id)}" ${o.archived ? 'disabled' : ''}>＋ Programar parcelas</button></div>${parts.map((p) => `<div class="ops-inline"><div><strong>${esc(p.label)} · ${brl(p.amountCents)}</strong><small>${dateLabel(p.due)} · ${installmentStatus(o, p)} · saldo ${brl(installmentBalance(o, p))}</small></div><button class="secondary" data-action="edit-installment" data-id="${esc(o.id)}" data-item="${esc(p.id)}" ${o.archived ? 'disabled' : ''}>Editar</button><button class="primary" data-action="receive-part" data-id="${esc(o.id)}" data-item="${esc(p.id)}" ${o.archived || p.cancelled || installmentBalance(o, p) <= 0 ? 'disabled' : ''}>Receber</button></div>`).join('') || '<p class="notes">Nenhuma parcela programada. Registre valores previstos separadamente dos recebidos.</p>'}` : ''}${o.items
    .map((i) => {
      const delivered = deliveredSizes(i),
        count = Object.values(delivered).reduce((s, n) => s + n, 0);
      return `<article class="ops-item"><h3>${esc(i.type)} · operação</h3>${technicalMarkup(i)}<div class="section-heading"><h4>Layout · versão ${i.layoutVersion || 1}</h4><span class="badge ${i.approved ? 'good' : 'pending'}">${i.approved ? 'Aprovado' : 'Pendente'}</span></div>${i.approvalEvidence?.name ? `<p class="notes">${esc(i.approvalEvidence.name)} · ${dateLabel(i.approvalEvidence.date)} · ${esc(i.approvalEvidence.channel)}<br>${esc(i.approvalEvidence.note || '')}</p>${i.approvalEvidence.attachment ? `<button class="secondary" data-action="current-evidence" data-id="${esc(i.id)}">Ver comprovante</button>` : ''}` : '<p class="hint">Aprovações antigas podem não ter comprovante registrado.</p>'}${(i.layoutHistory || []).map((h) => `<div class="ops-inline"><span>Versão ${h.version} · ${h.approved ? 'aprovada' : 'pendente'} · ${esc(h.evidence?.name || 'Sem aprovador registrado')}</span>${h.image ? `<button class="secondary" data-action="old-layout" data-id="${esc(i.id)}" data-item="${esc(h.id)}">Ver layout anterior</button>` : '<small>Versão sem imagem</small>'}${h.evidence?.attachment ? `<button class="secondary" data-action="old-evidence" data-id="${esc(i.id)}" data-item="${esc(h.id)}">Ver comprovante</button>` : ''}</div>`).join('') || '<p class="hint">Nenhuma substituição de layout registrada nesta versão do Tramê.</p>'}${
        o.kind !== 'quote'
          ? `<div class="detail-actions"><button class="secondary" data-action="new-task" data-item="${esc(i.id)}" ${o.archived ? 'disabled' : ''}>＋ Etapa de produção</button><button class="secondary" data-action="new-reservation" data-item="${esc(i.id)}" ${o.archived ? 'disabled' : ''}>＋ Reservar material</button><button class="primary" data-action="new-delivery" data-item="${esc(i.id)}" ${o.archived || count >= total(i) ? 'disabled' : ''}>Registrar entrega</button></div><h4>Etapas</h4>${
              TrameDomain.productionTasks(i)
                .map((t) => productionTaskRow(o, i, t))
                .join('') || '<p class="hint">Prepare as etapas da OS na aba Produção.</p>'
            }<h4>Entrega por tamanho · ${count}/${total(i)} peças</h4><p class="notes">${Object.entries(
              i.sizes
            )
              .filter(([, n]) => n)
              .map(([s, n]) => `${esc(s)}: ${delivered[s] || 0}/${n} entregues`)
              .join(' · ')}</p>${(i.deliveries || [])
              .map(
                (d) =>
                  `<div class="ops-inline"><div><strong>${dateLabel(d.date)} · ${esc(d.receiver)} ${d.voided ? '· ANULADA' : ''}</strong><small>${Object.entries(
                    d.sizes
                  )
                    .filter(([, n]) => n)
                    .map(([s, n]) => `${esc(s)}: ${n}`)
                    .join(
                      ' · '
                    )} ${d.voided ? '· ' + esc(d.voidReason) : ''}</small></div>${!d.voided ? `<button class="secondary" data-action="void-delivery" data-id="${esc(d.id)}" data-item="${esc(i.id)}" ${o.archived ? 'disabled' : ''}>Anular entrega</button>` : ''}</div>`
              )
              .join(
                ''
              )}<h4>Materiais do modelo</h4>${reservationMarkup(state.reservations.filter((r) => r.itemId === i.id))}`
          : ''
      }</article>`;
    })
    .join('')}</section>`;
}
function arrangeOrderOperations(o, expanded = []) {
  const source = document.createElement('div');
  source.innerHTML = detailOperations(o);
  const operations = source.querySelector('.operations-detail');
  const cards = $$('#detailContent>.item-card');
  operations.querySelectorAll('.ops-item').forEach((panel, index) => {
    panel.querySelector('h3')?.remove();
    panel.querySelector('.section-heading .badge')?.remove();
    const details = document.createElement('details');
    details.className = 'item-operations';
    details.dataset.itemId = o.items[index].id;
    details.open = expanded.includes(o.items[index].id) || (o.kind !== 'quote' && !done(o));
    const summary = document.createElement('summary');
    summary.textContent =
      o.kind === 'quote'
        ? 'Ficha técnica e histórico do layout'
        : 'Etapas e assinaturas da OS · entregas e histórico';
    details.append(summary, panel);
    cards[index]?.append(details);
  });
  operations.querySelector(':scope>h2')?.remove();
  if (o.kind !== 'quote') $('#detailContent .commercial').append(operations);
}
function bindOperationButtons(scope) {
  scope.querySelectorAll('[data-action]').forEach(
    (b) =>
      (b.onclick = async () => {
        const a = b.dataset.action,
          id = b.dataset.id,
          item = b.dataset.item;
        try {
          if (a === 'new-client') openClient();
          if (a === 'edit-client') openClient(id);
          if (a === 'client-history') clientHistory(id);
          if (a === 'new-employee') openEmployee();
          if (a === 'edit-employee') openEmployee(id);
          if (a === 'new-task') openTask(item);
          if (a === 'edit-task') openTask(item, id);
          if (a === 'sign-task') signTask(item, id);
          if (a === 'prepare-production') await prepareProduction(id);
          if (a === 'start-task') {
            const n = clone(),
              { i } = findItem(item, n);
            i.tasks.find((t) => t.id === id).stage = 'Em andamento';
            if (i.stage === 'Aguardando') i.stage = 'Em produção';
            await save(n);
          }
          if (a === 'open-order') openOpsOrder(id);
          if (a === 'edit-order') openOrder(id);
          if (a === 'new-stock') openStock();
          if (a === 'edit-stock') openStock(id);
          if (a === 'stock-move') stockMove(id);
          if (a === 'stock-history') stockHistory(id);
          if (a === 'new-reservation') openReservation(item);
          if (a === 'consume-reservation' || a === 'release-reservation') {
            const n = clone();
            n.reservations.find((r) => r.id === id).stage =
              a === 'consume-reservation' ? 'Consumido' : 'Liberado';
            await save(n);
          }
          if (a === 'new-installments') openInstallments(id);
          if (a === 'edit-installment') editInstallment(id, item);
          if (a === 'receive-part') receivePart(id, item);
          if (a === 'new-delivery') openDelivery(item);
          if (a === 'void-delivery') voidDelivery(item, id);
          if (['current-evidence', 'old-layout', 'old-evidence'].includes(a)) {
            const { i } = findItem(id),
              h = i.layoutHistory.find((h) => h.id === item),
              image =
                a === 'current-evidence'
                  ? i.approvalEvidence.attachment
                  : a === 'old-layout'
                    ? h.image
                    : h.evidence.attachment;
            $('#largeImage').src = image;
            $('#imageDialog').showModal();
          }
        } catch (err) {
          toast(err.message, true);
        }
      })
  );
}
function bindOperations(o) {
  $$('.ops-item').forEach((section, index) => {
    const i = o.items[index];
    if (i.approvalHistory?.length)
      section.insertAdjacentHTML(
        'beforeend',
        `<h4>Histórico das aprovações</h4>${i.approvalHistory.map((e) => `<div class="ops-inline"><div><strong>V${e.version} · ${esc(e.status)}</strong><small>${esc(e.evidence.name)} · ${dateLabel(e.evidence.date)} · ${esc(e.evidence.channel || '')}</small></div>${e.evidence.attachment ? `<button class="secondary" data-approval-event="${esc(e.id)}" data-approval-item="${esc(i.id)}">Ver comprovante registrado</button>` : ''}</div>`).join('')}`
      );
  });
  bindOperationButtons($('#detailContent'));
  $$('[data-approval-event]').forEach(
    (b) =>
      (b.onclick = () => {
        const { i } = findItem(b.dataset.approvalItem),
          e = i.approvalHistory.find((e) => e.id === b.dataset.approvalEvent);
        $('#largeImage').src = e.evidence.attachment;
        $('#imageDialog').showModal();
      })
  );
  $('#addPayment')?.addEventListener('click', () => setupPaymentParts(o));
}
function setupOperations() {
  $('.content').insertAdjacentHTML('afterbegin', '<section id="opsWorkspace" hidden></section>');
  document.body.insertAdjacentHTML(
    'beforeend',
    '<dialog id="opsDialog" class="wide"><form id="opsForm"><div class="modal-top"><h2 id="opsTitle"></h2><button type="button" id="opsClose" class="icon" aria-label="Fechar formulário">×</button></div><div id="opsFields"></div><div class="modal-actions"><button type="button" id="opsCancel" class="secondary">Fechar</button><button class="primary">Salvar</button></div></form></dialog>'
  );
  $('#opsClose').onclick = $('#opsCancel').onclick = () => $('#opsDialog').close();
  $('#opsForm').onsubmit = async (e) => {
    e.preventDefault();
    try {
      if (opsSubmit && (await opsSubmit(e.target))) {
        $('#opsDialog').close();
        toast('Registro salvo.');
      }
    } catch (err) {
      toast(err.message, true);
    }
  };
  for (const [id, name] of [
    ['navOrders', 'orders'],
    ['navQuotes', 'quotes'],
    ['navClients', 'clients'],
    ['navQueue', 'queue'],
    ['navStock', 'stock'],
    ['navBilling', 'billing'],
    ['navEmployees', 'employees'],
  ]) {
    const b = $('#' + id);
    b.dataset.view = name;
    if (!['orders', 'quotes'].includes(name))
      b.onclick = () => {
        view = name;
        render();
      };
  }
  $('#refreshData').onclick = async () => {
    if ($$('dialog').some((d) => d.open)) {
      toast('Feche o formulário atual antes de atualizar os dados.', true);
      return;
    }
    try {
      await TrameAccess.refreshSession();
      state = await TrameAccess.request('/api/state');
      render();
      $('#saveState').textContent = '● Atualizado';
    } catch (error) {
      toast(error.message, true);
    }
  };
}
