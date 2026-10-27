'use strict';
const serviceEscape = (value) =>
  String(value ?? '').replace(
    /[&<>"']/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]
  );
const serviceCurrency = (value) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value / 100);
const serviceDate = (value) => new Date(value + 'T12:00:00').toLocaleDateString('pt-BR');
async function loadServicePrint() {
  try {
    const params = new URLSearchParams(location.search),
      kind = params.get('technique'),
      month = params.get('month');
    const response = await fetch(
      `/api/services?technique=${encodeURIComponent(kind)}&month=${encodeURIComponent(month)}`
    );
    if (response.status === 401) {
      location.replace('/login?next=' + encodeURIComponent(location.pathname + location.search));
      return;
    }
    const data = await response.json();
    if (!response.ok) throw Error(data.error || 'Não foi possível preparar o demonstrativo.');
    const closed = data.closing?.status === 'Fechado',
      company = closed ? data.closing.company : data.company;
    let jobs = closed
      ? data.closing.jobs.map((j) => ({
          ...j,
          receivedCents:
            data.jobs.find((live) => live.id === j.id)?.receivedCents ?? j.receivedCents,
        }))
      : data.jobs.filter((j) => ['Concluído', 'Entregue'].includes(j.status));
    if (params.get('clientId')) jobs = jobs.filter((j) => j.clientId === params.get('clientId'));
    const clients = new Map();
    for (const job of jobs) {
      const rows = clients.get(job.clientId) || [];
      rows.push(job);
      clients.set(job.clientId, rows);
    }
    const total = jobs.reduce((s, j) => s + j.totalCents, 0),
      paid = jobs.reduce((s, j) => s + j.receivedCents, 0);
    document.title = `${kind} · ${month} · Demonstrativo de serviços`;
    document.querySelector('#printTitle').textContent =
      `${kind} · ${month} · ${closed ? 'Fechamento' : 'Prévia em aberto'}`;
    document.querySelector('#document').innerHTML =
      `<header class="document-header"><div><div class="brand">${serviceEscape(company.name || 'Tramê')}</div><p>${[company.tradeName, company.document, company.phone, company.email, company.address].filter(Boolean).map(serviceEscape).join('<br>')}</p></div><div class="document-code"><h1>DEMONSTRATIVO DE SERVIÇOS</h1><strong>${serviceEscape(kind)}</strong><p>Referência: ${serviceEscape(month.split('-').reverse().join('/'))}</p><b>${closed ? 'FECHAMENTO' : 'PRÉVIA EM ABERTO'}</b></div></header><p>${closed ? `Fechado por ${serviceEscape(data.closing.closedBy)} em ${new Date(data.closing.closedAt).toLocaleString('pt-BR')}. Itens e valores do fechamento preservados.` : 'Serviços concluídos no período. Este mês ainda não foi fechado.'} Recebimentos atualizados até esta emissão.</p>${[...clients.values()].map((rows) => `<section><h2>${serviceEscape(rows[0].client)}</h2><p>${serviceEscape(rows[0].document || '')}</p><div class="service-report-table"><table class="service-statement"><thead><tr><th>Serviço / conclusão</th><th>Descrição / vendedora</th><th>Quantidade</th><th>Total</th><th>Recebido</th><th>Saldo</th></tr></thead><tbody>${rows.map((j) => `<tr><td>${serviceEscape(j.code)}<br>${serviceDate(j.completedDate)}</td><td>${serviceEscape(j.description)}<small>Vendedora: ${serviceEscape(j.seller || 'Não informada')}</small>${j.reference ? `<small>Ref.: ${serviceEscape(j.reference)}</small>` : ''}</td><td>${new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 3 }).format(j.qtyMilli / 1000)} ${serviceEscape(j.unit)}</td><td>${serviceCurrency(j.totalCents)}</td><td>${serviceCurrency(j.receivedCents)}</td><td>${serviceCurrency(j.totalCents - j.receivedCents)}</td></tr>`).join('')}</tbody></table></div></section>`).join('') || '<p>Nenhum serviço concluído para este demonstrativo.</p>'}<section class="totals"><div class="total"><span>TOTAL DOS SERVIÇOS</span><b>${serviceCurrency(total)}</b></div><div><span>Recebido</span><b>${serviceCurrency(paid)}</b></div><div><span>Saldo a receber</span><b>${serviceCurrency(total - paid)}</b></div></section><footer>${serviceEscape(kind)} · ${serviceEscape(month)} · Emitido em ${new Date().toLocaleString('pt-BR')}</footer>`;
    document.querySelector('#printButton').disabled = false;
  } catch (error) {
    document.querySelector('#printTitle').textContent = 'Não foi possível preparar o demonstrativo';
    document.querySelector('#document').textContent = error.message;
  }
}
document.querySelector('#printButton').onclick = () => window.print();
loadServicePrint();
