export type SalesMetric = 'gross' | 'net' | 'tax' | 'discount' | 'courtesy';

export interface Indicator {
  known_cents: number;
  unknown_operation_count: number;
}

export interface AppliedFilters {
  from_utc: string;
  to_utc: string;
  branch_id: string | null;
  register_id: string | null;
  cash_shift_id: string | null;
  family_id: string | null;
  service_type: string | null;
}

export interface BreakdownItem {
  id: string;
  label: string;
  gross: Indicator;
  net: Indicator;
  tax: Indicator;
  discount: Indicator;
  courtesy: Indicator;
  order_count: number;
  line_count: number;
  item_quantity: number;
}

export interface FacetItem { id: string; label: string }

export interface BranchTimeZoneOption {
  id: string;
  timezone: string;
}

export interface SalesMonitorResponse {
  applied_filters: AppliedFilters;
  summary: {
    gross: Indicator;
    net: Indicator;
    tax: Indicator;
    discount: Indicator;
    courtesy: Indicator;
    order_count: number;
    line_count: number;
    item_quantity: number;
    legacy_backfilled_line_count: number;
  };
  breakdowns: { families: BreakdownItem[]; services: BreakdownItem[] };
  facets: { cash_shifts: FacetItem[]; families: FacetItem[]; service_types: FacetItem[] };
  data_quality: { incomplete_operation_count: number };
}

export interface DrillDownItem {
  payment_id: string;
  order_id: string;
  folio: string;
  branch_id: string;
  cash_shift_id: string;
  register_id: string;
  service_type: string;
  confirmed_at: string;
  gross: Indicator;
  net: Indicator;
  tax: Indicator;
  discount: Indicator;
  courtesy: Indicator;
  order_count: number;
  line_count: number;
  item_quantity: number;
  quality_status: string;
}

export interface SalesDrillDownResponse {
  applied_filters: AppliedFilters;
  metric: SalesMetric;
  items: DrillDownItem[];
  next_cursor: string | null;
}

const metrics: SalesMetric[] = ['gross', 'net', 'tax', 'discount', 'courtesy'];
const isRecord = (value: unknown): value is Record<string, unknown> => (
  typeof value === 'object' && value !== null && !Array.isArray(value)
);
const isSafeNonNegative = (value: unknown): value is number => (
  Number.isSafeInteger(value) && (value as number) >= 0
);
const isNullableString = (value: unknown): value is string | null => value === null || typeof value === 'string';
const exactKeys = (value: Record<string, unknown>, keys: string[]) => {
  const actual = Object.keys(value).sort();
  const expected = [...keys].sort();
  if (actual.length !== expected.length || actual.some((key, index) => key !== expected[index])) {
    throw new Error('Respuesta del monitor de ventas inválida: propiedades no permitidas.');
  }
};

function parseIndicator(value: unknown): Indicator {
  if (!isRecord(value)
      || !isSafeNonNegative(value.known_cents)
      || !isSafeNonNegative(value.unknown_operation_count)) {
    throw new Error('Respuesta del monitor de ventas inválida: indicador no confiable.');
  }
  exactKeys(value, ['known_cents', 'unknown_operation_count']);
  return { known_cents: value.known_cents, unknown_operation_count: value.unknown_operation_count };
}

function parseAppliedFilters(value: unknown): AppliedFilters {
  if (!isRecord(value)
      || typeof value.from_utc !== 'string'
      || typeof value.to_utc !== 'string'
      || !isNullableString(value.branch_id)
      || !isNullableString(value.register_id)
      || !isNullableString(value.cash_shift_id)
      || !isNullableString(value.family_id)
      || !isNullableString(value.service_type)) {
    throw new Error('Respuesta del monitor de ventas inválida: filtros ausentes.');
  }
  exactKeys(value, ['from_utc', 'to_utc', 'branch_id', 'register_id', 'cash_shift_id', 'family_id', 'service_type']);
  return value as unknown as AppliedFilters;
}

