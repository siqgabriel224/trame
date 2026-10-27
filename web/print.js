'use strict';
const escapeHTML = (value) =>
  String(value ?? '').replace(
    /[&<>"']/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]
  );
const currency = (c) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(c / 100);
const fullDate = (s) => (s ? new Date(s + 'T12:00:00').toLocaleDateString('pt-BR') : '—');
const params = new URLSearchParams(location.search);
let printedOrder = null;
function row(label, value) {
  return value ? `<div><b>${escapeHTML(label)}</b><span>${escapeHTML(value)}</span></div>` : '';
}
const quantity = TrameDomain.quantity;
const itemAmounts = TrameDomain.itemMoney;
function signatureRows(o) {
  const rows = o.items.flatMap((item, index) => {
    const tasks = item.tasks?.length
      ? TrameDomain.productionTasks(item)
      : TrameDomain.productionSectors(item).map((sector) => ({ sector, qty: quantity(item) }));
    return tasks.map((task) => ({
      task,
      model: `Modelo ${index + 1} · ${item.type} · ${item.color || 'cor não informada'}`,
    }));
  });
  const extra = Math.max(0, Math.min(30, Number(document.querySelector('#extraRows').value) || 0));
  for (let i = 0; i < extra; i++) rows.push({ task: { sector: 'Outra atividade' }, model: '' });
  return `<section class="signatures"><h2>OS-${String(o.osNumber).padStart(4, '0')} · Execução e assinaturas por etapa</h2><p>Quem executa preenche e assina a sua etapa. Registre depois a conclusão no Tramê. Etapas antigas sem assinatura não comprovam o responsável pela execução.</p><table><thead><tr><th>Etapa / modelo</th><th>Data</th><th>Qtd.</th><th>Responsável</th><th>Assinatura / registro</th></tr></thead><tbody>${rows.map(({ task, model }) => `<tr><td><strong>${escapeHTML(task.sector)}</strong><small>${escapeHTML(model)}</small></td><td>${task.signature ? fullDate(task.signature.date) : ''}</td><td>${task.qty || ''}</td><td>${escapeHTML(task.signature?.name || '')}</td><td>${task.signature ? `${escapeHTML(task.signature.name)}<small>${escapeHTML(task.signature.source)} · por ${escapeHTML(task.signature.recordedBy?.name || '')}</small>` : ''}</td></tr>`).join('')}</tbody></table><div class="delivery-sign"><div>Entregue por: ______________________________<br>Data: ____/____/________</div><div>Recebido por (cliente): ______________________<br>Assinatura: _______________________________</div></div></section>`;
}
async function loadDocument() {
  try {
    const response = await fetch('/api/state');
    if (response.status === 401) {
      location.replace('/login?next=' + encodeURIComponent(location.pathname + location.search));
      return;
    }
    if (!response.ok) throw Error('Não foi possível consultar os dados.');
    const state = await response.json();
    let o = state.orders.find((o) => o.id === params.get('id'));
    if (!o) throw Error('Documento não encontrado. Volte ao Tramê e tente novamente.');
    const type = params.get('type'),
      isQuote = type === 'quote',
      isOS = type === 'os',
      isSummary = type === 'summary';
    if (!isQuote && !isOS && !isSummary) throw Error('Tipo de documento inválido.');
    if (isQuote && o.kind !== 'quote') {
      if (!o.quoteSnapshot)
        throw Error(
          'A versão original deste orçamento não está disponível. Use Resumo de valores.'
        );
      state.company = o.quoteSnapshot.company;
      o = o.quoteSnapshot.order;
    }
    if (!isQuote && o.kind === 'quote')
      throw Error('Converta o orçamento em pedido antes de criar uma OS.');
    document.querySelector('#valuesControl').hidden = !isOS;
    document.querySelector('#rowsControl').hidden = !isOS;
    document.body.classList.toggle(
      'hide-values',
      isOS && !document.querySelector('#showValues').checked
    );
    const company = state.company || {},
      code = isQuote
        ? `ORÇ-${String(o.quoteNumber).padStart(4, '0')}`
        : `OS-${String(o.osNumber).padStart(4, '0')}`,
      title = isQuote ? 'ORÇAMENTO' : isOS ? 'ORDEM DE SERVIÇO' : 'RESUMO COMERCIAL',
      subtotal = o.items.reduce((s, i) => s + itemAmounts(i).total, 0),
      value = subtotal + (o.freightCents || 0) - (o.discountCents || 0),
      received = (o.payments || []).filter((p) => !p.voided).reduce((s, p) => s + p.amountCents, 0),
      payStatus = received === 0 ? 'Não pago' : received === value ? 'Pago' : 'Parcialmente pago';
    document.title = `${code} · ${o.client}`;
    document.querySelector('#printTitle').textContent = `${title} · ${code}`;
    document.querySelector('#document').innerHTML =
      `<header class="document-header"><div><div class="brand">${escapeHTML(company.name || 'Tramê')}</div><p>${[company.tradeName, company.document, company.phone, company.email, company.website, company.address].filter(Boolean).map(escapeHTML).join('<br>')}</p></div><div class="document-code"><h1>${title}</h1><strong>${code}</strong><p>Emitido em ${new Date().toLocaleDateString('pt-BR')}</p>${o.archived ? '<b>ARQUIVADO</b>' : ''}</div></header><section><h2>Cliente e atendimento</h2><div class="info-grid">${row('Cliente', o.client)}${row('CPF / CNPJ', o.document)}${row('Responsável pelo pedido (cliente)', o.responsible || 'Não informado')}${row('Vendedora / vendedor', o.seller || 'Não informado')}${row('Telefone', o.phone)}${row('WhatsApp', o.whatsapp)}${row('E-mail', o.email)}${row('Instagram', o.instagram)}${row('Site', o.website)}${row('Outros contatos', o.otherContact)}${row('Endereço de entrega', o.address)}${row('Data de entrada', fullDate(o.entry))}${row('Prazo / previsão de entrega', fullDate(o.due))}${isQuote ? row('Validade do orçamento', fullDate(o.validUntil)) : ''}</div><p class="description">${escapeHTML(o.description)}</p></section>${!o.items.length ? '<p>Nenhum modelo cadastrado.</p>' : ''}${o.items
        .map((i, index) => {
          const m = itemAmounts(i);
          return `<section class="piece"><h2>${code} · Modelo ${index + 1} · ${escapeHTML(i.type)} · ${quantity(i)} peças</h2><div class="piece-content"><div class="specs"><p>${escapeHTML(i.description)}</p><p><b>Tecido:</b> ${escapeHTML(i.fabric || '—')} &nbsp; <b>Cor:</b> ${escapeHTML(i.color || '—')}</p><p><b>Grade:</b> ${Object.entries(
            i.sizes
          )
            .filter(([, n]) => n)
            .map(([s, n]) => `${escapeHTML(s)}: ${n}`)
            .join(
              ' · '
            )}</p>${i.madeToMeasure || i.sizes['Sob medida'] ? `<p class="preserve"><b>Sob medida:</b> ${escapeHTML(i.measurements)}</p>` : ''}<p><b>Layout:</b> ${i.approved ? 'APROVADO' : 'AGUARDANDO APROVAÇÃO · NÃO PRODUZIR'}</p><p><b>Andamento:</b> ${escapeHTML(i.stage)}</p>${(i.techniques || []).map((t) => `<p><b>${escapeHTML(t.type)}:</b> ${escapeHTML(t.location || 'Local não informado')} · ${escapeHTML(t.description || 'Sem detalhes')}</p>`).join('') || '<p>Sem bordado, silk ou DTF.</p>'}${i.customizations ? `<p><b>Outras personalizações:</b> ${escapeHTML(i.customizations)}</p>` : ''}${i.notes ? `<p class="preserve"><b>Produção:</b> ${escapeHTML(i.notes)}</p>` : ''}</div>${i.image ? `<figure><img src="${escapeHTML(i.image)}" alt="Layout do modelo ${index + 1}"><figcaption>Layout de referência</figcaption></figure>` : ''}</div>${true ? `<table class="prices commercial-values"><thead><tr><th>Composição do preço</th><th>Por peça</th><th>Preparação única</th></tr></thead><tbody><tr><td>Peça sem personalização</td><td>${currency(i.unitPriceCents || 0)}</td><td>—</td></tr>${(i.techniques || []).map((t) => `<tr><td>${escapeHTML(t.type)}</td><td>${currency(t.unitCents || 0)}</td><td>${currency(t.setupCents || 0)}</td></tr>`).join('')}<tr class="line-total"><td>${quantity(i)} peças × ${currency(m.unit)} + ${currency(m.setup)} preparação</td><td colspan="2">Total do modelo: ${currency(m.total)}</td></tr></tbody></table>` : ''}</section>`;
        })
        .join(
          ''
        )}${true ? `<section class="totals commercial-values"><div><span>Subtotal das peças e técnicas</span><b>${currency(subtotal)}</b></div><div><span>Frete / entrega</span><b>${currency(o.freightCents || 0)}</b></div><div><span>Desconto</span><b>− ${currency(o.discountCents || 0)}</b></div><div class="total"><span>TOTAL</span><b>${currency(value)}</b></div>${!isQuote ? `<div><span>Recebido · ${payStatus}</span><b>${currency(received)}</b></div><div><span>Saldo a receber</span><b>${currency(value - received)}</b></div>` : ''}</section>` : ''}<section class="observations">${o.notes ? `<p class="preserve"><b>Observações:</b> ${escapeHTML(o.notes)}</p>` : ''}${!isOS && o.paymentTerms ? `<p class="preserve"><b>Condições de pagamento:</b> ${escapeHTML(o.paymentTerms)}</p>` : ''}${!isOS && o.quoteNotes ? `<p class="preserve"><b>Condições comerciais:</b> ${escapeHTML(o.quoteNotes)}</p>` : ''}</section>${isOS ? signatureRows(o) : isQuote ? '<section class="quote-approval"><p>Aprovação comercial do orçamento: ________________________________ &nbsp; Data: ____/____/________</p><p>Nome / assinatura do responsável pelo cliente: __________________________________________________</p><small>A aprovação comercial não substitui a aprovação individual dos layouts antes da produção.</small></section>' : `<section><h2>Histórico de recebimentos</h2>${o.payments?.length ? `<table><thead><tr><th>Data</th><th>Forma</th><th>Valor</th><th>Observação / situação</th></tr></thead><tbody>${o.payments.map((p) => `<tr><td>${fullDate(p.date)}</td><td>${escapeHTML(p.method)}</td><td>${currency(p.amountCents)}</td><td>${escapeHTML(p.note || '')}${p.voided ? ' · ANULADO: ' + escapeHTML(p.voidReason) : ''}</td></tr>`).join('')}</tbody></table>` : '<p>Nenhum recebimento registrado.</p>'}</section>`}<footer>${code} · ${escapeHTML(o.client)} · ${o.items.reduce((s, i) => s + quantity(i), 0)} peças no total${isOS ? ' · Valores comerciais disponíveis no resumo do pedido.' : ''}</footer>`;
    if (isOS) {
      document
        .querySelector('.document-header')
        .insertAdjacentHTML(
          'beforeend',
          `<figure class="order-qr"><img src="/api/qr?order=${encodeURIComponent(o.id)}" alt="QR code de consulta do pedido"><figcaption>Consulta na empresa<br>${code}</figcaption></figure>`
        );
      const specs = {
        Bordado: [
          ['points', 'Pontos'],
          ['matrix', 'Matriz'],
          ['threads', 'Linhas'],
        ],
        Silk: [
          ['screens', 'Telas'],
          ['inkColors', 'Tintas e cores'],
        ],
        DTF: [
          ['width', 'Largura (cm)'],
          ['height', 'Altura (cm)'],
          ['film', 'Filme'],
          ['temperature', 'Temperatura (°C)'],
          ['seconds', 'Tempo (s)'],
          ['pressure', 'Pressão'],
        ],
      };
      document.querySelectorAll('.piece').forEach((section, index) => {
        const i = o.items[index],
          details = (i.techniques || [])
            .map((t) => {
              const fields = (specs[t.type] || []).filter(([k]) => t.specs?.[k]);
              return fields.length
                ? `<p><b>Ficha técnica · ${escapeHTML(t.type)}:</b> ${fields.map(([k, label]) => `${label}: ${escapeHTML(t.specs[k])}`).join(' · ')}</p>`
                : '';
            })
            .join('');
        section.querySelector('.specs').insertAdjacentHTML('beforeend', details);
        const delivered = { ...(i.deliveryBaseline || {}) };
        for (const d of i.deliveries || [])
          if (!d.voided)
            for (const [size, n] of Object.entries(d.sizes))
              delivered[size] = (delivered[size] || 0) + n;
        section.insertAdjacentHTML(
          'beforeend',
          `<p><b>Entregas por tamanho:</b> ${Object.entries(i.sizes)
            .filter(([, n]) => n)
            .map(([size, n]) => `${escapeHTML(size)}: ${delivered[size] || 0}/${n}`)
            .join(' · ')}</p>`
        );
        if (i.tasks?.length)
          section.insertAdjacentHTML(
            'beforeend',
            `<table><thead><tr><th>Etapa</th><th>Responsável</th><th>Prazo</th><th>Quantidade</th><th>Andamento</th></tr></thead><tbody>${TrameDomain.productionTasks(
              i
            )
              .map(
                (t) =>
                  `<tr><td>${escapeHTML(t.sector)}</td><td>${escapeHTML((state.employees || []).find((e) => e.id === t.employeeId)?.name || 'A definir')}</td><td>${fullDate(t.due)}</td><td>${t.qty}</td><td>${escapeHTML(t.stage)}</td></tr>`
              )
              .join('')}</tbody></table>`
          );
      });
    }
    printedOrder = o;
    await Promise.all(
      [...document.images].map((img) =>
        img.complete
          ? Promise.resolve()
          : new Promise((resolve) => {
              img.addEventListener('load', resolve, { once: true });
              img.addEventListener('error', resolve, { once: true });
            })
      )
    );
    document.querySelector('#printButton').disabled = false;
  } catch (e) {
    document.querySelector('#printTitle').textContent = 'Não foi possível preparar o documento';
    document.querySelector('#document').textContent = e.message;
  }
}
document.querySelector('#printButton').onclick = () => window.print();
document.querySelector('#showValues').onchange = () =>
  document.body.classList.toggle('hide-values', !document.querySelector('#showValues').checked);
document.querySelector('#extraRows').oninput = () => {
  const section = document.querySelector('.signatures');
  if (printedOrder && section) section.outerHTML = signatureRows(printedOrder);
};
loadDocument();
