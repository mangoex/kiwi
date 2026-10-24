import React, { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchApi } from '@restaurantos/api-client';
import { Button } from '@restaurantos/ui';
import { useAdminSession } from '../../lib/adminSession';
import CorporateReconciliationDashboard from './CorporateReconciliationDashboard';

type IngredientRow = { item_id: string; item_name: string | null; unit_code: string | null; quantity: string; known_operation_count: number };
type ExpenseRow = { id: string; source: 'purchase' | 'purchase_cancellation' | 'cash_movement' | 'expense' | 'expense_cancellation'; branch_id: string; occurred_at: string; subtotal_cents: number | null; discount_cents: number | null; tax_cents: number | null; total_cents: number; linked_source_id: string | null };
type IngredientReport = { items: IngredientRow[]; incomplete_operation_count: number; next_cursor: string | null };
type ExpenseReport = { items: ExpenseRow[]; unknown_tax_source_count: number; next_cursor: string | null };
type Tab = 'reconciliation' | 'ingredient' | 'expenses';

const localDate = (timeZone: string) => new Intl.DateTimeFormat('en-CA', {
  timeZone, year: 'numeric', month: '2-digit', day: '2-digit',
}).format(new Date());

function zonedMidnight(date: string, timeZone: string) {
  const [year, month, day] = date.split('-').map(Number);
  const desired = Date.UTC(year, month - 1, day);
  let guess = desired;
  const formatter = new Intl.DateTimeFormat('en-CA', {
    timeZone, year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23',
  });
  for (let iteration = 0; iteration < 3; iteration += 1) {
    const parts = Object.fromEntries(formatter.formatToParts(new Date(guess)).map((part) => [part.type, part.value]));
    const observed = Date.UTC(Number(parts.year), Number(parts.month) - 1, Number(parts.day), Number(parts.hour), Number(parts.minute), Number(parts.second));
    guess += desired - observed;
  }
  return new Date(guess);
}

function localDayUtcBounds(date: string, timeZone: string) {
  const [year, month, day] = date.split('-').map(Number);
  const next = new Date(Date.UTC(year, month - 1, day + 1));
  const nextDate = `${next.getUTCFullYear()}-${String(next.getUTCMonth() + 1).padStart(2, '0')}-${String(next.getUTCDate()).padStart(2, '0')}`;
  return { fromUtc: zonedMidnight(date, timeZone).toISOString(), toUtc: zonedMidnight(nextDate, timeZone).toISOString() };
}

const money = new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' });
const tableWrap: React.CSSProperties = { overflowX: 'auto', border: '1px solid #d1d5db', borderRadius: 10, background: '#fff' };
const tableStyle: React.CSSProperties = { width: '100%', minWidth: 640, borderCollapse: 'collapse', color: '#111827' };
const headerStyle: React.CSSProperties = { padding: 12, textAlign: 'left', background: '#f3f4f6', borderBottom: '1px solid #d1d5db' };
const cellStyle: React.CSSProperties = { padding: 12, borderBottom: '1px solid #e5e7eb', whiteSpace: 'nowrap' };
const amountStyle: React.CSSProperties = { ...cellStyle, textAlign: 'right', fontVariantNumeric: 'tabular-nums' };

