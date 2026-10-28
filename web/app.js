'use strict';
const $ = (s) => document.querySelector(s),
  $$ = (s) => [...document.querySelectorAll(s)];
const esc = (s) =>
  String(s ?? '').replace(
    /[&<>"']/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]
  );
const uid = () => crypto.randomUUID();
const today = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};
const addDays = (n) => {
  const d = new Date();
  d.setDate(d.getDate() + n);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};
const dateLabel = (s) =>
  new Date(s + 'T12:00:00').toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' });
const daysLeft = (o) =>
  Math.round((new Date(o.due + 'T12:00:00') - new Date(today() + 'T12:00:00')) / 86400000);
const total = TrameDomain.quantity;
const done = (o) => o.items.length > 0 && o.items.every((i) => i.stage === 'Entregue');
const pending = (o) => o.items.filter((i) => !i.approved).length;
const stage = (o) =>
  o.kind === 'quote'
    ? 'Orçamento'
    : done(o)
      ? 'Entregue'
      : o.items.length && o.items.every((i) => ['Pronto', 'Entregue'].includes(i.stage))
        ? 'Pronto'
        : o.items.some((i) => i.stage !== 'Aguardando')
          ? 'Em produção'
          : 'Aguardando';
let state,
  filter = 'active',
  currentOrder = null,
  editOrder = null,
  editItem = null,
  itemImage = '',
  imageReading = false,
  busy = false;
function toast(message, error = false) {
  const openDialogs = [...document.querySelectorAll('dialog[open]')];
  const host = openDialogs[openDialogs.length - 1] || document.body;
  host.appendChild($('#toast'));
  $('#toast').textContent = message;
  $('#toast').className = 'visible' + (error ? ' error' : '');
  clearTimeout(window.toastTimer);
  window.toastTimer = setTimeout(() => ($('#toast').className = ''), 5500);
}
async function save(next) {
  if (busy) {
    toast('Aguarde o salvamento atual.', true);
    return false;
  }
  busy = true;
  $('#saveState').textContent = '● Salvando…';
  try {
    await TrameAccess.refreshSession();
    const changes = TrameAccess.changes(state, next);
    if (!changes.length) {
      $('#saveState').textContent = '● Dados atualizados';
      return true;
    }
    const d = await TrameAccess.request('/api/changes', { changes });
    state = d;
    render();
    TrameAccess.permissions();
    if ($('#detailDialog').open) renderDetail();
    $('#saveState').textContent = '● Salvo neste computador';
    return true;
  } catch (e) {
    toast(e.message, true);
    $('#saveState').textContent = '● Não salvo';
    return false;
  } finally {
    busy = false;
  }
}

const clone = () => structuredClone(state);
function dueBadge(o) {
  if (done(o)) return '<span class="badge good">Concluído</span>';
  const n = daysLeft(o);
  return n < 0
    ? `<span class="badge late">${-n} dia${n === -1 ? '' : 's'} em atraso</span>`
    : n === 0
      ? '<span class="badge pending">Entrega hoje</span>'
      : n <= state.warningDays
        ? `<span class="badge pending">Em ${n} dia${n === 1 ? '' : 's'}</span>`
        : `<span class="date-small">Em ${n} dias</span>`;
}
function orderRow(order) {
  const values = financial(order);
  const awaitingApproval = pending(order);
  const quantity = order.items.reduce((count, item) => count + total(item), 0);
  const initials = order.client
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((word) => word[0])
    .join('')
    .toUpperCase();
  const paymentClass = { Pago: 'good', 'Parcialmente pago': 'pending' }[values.status] || '';
  let approval = '<span class="badge good">Todos aprovados</span>';
  if (!order.items.length) approval = '<span class="badge">Sem modelos</span>';
  else if (awaitingApproval)
    approval = `<span class="badge pending">${awaitingApproval} pendente${awaitingApproval === 1 ? '' : 's'}</span>`;

  return `<tr>
    <td><div class="client">
      <div class="avatar">${esc(initials)}</div>
      <div><strong>${docLabel(order)} · ${esc(order.client)}</strong><small>${esc(order.description)}</small></div>
    </div></td>
    <td>${quantity}<span class="date-small">${order.items.length} modelo${order.items.length === 1 ? '' : 's'}</span></td>
    <td>${dateLabel(order.due)} ${new Date(order.due + 'T12:00:00').getFullYear()}<div>${dueBadge(order)}</div></td>
    <td>${approval}</td>
    <td>${brl(values.total)}<div><span class="badge ${paymentClass}">${order.kind === 'quote' ? 'Orçamento' : values.status}</span></div></td>
    <td><span class="badge ${done(order) ? 'good' : ''}">${stage(order)}</span></td>
    <td><div class="order-row-actions"><button class="secondary" data-edit-order="${esc(order.id)}" ${order.archived ? 'disabled' : ''}>Editar</button><button class="secondary" data-delete-scope="orders" data-delete-id="${esc(order.id)}" data-delete-name="${esc(docLabel(order) + ' · ' + order.client)}">Excluir</button><button class="open-btn" data-open="${esc(order.id)}" aria-label="Abrir ${docLabel(order)} de ${esc(order.client)}">↗</button></div></td>
  </tr>`;
}

