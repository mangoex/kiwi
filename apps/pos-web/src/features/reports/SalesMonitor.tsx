import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ApiError, fetchApi } from '@restaurantos/api-client';
import { BarChart3, RefreshCw, Search } from 'lucide-react';
import { Button } from '@restaurantos/ui';
import { usePosSession } from '../../session';
import {
  type BreakdownItem,
  type SalesDrillDownResponse,
  type SalesMetric,
  type SalesMonitorResponse,
  formatKnownMoney,
  localDayUtcBounds,
  parseSalesDrillDownResponse,
  parseSalesMonitorResponse,
  resolveBranchTimeZone,
} from './salesMonitorState';

interface BranchOption { id: string; name: string; timezone: string; status?: string }
interface Filters {
  fromDate: string;
  toDate: string;
  branchId: string;
  registerId: string;
  cashShiftId: string;
  familyId: string;
  serviceType: string;
}
interface ReportIntent extends Filters { timeZone: string }

const metricLabels: Record<SalesMetric, string> = {
  gross: 'Venta bruta', net: 'Venta neta', tax: 'Impuestos',
  discount: 'Descuentos', courtesy: 'Cortesías',
};

const localDateInZone = (timeZone: string) => {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone, year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(new Date());
  const fields = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${fields.year}-${fields.month}-${fields.day}`;
};

const apiMessage = (reason: unknown, fallback: string) => (
  reason instanceof ApiError ? reason.message : reason instanceof Error ? reason.message : fallback
);

const serviceLabel = (value: string) => ({
  'dine-in': 'En sucursal', takeout: 'Para llevar', delivery: 'A domicilio',
}[value] || value);

const SalesMonitor = () => {
  const { session } = usePosSession();
  const isOrganizationScope = session?.scope.level === 'organization';
  const [branches, setBranches] = useState<BranchOption[]>(() => session?.active_branch ? [{
    id: session.active_branch.id,
    name: session.active_branch.name,
    timezone: session.active_branch.timezone,
    status: session.active_branch.status,
  }] : []);
  const initialTimeZone = session?.active_branch?.timezone || 'UTC';
  const today = useMemo(() => localDateInZone(initialTimeZone), [initialTimeZone]);
  const [filters, setFilters] = useState<Filters>({
    fromDate: today, toDate: today, branchId: session?.active_branch?.id || '',
    registerId: '', cashShiftId: '', familyId: '', serviceType: '',
  });
  const [applied, setApplied] = useState<ReportIntent | null>(null);
  const [data, setData] = useState<SalesMonitorResponse | null>(null);
  const [status, setStatus] = useState<'idle' | 'loading' | 'ready' | 'empty' | 'error'>('loading');
  const [error, setError] = useState('');
  const [drillMetric, setDrillMetric] = useState<SalesMetric | null>(null);
  const [drill, setDrill] = useState<SalesDrillDownResponse | null>(null);
  const [drillStatus, setDrillStatus] = useState<'idle' | 'loading' | 'ready' | 'error'>('idle');
  const [drillError, setDrillError] = useState('');
  const requestController = useRef<AbortController | null>(null);
  const lastSummaryIntentRef = useRef<ReportIntent | null>(null);
  const drillController = useRef<AbortController | null>(null);
  const initialLoadRef = useRef(false);

  const selectedTimeZone = useMemo(
    () => resolveBranchTimeZone(filters.branchId, branches),
    [branches, filters.branchId],
  );

  useEffect(() => {
    setFilters((current) => ({
      ...current,
      fromDate: current.fromDate || today,
      toDate: current.toDate || today,
      branchId: current.branchId || session?.active_branch?.id || '',
    }));
  }, [session?.active_branch?.id, today]);

  useEffect(() => {
    if (!isOrganizationScope) {
      setBranches(session?.active_branch ? [{
        id: session.active_branch.id,
        name: session.active_branch.name,
        timezone: session.active_branch.timezone,
        status: session.active_branch.status,
      }] : []);
      return;
    }
    const controller = new AbortController();
    fetchApi<BranchOption[]>('/branches', { signal: controller.signal })
      .then((response) => setBranches(
        Array.isArray(response)
          ? response.filter((branch) => branch.status !== 'inactive'
            && (!session?.scope.allowed_branch_ids.length
              || session.scope.allowed_branch_ids.includes(branch.id)))
          : [],
      ))
      .catch((reason) => {
        if (!(reason instanceof DOMException && reason.name === 'AbortError')) setBranches([]);
      });
    return () => controller.abort();
  }, [isOrganizationScope, session?.active_branch, session?.scope.allowed_branch_ids]);

  const queryFor = useCallback((source: ReportIntent) => {
    const start = localDayUtcBounds(source.fromDate, source.timeZone).fromUtc;
    const end = localDayUtcBounds(source.toDate, source.timeZone).toUtc;
    const params = new URLSearchParams({ from_utc: start, to_utc: end });
    params.set('branch_id', source.branchId);
    if (source.registerId.trim()) params.set('register_id', source.registerId.trim());
    if (source.cashShiftId) params.set('cash_shift_id', source.cashShiftId);
    if (source.familyId) params.set('family_id', source.familyId);
    if (source.serviceType) params.set('service_type', source.serviceType);
    return params;
  }, []);

  const loadSummary = useCallback(async (source: ReportIntent) => {
    requestController.current?.abort();
    const controller = new AbortController();
    requestController.current = controller;
    lastSummaryIntentRef.current = Object.freeze({ ...source });
    setStatus('loading');
    setError('');
    try {
      const response = await fetchApi<unknown>(
        `/reports/sales-monitor?${queryFor(source).toString()}`,
        { signal: controller.signal },
      );
      if (controller.signal.aborted) return;
      const parsed = parseSalesMonitorResponse(response);
      setData(parsed);
      setApplied(source);
      setStatus(parsed.summary.order_count === 0 ? 'empty' : 'ready');
    } catch (reason) {
      if (controller.signal.aborted) return;
      setStatus('error');
      setError(apiMessage(reason, 'No fue posible cargar el monitor de ventas.'));
    }
  }, [queryFor]);

  useEffect(() => {
    if (initialLoadRef.current || !filters.branchId || !selectedTimeZone) return;
    initialLoadRef.current = true;
    const initial = {
      ...filters,
      fromDate: filters.fromDate || today,
      toDate: filters.toDate || today,
      timeZone: selectedTimeZone,
    };
    void loadSummary(initial);
    return () => requestController.current?.abort();
  }, [filters.branchId, loadSummary, selectedTimeZone, today]);

  const loadDrill = useCallback(async (metric: SalesMetric, cursor?: string | null) => {
    if (!applied) return;
    drillController.current?.abort();
    const controller = new AbortController();
    drillController.current = controller;
    setDrillMetric(metric);
    setDrillStatus('loading');
    setDrillError('');
    try {
      const params = queryFor(applied);
      params.set('metric', metric);
      params.set('limit', '50');
      if (cursor) params.set('cursor', cursor);
      const response = await fetchApi<unknown>(
        `/reports/sales-monitor/drill-down?${params.toString()}`,
        { signal: controller.signal },
      );
      if (controller.signal.aborted) return;
      const parsed = parseSalesDrillDownResponse(response);
      setDrill((current) => cursor && current
        ? { ...parsed, items: [...current.items, ...parsed.items] }
        : parsed);
      setDrillStatus('ready');
    } catch (reason) {
      if (controller.signal.aborted) return;
      setDrillStatus('error');
      setDrillError(apiMessage(reason, 'No fue posible cargar el detalle.'));
    }
  }, [applied, queryFor]);

  useEffect(() => () => drillController.current?.abort(), []);

  const applyFilters = (event: React.FormEvent) => {
    event.preventDefault();
    if (!filters.branchId || !selectedTimeZone) {
      setError('Selecciona una sucursal con zona horaria válida. No se combinan sucursales con zonas distintas.');
      setStatus('error');
      return;
    }
    if (!filters.fromDate || !filters.toDate || filters.fromDate > filters.toDate) {
      setError('Selecciona un periodo válido para la sucursal.');
      setStatus('error');
      return;
    }
    setDrill(null);
    setDrillMetric(null);
    void loadSummary({ ...filters, timeZone: selectedTimeZone });
  };

  const familyOptions = data?.facets.families || [];
  const shiftOptions = data?.facets.cash_shifts || [];

  return (
    <div className="sales-monitor-page">
      <header className="sales-monitor-header">
        <div>
          <h1><BarChart3 aria-hidden="true" /> Monitor de ventas</h1>
          <p>Consulta importes conocidos y operaciones con información histórica faltante.</p>
        </div>
        <span className="sales-monitor-timezone">Zona horaria: {selectedTimeZone || 'Selecciona una sucursal'}</span>
      </header>

      <form className="sales-monitor-filters" onSubmit={applyFilters} aria-label="Filtros del monitor de ventas">
        <label>Desde<input type="date" value={filters.fromDate} onChange={(event) => setFilters({ ...filters, fromDate: event.target.value })} required /></label>
        <label>Hasta<input type="date" value={filters.toDate} onChange={(event) => setFilters({ ...filters, toDate: event.target.value })} required /></label>
        <label>Sucursal
          <select value={filters.branchId} onChange={(event) => {
            setFilters({ ...filters, branchId: event.target.value, cashShiftId: '', familyId: '' });
            setData(null); setApplied(null); setDrill(null); setDrillMetric(null); setStatus('idle');
          }} disabled={!isOrganizationScope} required>
            {isOrganizationScope && <option value="">Selecciona una sucursal…</option>}
            {branches.map((branch) => <option key={branch.id} value={branch.id}>{branch.name}</option>)}
          </select>
        </label>
        <label>Caja<input value={filters.registerId} onChange={(event) => setFilters({ ...filters, registerId: event.target.value })} placeholder="Identificador" /></label>
        <label>Turno
          <select value={filters.cashShiftId} onChange={(event) => setFilters({ ...filters, cashShiftId: event.target.value })}>
            <option value="">Todos</option>{shiftOptions.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
          </select>
        </label>
        <label>Familia
          <select value={filters.familyId} onChange={(event) => setFilters({ ...filters, familyId: event.target.value })}>
            <option value="">Todas</option>{familyOptions.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
          </select>
        </label>
        <label>Servicio
          <select value={filters.serviceType} onChange={(event) => setFilters({ ...filters, serviceType: event.target.value })}>
            <option value="">Todos</option><option value="dine-in">En sucursal</option><option value="takeout">Para llevar</option><option value="delivery">A domicilio</option>
          </select>
        </label>
        <Button type="submit"><Search size={17} aria-hidden="true" /> Consultar</Button>
      </form>

      {status === 'loading' && <div className="sales-monitor-state" role="status"><RefreshCw className="sales-monitor-spin" /> Cargando ventas…</div>}
      {status === 'idle' && <div className="sales-monitor-state" role="status">Selecciona una sucursal y consulta el periodo.</div>}
      {status === 'error' && <div className="sales-monitor-state is-error" role="alert"><p>{error}</p><Button variant="secondary" onClick={() => { if (lastSummaryIntentRef.current) void loadSummary(lastSummaryIntentRef.current); }}>Reintentar</Button></div>}
      {status === 'empty' && <div className="sales-monitor-state" role="status"><p>No hay ventas para los filtros seleccionados.</p></div>}

      {data && status !== 'loading' && status !== 'error' && (
        <>
          <section className="sales-monitor-cards" aria-label="Indicadores de venta">
            {(Object.keys(metricLabels) as SalesMetric[]).map((metric) => (
              <button key={metric} type="button" className="sales-monitor-card" onClick={() => void loadDrill(metric)}>
                <span>{metricLabels[metric]}</span>
                <strong>{formatKnownMoney(data.summary[metric])}</strong>
                <small>Ver operaciones</small>
              </button>
            ))}
          </section>
          <section className="sales-monitor-counts" aria-label="Conteos del periodo">
            <span><strong>{data.summary.order_count}</strong> pedidos</span>
            <span><strong>{data.summary.line_count}</strong> líneas</span>
            <span><strong>{data.summary.item_quantity}</strong> artículos</span>
            <span><strong>{data.data_quality.incomplete_operation_count}</strong> operaciones incompletas</span>
            <span><strong>{data.summary.legacy_backfilled_line_count}</strong> líneas históricas reconstruidas</span>
          </section>
          <div className="sales-monitor-breakdowns">
            <BreakdownTable title="Ventas por familia" items={data.breakdowns.families} />
            <BreakdownTable title="Ventas por servicio" items={data.breakdowns.services.map((item) => ({ ...item, label: serviceLabel(item.label) }))} />
          </div>
        </>
      )}

      {drillMetric && (
        <section className="sales-monitor-drill" aria-labelledby="sales-monitor-drill-title">
          <div className="sales-monitor-drill-header">
            <h2 id="sales-monitor-drill-title">Operaciones: {metricLabels[drillMetric]}</h2>
            <Button variant="ghost" onClick={() => { drillController.current?.abort(); setDrillMetric(null); setDrill(null); }}>Cerrar detalle</Button>
          </div>
          {drillStatus === 'loading' && !drill && <p role="status">Cargando operaciones…</p>}
          {drillStatus === 'error' && <div role="alert"><p>{drillError}</p><Button variant="secondary" onClick={() => void loadDrill(drillMetric)}>Reintentar</Button></div>}
          {drill && <div className="sales-monitor-table-scroll"><table><thead><tr><th>Folio</th><th>Fecha</th><th>Caja</th><th>Servicio</th><th>Importe</th><th>Calidad</th></tr></thead><tbody>
            {drill.items.map((item) => <tr key={item.payment_id}><td>{item.folio}</td><td>{new Date(item.confirmed_at).toLocaleString('es-MX', { timeZone: applied?.timeZone || selectedTimeZone || 'UTC' })}</td><td>{item.register_id}</td><td>{serviceLabel(item.service_type)}</td><td>{formatKnownMoney(item[drillMetric])}</td><td>{item.quality_status === 'incomplete' ? 'Incompleta' : 'Completa'}</td></tr>)}
          </tbody></table></div>}
          {drill?.next_cursor && <Button variant="secondary" disabled={drillStatus === 'loading'} onClick={() => void loadDrill(drillMetric, drill.next_cursor)}>Cargar más</Button>}
        </section>
      )}
    </div>
  );
};

const BreakdownTable = ({ title, items }: { title: string; items: BreakdownItem[] }) => (
  <section className="sales-monitor-breakdown">
    <h2>{title}</h2>
    {items.length === 0 ? <p>Sin datos para desglosar.</p> : <div className="sales-monitor-table-scroll"><table><thead><tr><th>Grupo</th><th>Bruta</th><th>Neta</th><th>Impuestos</th><th>Descuentos</th><th>Cortesías</th><th>Pedidos</th><th>Artículos</th></tr></thead><tbody>
      {items.map((item) => <tr key={item.id}><td>{item.label}</td><td>{formatKnownMoney(item.gross)}</td><td>{formatKnownMoney(item.net)}</td><td>{formatKnownMoney(item.tax)}</td><td>{formatKnownMoney(item.discount)}</td><td>{formatKnownMoney(item.courtesy)}</td><td>{item.order_count}</td><td>{item.item_quantity}</td></tr>)}
    </tbody></table></div>}
  </section>
);

export default SalesMonitor;
