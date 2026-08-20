import React, { useEffect, useMemo, useState } from 'react';
import { fetchApi } from '@restaurantos/api-client';
import { Button } from '@restaurantos/ui';
import { usePosSession } from '../../session';
import { localDayUtcBounds } from './salesMonitorState';

import BranchDailyReconciliationReport from './BranchDailyReconciliationReport';

type IngredientRow = { item_id: string; item_name: string | null; unit_code: string | null; quantity: string; known_operation_count: number };
type ExpenseRow = { id: string; source: 'purchase' | 'purchase_cancellation' | 'cash_movement'; occurred_at: string; subtotal_cents: number | null; discount_cents: number | null; tax_cents: number | null; total_cents: number };
type IngredientReport = { items: IngredientRow[]; incomplete_operation_count: number; next_cursor: string | null };
type ExpenseReport = { items: ExpenseRow[]; unknown_tax_source_count: number; next_cursor: string | null };
type Tab = 'reconciliation' | 'ingredient' | 'expenses';
type Status = 'loading' | 'empty' | 'data' | 'incomplete' | 'error';

const localDate = (timeZone: string) => new Intl.DateTimeFormat('en-CA', {
  timeZone, year: 'numeric', month: '2-digit', day: '2-digit',
}).format(new Date());
const money = new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' });
const tableWrap: React.CSSProperties = { overflowX: 'auto', border: '1px solid #d1d5db', borderRadius: 8, background: '#fff' };
const tableStyle: React.CSSProperties = { width: '100%', minWidth: 640, borderCollapse: 'collapse', color: '#111827' };
const headerStyle: React.CSSProperties = { padding: 12, textAlign: 'left', background: '#f3f4f6', borderBottom: '1px solid #d1d5db' };
const cellStyle: React.CSSProperties = { padding: 12, borderBottom: '1px solid #e5e7eb', whiteSpace: 'nowrap' };
const amountStyle: React.CSSProperties = { ...cellStyle, textAlign: 'right', fontVariantNumeric: 'tabular-nums' };

