'use strict';
const TrameServices = (() => {
  let kind = 'Bordado',
    selectedMonth = '',
    mode = 'jobs',
    search = '',
    generation = 0;
  let data = { jobs: [], closing: null };
  const completed = (j) => ['Concluído', 'Entregue'].includes(j.status);
  const canAccess = () => ['admin', 'embroiderer'].includes(TrameAccess.session?.user.role);
  const printUrl = (clientId = '') =>
    `/service-print?technique=${encodeURIComponent(kind)}&month=${selectedMonth}${clientId ? '&clientId=' + encodeURIComponent(clientId) : ''}`;
  const moneyField = (label, name, value) =>
    inputField(label, name, moneyInput(value || 0), 'text', 'required inputmode="decimal"');

  async function render(selectedView) {
    if (!canAccess()) {
      $('#opsWorkspace').innerHTML =
        '<p class="ops-empty">Esta área é exclusiva do administrador e do perfil Bordador(a).</p>';
      return;
    }
    const next = selectedView === 'dtf' ? 'DTF' : 'Bordado';
    if (next !== kind) search = '';
    kind = next;
    selectedMonth ||= today().slice(0, 7);
    const current = ++generation;
    $('#opsWorkspace').innerHTML =
      `<h1>${kind}</h1><p class="form-note">Consultando serviços do mês…</p>`;
    try {
      const result = await TrameAccess.request(
        `/api/services?technique=${encodeURIComponent(kind)}&month=${selectedMonth}`
      );
      if (current !== generation || !['embroidery', 'dtf'].includes(view)) return;
      data = result;
      draw();
    } catch (error) {
      if (current === generation && ['embroidery', 'dtf'].includes(view))
        $('#opsWorkspace').innerHTML =
          `<h1>${kind}</h1><p class="ops-empty">${esc(error.message)}</p><button id="retryServices" class="secondary">Tentar novamente</button>`;
      $('#retryServices')?.addEventListener('click', () => render(view));
    }
  }
  async function reload() {
    await render(kind === 'DTF' ? 'dtf' : 'embroidery');
  }

  function draw() {
    const done = data.jobs.filter(completed),
      total = done.reduce((s, j) => s + j.totalCents, 0);
    const paid = done.reduce((s, j) => s + j.receivedCents, 0);
    $('#opsWorkspace').innerHTML =
      `<div class="section-heading"><div><h1>${kind}</h1><p class="notes">Serviços avulsos em peças do cliente. Estes lançamentos não criam uma OS de confecção nem entram na produção de roupas.</p></div><button class="primary" id="newService">＋ Novo serviço</button></div><div class="ops-toolbar"><label>Mês de referência<input type="month" id="serviceMonth" value="${selectedMonth}" required></label><button class="secondary" id="refreshServices">↻ Atualizar</button><div class="tabs service-tabs"><button id="serviceJobsTab" class="${mode === 'jobs' ? 'selected' : ''}">Serviços</button><button id="serviceClosingTab" class="${mode === 'closing' ? 'selected' : ''}">Fechamento mensal</button></div></div><div class="finance-summary"><div><small>SERVIÇOS NO MÊS</small><strong>${data.jobs.filter((j) => j.status !== 'Cancelado').length}</strong></div><div><small>CONCLUÍDOS NO MÊS</small><strong>${brl(total)}</strong></div><div><small>RECEBIDO DOS CONCLUÍDOS</small><strong>${brl(paid)}</strong></div><div><small>SALDO DOS CONCLUÍDOS</small><strong>${brl(total - paid)}</strong></div></div>${mode === 'jobs' ? `<label class="service-search">Pesquisar serviços<input type="search" id="serviceSearch" value="${esc(search)}" placeholder="Número, cliente, CNPJ ou vendedora"></label><div class="service-list" id="serviceList">${jobCards()}</div>` : closingPanel()}`;
    $('#newService').onclick = () => edit();
    $('#serviceMonth').onchange = (e) => {
      if (!e.target.value) return;
      selectedMonth = e.target.value;
      reload();
    };
    $('#refreshServices').onclick = reload;
    $('#serviceJobsTab').onclick = () => {
      mode = 'jobs';
      draw();
    };
    $('#serviceClosingTab').onclick = () => {
      mode = 'closing';
      draw();
    };
    if ($('#serviceSearch'))
      $('#serviceSearch').oninput = (e) => {
        search = e.target.value;
        $('#serviceList').innerHTML = jobCards();
        bind();
      };
    bind();
  }
  function jobCards() {
    const query = search.trim().toLocaleLowerCase('pt-BR');
    return (
      data.jobs
        .filter(
          (j) =>
            `${j.code} ${j.client} ${j.document} ${j.seller} ${j.reference}`
              .toLocaleLowerCase('pt-BR')
              .includes(query) ||
            (query.replace(/[.\s/-]/g, '') &&
              j.document.replace(/[.\s/-]/g, '').includes(query.replace(/[.\s/-]/g, '')))
        )
        .map((j) => {
          const locked = completed(j) && data.closing?.status === 'Fechado';
          return `<article class="ops-card service-card"><div class="section-heading"><div><span class="eyebrow">${esc(j.code)}</span><h2>${esc(j.client)}</h2></div><span class="badge ${completed(j) ? 'good' : 'pending'}">${esc(j.status)}</span></div><p><b>${esc(j.description)}</b></p><p class="client-seller">Vendedora: ${esc(j.seller || 'Não informada')} · Execução: ${esc(j.employee || 'A definir')}</p><p class="notes">Entrada: ${dateLabel(j.entryDate)}${j.completedDate ? ' · Conclusão: ' + dateLabel(j.completedDate) : ''} · ${formatQuantity(j.qtyMilli)} ${esc(j.unit)} · ${brl(j.unitCents)} por ${esc(j.unit)}${j.setupCents ? ' + ' + brl(j.setupCents) + ' de preparação' : ''}</p>${j.reference ? `<p>Matriz / referência: ${esc(j.reference)}</p>` : ''}${j.details ? `<p class="preserve">${esc(j.details)}</p>` : ''}<div class="money-grid"><div><small>Total do serviço</small><strong>${brl(j.totalCents)}</strong></div><div><small>Recebido</small><strong>${brl(j.receivedCents)}</strong></div><div><small>Saldo</small><strong>${brl(j.balanceCents)}</strong></div></div>${locked ? '<p class="hint">Incluído no fechamento. Recebimentos continuam disponíveis.</p>' : ''}<div class="detail-actions"><button class="secondary" data-service-edit="${esc(j.id)}" ${locked ? 'disabled' : ''}>Editar serviço</button><button class="primary" data-service-receive="${esc(j.id)}" ${j.status === 'Cancelado' || j.balanceCents <= 0 ? 'disabled' : ''}>Registrar recebimento</button></div>${j.payments.length ? `<details class="service-payments"><summary>Recebimentos e histórico</summary>${j.payments.map((p) => `<div class="ops-inline"><div><strong>${brl(p.amountCents)} · ${esc(p.method)}${p.voided ? ' · ANULADO' : ''}</strong><small>${dateLabel(p.date)} · ${esc(p.recordedBy)}${p.voided ? ' · ' + esc(p.voidReason) : ''}</small></div>${!p.voided ? `<button class="secondary" data-service-void="${esc(j.id)}" data-payment="${esc(p.id)}">Anular com motivo</button>` : ''}</div>`).join('')}</details>` : ''}</article>`;
        })
        .join('') ||
      '<p class="ops-empty">Nenhum serviço encontrado neste mês. Use Novo serviço para registrar bordados ou DTF em peças trazidas pelo cliente.</p>'
    );
  }
  function closingPanel() {
    const closing = data.closing,
      closed = closing?.status === 'Fechado';
    const jobs = closed
      ? closing.jobs.map((j) => ({
          ...j,
          receivedCents:
            data.jobs.find((live) => live.id === j.id)?.receivedCents ?? j.receivedCents,
        }))
      : data.jobs.filter(completed);
    const groups = new Map();
    for (const j of jobs) {
      const g = groups.get(j.clientId) || {
        id: j.clientId,
        name: j.client,
        document: j.document,
        count: 0,
        total: 0,
        paid: 0,
      };
      g.count++;
      g.total += j.totalCents;
      g.paid += j.receivedCents;
      groups.set(j.clientId, g);
    }
    const pending = data.jobs.filter((j) => ['Recebido', 'Em execução'].includes(j.status)).length;
    return `<section class="service-closing"><div class="section-heading"><div><h2>Fechamento de ${kind} · ${selectedMonth.split('-').reverse().join('/')}</h2><span class="badge ${closed ? 'good' : 'pending'}">${closed ? 'Fechado' : closing?.status || 'Em aberto'}</span></div><div class="detail-actions">${closed ? (TrameAccess.session.user.role === 'admin' ? '<button class="secondary" id="reopenServices">Reabrir com motivo</button>' : '') : `<button class="primary" id="closeServices" ${!jobs.length ? 'disabled' : ''}>Conferir e fechar mês</button>`}<a class="secondary" target="_blank" rel="noopener" href="${printUrl()}">Imprimir demonstrativo</a></div></div><p class="form-note">Entram no fechamento os serviços concluídos ou entregues, pela data de conclusão. ${pending ? `${pending} serviço(s) recebido(s) ou em execução ficam fora deste fechamento.` : ''}</p>${closed ? `<p class="notes">Fechado por ${esc(closing.closedBy)} em ${new Date(closing.closedAt).toLocaleString('pt-BR')}. Itens e valores preservados; recebimentos posteriores atualizam o saldo.</p>` : ''}${closing?.reopened ? `<p class="notes">Última reabertura: ${esc(closing.reopened.by)} · ${esc(closing.reopened.reason)}</p>` : ''}<div class="ops-cards">${[...groups.values()].map((g) => `<article class="ops-card"><h3>${esc(g.name)}</h3><p class="notes">${esc(g.document || 'Documento não informado')} · ${g.count} serviço(s)</p><div class="money-grid"><div><small>Total</small><strong>${brl(g.total)}</strong></div><div><small>Recebido</small><strong>${brl(g.paid)}</strong></div><div><small>Saldo atual</small><strong>${brl(g.total - g.paid)}</strong></div></div><a class="secondary" target="_blank" rel="noopener" href="${printUrl(g.id)}">Demonstrativo deste cliente</a></article>`).join('') || '<p class="ops-empty">Nenhum serviço concluído para fechar neste mês.</p>'}</div>${closing?.history?.length ? `<details><summary>Versões anteriores do fechamento</summary>${closing.history.map((h) => `<p class="notes">Versão ${h.revision} · ${esc(h.closedBy)} · ${new Date(h.closedAt).toLocaleString('pt-BR')} · ${brl(h.totalCents)}${h.reopened ? '<br>Reaberto: ' + esc(h.reopened.reason) : ''}</p>`).join('')}</details>` : ''}</section>`;
  }
  function bind() {
    $$('[data-service-edit]').forEach(
      (b) => (b.onclick = () => edit(data.jobs.find((j) => j.id === b.dataset.serviceEdit)))
    );
    $$('[data-service-receive]').forEach(
      (b) => (b.onclick = () => receive(data.jobs.find((j) => j.id === b.dataset.serviceReceive)))
    );
    $$('[data-service-void]').forEach(
      (b) =>
        (b.onclick = () =>
          voidPayment(
            data.jobs.find((j) => j.id === b.dataset.serviceVoid),
            b.dataset.payment
          ))
    );
    $('#closeServices')?.addEventListener('click', closeMonth);
    $('#reopenServices')?.addEventListener('click', reopenMonth);
  }
  function edit(job = {}) {
    const clients = state.clients.filter((c) => c.active !== false || c.id === job.clientId);
    if (!clients.length) return toast('Cadastre o cliente antes de lançar o serviço.', true);
    opsForm(
      job.id ? `Editar ${job.code}` : `Novo serviço de ${kind}`,
      `<p class="form-note">Registre somente o serviço prestado. O custo das peças trazidas pelo cliente não entra no valor.</p><div class="form-grid">${selectField('Cliente', 'clientId', option('', 'Selecione o cliente', job.clientId) + clients.map((c) => option(c.id, c.name, job.clientId)).join(''))}${inputField('Vendedora responsável', 'seller', job.seller || '', 'text', 'maxlength="200"')}${inputField('Descrição do serviço', 'description', job.description || '', 'text', 'required maxlength="500"')}${selectField(
        'Responsável pela execução',
        'employeeId',
        option('', 'A definir', job.employeeId) +
          state.employees
            .filter((e) => e.active !== false || e.id === job.employeeId)
            .map((e) => option(e.id, e.name, job.employeeId))
            .join('')
      )}${inputField('Data de entrada', 'entryDate', job.entryDate || today(), 'date', 'required')}${selectField('Situação', 'status', ['Recebido', 'Em execução', 'Concluído', 'Entregue', 'Cancelado'].map((s) => option(s, s, job.status || 'Recebido')).join(''))}<div id="serviceCompletion">${inputField('Data de conclusão', 'completedDate', job.completedDate || today(), 'date', `max="${today()}"`)}</div>${inputField('Quantidade', 'qty', TrameDomain.quantityInput(job.qtyMilli || 1000), 'text', 'required inputmode="decimal" placeholder="Ex.: 1000 ou 1,5"')}${selectField('Unidade', 'unit', ['peça', 'metro', 'aplicação', 'lote'].map((u) => option(u, u, job.unit || 'peça')).join(''))}${moneyField('Valor por unidade (R$)', 'unitPrice', job.unitCents)}${moneyField('Preparação / matriz (R$)', 'setup', job.setupCents)}${inputField('Matriz / arquivo / referência', 'reference', job.reference || '', 'text', 'maxlength="300"')}${textField('Detalhes para executar o serviço', 'details', job.details || '')}${textField('Observações', 'notes', job.notes || '')}<div class="full" id="serviceCancelReason">${textField('Motivo do cancelamento', 'cancelReason', job.cancelReason || '')}</div></div><div class="price-preview" id="servicePricePreview"></div>`,
      async (f) => {
        const row = Object.fromEntries(new FormData(f));
        row.technique = kind;
        row.qtyMilli = parseQuantity(row.qty);
        row.unitCents = parseMoney(row.unitPrice);
        row.setupCents = parseMoney(row.setup);
        if (job.id) row.id = job.id;
        const saved = await TrameAccess.request('/api/services/save', {
          job: row,
          revision: job.revision || 0,
        });
        selectedMonth = (saved.completedDate || saved.entryDate).slice(0, 7);
        await reload();
        return true;
      }
    );
    const f = $('#opsForm');
    f.elements.clientId.required = true;
    f.elements.clientId.onchange = () => {
      f.elements.seller.value =
        clients.find((c) => c.id === f.elements.clientId.value)?.seller || '';
    };
    function preview() {
      const done = ['Concluído', 'Entregue'].includes(f.elements.status.value);
      $('#serviceCompletion').hidden = !done;
      f.elements.completedDate.required = done;
      $('#serviceCancelReason').hidden = f.elements.status.value !== 'Cancelado';
      f.elements.cancelReason.required = f.elements.status.value === 'Cancelado';
      try {
        $('#servicePricePreview').textContent =
          'Total do serviço: ' +
          brl(
            TrameDomain.serviceTotal(
              parseQuantity(f.elements.qty.value),
              parseMoney(f.elements.unitPrice.value),
              parseMoney(f.elements.setup.value)
            )
          );
      } catch {
        $('#servicePricePreview').textContent = 'Informe quantidade e valores válidos.';
      }
    }
    f.elements.status.onchange = preview;
    ['qty', 'unitPrice', 'setup'].forEach((k) => (f.elements[k].oninput = preview));
    preview();
  }
  function receive(job) {
    opsForm(
      `Receber · ${job.code}`,
      `<p class="form-note">${esc(job.client)} · saldo ${brl(job.balanceCents)}</p><div class="form-grid">${moneyField('Valor recebido (R$)', 'amount', job.balanceCents)}${inputField('Data do recebimento', 'date', today(), 'date', `required max="${today()}"`)}${selectField('Forma', 'method', ['Pix', 'Dinheiro', 'Transferência', 'Cartão', 'Boleto', 'Outro'].map((m) => option(m, m, 'Pix')).join(''))}${textField('Observação', 'note', '')}</div>`,
      async (f) => {
        await TrameAccess.request('/api/services/receive', {
          id: job.id,
          revision: job.revision,
          amountCents: parseMoney(f.elements.amount.value),
          date: f.elements.date.value,
          method: f.elements.method.value,
          note: f.elements.note.value.trim(),
        });
        await reload();
        return true;
      }
    );
  }
  function voidPayment(job, paymentId) {
    opsForm(
      `Anular recebimento · ${job.code}`,
      textField('Motivo da anulação', 'reason', '') +
        '<p class="hint">O lançamento permanece no histórico e deixa de compor o recebido.</p>',
      async (f) => {
        await TrameAccess.request('/api/services/void-receipt', {
          id: job.id,
          revision: job.revision,
          paymentId,
          reason: f.elements.reason.value.trim(),
        });
        await reload();
        return true;
      }
    );
    $('#opsForm').elements.reason.required = true;
  }
  function closeMonth() {
    const jobs = data.jobs.filter(completed),
      total = jobs.reduce((s, j) => s + j.totalCents, 0);
    opsForm(
      `Confirmar fechamento · ${kind}`,
      `<p>Fechar <b>${selectedMonth.split('-').reverse().join('/')}</b> com <b>${jobs.length} serviço(s)</b> concluído(s), no total de <b>${brl(total)}</b>?</p><p class="form-note">Os itens e valores ficarão preservados. Correções exigem reabertura pelo administrador, com motivo. Serviços ainda em execução ficam de fora.</p>`,
      async () => {
        await TrameAccess.request('/api/services/close', {
          technique: kind,
          month: selectedMonth,
          revision: data.closing?.revision || 0,
        });
        await reload();
        return true;
      }
    );
    $('#opsForm .modal-actions .primary').textContent = 'Confirmar fechamento';
  }
  function reopenMonth() {
    opsForm(
      `Reabrir fechamento · ${kind}`,
      textField('Motivo da reabertura', 'reason', '') +
        '<p class="form-note">O fechamento anterior será preservado no histórico ao fechar novamente.</p>',
      async (f) => {
        await TrameAccess.request('/api/services/reopen', {
          technique: kind,
          month: selectedMonth,
          revision: data.closing.revision,
          reason: f.elements.reason.value.trim(),
        });
        await reload();
        return true;
      }
    );
    $('#opsForm').elements.reason.required = true;
  }
  return { render };
})();
