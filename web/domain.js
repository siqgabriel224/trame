'use strict';
// Regras de cálculo compartilhadas pela aplicação e pelos documentos impressos.
const TrameDomain = (() => {
  const matchesClient = (client, query) => {
    const fold = (value) =>
      String(value || '')
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .toLocaleLowerCase('pt-BR');
    const q = fold(query).trim();
    const document = (value) =>
      String(value || '')
        .replace(/[.\s/-]/g, '')
        .toUpperCase();
    return (
      !q ||
      fold(`${client.name} ${client.tradeName || ''}`).includes(q) ||
      document(client.document).includes(document(q))
    );
  };
  const serviceTotal = (qtyMilli, unitCents, setupCents = 0) =>
    Math.floor((qtyMilli * unitCents + 500) / 1000) + setupCents;
  const quantityInput = (qtyMilli) =>
    new Intl.NumberFormat('pt-BR', { useGrouping: false, maximumFractionDigits: 3 }).format(
      qtyMilli / 1000
    );
  const standardSizes = ['PP', 'P', 'M', 'G', 'GG'];
  const sizeGroups = (sizes = {}) => {
    const groups = ['Feminino', 'Masculino'].map((group) => ({
      label: group,
      rows: standardSizes.map((size) => [`${group} ${size}`, sizes[`${group} ${size}`] || 0]),
    }));
    const standard = new Set(groups.flatMap((g) => g.rows.map(([key]) => key)));
    const legacy = Object.entries(sizes).filter(
      ([key]) => !standard.has(key) && key !== 'Sob medida'
    );
    if (legacy.length) groups.push({ label: 'Grade anterior / outros tamanhos', rows: legacy });
    return groups;
  };
  const orderNumberQuery = (query) => {
    const match = String(query)
      .trim()
      .match(/^(?:(?:os|pedido|orç|orc|orçamento|orcamento|#)\s*[-#:]?\s*)?(\d+)$/i);
    return match ? Number(match[1]) : null;
  };
  const matchesOrder = (order, query) => {
    const number = orderNumberQuery(query);
    if (number !== null)
      return (order.kind === 'quote' ? order.quoteNumber : order.osNumber) === number;
    return [order.client, order.description, order.responsible, order.seller]
      .filter(Boolean)
      .join(' ')
      .toLocaleLowerCase('pt-BR')
      .includes(String(query).trim().toLocaleLowerCase('pt-BR'));
  };
  const quantity = (i) => Object.values(i.sizes || {}).reduce((sum, n) => sum + n, 0);
  const productionSectors = (i) => [
    'Separação',
    'Corte',
    'Costura',
    ...techniques(i).map((t) => t.type),
    'Acabamento',
    'Revisão',
    'Expedição',
  ];
  const productionTasks = (i) => {
    const sequence = [
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
    return [...(i.tasks || [])].sort(
      (a, b) => sequence.indexOf(a.sector) - sequence.indexOf(b.sector)
    );
  };
  const techniques = (i) =>
    i.techniques ||
    (i.embroidery
      ? [
          {
            type: 'Bordado',
            description: i.embroideryNotes || '',
            location: '',
            unitCents: 0,
            setupCents: 0,
          },
        ]
      : []);
  function itemMoney(i) {
    const rows = techniques(i),
      unit = (i.unitPriceCents || 0) + rows.reduce((sum, t) => sum + (t.unitCents || 0), 0),
      setup = rows.reduce((sum, t) => sum + (t.setupCents || 0), 0);
    return { unit, setup, total: quantity(i) * unit + setup };
  }
  function orderMoney(o) {
    const subtotal = o.items.reduce((sum, i) => sum + itemMoney(i).total, 0),
      total = subtotal + (o.freightCents || 0) - (o.discountCents || 0),
      received = (o.payments || [])
        .filter((p) => !p.voided)
        .reduce((sum, p) => sum + p.amountCents, 0);
    return {
      subtotal,
      total,
      received,
      balance: total - received,
      status: received === 0 ? 'Não pago' : received === total ? 'Pago' : 'Parcialmente pago',
    };
  }
  function delivered(i) {
    const sizes = { ...(i.deliveryBaseline || {}) };
    for (const d of i.deliveries || [])
      if (!d.voided)
        for (const [size, n] of Object.entries(d.sizes)) sizes[size] = (sizes[size] || 0) + n;
    return sizes;
  }
  const installmentBalance = (o, p) =>
    p.amountCents -
    (o.payments || [])
      .filter((r) => !r.voided && r.installmentId === p.id)
      .reduce((sum, r) => sum + r.amountCents, 0);
  function stock(state, s) {
    const rows = (state.reservations || []).filter((r) => r.stockId === s.id),
      onHand =
        s.openingMilli +
        (s.movements || []).reduce(
          (sum, m) => sum + m.qtyMilli * (m.kind === 'Entrada' ? 1 : -1),
          0
        ) -
        rows.filter((r) => r.stage === 'Consumido').reduce((sum, r) => sum + r.qtyMilli, 0),
      reserved = rows
        .filter((r) => r.stage === 'Reservado')
        .reduce((sum, r) => sum + r.qtyMilli, 0);
    return { onHand, reserved, available: onHand - reserved };
  }
  return Object.freeze({
    matchesClient,
    serviceTotal,
    quantityInput,
    sizeGroups,
    orderNumberQuery,
    matchesOrder,
    productionSectors,
    productionTasks,
    quantity,
    techniques,
    itemMoney,
    orderMoney,
    delivered,
    installmentBalance,
    stock,
  });
})();