const PCO007Reports = () => {
  const { session, hasPermission } = usePosSession();
  const ingredientAllowed = hasPermission('reports.ingredient_sales.read');
  const expenseAllowed = hasPermission('reports.expenses.read');
  const timeZone = session?.active_branch?.timezone || 'UTC';
  const [tab, setTab] = useState<Tab>('reconciliation');
  const [date, setDate] = useState(() => localDate(timeZone));
  const [status, setStatus] = useState<Status>('loading');
  const [ingredients, setIngredients] = useState<IngredientReport | null>(null);
  const [expenses, setExpenses] = useState<ExpenseReport | null>(null);
  const [cursors, setCursors] = useState<Record<string, string | null>>({ ingredient: null, expenses: null });
  const [error, setError] = useState('');
  const bounds = useMemo(() => localDayUtcBounds(date, timeZone), [date, timeZone]);
  const load = async (nextCursor: string | null = null) => {
    if (tab === 'reconciliation') return;
    setStatus('loading'); setError('');
    try {
      const params = new URLSearchParams({ from_utc: bounds.fromUtc, to_utc: bounds.toUtc, limit: '50' });
      if (session?.active_branch?.id) params.set('branch_id', session.active_branch.id);
      if (nextCursor) params.set('cursor', nextCursor);
      if (tab === 'ingredient') {
        const data = await fetchApi<IngredientReport>(`/reports/ingredient-sales?${params}`);
        setIngredients(data); setCursors((current) => ({ ...current, ingredient: data.next_cursor }));
        setStatus(data.incomplete_operation_count ? 'incomplete' : data.items.length ? 'data' : 'empty');
      } else {
        const data = await fetchApi<ExpenseReport>(`/reports/expenses?${params}`);
        setExpenses(data); setCursors((current) => ({ ...current, expenses: data.next_cursor }));
        setStatus(data.unknown_tax_source_count ? 'incomplete' : data.items.length ? 'data' : 'empty');
      }
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'No fue posible cargar el reporte.'); setStatus('error'); }
  };
  useEffect(() => { void load(); }, [tab, bounds.fromUtc, bounds.toUtc, session?.active_branch?.id]);
  return <main className="sales-monitor-page">
    <header className="sales-monitor-header"><div><h1>Reportes históricos y de corte</h1><p>Consulta autoritativa; cantidades, impuestos e importes se calculan en el backend.</p></div><span>Zona horaria: {timeZone}</span></header>
    <div className="sales-monitor-filters" role="tablist" aria-label="Tipos de reporte">
      <Button type="button" variant={tab === 'reconciliation' ? 'primary' : 'secondary'} onClick={() => setTab('reconciliation')}>Corte y Conciliación</Button>
      {ingredientAllowed && <Button type="button" variant={tab === 'ingredient' ? 'primary' : 'secondary'} onClick={() => setTab('ingredient')}>Venta por insumos</Button>}
      {expenseAllowed && <Button type="button" variant={tab === 'expenses' ? 'primary' : 'secondary'} onClick={() => setTab('expenses')}>Gastos</Button>}
    </div>
    {tab === 'reconciliation' && <BranchDailyReconciliationReport />}
    {tab !== 'reconciliation' && (
      <>
        <form className="sales-monitor-filters" onSubmit={(event) => { event.preventDefault(); void load(); }}><label>Fecha<input type="date" value={date} onChange={(event) => setDate(event.target.value)} required /></label><Button type="submit">Consultar</Button></form>
        {status === 'loading' && <div className="sales-monitor-state" role="status">Cargando reporte…</div>}
        {status === 'error' && <div className="sales-monitor-state" role="alert">{error}<Button type="button" onClick={() => void load()}>Reintentar</Button></div>}
        {status === 'empty' && <div className="sales-monitor-state">No hay datos para el periodo seleccionado.</div>}
      </>
    )}
    {tab === 'ingredient' && ingredients && status !== 'loading' && status !== 'error' && <section><div style={tableWrap}><table className="sales-monitor-table" style={tableStyle}><thead><tr><th style={headerStyle}>Insumo</th><th style={headerStyle}>Unidad</th><th style={{ ...headerStyle, textAlign: 'right' }}>Cantidad</th><th style={{ ...headerStyle, textAlign: 'right' }}>Operaciones</th></tr></thead><tbody>{ingredients.items.map((item) => <tr key={`${item.item_id}-${item.unit_code}`}><td style={cellStyle}>{item.item_name || item.item_id}</td><td style={cellStyle}>{item.unit_code || 'Sin unidad'}</td><td style={amountStyle}>{item.quantity}</td><td style={amountStyle}>{item.known_operation_count}</td></tr>)}</tbody></table></div>{ingredients.incomplete_operation_count > 0 && <p role="status">Hay operaciones históricas incompletas; no se reemplazaron por cero.</p>}</section>}
    {tab === 'expenses' && expenses && status !== 'loading' && status !== 'error' && <section><div style={tableWrap}><table className="sales-monitor-table" style={tableStyle}><thead><tr><th style={headerStyle}>Fuente</th><th style={headerStyle}>Fecha</th><th style={{ ...headerStyle, textAlign: 'right' }}>Subtotal</th><th style={{ ...headerStyle, textAlign: 'right' }}>Impuestos</th><th style={{ ...headerStyle, textAlign: 'right' }}>Total</th></tr></thead><tbody>{expenses.items.map((item) => <tr key={item.id}><td style={cellStyle}>{item.source === 'purchase' ? 'Compra' : item.source === 'purchase_cancellation' ? 'Cancelación de compra' : 'Retiro de caja'}</td><td style={cellStyle}>{new Intl.DateTimeFormat('es-MX', { timeZone }).format(new Date(item.occurred_at))}</td><td style={amountStyle}>{item.subtotal_cents === null ? 'No disponible' : money.format(item.subtotal_cents / 100)}</td><td style={amountStyle}>{item.tax_cents === null ? 'No disponible' : money.format(item.tax_cents / 100)}</td><td style={amountStyle}>{money.format(item.total_cents / 100)}</td></tr>)}</tbody></table></div>{expenses.unknown_tax_source_count > 0 && <p role="status">Hay impuestos sin fuente canónica; no se infirió IVA.</p>}</section>}
    {cursors[tab] && <Button type="button" onClick={() => void load(cursors[tab])}>Siguiente página</Button>}
  </main>;
};
export default PCO007Reports;
