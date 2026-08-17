import { Product, Category, CustomerOrderInfo, CreatedOrderResult, CartItem } from './types';
import { getProductImage, getProductNutritionMeta } from './imageMap';

const API_BASE_URL = '/api/v1';

// Seed catalog fallback to guarantee 100% fail-safe display if API server is not running
const BACKUP_CATALOG: Product[] = [
  {
    id: 'prod-jug-ver',
    name: 'Jugo Verde',
    sku: 'JUG-VER',
    category_name: 'Jugos y Extractos',
    price_cents: 6500,
    description: 'Naranja, piña, pepino, apio y nopal recién extraídos.',
    station: 'barra',
  },
  {
    id: 'prod-ext-roj',
    name: 'Extracto Rojo',
    sku: 'EXT-ROJ',
    category_name: 'Jugos y Extractos',
    price_cents: 6300,
    description: 'Fresco sabor de pepino con apio, betabel, limón y dulce de manzana roja.',
    station: 'barra',
  },
  {
    id: 'prod-smo-ros',
    name: 'Smoothie Rosa',
    sku: 'SMO-ROS',
    category_name: 'Smoothies y Licuados',
    price_cents: 9000,
    description: 'Fresa con leche de almendra, miel de abeja, dátil, chía y espinaca.',
    station: 'barra',
  },
  {
    id: 'prod-mat-pin',
    name: 'Maccha Pinku (con fresa)',
    sku: 'MAT-PIN',
    category_name: 'Café y Matcha',
    price_cents: 13000,
    description: 'Matcha ceremonial japonés en capas sobre leche de avena y puré natural de fresa.',
    station: 'barra',
  },
  {
    id: 'prod-ens-fru',
    name: 'Ensalada Frutos Rojos',
    sku: 'ENS-FRU',
    category_name: 'Ensaladas',
    price_cents: 12500,
    description: 'Lechuga orgánica, fresa, arándanos, queso panela, cacahuates garapiñados y aderezo balsámico.',
    station: 'cocina',
  },
  {
    id: 'prod-san-kyo',
    name: 'Sando Kyoto Pollo BBQ',
    sku: 'SAN-KYO-BBQ',
    category_name: 'Emparedados y Sandos',
    price_cents: 12000,
    description: 'Sándwich estilo japonés en pan brioche grueso, pollo crujiente con glaseado BBQ y col fresca.',
    station: 'cocina',
  },
  {
    id: 'prod-pan-cue',
    name: 'Cuernito Jamón/Phila',
    sku: 'PAN-CUE',
    category_name: 'Panadería',
    price_cents: 3800,
    description: 'Croissant artesanal dorado horneado relleno de jamón ahumado y queso Philadelphia.',
    station: 'barra',
  },
  {
    id: 'prod-com-lig',
    name: 'Combo Ligero',
    sku: 'COM-LIG',
    category_name: 'Combos',
    price_cents: 10500,
    description: 'Sándwich básico artesanal + fresco jugo de naranja del día + dulce galleta con chispas.',
    station: 'barra',
  }
];

const DEFAULT_CATEGORIES: Category[] = [
  { id: 'all', name: 'Todos' },
  { id: 'c1', name: 'Jugos y Extractos' },
  { id: 'c2', name: 'Smoothies y Licuados' },
  { id: 'c3', name: 'Café y Matcha' },
  { id: 'c4', name: 'Ensaladas' },
  { id: 'c5', name: 'Emparedados y Sandos' },
  { id: 'c6', name: 'Panadería' },
  { id: 'c7', name: 'Combos' },
];