export default function HistoricalReports() {
  const { session, dashboardBranchId, selectDashboardBranch } = useAdminSession();
  const canReconcile = session.admin_capabilities['dashboard.read'] === true;
  const canIngredients = session.admin_capabilities['reports.ingredient_sales.read'] === true;
  const canExpenses = session.admin_capabilities['reports.expenses.read'] === true;
  const initialTab: Tab = canReconcile ? 'reconciliation' : canIngredients ? 'ingredient' : 'expenses';
  const [tab, setTab] = useState<Tab>(initialTab);
  const branches = session.allowed_branches.filter((branch) => branch.status === 'active');
  const permission = tab === 'reconciliation' ? 'dashboard.read' : tab === 'ingredient' ? 'reports.ingredient_sales.read' : 'reports.expenses.read';
  const canReadOrganization = session.admin_capabilities[`${permission}.organization`] === true;
  const effectiveBranchId = canReadOrganization ? dashboardBranchId : session.active_branch.id;
  const selectableBranches = canReadOrganization
    ? branches
    : branches.filter((branch) => branch.id === session.active_branch.id);
  const selectedBranch = branches.find((branch) => branch.id === effectiveBranchId);
  const timeZone = selectedBranch?.timezone || 'UTC';
  const [date, setDate] = useState(() => localDate(timeZone));
  const [cursor, setCursor] = useState<string | null>(null);
  const bounds = useMemo(() => localDayUtcBounds(date, timeZone), [date, timeZone]);

  useEffect(() => { setCursor(null); }, [tab, date, effectiveBranchId]);

  const report = useQuery<IngredientReport | ExpenseReport>({
    queryKey: ['admin-historical-report', session.organization_id, session.user.id, tab, effectiveBranchId, bounds.fromUtc, bounds.toUtc, cursor],
    enabled: tab !== 'reconciliation',
    queryFn: ({ signal }) => {
      const params = new URLSearchParams({ from_utc: bounds.fromUtc, to_utc: bounds.toUtc, limit: '50' });
      if (effectiveBranchId) params.set('branch_id', effectiveBranchId);
      if (cursor) params.set('cursor', cursor);
      const endpoint = tab === 'ingredient' ? '/reports/ingredient-sales' : '/reports/expenses';
      return fetchApi(`${endpoint}?${params.toString()}`, { signal });
    },
  });

  const ingredients = tab === 'ingredient' ? report.data as IngredientReport | undefined : undefined;
  const expenses = tab === 'expenses' ? report.data as ExpenseReport | undefined : undefined;
  const nextCursor = ingredients?.next_cursor || expenses?.next_cursor || null;

  return <main style={{ padding: 24, maxWidth: 1240, margin: '0 auto', display: 'grid', gap: 20 }}>
    <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16, flexWrap: 'wrap' }}>
      <div><h1 style={{ margin: 0, color: '#0f172a' }}>Reportes históricos y de corte</h1><p style={{ margin: '6px 0 0', color: '#64748b' }}>Consulta autoritativa por sucursal o de toda la organización; los cálculos permanecen en el backend.</p></div>
      <label style={{ display: 'grid', gap: 5, color: '#475569', fontSize: 13 }}>Sucursal
        <select aria-label="Sucursal del reporte histórico" value={effectiveBranchId ?? ''} onChange={(event) => selectDashboardBranch(event.target.value || null)} style={{ minWidth: 230, padding: '9px 12px', border: '1px solid #cbd5e1', borderRadius: 8 }}>
          {canReadOrganization && <option value="">Todas las sucursales</option>}
          {selectableBranches.map((branch) => <option key={branch.id} value={branch.id}>{branch.name}</option>)}
        </select>
      </label>
    </header>

    <div role="tablist" aria-label="Tipos de reporte histórico" style={{ display: 'grid', gridTemplateColumns: `repeat(${[canReconcile, canIngredients, canExpenses].filter(Boolean).length}, minmax(0, 1fr))`, gap: 12, padding: 12, background: '#fff', border: '1px solid #e2e8f0', borderRadius: 14 }}>
      {canReconcile && <Button type="button" variant={tab === 'reconciliation' ? 'primary' : 'secondary'} onClick={() => setTab('reconciliation')}>Corte y Conciliación</Button>}
      {canIngredients && <Button type="button" variant={tab === 'ingredient' ? 'primary' : 'secondary'} onClick={() => setTab('ingredient')}>Venta por insumos</Button>}
      {canExpenses && <Button type="button" variant={tab === 'expenses' ? 'primary' : 'secondary'} onClick={() => setTab('expenses')}>Gastos</Button>}
    </div>

    {tab === 'reconciliation' && <CorporateReconciliationDashboard embedded branchId={effectiveBranchId} />}
    {tab !== 'reconciliation' && <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'end', gap: 12, flexWrap: 'wrap' }}>
        <label style={{ display: 'grid', gap: 5, color: '#475569', fontSize: 13 }}>Fecha<input aria-label="Fecha del reporte histórico" type="date" value={date} onChange={(event) => setDate(event.target.value)} style={{ padding: '8px 12px', border: '1px solid #cbd5e1', borderRadius: 8 }} /></label>
        <span style={{ color: '#64748b', fontSize: 13 }}>{effectiveBranchId ? `Zona horaria del período: ${timeZone}` : 'Período corporativo: UTC'}</span>
      </div>
      {report.isLoading && <div role="status">Cargando reporte…</div>}
      {report.error && <div role="alert" style={{ padding: 12, borderRadius: 8, background: '#fee2e2', color: '#b91c1c' }}>{report.error instanceof Error ? report.error.message : 'No fue posible cargar el reporte.'}</div>}
      {!report.isLoading && !report.error && report.data?.items.length === 0 && <div>No hay datos para el periodo seleccionado.</div>}
    </>}

    {ingredients && !report.isLoading && !report.error && <section><div style={tableWrap}><table style={tableStyle}><thead><tr><th style={headerStyle}>Insumo</th><th style={headerStyle}>Unidad</th><th style={{ ...headerStyle, textAlign: 'right' }}>Cantidad</th><th style={{ ...headerStyle, textAlign: 'right' }}>Operaciones</th></tr></thead><tbody>{ingredients.items.map((item) => <tr key={`${item.item_id}-${item.unit_code}`}><td style={cellStyle}>{item.item_name || item.item_id}</td><td style={cellStyle}>{item.unit_code || 'Sin unidad'}</td><td style={amountStyle}>{item.quantity}</td><td style={amountStyle}>{item.known_operation_count}</td></tr>)}</tbody></table></div>{ingredients.incomplete_operation_count > 0 && <p role="status">Hay operaciones históricas incompletas; no se reemplazaron por cero.</p>}</section>}
    {expenses && !report.isLoading && !report.error && <section><div style={tableWrap}><table style={tableStyle}><thead><tr>{!effectiveBranchId && <th style={headerStyle}>Sucursal</th>}<th style={headerStyle}>Fuente</th><th style={headerStyle}>Fecha</th><th style={{ ...headerStyle, textAlign: 'right' }}>Subtotal</th><th style={{ ...headerStyle, textAlign: 'right' }}>Descuento</th><th style={{ ...headerStyle, textAlign: 'right' }}>Impuestos</th><th style={{ ...headerStyle, textAlign: 'right' }}>Total</th></tr></thead><tbody>{expenses.items.map((item) => <tr key={item.id}>{!effectiveBranchId && <td style={cellStyle}>{branches.find((branch) => branch.id === item.branch_id)?.name || item.branch_id}</td>}<td style={cellStyle}>{item.source === 'purchase' ? 'Compra' : item.source === 'purchase_cancellation' ? 'Cancelación de compra' : item.source === 'expense' ? 'Gasto operativo' : item.source === 'expense_cancellation' ? 'Anulación de gasto' : item.linked_source_id ? 'Compensación de caja' : 'Retiro de caja'}</td><td style={cellStyle}>{new Intl.DateTimeFormat('es-MX', { timeZone }).format(new Date(item.occurred_at))}</td><td style={amountStyle}>{item.subtotal_cents === null ? 'No disponible' : money.format(item.subtotal_cents / 100)}</td><td style={amountStyle}>{item.discount_cents === null ? 'No disponible' : money.format(item.discount_cents / 100)}</td><td style={amountStyle}>{item.tax_cents === null ? 'No disponible' : money.format(item.tax_cents / 100)}</td><td style={amountStyle}>{money.format(item.total_cents / 100)}</td></tr>)}</tbody></table></div>{expenses.unknown_tax_source_count > 0 && <p role="status">Hay impuestos sin fuente canónica; no se infirió IVA.</p>}</section>}
    {tab !== 'reconciliation' && cursor && <Button type="button" variant="secondary" onClick={() => setCursor(null)}>Volver a la primera página</Button>}
    {tab !== 'reconciliation' && nextCursor && <Button type="button" onClick={() => setCursor(nextCursor)}>Siguiente página</Button>}
  </main>;
}
