import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Button } from '@restaurantos/ui';
import { fetchApi, parseConsolidatedReconciliation, physicalCountLabel, downloadReconciliationWorkbook, formatReportMoney, type ConsolidatedReport } from '@restaurantos/api-client';
import { useAdminSession } from '../../lib/adminSession';

interface Branch {
  id: string;
  name: string;
}

const money = formatReportMoney;

export default function CorporateReconciliationDashboard() {
  const {session} = useAdminSession();
  const [exportError, setExportError] = useState('');
  const today = new Date().toISOString().split('T')[0];
  const firstDay = `${today.substring(0, 7)}-01`;

  const [dateFrom, setDateFrom] = useState(firstDay);
  const [dateTo, setDateTo] = useState(today);
  const [selectedBranchId, setSelectedBranchId] = useState('');

  const { data: branches = [] } = useQuery<Branch[]>({
    queryKey: ['branches'],
    queryFn: () => fetchApi('/branches'),
  });

  const { data, isLoading, error, refetch } = useQuery<ConsolidatedReport>({
    queryKey: ['consolidated-reconciliation-v2', session?.organization_id, session?.user.id, dateFrom, dateTo, selectedBranchId],
    queryFn: async ({signal}) => {
      const params = new URLSearchParams({
        date_from: dateFrom,
        date_to: dateTo,
      });
      if (selectedBranchId) params.set('branch_id', selectedBranchId);
      return parseConsolidatedReconciliation(await fetchApi(`/reports/branch-reconciliation/consolidated?${params.toString()}`, {signal}, 'v2'));
    },
  });

  const handleExportExcel = async () => {
    if (!selectedBranchId) {
      setExportError('Selecciona una sucursal para descargar su Excel mensual.');
      return;
    }
    const d = new Date(dateTo);
    const month = d.getUTCMonth() + 1;
    const year = d.getUTCFullYear();
    const branchParam = selectedBranchId;
    setExportError('');
    try { await downloadReconciliationWorkbook(branchParam, month, year); }
    catch (err) { setExportError(err instanceof Error ? err.message : 'No se pudo descargar Excel.'); }
  };

  const summary = data?.summary;

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: '0 auto', fontFamily: 'system-ui, sans-serif' }}>
      {/* Header & Controls */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 16, marginBottom: 24 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.75rem', fontWeight: 800, color: '#0f172a' }}>
            Consolidado Multi-Sucursal y Cortes
          </h1>
          <p style={{ margin: '4px 0 0', color: '#64748b', fontSize: '0.9rem' }}>
            Informe General Acumulado Diaria y Mensualmente (Formato Oficial Kiwi)
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <select
            value={selectedBranchId}
            onChange={(e) => setSelectedBranchId(e.target.value)}
            style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid #cbd5e1', fontSize: '0.9rem' }}
          >
            <option value="">🏢 Todas las Sucursales</option>
            {branches.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </select>

          <label style={{ fontSize: '0.85rem', color: '#475569', display: 'flex', alignItems: 'center', gap: 6 }}>
            Desde:
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              style={{ padding: '6px 10px', borderRadius: 6, border: '1px solid #cbd5e1' }}
            />
          </label>

          <label style={{ fontSize: '0.85rem', color: '#475569', display: 'flex', alignItems: 'center', gap: 6 }}>
            Hasta:
            <input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              style={{ padding: '6px 10px', borderRadius: 6, border: '1px solid #cbd5e1' }}
            />
          </label>

          <Button variant="secondary" onClick={handleExportExcel} disabled={!selectedBranchId}>
            📥 Excel mensual de sucursal (.xlsx)
          </Button>
        </div>
      </div>

      {isLoading && <p style={{ color: '#64748b' }}>Consolidando reportes de sucursales…</p>}
      {error && <div role="alert" style={{ padding: 12, borderRadius: 8, background: '#fee2e2', color: '#b91c1c' }}>{error instanceof Error ? error.message : 'Error al cargar el consolidado.'}</div>}

      {exportError && <div role="alert">{exportError}</div>}
      {summary && data && (
        <div style={{ display: 'grid', gap: 24 }}>
          <p style={{ margin: 0 }}>Saldo de turnos por fecha de apertura local; ledger completo o cierre congelado.
            Suma de turnos, no existencia simultánea de cajas. Desgloses verificados contra el ledger.</p>
          <section aria-label="Arqueo consolidado">
            <strong>{physicalCountLabel(data.physical_count)}</strong>
            <p>Contado: {summary.physical_cash_count === null ? 'Sin conteo completo equivalente' : money(summary.physical_cash_count)} · Diferencia: {summary.difference === null ? 'Sin diferencia calculable' : money(summary.difference)}</p>
          </section>
          <section aria-label="Actividad calendario">
            <h2 style={{ fontSize: '1rem' }}>Actividad calendario del período</h2>
            <p>Eventos por fecha local, independientes del saldo de turnos y del arqueo.</p>
            <p>Cobros: {money(data.activity.totals.total_sales_with_tax)} · Proveedores cash: {money(data.activity.totals.supplier_expenses)} · Gastos cash: {money(data.activity.totals.fixed_expenses)}</p>
          </section>
          {/* Summary KPIs */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16 }}>
            <div style={{ background: '#fff', padding: 16, borderRadius: 10, border: '1px solid #e2e8f0' }}>
              <div style={{ color: '#64748b', fontSize: '0.8rem', fontWeight: 600 }}>VENTAS TOTALES</div>
              <div style={{ fontSize: '1.3rem', fontWeight: 800, color: '#0f172a', marginTop: 4 }}>
                {money(summary.total_sales)}
              </div>
            </div>

            <div style={{ background: '#fff', padding: 16, borderRadius: 10, border: '1px solid #e2e8f0' }}>
              <div style={{ color: '#64748b', fontSize: '0.8rem', fontWeight: 600 }}>COBROS CON TARJETA</div>
              <div style={{ fontSize: '1.3rem', fontWeight: 800, color: '#2563eb', marginTop: 4 }}>
                {money(summary.total_cards)}
              </div>
            </div>

            <div style={{ background: '#fff', padding: 16, borderRadius: 10, border: '1px solid #e2e8f0' }}>
              <div style={{ color: '#64748b', fontSize: '0.8rem', fontWeight: 600 }}>PAGO A PROVEEDORES</div>
              <div style={{ fontSize: '1.3rem', fontWeight: 800, color: '#dc2626', marginTop: 4 }}>
                {money(summary.total_suppliers)}
              </div>
            </div>

            <div style={{ background: '#fff', padding: 16, borderRadius: 10, border: '1px solid #e2e8f0' }}>
              <div style={{ color: '#64748b', fontSize: '0.8rem', fontWeight: 600 }}>GASTOS FIJOS / SUELDOS</div>
              <div style={{ fontSize: '1.3rem', fontWeight: 800, color: '#dc2626', marginTop: 4 }}>
                {money(summary.total_fixed)}
              </div>
            </div>

            <div style={{ background: '#ecfdf5', padding: 16, borderRadius: 10, border: '1px solid #10b981' }}>
              <div style={{ color: '#065f46', fontSize: '0.8rem', fontWeight: 600 }}>EFECTIVO ESPERADO TOTAL</div>
              <div style={{ fontSize: '1.3rem', fontWeight: 800, color: '#059669', marginTop: 4 }}>
                {money(summary.total_expected_cash)}
              </div>
            </div>
          </div>

          {/* 3 Tables Layout: Sucursales, Proveedores, Gastos Fijos */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 360px), 1fr))', gap: 20 }}>
            {/* Sucursales */}
            <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 8, overflow: 'hidden' }}>
              <div style={{ padding: '12px 16px', background: '#f8fafc', fontWeight: 700, borderBottom: '1px solid #e2e8f0' }}>
                🏪 Resumen por Sucursal
              </div>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid #e2e8f0', color: '#64748b', textAlign: 'left' }}>
                    <th style={{ padding: 10 }}>Sucursal</th>
                    <th style={{ padding: 10, textAlign: 'right' }}>Ventas</th>
                    <th style={{ padding: 10, textAlign: 'right' }}>Egresos</th>
                  </tr>
                </thead>
                <tbody>
                  {data.branches.map((b) => (
                    <tr key={b.branch_id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                      <td style={{ padding: 10, fontWeight: 600 }}>{b.branch_name}</td>
                      <td style={{ padding: 10, textAlign: 'right', fontWeight: 700, color: '#059669' }}>{money(b.total_sales)}</td>
                      <td style={{ padding: 10, textAlign: 'right', fontWeight: 700, color: '#dc2626' }}>{money(b.total_expenses)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Proveedores */}
            <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 8, overflow: 'hidden' }}>
              <div style={{ padding: '12px 16px', background: '#f8fafc', fontWeight: 700, borderBottom: '1px solid #e2e8f0' }}>
                📦 Acumulado por Proveedor de Insumos
              </div>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid #e2e8f0', color: '#64748b', textAlign: 'left' }}>
                    <th style={{ padding: 10 }}>Proveedor</th>
                    <th style={{ padding: 10, textAlign: 'right' }}>Efectivo retirado</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(data.supplier_totals).length === 0 ? (
                    <tr><td colSpan={2} style={{ padding: 12, color: '#94a3b8' }}>Sin pagos a proveedores en el periodo.</td></tr>
                  ) : (
                    Object.entries(data.supplier_totals).map(([name, total]) => (
                      <tr key={name} style={{ borderBottom: '1px solid #f1f5f9' }}>
                        <td style={{ padding: 10, fontWeight: 600 }}>{name}</td>
                        <td style={{ padding: 10, textAlign: 'right', fontWeight: 700 }}>{money(total)}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* Gastos Fijos */}
            <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 8, overflow: 'hidden' }}>
              <div style={{ padding: '12px 16px', background: '#f8fafc', fontWeight: 700, borderBottom: '1px solid #e2e8f0' }}>
                Salidas de efectivo por concepto
                <p style={{fontWeight:400,fontSize:13}}>Sólo efectivo. Consulta los otros medios de pago en Gastos.</p>
              </div>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid #e2e8f0', color: '#64748b', textAlign: 'left' }}>
                    <th style={{ padding: 10 }}>Tipo de Gasto</th>
                    <th style={{ padding: 10, textAlign: 'right' }}>Efectivo retirado</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(data.fixed_expense_totals).length === 0 ? (
                    <tr><td colSpan={2} style={{ padding: 12, color: '#94a3b8' }}>Sin salidas de efectivo registradas en el periodo.</td></tr>
                  ) : (
                    Object.entries(data.fixed_expense_totals).map(([name, total]) => (
                      <tr key={name} style={{ borderBottom: '1px solid #f1f5f9' }}>
                        <td style={{ padding: 10, fontWeight: 600 }}>{name}</td>
                        <td style={{ padding: 10, textAlign: 'right', fontWeight: 700 }}>{money(total)}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
