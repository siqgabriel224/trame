'use strict';
const TrameServices = (() => {
  let kind = 'Bordado',
    selectedMonth = '',
    mode = 'jobs',
    selectedCompany = '',
    search = '',
    generation = 0,
    stockFamily = '',
    stockSearch = '',
    stockType = '';
  let data = { jobs: [], closing: null };
  let paletteLoading = null;
  const loadThreadPalette = () => {
    if (!paletteLoading)
      paletteLoading = TrameAccess.request('/api/thread-colors')
        .then((palette) => TrameDomain.setThreadPalette(palette))
        .catch((error) => {
          paletteLoading = null;
          throw error;
        });
    return paletteLoading;
  };
  const completed = (j) => ['Concluído', 'Entregue'].includes(j.status);
  const canAccess = () => ['admin', 'embroiderer'].includes(TrameAccess.session?.user.role);
  const printUrl = (clientId = selectedCompany) =>
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
    if (kind === 'DTF' && mode === 'stock') mode = 'jobs';
    selectedMonth ||= today().slice(0, 7);
    const current = ++generation;
    $('#opsWorkspace').innerHTML =
      `<h1>${kind}</h1><p class="form-note">Consultando serviços do mês…</p>`;
    try {
      const result = await TrameAccess.request(
        `/api/services?technique=${encodeURIComponent(kind)}&month=${selectedMonth}`
      );
      if (current !== generation || !['embroidery', 'dtf'].includes(view)) return;
      if (kind === 'Bordado' && mode === 'stock') await loadThreadPalette();
      if (current !== generation || !['embroidery', 'dtf'].includes(view)) return;
      data = result;
      if (selectedCompany && !data.companies.some((company) => company.id === selectedCompany))
        selectedCompany = '';
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

  const companyMatches = (job) =>
    !selectedCompany || (job.companyId || job.clientId) === selectedCompany;
  const filteredJobs = () => data.jobs.filter(companyMatches);
  function companyTabs() {
    const rows = data.companies || [];
    const selected = rows.find((c) => c.id === selectedCompany);
    return `<div class="tabs company-tabs" role="group" aria-label="Empresas contratantes"><button type="button" data-service-company="" class="${!selectedCompany ? 'selected' : ''}" aria-pressed="${!selectedCompany}">Todas as empresas</button>${rows
      .filter(
        (c) => c.active !== false || data.jobs.some((j) => (j.companyId || j.clientId) === c.id)
      )
      .map(
        (c) =>
          `<button type="button" data-service-company="${esc(c.id)}" class="${selectedCompany === c.id ? 'selected' : ''}" aria-pressed="${selectedCompany === c.id}">${c.kind === 'internal' ? 'Minha empresa' : esc(c.name)}${c.active === false ? ' · Inativa' : ''}</button>`
      )
      .join(
        ''
      )}</div>${selected ? `<p class="notes"><strong>${esc(selected.name)}</strong> · ${selected.kind === 'internal' ? 'Serviços para a própria empresa' : 'Empresa contratante / terceirização'} ${selected.kind === 'external' ? '<button type="button" class="secondary" id="editServiceCompany">Editar empresa</button>' : ''}${selected.kind === 'external' ? `<button type="button" class="secondary" data-delete-scope="serviceCompanies" data-delete-id="${esc(selected.id)}" data-delete-name="${esc(selected.name)}" data-delete-revision="${selected.revision}">Excluir empresa</button>` : ''}</p>` : ''}`;
  }
  function companyForm(company = {}) {
    opsForm(
      company.id ? 'Editar empresa contratante' : 'Cadastrar empresa contratante',
      `<p class="form-note">O cadastro ficará disponível em Bordado e DTF. Os serviços da própria empresa ficam na aba Minha empresa.</p><div class="form-grid">${inputField('Nome da empresa', 'name', company.name || '', 'text', 'required maxlength="200"')}${inputField('CNPJ / CPF (opcional)', 'document', company.document || '', 'text', 'maxlength="30"')}${inputField('Contato responsável', 'contact', company.contact || '', 'text', 'maxlength="150"')}${inputField('Telefone / WhatsApp', 'phone', company.phone || '', 'text', 'maxlength="60"')}${inputField('E-mail de contato', 'email', company.email || '', 'email', 'maxlength="254"')}${selectField('Situação', 'active', option('true', 'Ativa', String(company.active !== false)) + option('false', 'Inativa', String(company.active !== false)))}${textField('Observações', 'notes', company.notes || '')}</div>`,
      async (form) => {
        const row = Object.fromEntries(new FormData(form));
        row.active = row.active === 'true';
        if (company.id) row.id = company.id;
        const saved = await TrameAccess.request('/api/services/company/save', {
          company: row,
          revision: company.revision || 0,
        });
        selectedCompany = saved.active ? saved.id : '';
        await reload();
        return true;
      }
    );
  }
  function paintThreadColors(root) {
    root.querySelectorAll('[data-thread-tone]').forEach((element) => {
      if (/^#[0-9a-f]{6}$/i.test(element.dataset.threadTone))
        element.style.backgroundColor = element.dataset.threadTone;
    });
  }
  function drawStock() {
    const items = data.embroideryStock || [];
    const families = [...new Set(items.map((item) => TrameDomain.stockFamily(item)))].sort((a, b) =>
      a.localeCompare(b, 'pt-BR')
    );
    if (stockFamily && !families.includes(stockFamily)) stockFamily = '';
    if (stockType && !items.some((item) => item.category === stockType)) stockType = '';
    const low = items.filter((item) => item.active && item.balanceMilli < item.minimumMilli).length;
    $('#opsWorkspace').innerHTML = `
      <section class="embroidery-stock">
        <div class="thread-heading"><div><p class="thread-eyebrow">BORDADO · LINHAS E INSUMOS</p><h1>Estoque do bordado</h1><p class="notes">Encontre a cor, confira o código e acompanhe seus cones.</p></div><button class="primary" id="newEmbroiderySupply">＋ Cadastrar insumo</button></div>
        <div class="tabs"><button id="backEmbroideryJobs">Serviços</button><button class="selected" aria-pressed="true">Estoque do bordado</button><button id="refreshEmbroideryStock">↻ Atualizar</button></div>
        <div class="thread-summary"><span><strong>${items.length}</strong> cadastros</span><span><strong>${families.length}</strong> cores cadastradas</span><span class="${low ? 'thread-low' : ''}"><strong>${low}</strong> abaixo do mínimo</span></div>
        <div class="thread-inventory"><aside class="thread-colors" aria-label="Filtrar por cor"><h2>Suas cores</h2><p>Escolha uma cor para ver os códigos.</p><div class="thread-color-options"><button type="button" data-thread-family=""><span class="thread-all-colors" aria-hidden="true"></span><span>Todas as cores</span><small>${items.length}</small></button>${families
          .map((family) => {
            const matching = items.filter((item) => TrameDomain.stockFamily(item) === family);
            const tone = TrameDomain.stockColorHex(matching[0]);
            return `<button type="button" data-thread-family="${esc(family)}"><span class="thread-dot" data-thread-tone="${esc(tone)}" aria-hidden="true"></span><span>${esc(family)}</span><small>${matching.length}</small></button>`;
          })
          .join(
            ''
          )}</div><p class="thread-palette-note">Amostras aproximadas da cartela Zenith, consultadas pelo código da linha.</p></aside>
        <div class="thread-results"><div class="thread-toolbar"><label>Buscar código ou cor<input id="threadSearch" type="search" placeholder="Ex.: 2028, verde, azul…" value="${esc(stockSearch)}"></label><label>Tipo<select id="threadType">${option('', 'Todos os tipos', stockType)}${[
          ...new Set(items.map((item) => item.category)),
        ]
          .sort()
          .map((type) => option(type, type, stockType))
          .join(
            ''
          )}</select></label></div><p class="thread-result-count" id="threadResultCount" role="status"></p><div class="thread-cards" id="threadCards"></div></div></div>
      </section>`;
    const updateResults = () => {
      const visible = items
        .filter(
          (item) =>
            (!stockFamily || TrameDomain.stockFamily(item) === stockFamily) &&
            (!stockType || item.category === stockType) &&
            TrameDomain.matchesSupply(item, stockSearch)
        )
        .sort((a, b) =>
          String(a.code || a.color || a.category).localeCompare(
            String(b.code || b.color || b.category),
            'pt-BR',
            { numeric: true }
          )
        );
      $('#threadResultCount').textContent =
        `${stockFamily || 'Todas as cores'} · ${visible.length} de ${items.length} cadastros`;
      $$('[data-thread-family]').forEach((button) => {
        const selected = button.dataset.threadFamily === stockFamily;
        button.classList.toggle('selected', selected);
        button.setAttribute('aria-pressed', String(selected));
      });
      $('#threadCards').innerHTML =
        visible
          .map((item) => {
            const label = TrameDomain.stockLabel(item);
            const below = item.balanceMilli < item.minimumMilli;
            return `<article class="thread-card"><span class="thread-tone" data-thread-tone="${esc(TrameDomain.stockColorHex(item))}" aria-hidden="true"></span><div class="thread-card-body"><div class="thread-card-top"><span class="thread-type">${esc(item.category)}${item.brand ? ' · ' + esc(item.brand) : ''}</span><span class="badge ${!item.active ? '' : below ? 'late' : 'good'}">${!item.active ? 'Inativo' : below ? 'Repor' : 'Disponível'}</span></div><h3 class="thread-code">${esc(item.code || 'Sem código')}</h3><p class="thread-color-name">${esc(item.color || TrameDomain.stockReference(item)?.family || 'Grupo não informado')}</p><div class="thread-balance"><strong>${formatQuantity(item.balanceMilli)} <small>${esc(item.unit)}</small></strong><span>Mínimo ${formatQuantity(item.minimumMilli)} ${esc(item.unit)}</span></div><div class="thread-card-actions"><button class="secondary" data-supply-move="${esc(item.id)}" ${!item.active ? 'disabled' : ''}>Entrada / saída</button><button class="secondary" data-supply-edit="${esc(item.id)}">Editar</button><button class="secondary" data-supply-history="${esc(item.id)}">Histórico</button>${!item.active ? `<button class="secondary" data-supply-reactivate="${esc(item.id)}">Reativar</button>` : ''}<button class="thread-remove" data-delete-scope="embroideryStock" data-delete-id="${esc(item.id)}" data-delete-name="${esc(label)}" data-delete-revision="${item.revision}">Excluir</button></div></div></article>`;
          })
          .join('') ||
        `<div class="thread-empty"><h3>${items.length ? 'Nenhum código encontrado' : 'Sua cartela começa aqui'}</h3><p>${items.length ? 'Experimente outra cor ou limpe a busca.' : 'Cadastre sua primeira linha. A cor aparecerá na lateral e você poderá filtrar seus códigos.'}</p></div>`;
      paintThreadColors($('#opsWorkspace'));
      $$('[data-supply-edit]').forEach(
        (button) =>
          (button.onclick = () =>
            supplyForm(items.find((item) => item.id === button.dataset.supplyEdit)))
      );
      $$('[data-supply-move]').forEach(
        (button) =>
          (button.onclick = () =>
            supplyMove(items.find((item) => item.id === button.dataset.supplyMove)))
      );
      $$('[data-supply-history]').forEach(
        (button) =>
          (button.onclick = () =>
            supplyHistory(items.find((item) => item.id === button.dataset.supplyHistory)))
      );
      $$('[data-supply-reactivate]').forEach(
        (button) =>
          (button.onclick = async () => {
            const item = items.find((row) => row.id === button.dataset.supplyReactivate);
            try {
              await TrameAccess.request('/api/services/embroidery-stock/save', {
                item: { ...item, active: true },
                revision: item.revision,
              });
              await reload();
            } catch (error) {
              toast(error.message, true);
            }
          })
      );
    };
    $('#newEmbroiderySupply').onclick = () => supplyForm();
    $('#backEmbroideryJobs').onclick = () => {
      mode = 'jobs';
      draw();
    };
    $('#refreshEmbroideryStock').onclick = reload;
    $('#threadSearch').oninput = (event) => {
      stockSearch = event.target.value;
      updateResults();
    };
    $('#threadType').onchange = (event) => {
      stockType = event.target.value;
      updateResults();
    };
    $$('[data-thread-family]').forEach(
      (button) =>
        (button.onclick = () => {
          stockFamily = button.dataset.threadFamily;
          updateResults();
        })
    );
    updateResults();
  }
  function supplyForm(item = {}) {
    const suggestions = [
      ...new Set([
        ...TrameDomain.threadColors.map(([name]) => name),
        ...(data.embroideryStock || []).map((row) => row.color).filter(Boolean),
      ]),
    ];
    opsForm(
      item.id ? 'Editar insumo de bordado' : 'Cadastrar insumo de bordado',
      `<div class="supply-editor"><div><p class="supply-intro">Digite o código Zenith para buscar a amostra da cartela. O grupo abaixo serve apenas para filtrar.</p><div class="form-grid">${selectField('Tipo', 'category', ['Linha', 'Bobina', 'Entretela', 'Agulha', 'Estabilizador', 'Acessório', 'Outro'].map((type) => option(type, type, item.category || 'Linha')).join(''))}${inputField('Código / número da cor', 'code', item.code || '', 'text', 'maxlength="100" placeholder="Ex.: 2228"')}${inputField('Grupo para filtro', 'color', item.color || '', 'text', 'maxlength="100" list="stockColorSuggestions" placeholder="Ex.: Verde"')}<datalist id="stockColorSuggestions">${suggestions.map((color) => `<option value="${esc(color)}"></option>`).join('')}</datalist>${inputField('Unidade', 'unit', item.unit || 'cone', 'text', `required maxlength="20" ${item.id ? 'readonly' : ''}`)}${inputField('Saldo inicial', 'opening', TrameDomain.quantityInput(item.openingMilli || 0), 'text', `required inputmode="decimal" ${item.id ? 'readonly' : ''}`)}${inputField('Estoque mínimo', 'minimum', TrameDomain.quantityInput(item.minimumMilli || 0), 'text', 'required inputmode="decimal"')}</div><p class="hint">${item.id ? 'Saldo inicial e unidade são preservados. Use Entrada / saída para movimentar.' : 'Informe a quantidade na unidade escolhida. Depois, use Entrada / saída para movimentar.'}</p></div><aside class="supply-preview"><span class="supply-brand">${esc(item.brand || 'Zenith')}</span><div class="supply-color-sample" id="supplyColorSample" aria-hidden="true"></div><strong id="supplyPreviewColor">Digite o código</strong><span id="supplyPreviewCode">Busca na cartela Zenith</span><span class="supply-code-reference" id="supplyColorReference"></span><small>Amostra da cartela digital Zenith. O tom na tela é aproximado.</small></aside></div>`,
      async (form) => {
        const values = Object.fromEntries(new FormData(form));
        const row = {
          ...item,
          ...values,
          brand: item.brand || (values.category === 'Linha' ? 'Zenith' : ''),
          active: item.active !== false,
        };
        row.colorHex = TrameDomain.stockReference(row)?.hex || '';
        row.openingMilli = parseQuantity(row.opening);
        row.minimumMilli = parseQuantity(row.minimum);
        delete row.opening;
        delete row.minimum;
        await TrameAccess.request('/api/services/embroidery-stock/save', {
          item: row,
          revision: item.revision || 0,
        });
        stockFamily = TrameDomain.stockFamily(row);
        stockSearch = '';
        stockType = '';
        await reload();
        return true;
      }
    );
    const form = $('#opsForm');
    let autoGroup = !item.color;
    const preview = () => {
      const reference = TrameDomain.stockReference({
        ...item,
        category: form.elements.category.value,
        code: form.elements.code.value,
      });
      if (reference && autoGroup) form.elements.color.value = reference.family;
      $('#supplyColorSample').style.backgroundColor = reference?.hex || '#dce3de';
      $('#supplyPreviewColor').textContent = reference
        ? 'Zenith ' + reference.code
        : form.elements.code.value.trim()
          ? 'Código não localizado'
          : 'Digite o código';
      $('#supplyPreviewCode').textContent = reference
        ? reference.hex.toUpperCase()
        : 'Sem amostra na cartela digital';
      $('#supplyColorReference').textContent = reference
        ? 'Referência ' + reference.position + ' · Cartela 25'
        : 'Confira o código na sua cartela Zenith.';
      form.elements.color.required = form.elements.category.value === 'Linha';
      form.elements.code.required = form.elements.category.value === 'Linha';
    };
    form.elements.color.oninput = () => {
      autoGroup = false;
      preview();
    };
    form.elements.code.oninput = () => {
      autoGroup = true;
      preview();
    };
    form.elements.category.onchange = preview;
    preview();
  }

  function supplyMove(item) {
    opsForm(
      'Movimentar · ' + TrameDomain.stockLabel(item),
      `<p class="notes">Saldo: ${formatQuantity(item.balanceMilli)} ${esc(item.unit)}</p><div class="form-grid">${selectField('Movimentação', 'kind', option('Entrada', 'Entrada', 'Entrada') + option('Saída', 'Saída', ''))}${inputField('Quantidade em ' + item.unit, 'quantity', '1', 'text', 'required inputmode="decimal"')}${inputField('Data', 'date', today(), 'date', `required max="${today()}"`)}${inputField('Motivo', 'reason', '', 'text', 'required maxlength="1000"')}</div>`,
      async (form) => {
        const row = Object.fromEntries(new FormData(form));
        await TrameAccess.request('/api/services/embroidery-stock/move', {
          ...row,
          id: item.id,
          revision: item.revision,
          qtyMilli: parseQuantity(row.quantity),
        });
        await reload();
        return true;
      }
    );
  }
  function supplyHistory(item) {
    opsForm(
      'Histórico · ' + TrameDomain.stockLabel(item),
      `<p>Saldo inicial: ${formatQuantity(item.openingMilli)} ${esc(item.unit)} · Saldo atual: ${formatQuantity(item.balanceMilli)} ${esc(item.unit)}</p><div class="service-table-scroll"><table class="service-entry-table"><thead><tr><th>Data / tipo</th><th>Quantidade</th><th>Motivo</th><th>Registrado por</th></tr></thead><tbody>${item.movements.map((movement) => `<tr><td>${dateLabel(movement.date)} · ${esc(movement.kind)}</td><td>${formatQuantity(movement.qtyMilli)} ${esc(item.unit)}</td><td>${esc(movement.reason)}</td><td>${esc(movement.recordedBy)}</td></tr>`).join('') || '<tr><td colspan="4">Nenhuma movimentação registrada.</td></tr>'}</tbody></table></div>`,
      async () => true
    );
    $('#opsForm .modal-actions .primary').hidden = true;
  }
  function draw() {
    if (kind === 'Bordado' && mode === 'stock') {
      drawStock();
      return;
    }

    const done = filteredJobs().filter(completed),
      total = done.reduce((s, j) => s + j.totalCents, 0);
    const paid = done.reduce((s, j) => s + j.receivedCents, 0);
    $('#opsWorkspace').innerHTML =
      `<div class="section-heading"><div><h1>${kind}</h1><p class="notes">Serviços para a própria empresa e para empresas contratantes, separados por aba. Estes lançamentos não criam uma OS de confecção nem entram na produção de roupas.</p></div><div class="detail-actions"><button class="secondary" id="newServiceCompany">＋ Cadastrar empresa</button><button class="primary" id="newService">＋ Novo serviço</button></div></div>${companyTabs()}<div class="ops-toolbar"><label>Mês de referência<input type="month" id="serviceMonth" value="${selectedMonth}" required></label><button class="secondary" id="refreshServices">↻ Atualizar</button><div class="tabs service-tabs"><button id="serviceJobsTab" class="${mode === 'jobs' ? 'selected' : ''}">Serviços</button><button id="serviceClosingTab" class="${mode === 'closing' ? 'selected' : ''}">Fechamento mensal</button>${kind === 'Bordado' ? '<button id="embroideryStockTab">Estoque do bordado</button>' : ''}</div></div><div class="finance-summary"><div><small>SERVIÇOS NO MÊS</small><strong>${filteredJobs().filter((j) => j.status !== 'Cancelado').length}</strong></div><div><small>CONCLUÍDOS NO MÊS</small><strong>${brl(total)}</strong></div><div><small>RECEBIDO DOS CONCLUÍDOS</small><strong>${brl(paid)}</strong></div><div><small>SALDO DOS CONCLUÍDOS</small><strong>${brl(total - paid)}</strong></div></div>${mode === 'jobs' ? `<label class="service-search">Pesquisar serviços<input type="search" id="serviceSearch" value="${esc(search)}" placeholder="Número, empresa, CNPJ ou bordado"></label><div class="service-list" id="serviceList">${jobCards()}</div>` : closingPanel()}`;
    $('#embroideryStockTab')?.addEventListener('click', () => {
      mode = 'stock';
      render('embroidery');
    });
    $('#newService').onclick = () => edit();
    $('#newServiceCompany').onclick = () => companyForm();
    $('#editServiceCompany')?.addEventListener('click', () =>
      companyForm(data.companies.find((c) => c.id === selectedCompany))
    );
    $$('[data-service-company]').forEach((button) => {
      button.onclick = () => {
        selectedCompany = button.dataset.serviceCompany;
        draw();
      };
    });
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
  const serviceLines = (job) =>
    job.lines || [
      { description: job.description, qtyMilli: job.qtyMilli, unitCents: job.unitCents },
    ];
  const lineTotal = (line) => TrameDomain.serviceTotal(line.qtyMilli, line.unitCents);
  function jobCards() {
    const query = search.trim().toLocaleLowerCase('pt-BR');
    const jobs = filteredJobs().filter((j) =>
      `${j.code} ${j.orderNumber || ''} ${j.client} ${j.document} ${serviceLines(j)
        .map((l) => l.description)
        .join(' ')}`
        .toLocaleLowerCase('pt-BR')
        .includes(query)
    );
    if (!jobs.length) return '<p class="ops-empty">Nenhum serviço encontrado neste mês.</p>';
    return `<div class="compact-services">${jobs
      .map((j) => {
        const locked = completed(j) && data.closing?.status === 'Fechado';
        return `<section class="service-sheet"><div class="service-sheet-heading"><strong>${esc(j.client)} · ${esc(j.code)}${j.orderNumber ? ' · Pedido ' + esc(j.orderNumber) : ''}</strong><span>Entrada: ${dateLabel(j.entryDate)} · Prazo: ${j.dueDate ? dateLabel(j.dueDate) : 'Não informado'} · ${esc(completed(j) ? 'Concluído' : j.status === 'Cancelado' ? 'Cancelado' : 'Em andamento')}</span><div class="detail-actions"><button class="secondary" data-service-edit="${esc(j.id)}" ${locked || j.status === 'Cancelado' ? 'disabled' : ''}>Editar</button><button class="secondary" data-service-receive="${esc(j.id)}" ${j.status === 'Cancelado' || j.balanceCents <= 0 ? 'disabled' : ''}>Receber</button><button class="secondary" data-delete-scope="services" data-delete-id="${esc(j.id)}" data-delete-name="${esc(j.code + ' · ' + j.client)}" data-delete-revision="${j.revision}">Excluir</button></div></div><div class="service-table-scroll"><table class="service-entry-table"><thead><tr><th scope="col">${kind === 'Bordado' ? 'Bordado / posição' : 'DTF / aplicação'}</th><th scope="col">R$ / unidade</th><th scope="col">Quantidade</th><th scope="col">Total</th></tr></thead><tbody>${serviceLines(
          j
        )
          .map(
            (line) =>
              `<tr><td>${esc(line.description)}</td><td>${brl(line.unitCents)}</td><td>${formatQuantity(line.qtyMilli)}</td><td>${brl(lineTotal(line))}</td></tr>`
          )
          .join(
            ''
          )}${j.setupCents ? `<tr><td colspan="3">Preparação / matriz anterior</td><td>${brl(j.setupCents)}</td></tr>` : ''}</tbody><tfoot><tr><th scope="row" colspan="3">TOTAL</th><td>${brl(j.totalCents)}</td></tr></tfoot></table></div><div class="service-sheet-footer">Recebido: ${brl(j.receivedCents)} · Saldo: ${brl(j.balanceCents)}${locked ? ' · Mês fechado' : ''}${j.payments.length ? `<details><summary>Recebimentos e histórico</summary>${j.payments.map((payment) => `<div class="ops-inline"><span>${dateLabel(payment.date)} · ${esc(payment.method)} · ${brl(payment.amountCents)}${payment.voided ? ' · ANULADO: ' + esc(payment.voidReason) : ''}</span>${!payment.voided ? `<button class="secondary" data-service-void="${esc(j.id)}" data-payment="${esc(payment.id)}">Anular com motivo</button>` : ''}</div>`).join('')}</details>` : ''}</div></section>`;
      })
      .join(
        ''
      )}<p class="service-total">TOTAL DA LISTA: <strong>${brl(jobs.filter((j) => j.status !== 'Cancelado').reduce((sum, j) => sum + j.totalCents, 0))}</strong></p></div>`;
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
      : filteredJobs().filter(completed);
    const groups = new Map();
    for (const j of jobs.filter(companyMatches)) {
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
    const pending = filteredJobs().filter((j) =>
      ['Recebido', 'Em execução', 'Em andamento'].includes(j.status)
    ).length;
    return `<section class="service-closing"><div class="section-heading"><div><h2>Fechamento de ${kind} · ${selectedMonth.split('-').reverse().join('/')}</h2><span class="badge ${closed ? 'good' : 'pending'}">${closed ? 'Fechado' : closing?.status || 'Em aberto'}</span></div><div class="detail-actions">${closed ? (TrameAccess.session.user.role === 'admin' ? '<button class="secondary" id="reopenServices">Reabrir com motivo</button>' : '') : `<button class="primary" id="closeServices" ${!jobs.length || selectedCompany ? 'disabled' : ''}>Fechar mês de todas as empresas</button>`}<a class="secondary" target="_blank" rel="noopener" href="${printUrl()}">Imprimir demonstrativo</a></div></div><p class="form-note">Entram no fechamento os serviços concluídos ou entregues, pela data de conclusão. ${pending ? `${pending} serviço(s) recebido(s) ou em execução ficam fora deste fechamento.` : ''}</p>${selectedCompany ? '<p class="hint">O fechamento mensal reúne todas as empresas. Use a aba Todas as empresas para fechar; os demonstrativos podem ser impressos por empresa.</p>' : ''}${closed ? `<p class="notes">Fechado por ${esc(closing.closedBy)} em ${new Date(closing.closedAt).toLocaleString('pt-BR')}. Itens e valores preservados; recebimentos posteriores atualizam o saldo.</p>` : ''}${closing?.reopened ? `<p class="notes">Última reabertura: ${esc(closing.reopened.by)} · ${esc(closing.reopened.reason)}</p>` : ''}<div class="ops-cards">${[...groups.values()].map((g) => `<article class="ops-card"><h3>${esc(g.name)}</h3><p class="notes">${esc(g.document || 'Documento não informado')} · ${g.count} serviço(s)</p><div class="money-grid"><div><small>Total</small><strong>${brl(g.total)}</strong></div><div><small>Recebido</small><strong>${brl(g.paid)}</strong></div><div><small>Saldo atual</small><strong>${brl(g.total - g.paid)}</strong></div></div><a class="secondary" target="_blank" rel="noopener" href="${printUrl(g.id)}">Demonstrativo deste cliente</a></article>`).join('') || '<p class="ops-empty">Nenhum serviço concluído para fechar neste mês.</p>'}</div>${closing?.history?.length ? `<details><summary>Versões anteriores do fechamento</summary>${closing.history.map((h) => `<p class="notes">Versão ${h.revision} · ${esc(h.closedBy)} · ${new Date(h.closedAt).toLocaleString('pt-BR')} · ${brl(h.totalCents)}${h.reopened ? '<br>Reaberto: ' + esc(h.reopened.reason) : ''}</p>`).join('')}</details>` : ''}</section>`;
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
    const clients = (data.companies || []).filter(
      (c) => c.active !== false || c.id === (job.companyId || job.clientId)
    );
    const companyId = job.companyId || job.clientId || selectedCompany;
    let lines = job.id
      ? serviceLines(job).map((l) => ({ ...l }))
      : [{ description: '', qtyMilli: 1000, unitCents: 0 }];
    opsForm(
      job.id ? `Editar ${job.code}` : `Novo serviço de ${kind}`,
      `<div class="form-grid">${selectField('Empresa contratante', 'clientId', option('', 'Selecione a empresa', companyId) + clients.map((c) => option(c.id, c.kind === 'internal' ? 'Minha empresa · ' + c.name : c.name, companyId)).join(''))}${inputField('Número do pedido', 'orderNumber', job.orderNumber || '', 'text', 'maxlength="60"')}${inputField('Data de entrada', 'entryDate', job.entryDate || today(), 'date', 'required')}${inputField('Prazo', 'dueDate', job.dueDate || job.entryDate || today(), 'date', 'required')}${selectField('Situação', 'status', ['Em andamento', 'Concluído'].map((status) => option(status, status, completed(job) ? 'Concluído' : 'Em andamento')).join(''))}</div><p class="form-note">Registre cada posição ou aplicação em uma linha: frente, costas, manga…</p><div class="service-table-scroll"><table class="service-entry-table service-lines-editor"><thead><tr><th>${kind === 'Bordado' ? 'Bordado / posição' : 'DTF / aplicação'}</th><th>R$ / unidade</th><th>Quantidade</th><th>Total</th><th></th></tr></thead><tbody id="serviceLineRows"></tbody></table></div><button type="button" class="secondary" id="addServiceLine">＋ Adicionar ${kind === 'Bordado' ? 'bordado' : 'aplicação'}</button><div class="price-preview" id="servicePricePreview"></div>${job.setupCents ? '<p class="hint">O valor de preparação / matriz anterior será preservado no total.</p>' : ''}`,
      async (form) => {
        readLines();
        const row = {
          ...job,
          ...Object.fromEntries(new FormData(form)),
          technique: kind,
          lines,
          setupCents: job.setupCents || 0,
        };
        row.companyId = row.clientId;
        const saved = await TrameAccess.request('/api/services/save', {
          job: row,
          revision: job.revision || 0,
        });
        selectedMonth = (saved.completedDate || saved.entryDate).slice(0, 7);
        await reload();
        return true;
      }
    );
    const form = $('#opsForm');
    form.elements.clientId.required = true;
    function readLines() {
      lines = [...document.querySelectorAll('#serviceLineRows tr')].map((row) => ({
        description: row.querySelector('[data-line-description]').value.trim(),
        qtyMilli: parseQuantity(row.querySelector('[data-line-qty]').value),
        unitCents: parseMoney(row.querySelector('[data-line-price]').value),
      }));
    }
    function preview() {
      try {
        readLines();
        [...document.querySelectorAll('#serviceLineRows tr')].forEach((row, index) => {
          row.querySelector('[data-line-total]').textContent = brl(lineTotal(lines[index]));
        });
        $('#servicePricePreview').textContent =
          'TOTAL: ' + brl(lines.reduce((sum, line) => sum + lineTotal(line), job.setupCents || 0));
      } catch {
        $('#servicePricePreview').textContent = 'Informe quantidades e valores válidos.';
      }
    }
    function drawLines() {
      $('#serviceLineRows').innerHTML = lines
        .map(
          (line, index) =>
            `<tr><td><input data-line-description aria-label="Descrição do item ${index + 1}" required maxlength="500" value="${esc(line.description)}" placeholder="Ex.: Bordado frente"></td><td><input data-line-price aria-label="Valor unitário do item ${index + 1}" required inputmode="decimal" value="${esc(moneyInput(line.unitCents))}"></td><td><input data-line-qty aria-label="Quantidade do item ${index + 1}" required inputmode="decimal" value="${esc(TrameDomain.quantityInput(line.qtyMilli))}"></td><td data-line-total>${brl(lineTotal(line))}</td><td><button type="button" class="secondary" data-remove-service-line="${index}" aria-label="Remover item ${index + 1}" ${lines.length === 1 ? 'disabled' : ''}>×</button></td></tr>`
        )
        .join('');
      $$('[data-remove-service-line]').forEach((button) => {
        button.onclick = () => {
          try {
            readLines();
          } catch {
            return toast('Confira os valores antes de remover uma linha.', true);
          }
          lines.splice(Number(button.dataset.removeServiceLine), 1);
          drawLines();
        };
      });
      $('#serviceLineRows').oninput = preview;
      preview();
    }
    $('#addServiceLine').onclick = () => {
      try {
        readLines();
      } catch {
        return toast('Confira os valores antes de adicionar uma linha.', true);
      }
      if (lines.length >= 100) return toast('Limite de 100 itens por serviço.', true);
      lines.push({ description: '', qtyMilli: 1000, unitCents: 0 });
      drawLines();
    };
    drawLines();
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