function parseBreakdown(value: unknown): BreakdownItem {
  if (!isRecord(value)
      || typeof value.id !== 'string'
      || typeof value.label !== 'string'
      || !isSafeNonNegative(value.order_count)
      || !isSafeNonNegative(value.line_count)
      || !isSafeNonNegative(value.item_quantity)) {
    throw new Error('Respuesta del monitor de ventas inválida: desglose no confiable.');
  }
  exactKeys(value, ['id', 'label', ...metrics, 'order_count', 'line_count', 'item_quantity']);
  return {
    id: value.id,
    label: value.label,
    gross: parseIndicator(value.gross),
    net: parseIndicator(value.net),
    tax: parseIndicator(value.tax),
    discount: parseIndicator(value.discount),
    courtesy: parseIndicator(value.courtesy),
    order_count: value.order_count,
    line_count: value.line_count,
    item_quantity: value.item_quantity,
  };
}

function parseFacet(value: unknown): FacetItem {
  if (!isRecord(value) || typeof value.id !== 'string' || typeof value.label !== 'string') {
    throw new Error('Respuesta del monitor de ventas inválida: faceta no confiable.');
  }
  exactKeys(value, ['id', 'label']);
  return { id: value.id, label: value.label };
}

export function parseSalesMonitorResponse(value: unknown): SalesMonitorResponse {
  if (!isRecord(value) || !isRecord(value.summary) || !isRecord(value.breakdowns)
      || !isRecord(value.facets) || !isRecord(value.data_quality)) {
    throw new Error('Respuesta del sales monitor inválida.');
  }
  exactKeys(value, ['applied_filters', 'summary', 'breakdowns', 'facets', 'data_quality']);
  const summary = value.summary;
  const breakdowns = value.breakdowns;
  const facets = value.facets;
  if (!metrics.every((metric) => metric in summary)
      || !isSafeNonNegative(summary.order_count)
      || !isSafeNonNegative(summary.line_count)
      || !isSafeNonNegative(summary.item_quantity)
      || !isSafeNonNegative(summary.legacy_backfilled_line_count)
      || !Array.isArray(breakdowns.families)
      || !Array.isArray(breakdowns.services)
      || !Array.isArray(facets.cash_shifts)
      || !Array.isArray(facets.families)
      || !Array.isArray(facets.service_types)
      || !isSafeNonNegative(value.data_quality.incomplete_operation_count)) {
    throw new Error('Respuesta del monitor de ventas inválida: estructura incompleta.');
  }
  exactKeys(summary, [...metrics, 'order_count', 'line_count', 'item_quantity', 'legacy_backfilled_line_count']);
  exactKeys(breakdowns, ['families', 'services']);
  exactKeys(facets, ['cash_shifts', 'families', 'service_types']);
  exactKeys(value.data_quality, ['incomplete_operation_count']);
  return {
    applied_filters: parseAppliedFilters(value.applied_filters),
    summary: {
      gross: parseIndicator(summary.gross), net: parseIndicator(summary.net),
      tax: parseIndicator(summary.tax), discount: parseIndicator(summary.discount),
      courtesy: parseIndicator(summary.courtesy), order_count: summary.order_count,
      line_count: summary.line_count, item_quantity: summary.item_quantity,
      legacy_backfilled_line_count: summary.legacy_backfilled_line_count,
    },
    breakdowns: {
      families: breakdowns.families.map(parseBreakdown),
      services: breakdowns.services.map(parseBreakdown),
    },
    facets: {
      cash_shifts: facets.cash_shifts.map(parseFacet), families: facets.families.map(parseFacet),
      service_types: facets.service_types.map(parseFacet),
    },
    data_quality: { incomplete_operation_count: value.data_quality.incomplete_operation_count },
  };
}