export async function fetchMobileMenu(): Promise<{ products: Product[]; categories: Category[] }> {
  try {
    const [catRes, prodRes] = await Promise.all([
      fetch(`${API_BASE_URL}/categories`),
      fetch(`${API_BASE_URL}/catalog/products`),
    ]);

    if (!prodRes.ok) {
      throw new Error('API unavailable, loading local catalog');
    }

    const rawProducts = await prodRes.json();
    const rawCats = catRes.ok ? await catRes.json() : [];

    const products: Product[] = (Array.isArray(rawProducts) && rawProducts.length > 0 ? rawProducts : BACKUP_CATALOG)
      .filter((p: any) => p.status === 'active' || !p.status)
      .map((p: any) => {
        const meta = getProductNutritionMeta(p.name || '');
        return {
          id: p.id || p.sku,
          name: p.name,
          sku: p.sku,
          category_name: p.category_name || 'Menú',
          category_id: p.category_id,
          price_cents: typeof p.price_cents === 'number' ? p.price_cents : 6500,
          description: p.description || '',
          station: p.station || 'barra',
          image_url: getProductImage(p),
          calories: meta.calories,
          prep_time: meta.prep_time,
          tags: [meta.tag],
          is_available: p.is_available !== false,
        };
      });

    const categories: Category[] = [{ id: 'all', name: 'Todos' }];
    if (Array.isArray(rawCats) && rawCats.length > 0) {
      rawCats.forEach((c: any) => {
        if (!categories.find(item => item.name === c.name)) {
          categories.push({ id: c.id, name: c.name, display_order: c.display_order });
        }
      });
    } else {
      DEFAULT_CATEGORIES.forEach(c => {
        if (!categories.find(item => item.name === c.name)) {
          categories.push(c);
        }
      });
    }

    return { products, categories };
  } catch {
    // Graceful offline/direct load with high-res images
    const products: Product[] = BACKUP_CATALOG.map(p => {
      const meta = getProductNutritionMeta(p.name);
      return {
        ...p,
        image_url: getProductImage(p),
        calories: meta.calories,
        prep_time: meta.prep_time,
        tags: [meta.tag],
        is_available: true,
      };
    });
    return { products, categories: DEFAULT_CATEGORIES };
  }
}

export function formatMoney(cents: number): string {
  return `$${(cents / 100).toFixed(2)} MXN`;
}

export function buildWhatsAppLink(
  folio: string,
  info: CustomerOrderInfo,
  items: CartItem[],
  totalCents: number,
  restaurantPhone: string = '5215500000000'
): string {
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

export async function submitMobileOrder(
  info: CustomerOrderInfo,
  items: CartItem[],
  totalCents: number,
  branchId?: string
): Promise<CreatedOrderResult> {
  const folioNumber = Math.floor(1000 + Math.random() * 9000);
  const folio = `KIWI-${folioNumber}`;
  const now = new Date().toISOString();

  // Submit directly to public orders API
  try {
    const deliveryAddressText = info.order_type === 'delivery'
      ? `${info.address_street} #${info.address_number}, Col. ${info.address_neighborhood}${info.address_notes ? ` (Ref: ${info.address_notes})` : ''}`
      : undefined;

    const payload = {
      owner_name: info.name,
      customer_phone: info.phone,
      order_type: info.order_type === 'takeaway' ? 'takeout' : 'delivery',
      branch_id: branchId,
      delivery_address: deliveryAddressText,
      payment_method_intent: info.payment_method,
      order_notes: info.order_notes,
      lines: items.map(item => ({
        product_id: item.product.id || item.product.sku,
        quantity: item.quantity,
        notes: item.notes || '',
      })),
    };

    const res = await fetch(`${API_BASE_URL}/public/orders`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (res.ok) {
      const data = await res.json();
      const realFolio = data.folio || folio;
      const whatsappUrl = buildWhatsAppLink(realFolio, info, items, data.total_cents || totalCents);
      return {
        folio: realFolio,
        id: data.id || `ord-${folioNumber}`,
        created_at: data.created_at || now,
        customer_info: info,
        items,
        total_cents: data.total_cents || totalCents,
        whatsapp_url: whatsappUrl,
      };
    }
  } catch (err) {
    console.warn('Could not post directly to /public/orders, proceeding with WhatsApp link:', err);
  }

  const whatsappUrl = buildWhatsAppLink(folio, info, items, totalCents);
  return {
    folio,
    id: `ord-${folioNumber}`,
    created_at: now,
    customer_info: info,
    items,
    total_cents: totalCents,
    whatsapp_url: whatsappUrl,
  };
}