function render() {
  TrameAccess.permissions();
  if (renderOperationsView()) {
    TrameAccess.permissions();
    return;
  }
  const active = state.orders.filter((o) => o.kind !== 'quote' && !o.archived && !done(o));
  renderCommerceHeader();
  const stats = [
    ['Pedidos em aberto', active.length, 'Acompanhamento ativo', '▦', ''],
    [
      'Aguardando aprovação',
      active.reduce((n, o) => n + pending(o), 0),
      'Modelos para conferir',
      '◷',
      'warn',
    ],
    [
      'Próximos do prazo',
      active.filter((o) => daysLeft(o) >= 0 && daysLeft(o) <= state.warningDays).length,
      `Entrega em até ${state.warningDays} dias`,
      '↗',
      'warn',
    ],
    [
      'Pedidos atrasados',
      active.filter((o) => daysLeft(o) < 0).length,
      'Precisam de atenção',
      '!',
      'late',
    ],
  ];
  $('#stats').innerHTML = (view === 'quotes' ? quoteStats() : stats)
    .map(
      ([label, n, sub, icon, cls]) =>
        `<div class="stat ${cls}"><span>${label}</span><span class="stat-icon">${icon}</span><strong>${String(n).padStart(2, '0')}</strong><small>${sub}</small></div>`
    )
    .join('');
  $('#sideCount').textContent = active.length;
  $('#warningDays').value = state.warningDays;
  const q = $('#search').value.trim();
  const searchedNumber = TrameDomain.orderNumberQuery(q);
  const orders = state.orders
    .filter((o) => {
      if (searchedNumber !== null) return (view === 'quotes') === (o.kind === 'quote');
      if (view === 'quotes' && filter === 'converted')
        return !o.archived && o.kind === 'order' && !!o.quoteNumber;
      if ((view === 'quotes') !== (o.kind === 'quote')) return false;
      if (filter === 'archive') return o.archived;
      if (o.archived) return false;
      if (filter === 'done') return done(o);
      if (filter === 'all') return true;
      if (done(o)) return false;
      if (filter === 'pending') return pending(o) > 0;
      if (filter === 'urgent') return daysLeft(o) <= state.warningDays;
      return true;
    })
    .filter((o) => TrameDomain.matchesOrder(o, q))
    .filter(
      (o) =>
        searchedNumber !== null ||
        view === 'quotes' ||
        $('#paymentFilter').value === 'all' ||
        financial(o).status === $('#paymentFilter').value
    )
    .sort((a, b) => a.due.localeCompare(b.due));
  $('#totalCount').textContent = orders.length;
  $$('#tabs button').forEach((b) => b.classList.toggle('selected', b.dataset.filter === filter));
  if (!orders.length) {
    const hasDocuments = state.orders.some((o) => (view === 'quotes') === (o.kind === 'quote'));
    $('#orderList').innerHTML =
      `<div class="empty"><div class="empty-symbol">◎</div><h3>${hasDocuments ? 'Nenhum resultado para estes filtros' : view === 'quotes' ? 'Nenhum orçamento cadastrado' : 'Nenhum pedido cadastrado'}</h3><p>${hasDocuments ? 'Ajuste a busca ou os filtros para consultar outros registros.' : view === 'quotes' ? 'Use Novo orçamento para começar.' : 'Use Novo pedido para começar.'}</p></div>`;
    return;
  }
  $('#orderList').innerHTML = `<div class="table-wrap"><table>
      <thead><tr><th>Cliente / Pedido</th><th>Peças</th><th>Prazo de entrega</th><th>Layout</th><th>Valor / pagamento</th><th>Andamento</th><th></th></tr></thead>
      <tbody>${orders.map(orderRow).join('')}</tbody>
    </table></div>`;
  $$('[data-edit-order]').forEach((b) => (b.onclick = () => openOrder(b.dataset.editOrder)));
  $$('[data-open]').forEach((b) => (b.onclick = () => openDetail(b.dataset.open)));
}
function openOrder(id = null) {
  editOrder = id;
  const o = state.orders.find((o) => o.id === id) || {
    client: '',
    description: '',
    entry: today(),
    due: addDays(7),
    notes: '',
  };
  const f = $('#orderForm');
  f.reset();
  ['client', 'description', 'entry', 'due', 'notes'].forEach(
    (k) => (f.elements[k].value = o[k] || '')
  );
  populateOrderCommerce(o, id);
  $('#orderTitle').textContent = id
    ? o.kind === 'quote'
      ? 'Editar orçamento'
      : 'Editar pedido'
    : view === 'quotes'
      ? 'Novo orçamento'
      : 'Novo pedido';
  if (id) $('#orderTitle').textContent += ' · ' + docLabel(o);
  $('#orderDialog').showModal();
}
$('#orderForm').onsubmit = async (e) => {
  e.preventDefault();
  const f = e.target;
  if (f.elements.due.value < f.elements.entry.value) {
    toast('O prazo não pode ser anterior à entrada.', true);
    return;
  }
  const n = clone();
  let o = n.orders.find((o) => o.id === editOrder);
  const isNew = !o;
  if (!o) {
    o = {
      id: uid(),
      items: [],
      archived: false,
      kind: view === 'quotes' ? 'quote' : 'order',
      payments: [],
    };
    n.orders.push(o);
  }
  ['client', 'description', 'entry', 'due', 'notes'].forEach(
    (k) => (o[k] = f.elements[k].value.trim())
  );
  try {
    readOrderCommerce(o, f);
  } catch (err) {
    toast(err.message, true);
    return;
  }
  if (await save(n)) {
    $('#orderDialog').close();
    if (isNew) openDetail(o.id);
    toast(o.kind === 'quote' ? 'Orçamento salvo.' : 'Pedido salvo.');
  }
};
function openDetail(id) {
  currentOrder = id;
  renderDetail();
  if (!$('#detailDialog').open) $('#detailDialog').showModal();
}
function renderDetail() {
  const o = state.orders.find((o) => o.id === currentOrder);
  if (!o) return;
  const expanded = $$('#detailContent details[open]').map((d) => d.dataset.itemId);
  const detailScroll = $('#detailDialog').scrollTop;
  $('#detailContent').innerHTML =
    `<div class="modal-top"><div><div class="eyebrow">${docLabel(o)} ${o.archived ? '· ARQUIVADO' : ''}</div><h2>${esc(o.client)}</h2></div><button class="icon" id="closeDetail" aria-label="Fechar detalhes">×</button></div><p class="notes">${esc(o.description)}</p><div class="detail-meta"><div><small>Entrada</small>${dateLabel(o.entry)}</div><div><small>Entrega</small>${dateLabel(o.due)} ${o.due.slice(0, 4)}</div><div><small>Situação</small>${stage(o)}</div><div><small>Quantidade total</small>${o.items.reduce((n, i) => n + total(i), 0)} peças</div><div>${dueBadge(o)}</div></div>${o.notes ? `<p class="notes">${esc(o.notes)}</p>` : ''}<div class="detail-actions"><button class="primary" id="addItem" ${o.archived ? 'disabled' : ''}>＋ Adicionar modelo</button><button class="secondary" id="editOrder">Editar pedido</button><button class="secondary" data-delete-scope="orders" data-delete-id="${esc(o.id)}" data-delete-name="${esc(docLabel(o) + ' · ' + o.client)}">Excluir</button><button class="secondary" id="archiveOrder">${o.archived ? 'Restaurar pedido' : 'Arquivar pedido'}</button></div>${detailCommerce(o)}<h2>Modelos de peças <span>${o.items.length}</span></h2>${
      o.items.length
        ? o.items
            .map(
              (i) =>
                `<article class="item-card"><div class="item-head"><h2>${esc(i.type)} <span>${total(i)} peças</span></h2><span class="badge ${i.approved ? 'good' : 'pending'}">${i.approved ? 'Layout aprovado' : 'Aguardando aprovação'}</span></div><div class="item-body"><button class="layout-thumb" data-image="${esc(i.id)}" ${!i.image ? 'disabled' : ''}>${i.image ? `<img src="${esc(i.image)}" alt="Layout de ${esc(i.type)}">` : 'Sem imagem de layout'}</button><div><p>${esc(i.description) || 'Sem descrição'}</p><p><b>Tecido:</b> ${esc(i.fabric) || '—'} &nbsp; <b>Cor:</b> ${esc(i.color) || '—'}</p><p><b>Grade:</b> ${Object.entries(
                  i.sizes
                )
                  .filter(([, n]) => n > 0)
                  .map(([s, n]) => `${esc(s)}: ${n}`)
                  .join(
                    ' · '
                  )}</p>${i.madeToMeasure || i.sizes['Sob medida'] ? `<p class="preserve"><b>Sob medida:</b> ${esc(i.measurements)}</p>` : ''}${techniqueDescription(i)}<p><b>Preço:</b> ${brl(itemFinancial(i).unit)} / peça · <b>Total:</b> ${brl(itemFinancial(i).total)}</p>${i.customizations ? `<p><b>Personalizações:</b> ${esc(i.customizations)}</p>` : ''}${i.notes ? `<p class="notes">${esc(i.notes)}</p>` : ''}</div></div><div class="item-controls"><button class="${i.approved ? 'secondary' : 'primary'}" data-approve="${esc(i.id)}" ${o.archived || i.stage !== 'Aguardando' ? 'disabled' : ''}>${i.approved ? 'Retirar aprovação' : 'Confirmar aprovação'}</button><select data-stage="${esc(i.id)}" aria-label="Andamento de ${esc(i.type)}" ${o.archived ? 'disabled' : ''}>${['Aguardando', 'Em produção', 'Pronto', 'Entregue'].map((s) => `<option ${i.stage === s ? 'selected' : ''} ${s === 'Entregue' || (s === 'Pronto' && i.stage !== 'Pronto' && !(i.tasks?.length && i.tasks.every((t) => t.signature))) || (s !== 'Aguardando' && (!i.approved || o.kind === 'quote')) ? 'disabled' : ''}>${s}</option>`).join('')}</select><button class="secondary" data-edit-item="${esc(i.id)}" ${o.archived ? 'disabled' : ''}>Editar modelo</button><button class="secondary" data-delete-scope="items" data-delete-id="${esc(i.id)}" data-delete-name="${esc(i.type + ' · ' + o.client)}">Excluir modelo</button></div></article>`
            )
            .join('')
        : '<div class="empty"><p>Adicione o primeiro modelo, com tecido, cor e grade de tamanhos.</p></div>'
    }`;
  arrangeOrderOperations(o, expanded);
  bindCommerce(o);
  bindOperations(o);
  $('#closeDetail').onclick = () => $('#detailDialog').close();
  $('#addItem').onclick = () => openItem();
  $('#editOrder').textContent = o.kind === 'quote' ? 'Editar orçamento' : 'Editar pedido';
  $('#archiveOrder').textContent = o.archived
    ? o.kind === 'quote'
      ? 'Restaurar orçamento'
      : 'Restaurar pedido'
    : o.kind === 'quote'
      ? 'Arquivar orçamento'
      : 'Arquivar pedido';
  $('#editOrder').onclick = () => openOrder(o.id);
  $('#archiveOrder').onclick = async () => {
    const n = clone();
    n.orders.find((x) => x.id === o.id).archived = !o.archived;
    await save(n);
  };
  $$('[data-image]').forEach(
    (b) =>
      (b.onclick = () => {
        const i = o.items.find((i) => i.id === b.dataset.image);
        $('#largeImage').src = i.image;
        $('#imageDialog').showModal();
      })
  );
  $$('[data-edit-item]').forEach((b) => (b.onclick = () => openItem(b.dataset.editItem)));
  $$('[data-approve]').forEach(
    (b) =>
      (b.onclick = async () => {
        const n = clone(),
          i = n.orders.find((x) => x.id === o.id).items.find((i) => i.id === b.dataset.approve);
        if (!i.approved) {
          openApproval(i.id);
          return;
        }
        i.approved = false;
        i.approvalEvidence = {};
        await save(n);
      })
  );
  $$('[data-stage]').forEach(
    (s) =>
      (s.onchange = async () => {
        const n = clone();
        n.orders.find((x) => x.id === o.id).items.find((i) => i.id === s.dataset.stage).stage =
          s.value;
        await save(n);
      })
  );
  $('#detailDialog').scrollTop = detailScroll;
}
function addSizeField(name, value = 0, container = $('#otherSizes'), labelText = name) {
  if (
    $$('#sizes input, #bespokeSizes input').some(
      (x) => x.dataset.size.toLowerCase() === name.toLowerCase()
    )
  )
    return toast('Este tamanho já está na grade.', true);
  const label = document.createElement('label');
  label.textContent = labelText;
  const input = document.createElement('input');
  input.type = 'number';
  input.min = 0;
  input.max = 100000;
  input.step = 1;
  input.value = value;
  input.dataset.size = name;
  input.setAttribute('aria-label', `Quantidade ${name}`);
  input.oninput = updateTotal;
  label.append(input);
  container.append(label);
}
function updateTotal() {
  updatePricePreview();
  $('#sizeTotal').textContent =
    $$('#sizes input:not(:disabled), #bespokeSizes input:not(:disabled)').reduce(
      (n, i) => n + Number(i.value || 0),
      0
    ) + ' peças';
}
function imagePreview() {
  $('#imageEditor').innerHTML = itemImage
    ? `<img src="${esc(itemImage)}" alt="Prévia do layout"><p class="hint">Salve para aplicar a imagem. Clique na imagem nos detalhes para ampliar.</p>`
    : '';
}
function openItem(id = null) {
  editItem = id;
  const o = state.orders.find((o) => o.id === currentOrder),
    i = o.items.find((i) => i.id === id);
  const f = $('#itemForm');
  f.reset();
  $('#customSize').value = '';
  $('#bespokeSizes')?.remove();
  $('#sizes').innerHTML = '';
  const sizes = i?.sizes || {};
  for (const group of TrameDomain.sizeGroups(sizes)) {
    const section = document.createElement('section');
    section.className = 'size-group';
    section.innerHTML = `<h3>${esc(group.label)}</h3><div class="sizes"></div>`;
    $('#sizes').append(section);
    for (const [size, count] of group.rows)
      addSizeField(
        size,
        count,
        section.querySelector('.sizes'),
        size.replace(group.label + ' ', '')
      );
  }
  $('#sizes').insertAdjacentHTML(
    'beforeend',
    '<div id="otherSizes" class="sizes"></div><div id="bespokeSizes" class="sizes size-group"></div>'
  );
  addSizeField('Sob medida', sizes['Sob medida'] || 0, $('#bespokeSizes'), 'Quantidade sob medida');
  $('#measurementsArea').prepend($('#bespokeSizes'));
  $('#madeToMeasure').checked = !!i?.madeToMeasure || !!sizes['Sob medida'];
  f.elements.measurements.value = i?.measurements || '';
  toggleMeasurements();
  ['type', 'description', 'fabric', 'color', 'customizations', 'notes'].forEach(
    (k) => (f.elements[k].value = i?.[k] || (k === 'type' ? 'Camiseta' : ''))
  );
  populateItemCommerce(i);
  itemImage = i?.image || '';
  imageReading = false;
  $('#layoutFile').disabled = !!i && i.stage !== 'Aguardando';
  $('#itemTitle').textContent = id ? 'Editar modelo' : 'Adicionar modelo';
  imagePreview();
  updateTotal();
  $('#itemDialog').showModal();
}
function toggleMeasurements() {
  const enabled = $('#madeToMeasure').checked;
  $('#measurementsArea').hidden = !enabled;
  $('#bespokeSizes').hidden = !enabled;
  $('#bespokeSizes input').disabled = !enabled;
  $('#itemForm').elements.measurements.required = enabled;
  updateTotal();
}
$('#madeToMeasure').onchange = toggleMeasurements;
$('#addSize').onclick = () => {
  const s = $('#customSize').value.trim();
  if (s) {
    addSizeField(s);
    $('#customSize').value = '';
  }
};
$('#layoutFile').onchange = async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  if (
    file.size > 5 * 1024 * 1024 ||
    !['image/png', 'image/jpeg', 'image/webp'].includes(file.type)
  ) {
    toast('Use uma imagem PNG, JPEG ou WebP de até 5 MB.', true);
    e.target.value = '';
    return;
  }
  imageReading = true;
  try {
    itemImage = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = () => reject(Error('Falha ao ler imagem.'));
      reader.readAsDataURL(file);
    });
    imagePreview();
  } catch (err) {
    toast(err.message, true);
  } finally {
    imageReading = false;
  }
};
$('#itemForm').onsubmit = async (e) => {
  e.preventDefault();
  if (imageReading) return toast('Aguarde a leitura da imagem.', true);
  const f = e.target,
    n = clone(),
    o = n.orders.find((o) => o.id === currentOrder);
  let i = o.items.find((i) => i.id === editItem);
  if (!i) {
    i = { id: uid(), stage: 'Aguardando', approved: false };
    o.items.push(i);
  }
  const layoutToSave = itemImage;
  if (!(await TrameDomain.sameLayout(i.image, layoutToSave))) i.approved = false;
  ['type', 'description', 'fabric', 'color', 'customizations', 'notes'].forEach(
    (k) => (i[k] = f.elements[k].value.trim())
  );
  try {
    readItemCommerce(i, f);
  } catch (err) {
    toast(err.message, true);
    return;
  }
  i.madeToMeasure = $('#madeToMeasure').checked;
  i.measurements = f.elements.measurements.value.trim();
  if (i.madeToMeasure && (!i.measurements || Number($('#bespokeSizes input').value) < 1))
    return toast('Informe as medidas e a quantidade de peças sob medida.', true);
  i.image = layoutToSave;
  i.sizes = Object.fromEntries(
    $$('#sizes input:not(:disabled), #bespokeSizes input:not(:disabled)').map((x) => [
      x.dataset.size,
      Number(x.value || 0),
    ])
  );
  if (!i.madeToMeasure && Object.hasOwn(i.sizes, 'Sob medida')) i.sizes['Sob medida'] = 0;
  if (total(i) < 1) return toast('Informe pelo menos uma peça na grade.', true);
  if (await save(n)) {
    $('#itemDialog').close();
    toast('Modelo salvo.');
  }
};
$$('.close').forEach((b) => (b.onclick = () => b.closest('dialog').close()));
$('#newOrder').onclick = () => openOrder();
$('#navOrders').onclick = () => {
  view = 'orders';
  filter = 'active';
  $('#search').value = '';
  render();
};
$('#search').oninput = render;
$$('#tabs button').forEach(
  (b) =>
    (b.onclick = () => {
      filter = b.dataset.filter;
      render();
    })
);
$('#warningDays').innerHTML = Array.from(
  { length: 30 },
  (_, i) => `<option value="${i + 1}">${i + 1} dia${i ? 's' : ''}</option>`
).join('');
$('#warningDays').onchange = async (e) => {
  const n = clone();
  n.warningDays = Number(e.target.value);
  if (!(await save(n))) render();
};
$('#export').onclick = async () => {
  if (!state) return;
  let exported;
  try {
    exported = await TrameAccess.request('/api/export');
  } catch (error) {
    toast(error.message, true);
    return;
  }
  const blob = new Blob(
      [
        JSON.stringify(
          { ...exported, exportedAt: new Date().toISOString(), app: 'radar-pedidos' },
          null,
          2
        ),
      ],
      { type: 'application/json' }
    ),
    url = URL.createObjectURL(blob),
    a = document.createElement('a');
  a.href = url;
  a.download = `trame-copia-${today()}.json`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  toast('Cópia exportada. Guarde o arquivo em um lugar seguro.');
};
setupCommerce();
setupOperations();
$('#today').textContent = new Date().toLocaleDateString('pt-BR', {
  day: 'numeric',
  month: 'long',
  year: 'numeric',
});
TrameAccess.ready
  .then((s) => {
    if (!s) throw Error('Entre para consultar os pedidos.');
    return TrameAccess.request('/api/state');
  })
  .then((d) => {
    state = d;
    render();
    $('#saveState').textContent = '● Dados deste computador';
    const requested = new URLSearchParams(location.search).get('order');
    if (requested && state.orders.some((o) => o.id === requested)) openDetail(requested);
  })
  .catch((e) => {
    $('#orderList').innerHTML =
      '<div class="empty"><h3>Não foi possível carregar os pedidos.</h3><p>Reabra o Tramê pelo atalho para tentar novamente.</p></div>';
    toast(e.message, true);
  });
let checkingServer = false;
setInterval(async () => {
  if (
    checkingServer ||
    busy ||
    !state ||
    document.hidden ||
    $$('dialog').some((d) => d.open) ||
    ['INPUT', 'SELECT', 'TEXTAREA'].includes(document.activeElement.tagName)
  )
    return;
  checkingServer = true;
  try {
    const info = await TrameAccess.request('/api/revision');
    if (info.revision !== state.revision) {
      state = await TrameAccess.request('/api/state');
      render();
      $('#saveState').textContent = '● Atualizado neste computador';
    }
  } catch (e) {
    $('#saveState').textContent = '● Verifique a conexão ou sessão';
  } finally {
    checkingServer = false;
  }
}, 15000);