export function parseSalesDrillDownResponse(value: unknown): SalesDrillDownResponse {
  if (!isRecord(value) || !metrics.includes(value.metric as SalesMetric)
      || !Array.isArray(value.items) || !isNullableString(value.next_cursor)) {
    throw new Error('Respuesta del detalle del monitor de ventas inválida.');
  }
  exactKeys(value, ['applied_filters', 'metric', 'items', 'next_cursor']);
  const items = value.items.map((item): DrillDownItem => {
    if (!isRecord(item)
        || !['payment_id', 'order_id', 'folio', 'branch_id', 'cash_shift_id', 'register_id',
          'service_type', 'confirmed_at', 'quality_status'].every((key) => typeof item[key] === 'string')
        || !isSafeNonNegative(item.order_count)
        || !isSafeNonNegative(item.line_count)
        || !isSafeNonNegative(item.item_quantity)) {
      throw new Error('Respuesta del detalle del monitor de ventas inválida: operación incompleta.');
    }
    exactKeys(item, [
      'payment_id', 'order_id', 'folio', 'branch_id', 'cash_shift_id', 'register_id',
      'service_type', 'confirmed_at', 'quality_status', ...metrics,
      'order_count', 'line_count', 'item_quantity',
    ]);
    return {
      payment_id: item.payment_id as string, order_id: item.order_id as string,
      folio: item.folio as string, branch_id: item.branch_id as string,
      cash_shift_id: item.cash_shift_id as string, register_id: item.register_id as string,
      service_type: item.service_type as string, confirmed_at: item.confirmed_at as string,
      quality_status: item.quality_status as string, gross: parseIndicator(item.gross),
      net: parseIndicator(item.net), tax: parseIndicator(item.tax),
      discount: parseIndicator(item.discount), courtesy: parseIndicator(item.courtesy),
      order_count: item.order_count, line_count: item.line_count, item_quantity: item.item_quantity,
    };
  });
  return {
    applied_filters: parseAppliedFilters(value.applied_filters), metric: value.metric as SalesMetric,
    items, next_cursor: value.next_cursor,
  };
}

function zonedMidnight(date: string, timeZone: string): Date {
  const [year, month, day] = date.split('-').map(Number);
  if (!year || !month || !day) throw new Error('Fecha local inválida.');
  const desired = Date.UTC(year, month - 1, day);
  let guess = desired;
  const formatter = new Intl.DateTimeFormat('en-CA', {
    timeZone, year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23',
  });
  for (let iteration = 0; iteration < 3; iteration += 1) {
    const parts = Object.fromEntries(
      formatter.formatToParts(new Date(guess)).map((part) => [part.type, part.value]),
    );
    const observed = Date.UTC(
      Number(parts.year), Number(parts.month) - 1, Number(parts.day),
      Number(parts.hour), Number(parts.minute), Number(parts.second),
    );
    guess += desired - observed;
  }
  return new Date(guess);
}

export function localDayUtcBounds(localDate: string, timeZone: string) {
  const start = zonedMidnight(localDate, timeZone);
  const [year, month, day] = localDate.split('-').map(Number);
  const next = new Date(Date.UTC(year, month - 1, day + 1));
  const nextDate = `${next.getUTCFullYear()}-${String(next.getUTCMonth() + 1).padStart(2, '0')}-${String(next.getUTCDate()).padStart(2, '0')}`;
  return { fromUtc: start.toISOString(), toUtc: zonedMidnight(nextDate, timeZone).toISOString() };
}

export function resolveBranchTimeZone(
  branchId: string,
  branches: BranchTimeZoneOption[],
): string | null {
  if (!branchId) return null;
  const branch = branches.find((item) => item.id === branchId);
  if (!branch?.timezone) return null;
  try {
    new Intl.DateTimeFormat('en-US', { timeZone: branch.timezone }).format(new Date(0));
    return branch.timezone;
  } catch {
    return null;
  }
}

export function formatKnownMoney(indicator: Indicator): string {
  const pesos = new Intl.NumberFormat('es-MX', {
    style: 'currency', currency: 'MXN', minimumFractionDigits: 2,
  }).format(indicator.known_cents / 100);
  return indicator.unknown_operation_count
    ? `${pesos} · ${indicator.unknown_operation_count} sin dato`
    : pesos;
}
