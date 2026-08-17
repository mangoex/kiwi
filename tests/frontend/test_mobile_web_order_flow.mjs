import assert from 'node:assert/strict';
import test from 'node:test';

function formatMoney(cents) {
  return `$${(cents / 100).toFixed(2)} MXN`;
}

function buildWhatsAppLink(folio, info, items, totalCents, restaurantPhone = '5215500000000') {
  const methodLabel = {
    cash: `Efectivo ${info.cash_amount ? `(Paga con: $${info.cash_amount})` : ''}`,
    card: 'Tarjeta (Al recibir)',
    transfer: 'Transferencia Bancaria',
  }[info.payment_method];

  const typeLabel = info.order_type === 'takeaway' ? '🏃 Para Recoger en Sucursal' : '🛵 Envío a Domicilio';

  let text = `🥝 *NUEVO PEDIDO - KIWI RESTAURANTE*\n`;
  text += `📋 *Folio:* #${folio}\n`;
  text += `👤 *Cliente:* ${info.name}\n`;
  text += `📱 *Teléfono:* ${info.phone}\n`;
  text += `📦 *Modalidad:* ${typeLabel}\n`;

  if (info.order_type === 'delivery') {
    const colPrefix = info.address_neighborhood.toLowerCase().startsWith('col') ? '' : 'Col. ';
    text += `📍 *Dirección:* ${info.address_street} #${info.address_number}, ${colPrefix}${info.address_neighborhood}\n`;
    if (info.address_notes) text += `📌 *Referencias:* ${info.address_notes}\n`;
  }

  text += `💳 *Método de Pago:* ${methodLabel}\n\n`;
  text += `🛒 *DETALLE DEL PEDIDO:*\n`;

  items.forEach((item) => {
    text += `• ${item.quantity}x ${item.product.name} (${formatMoney(item.product.price_cents)})\n`;
    if (item.notes) {
      text += `   ↳ _Nota: ${item.notes}_\n`;
    }
  });

  text += `\n💰 *TOTAL A PAGAR:* *${formatMoney(totalCents)}*\n`;
  if (info.order_notes) {
    text += `📝 *Comentarios Adicionales:* ${info.order_notes}\n`;
  }
  text += `\n✨ _Pedido generado desde la Web App Móvil de Kiwi_`;

  return `https://wa.me/${restaurantPhone}?text=${encodeURIComponent(text)}`;
}

test('Mobile Order WhatsApp link format for takeaway', () => {
  const info = {
    name: 'Carlos Ruiz',
    phone: '5511223344',
    order_type: 'takeaway',
    address_street: '',
    address_number: '',
    address_neighborhood: '',
    address_notes: '',
    payment_method: 'cash',
    cash_amount: '200',
    order_notes: 'Sin cubiertos',
  };

  const items = [
    {
      cart_id: 'item-1',
      product: { id: 'prod-1', name: 'Jugo Verde', price_cents: 6500 },
      quantity: 2,
      notes: 'Sin popote',
      line_total_cents: 13000,
    },
  ];

  const total = 13000;
  const link = buildWhatsAppLink('KIWI-5001', info, items, total);

  assert.ok(link.startsWith('https://wa.me/5215500000000?text='));
  const decoded = decodeURIComponent(link.replace('https://wa.me/5215500000000?text=', ''));

  assert.match(decoded, /#KIWI-5001/);
  assert.match(decoded, /Carlos Ruiz/);
  assert.match(decoded, /Para Recoger en Sucursal/);
  assert.match(decoded, /2x Jugo Verde/);
  assert.match(decoded, /\$130\.00 MXN/);
  assert.match(decoded, /Sin popote/);
  assert.match(decoded, /Paga con: \$200/);
});

test('Mobile Order WhatsApp link format for delivery with address', () => {
  const info = {
    name: 'Mariana Lopez',
    phone: '5599887766',
    order_type: 'delivery',
    address_street: 'Calle Roble',
    address_number: '450 Int 2',
    address_neighborhood: 'Col. Roma',
    address_notes: 'Edificio gris',
    payment_method: 'card',
    order_notes: '',
  };

  const items = [
    {
      cart_id: 'item-2',
      product: { id: 'prod-2', name: 'Sando Kyoto Pollo BBQ', price_cents: 12000 },
      quantity: 1,
      notes: '',
      line_total_cents: 12000,
    },
    {
      cart_id: 'item-3',
      product: { id: 'prod-3', name: 'Smoothie Rosa', price_cents: 9000 },
      quantity: 1,
      notes: '',
      line_total_cents: 9000,
    },
  ];

  const total = 21000;
  const link = buildWhatsAppLink('KIWI-8822', info, items, total);
  const decoded = decodeURIComponent(link.replace('https://wa.me/5215500000000?text=', ''));

  assert.match(decoded, /#KIWI-8822/);
  assert.match(decoded, /Mariana Lopez/);
  assert.match(decoded, /Envío a Domicilio/);
  assert.match(decoded, /Calle Roble #450 Int 2, Col\. Roma/);
  assert.match(decoded, /Tarjeta \(Al recibir\)/);
  assert.match(decoded, /\$210\.00 MXN/);
});
