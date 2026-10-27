'use strict';
let view = 'orders',
  voidPaymentId = null;
const commercialFields = [
  'responsible',
  'seller',
  'document',
  'phone',
  'whatsapp',
  'email',
  'instagram',
  'website',
  'otherContact',
  'address',
  'paymentTerms',
  'quoteNotes',
];
const companyFields = ['name', 'document', 'phone', 'email', 'address', 'website'];
const techniqueNames = ['Bordado', 'Silk', 'DTF'];
const brl = (cents) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(cents / 100);
const moneyInput = (cents) => ((cents || 0) / 100).toFixed(2).replace('.', ',');
function parseMoney(value) {
  let s = String(value)
    .trim()
    .replace(/^R\$\s*/, '');
  if (!s) return 0;
  if (s.includes(',')) {
    if (!/^(\d+|\d{1,3}(\.\d{3})+)(,\d{1,2})?$/.test(s))
      throw Error('Use um valor válido, como 35,90 ou 1.234,56.');
    s = s.replace(/\./g, '').replace(',', '.');
  } else if (/^\d{1,3}(\.\d{3})+$/.test(s)) s = s.replace(/\./g, '');
  if (!/^\d+(\.\d{1,2})?$/.test(s))
    throw Error('Use um valor positivo com até duas casas decimais.');
  const [whole, decimal = ''] = s.split('.'),
    amount = Number(whole) * 100 + Number(decimal.padEnd(2, '0'));
  if (!Number.isSafeInteger(amount) || amount > 100000000)
    throw Error('O limite por campo é R$ 1.000.000,00.');
  return amount;
}
const techniquesOf = TrameDomain.techniques;
const itemFinancial = TrameDomain.itemMoney;
const financial = TrameDomain.orderMoney;
function docLabel(o) {
  return o.kind === 'quote'
    ? `ORÇ-${String(o.quoteNumber || 0).padStart(4, '0')}`
    : `OS-${String(o.osNumber || 0).padStart(4, '0')}`;
}
function quoteStats() {
  const quotes = state.orders.filter((o) => o.kind === 'quote' && !o.archived);
  return [
    ['Orçamentos em aberto', quotes.length, 'Prontos para negociar', '▤', ''],
    [
      'Modelos orçados',
      quotes.reduce((s, o) => s + o.items.length, 0),
      'Peças e personalizações',
      '▦',
      '',
    ],
    [
      'Validade vencida',
      quotes.filter((o) => o.validUntil && o.validUntil < today()).length,
      'Revise antes de converter',
      '◷',
      'warn',
    ],
    [
      'Convertidos em OS',
      state.orders.filter((o) => o.kind === 'order' && o.quoteNumber && !o.archived).length,
      'Orçamentos que viraram pedidos',
      '↗',
      '',
    ],
  ];
}
function renderCommerceHeader() {
  const quotes = view === 'quotes';
  $('#quoteCount').textContent = state.orders.filter(
    (o) => o.kind === 'quote' && !o.archived
  ).length;
  $('#navOrders').classList.toggle('active', !quotes);
  $('#navQuotes').classList.toggle('active', quotes);
  $('#listTitle').textContent = quotes ? 'orçamentos' : 'pedidos';
  $('#newOrder').textContent = quotes ? '＋ Novo orçamento' : '＋ Novo pedido';
  $('.heading h1').textContent = quotes ? 'Orçamentos' : 'Pedidos';
  $$('.tabs button').forEach(
    (b) =>
      (b.hidden = quotes
        ? !['active', 'archive', 'converted'].includes(b.dataset.filter)
        : b.dataset.filter === 'converted')
  );
  $('#tabs button[data-filter="active"]').textContent = quotes ? 'Em negociação' : 'Em aberto';
  $('#paymentFilter').hidden = quotes;
  const orders = state.orders.filter(
    (o) => !o.archived && (quotes ? o.kind === 'quote' : o.kind !== 'quote')
  );
  const f = orders.reduce(
    (s, o) => {
      const f = financial(o);
      s.total += f.total;
      s.received += f.received;
      s.balance += f.balance;
      return s;
    },
    { total: 0, received: 0, balance: 0 }
  );
  $('#financeSummary').innerHTML = quotes
    ? `<div><small>VALOR DOS ORÇAMENTOS EM ABERTO</small><strong>${brl(f.total)}</strong></div><p></p>`
    : `<div><small>TOTAL DOS PEDIDOS</small><strong>${brl(f.total)}</strong></div><div><small>RECEBIDO</small><strong>${brl(f.received)}</strong></div><div><small>A RECEBER</small><strong>${brl(f.balance)}</strong></div><p>Pedidos não arquivados.</p>`;
}
function populateOrderCommerce(o, id) {
  const f = $('#orderForm');
  commercialFields.forEach((k) => (f.elements[k].value = o[k] || ''));
  f.elements.discount.value = moneyInput(o.discountCents);
  f.elements.freight.value = moneyInput(o.freightCents);
  const isQuote = id ? o.kind === 'quote' : view === 'quotes';
  $('#validUntilLabel').hidden = !isQuote;
  f.elements.validUntil.value = o.validUntil || (isQuote ? addDays(7) : '');
  populateClientSelector(o);
  $('#orderForm button.primary').textContent = isQuote ? 'Salvar orçamento' : 'Salvar pedido';
}
function readOrderCommerce(o, f) {
  o.clientId = f.elements.clientId.value;
  commercialFields.forEach((k) => (o[k] = f.elements[k].value.trim()));
  o.discountCents = parseMoney(f.elements.discount.value);
  o.freightCents = parseMoney(f.elements.freight.value);
  o.validUntil = f.elements.validUntil.value;
}
function populateItemCommerce(i) {
  const f = $('#itemForm');
  f.elements.unitPrice.value = moneyInput(i?.unitPriceCents);
  $('#techniqueFields').innerHTML = techniqueNames
    .map((name, index) => {
      const t = techniquesOf(i || {}).find((t) => t.type === name);
      return `<section class="technique"><label class="check"><input type="checkbox" id="tech${index}" data-tech="${name}" ${t ? 'checked' : ''}> ${name}</label><div class="tech-grid" id="techBody${index}" ${t ? '' : 'hidden'}><label>Local de aplicação<input data-location="${name}" value="${esc(t?.location || '')}" maxlength="300" placeholder="Local da personalização"></label><label>Descrição / cores / dimensões<input data-description="${name}" value="${esc(t?.description || '')}" maxlength="1000" placeholder="Detalhes para executar esta técnica"></label><label>Adicional por peça (R$)<input data-unit="${name}" inputmode="decimal" value="${moneyInput(t?.unitCents)}"></label><label>Preparação única do modelo (R$)<input data-setup="${name}" inputmode="decimal" value="${moneyInput(t?.setupCents)}" placeholder="Matriz, tela ou preparação"></label></div></section>`;
    })
    .join('');
  $$('[data-tech]').forEach(
    (c, index) =>
      (c.onchange = () => {
        $('#techBody' + index).hidden = !c.checked;
        updatePricePreview();
      })
  );
  $$('#techniqueFields input').forEach((x) => x.addEventListener('input', updatePricePreview));
  f.elements.unitPrice.oninput = updatePricePreview;
  populateTechnicalFields(i);
}
function readItemCommerce(i, f) {
  i.unitPriceCents = parseMoney(f.elements.unitPrice.value);
  i.techniques = $$('[data-tech]:checked').map((c) => {
    const name = c.dataset.tech;
    return {
      type: name,
      description: $(`[data-description="${name}"]`).value.trim(),
      location: $(`[data-location="${name}"]`).value.trim(),
      unitCents: parseMoney($(`[data-unit="${name}"]`).value),
      setupCents: parseMoney($(`[data-setup="${name}"]`).value),
    };
  });
  i.techniques.forEach((t) => (t.specs = readTechnicalFields(t.type)));
  i.embroidery = i.techniques.some((t) => t.type === 'Bordado');
  i.embroideryNotes = i.techniques.find((t) => t.type === 'Bordado')?.description || '';
}
function updatePricePreview() {
  if (!$('#itemForm').elements.unitPrice) return;
  try {
    const i = {
      sizes: Object.fromEntries(
        $$('#sizes input').map((x) => [x.dataset.size, Number(x.value || 0)])
      ),
    };
    readItemCommerce(i, $('#itemForm'));
    const f = itemFinancial(i);
    $('#itemPricePreview').innerHTML =
      `<div><small>Preço final por peça</small><strong>${brl(f.unit)}</strong></div><div><small>Preparação única</small><strong>${brl(f.setup)}</strong></div><div><small>Total do modelo (${total(i)} peças)</small><strong>${brl(f.total)}</strong></div>`;
  } catch (e) {
    $('#itemPricePreview').textContent = e.message;
  }
}
function techniqueDescription(i) {
  const techniques = techniquesOf(i);
  return techniques.length
    ? techniques
        .map(
          (t) =>
            `<p><b>${esc(t.type)}:</b> ${esc([t.location, t.description].filter(Boolean).join(' · ')) || 'Sem detalhes'} <span class="hint">${brl(t.unitCents || 0)}/peça${t.setupCents ? ' + ' + brl(t.setupCents) + ' de preparação' : ''}</span></p>`
        )
        .join('')
    : '<p><b>Personalização:</b> sem bordado, silk ou DTF.</p>';
}
function detailCommerce(o) {
  const f = financial(o),
    quote = o.kind === 'quote',
    contact = [
      ['Responsável (cliente)', o.responsible],
      ['Vendedora / vendedor', o.seller],
      ['CPF / CNPJ', o.document],
      ['Telefone', o.phone],
      ['WhatsApp', o.whatsapp],
      ['E-mail', o.email],
      ['Instagram', o.instagram],
      ['Site', o.website],
      ['Outros contatos', o.otherContact],
      ['Endereço de entrega', o.address],
    ].filter(([, v]) => v);
  return `<section class="commercial"><div class="section-heading"><h2>${quote ? 'Orçamento' : 'Valores e pagamentos'}</h2><div class="document-actions">${o.quoteSnapshot ? `<a class="secondary" target="_blank" rel="noopener" href="/print?id=${encodeURIComponent(o.id)}&type=quote">Orçamento aprovado</a>` : ''}<a class="secondary" target="_blank" rel="noopener" href="/print?id=${encodeURIComponent(o.id)}&type=${quote ? 'quote' : 'os'}">▤ ${quote ? 'Imprimir orçamento' : 'Imprimir OS'}</a>${!quote ? `<a class="secondary" target="_blank" rel="noopener" href="/print?id=${encodeURIComponent(o.id)}&type=summary">Resumo de valores</a>` : ''}${quote ? `<button class="primary" id="convertQuote" ${o.archived || !o.items.length ? 'disabled' : ''}>Aprovar orçamento e criar OS</button>` : ''}</div></div>${o.quoteNumber && !quote ? `<p class="hint">Originado do orçamento ORÇ-${String(o.quoteNumber).padStart(4, '0')}.</p>` : ''}<div class="contact-grid">${contact.map(([k, v]) => `<div><small>${esc(k)}</small><span>${esc(v)}</span></div>`).join('') || '<p class="hint">Complete os contatos e responsáveis em Editar pedido.</p>'}</div><div class="money-grid"><div><small>Subtotal das peças e técnicas</small><strong>${brl(f.subtotal)}</strong></div><div><small>Frete / entrega</small><strong>${brl(o.freightCents || 0)}</strong></div><div><small>Desconto</small><strong>− ${brl(o.discountCents || 0)}</strong></div><div class="grand-total"><small>Total ${quote ? 'do orçamento' : 'do pedido'}</small><strong>${brl(f.total)}</strong></div>${!quote ? `<div><small>Recebido</small><strong>${brl(f.received)}</strong></div><div><small>Saldo a receber</small><strong>${brl(f.balance)}</strong></div>` : ''}</div><div class="commercial-terms">${quote ? `<p><b>Validade:</b> ${o.validUntil ? new Date(o.validUntil + 'T12:00:00').toLocaleDateString('pt-BR') : 'Não informada'} ${o.validUntil && o.validUntil < today() ? '<span class="badge late">Vencido · revise antes de aprovar</span>' : ''}</p>` : `<span class="badge ${f.status === 'Pago' ? 'good' : f.status === 'Parcialmente pago' ? 'pending' : ''}">${f.status}</span>`}${o.paymentTerms ? `<p><b>Pagamento:</b> ${esc(o.paymentTerms)}</p>` : ''}${o.quoteNotes ? `<p class="notes"><b>Condições comerciais:</b> ${esc(o.quoteNotes)}</p>` : ''}</div>${!quote ? `<div class="section-heading"><h3>Recebimentos</h3><button class="primary" id="addPayment" ${o.archived || f.balance <= 0 ? 'disabled' : ''}>＋ Registrar recebimento</button></div><p class="hint">O status muda automaticamente conforme o total recebido. Lançamentos incorretos podem ser anulados com motivo.</p>${o.payments?.length ? `<div class="payment-list">${o.payments.map((p) => `<div class="payment-row ${p.voided ? 'voided' : ''}"><div><strong>${brl(p.amountCents)}</strong><small>${new Date(p.date + 'T12:00:00').toLocaleDateString('pt-BR')} · ${esc(p.method)}${p.note ? ' · ' + esc(p.note) : ''}</small>${p.voided ? `<small>Anulado: ${esc(p.voidReason)}</small>` : ''}</div>${p.voided ? '<span class="badge">Anulado</span>' : `<button class="secondary" data-void="${esc(p.id)}" ${o.archived ? 'disabled' : ''}>Anular</button>`}</div>`).join('')}</div>` : '<p class="notes">Nenhum valor recebido registrado.</p>'}` : ''}</section>`;
}
function bindCommerce(o) {
  $('#convertQuote')?.addEventListener('click', async () => {
    if (o.validUntil && o.validUntil < today()) {
      toast('Revise a validade do orçamento em Editar pedido antes de aprovar.', true);
      return;
    }
    const n = clone(),
      order = n.orders.find((x) => x.id === o.id);
    order.kind = 'order';
    order.convertedAt = today();
    if (await save(n)) {
      view = 'orders';
      filter = 'active';
      render();
      renderDetail();
      toast('Orçamento convertido em pedido. A OS está pronta para imprimir.');
    }
  });
  $('#addPayment')?.addEventListener('click', () => {
    const f = $('#paymentForm');
    f.reset();
    f.elements.date.value = today();
    $('#paymentBalance').textContent =
      `Saldo a receber: ${brl(financial(o).balance)}. ${docLabel(o)} · ${o.client}`;
    $('#paymentDialog').showModal();
  });
  $$('[data-void]').forEach(
    (b) =>
      (b.onclick = () => {
        voidPaymentId = b.dataset.void;
        $('#voidForm').reset();
        $('#voidDialog').showModal();
      })
  );
}
function setupCommerce() {
  $('#navQuotes').onclick = () => {
    view = 'quotes';
    filter = 'active';
    $('#search').value = '';
    render();
  };
  $('#paymentFilter').onchange = () => {
    if ($('#paymentFilter').value !== 'all') filter = 'all';
    render();
  };
  $('#companyButton').onclick = () => {
    const f = $('#companyForm');
    companyFields.forEach((k) => (f.elements[k].value = state.company?.[k] || ''));
    $('#companyDialog').showModal();
  };
  $('#companyForm').onsubmit = async (e) => {
    e.preventDefault();
    const n = clone();
    n.company = Object.fromEntries(
      companyFields.map((k) => [k, e.target.elements[k].value.trim()])
    );
    if (await save(n)) {
      $('#companyDialog').close();
      toast('Dados da empresa salvos.');
    }
  };
  $('#paymentForm').onsubmit = async (e) => {
    e.preventDefault();
    const f = e.target;
    let amount;
    try {
      amount = parseMoney(f.elements.amount.value);
    } catch (err) {
      toast(err.message, true);
      return;
    }
    if (amount <= 0) {
      toast('Informe um valor maior que zero.', true);
      return;
    }
    const n = clone(),
      o = n.orders.find((o) => o.id === currentOrder);
    o.payments ||= [];
    o.payments.push({
      id: uid(),
      date: f.elements.date.value,
      method: f.elements.method.value,
      amountCents: amount,
      installmentId: f.elements.installmentId?.value || '',
      note: f.elements.note.value.trim(),
      voided: false,
    });
    if (await save(n)) {
      $('#paymentDialog').close();
      toast('Recebimento registrado.');
    }
  };
  $('#voidForm').onsubmit = async (e) => {
    e.preventDefault();
    const n = clone(),
      p = n.orders.find((o) => o.id === currentOrder).payments.find((p) => p.id === voidPaymentId);
    p.voided = true;
    p.voidReason = e.target.elements.reason.value.trim();
    if (await save(n)) {
      $('#voidDialog').close();
      toast('Lançamento anulado e preservado no histórico.');
    }
  };
}
