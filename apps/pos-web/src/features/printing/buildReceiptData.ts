import type { TicketPrintData, KitchenPrintData, ReceiptLine } from './receiptFormatter';

export interface OrderLike {
  id?: string;
  folio: string;
  order_number?: string | number;
  created_at: string;
  total_cents: number;
  subtotal_cents?: number;
  tax_cents?: number;
  customer_label?: string | null;
  customer_phone?: string | null;
  delivery_address?: string | null;
  delivery_notes?: string | null;
  service_type?: string | null;
  driver_name?: string | null;
  lines?: Array<{
    quantity: number;
    product_name?: string;
    productName?: string;
    unit_price_cents?: number;
    line_total_cents?: number;
    total_cents?: number;
    line_notes?: string | null;
    station?: string | null;
    selected_modifiers?: Array<Record<string, unknown> | string>;
  }>;
}

export interface SessionLike {
  organization_id?: string;
  active_branch?: {
    id: string;
    name: string;
    timezone?: string;
    address?: string;
  } | null;
}

export function formatDateTimeMx(isoOrDate: string, timezone: string = 'America/Mazatlan'): string {
  try {
    const d = new Date(isoOrDate);
    if (isNaN(d.getTime())) return isoOrDate;
    return d.toLocaleString('es-MX', {
      timeZone: timezone,
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: true,
    });
  } catch {
    return isoOrDate;
  }
}

export function getServiceTypeLabel(type: string | null | undefined): string {
  if (!type) return 'MOSTRADOR';
  switch (type.toLowerCase()) {
    case 'delivery':
    case 'a domicilio':
      return 'A DOMICILIO';
    case 'takeout':
    case 'para llevar':
    case 'pasa por el':
    case 'pasan por el':
      return 'PASA POR EL';
    case 'dine-in':
    case 'en sucursal':
    case 'comedor':
      return 'EN SUCURSAL';
    default:
      return type.toUpperCase();
  }
}

export function buildTicketPrintData(
  order: OrderLike,
  options?: {
    session?: SessionLike | null;
    cashTender?: { receivedCents: number; changeCents: number } | null;
    footerNotes?: string[];
  }
): TicketPrintData {
  const branchTimezone = options?.session?.active_branch?.timezone || 'America/Mazatlan';
  const formattedDate = formatDateTimeMx(order.created_at || new Date().toISOString(), branchTimezone);

  const lines: ReceiptLine[] = (order.lines || []).map((l) => {
    const name = l.product_name || l.productName || 'PRODUCTO';
    const total = l.line_total_cents ?? l.total_cents ?? 0;
    const modifiers: string[] = [];
    if (Array.isArray(l.selected_modifiers)) {
      for (const mod of l.selected_modifiers) {
        if (typeof mod === 'string') {
          modifiers.push(mod);
        } else if (mod && typeof mod === 'object') {
          const text = (mod.kitchen_text || mod.text || mod.name || mod.option_name || '') as string;
          if (text) modifiers.push(text);
        }
      }
    }
    return {
      quantity: l.quantity,
      productName: name,
      unitPriceCents: l.unit_price_cents,
      totalCents: total,
      modifiers: modifiers.length > 0 ? modifiers : undefined,
      lineNotes: l.line_notes,
      station: l.station,
    };
  });

  const serviceLabel = getServiceTypeLabel(order.service_type);

  return {
    folio: order.folio,
    orderNumber: order.order_number || order.folio,
    createdAt: formattedDate,
    customerName: order.customer_label || 'PUBLICO GENERAL',
    customerPhone: order.customer_phone,
    driverName: order.driver_name,
    colonia: order.delivery_address ? order.delivery_address.substring(0, 20) : null,
    zone: serviceLabel,
    serviceTypeLabel: serviceLabel,
    lines,
    subtotalCents: order.subtotal_cents,
    taxCents: order.tax_cents,
    totalCents: order.total_cents,
    cashTender: options?.cashTender,
    footerNotes: options?.footerNotes,
  };
}

export function buildKitchenPrintData(
  order: OrderLike,
  options?: {
    session?: SessionLike | null;
    station?: string | null;
  }
): KitchenPrintData {
  const ticket = buildTicketPrintData(order, { session: options?.session });
  return {
    folio: ticket.folio,
    orderNumber: ticket.orderNumber,
    createdAt: ticket.createdAt,
    serviceTypeLabel: ticket.serviceTypeLabel,
    customerName: ticket.customerName,
    customerPhone: ticket.customerPhone,
    driverName: ticket.driverName,
    orderNotes: order.delivery_notes,
    station: options?.station,
    lines: ticket.lines,
  };
}
