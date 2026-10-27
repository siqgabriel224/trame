'use strict';
// Regras de cálculo compartilhadas pela aplicação e pelos documentos impressos.
const TrameDomain = (() => {
  const quantity = (i) => Object.values(i.sizes || {}).reduce((sum, n) => sum + n, 0);
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
    quantity,
    techniques,
    itemMoney,
    orderMoney,
    delivered,
    installmentBalance,
    stock,
  });
})();
