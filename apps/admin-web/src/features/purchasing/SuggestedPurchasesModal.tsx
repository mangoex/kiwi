import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Sparkles,
  Building2,
  Calendar,
  DollarSign,
  AlertTriangle,
  CheckCircle2,
  ArrowRight,
  ShieldCheck,
  RefreshCw,
  PackageCheck,
  FileSpreadsheet,
} from 'lucide-react';
import { Modal, Button, Badge } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';

interface SuggestedPurchasesModalProps {
  open: boolean;
  onClose: () => void;
  branchId?: string | null;
  onSelectSupplierForPurchase?: (supplierId: string, presentationId?: string) => void;
}

interface SuggestedItem {
  item_id: string;
  item_name: string;
  sku: string;
  suggested_quantity: number;
  unit_cost_cents: number;
  line_total_cents: number;
}

interface SupplierProposal {
  supplier_id: string;
  supplier_name: string;
  supplier_code: string;
  estimated_total_cents: number;
  lines: SuggestedItem[];
}

interface SuggestedPurchasesResponse {
  proposals: SupplierProposal[];
  summary: {
    total_suppliers: number;
    total_items: number;
    total_estimated_cents: number;
    days_ahead: number;
  };
}

interface WasteAuditRecord {
  item_id: string;
  item_name: string;
  total_waste_quantity: number;
  total_waste_cents: number;
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH';
  recommendation: string;
}

interface WasteAuditResponse {
  audit_records: WasteAuditRecord[];
  period_days: number;
}

export const SuggestedPurchasesModal: React.FC<SuggestedPurchasesModalProps> = ({
  open,
  onClose,
  branchId,
  onSelectSupplierForPurchase,
}) => {
  const [activeTab, setActiveTab] = useState<'purchases' | 'waste'>('purchases');
  const [daysAhead, setDaysAhead] = useState(7);

  const {
    data: purchasesData,
    isLoading: loadingPurchases,
    refetch: refetchPurchases,
  } = useQuery<SuggestedPurchasesResponse>({
    queryKey: ['suggested-purchases', branchId, daysAhead],
    queryFn: () =>
      fetchApi('/admin-ai/suggested-purchases', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          branch_id: branchId || undefined,
          days_ahead: daysAhead,
        }),
      }),
    enabled: open && activeTab === 'purchases',
  });

  const {
    data: wasteData,
    isLoading: loadingWaste,
    refetch: refetchWaste,
  } = useQuery<WasteAuditResponse>({
    queryKey: ['inventory-yield-audit', branchId],
    queryFn: () =>
      fetchApi(
        `/admin-ai/inventory-yield-audit${
          branchId ? `?branch_id=${branchId}` : ''
        }`
      ),
    enabled: open && activeTab === 'waste',
  });

  const formatMoney = (cents: number) => {
    return (cents / 100).toLocaleString('es-MX', {
      style: 'currency',
      currency: 'MXN',
    });
  };

  return (
    <Modal isOpen={open} onClose={onClose} title="Inteligencia de Abastecimiento & Mermas">
      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', minWidth: '720px', maxWidth: '900px' }}>
        {/* Navigation Tabs */}
        <div style={{ display: 'flex', gap: '6px', background: '#f1f5f9', padding: '4px', borderRadius: '12px' }}>
          <button
            type="button"
            onClick={() => setActiveTab('purchases')}
            style={{
              flex: 1,
              padding: '10px 16px',
              borderRadius: '8px',
              border: 'none',
              background: activeTab === 'purchases' ? '#ffffff' : 'transparent',
              color: activeTab === 'purchases' ? '#0f172a' : '#64748b',
              fontWeight: activeTab === 'purchases' ? 700 : 500,
              fontSize: '0.9rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              boxShadow: activeTab === 'purchases' ? '0 1px 3px rgba(0,0,0,0.08)' : 'none',
              transition: 'all 0.15s ease',
            }}
          >
            <Sparkles size={16} color={activeTab === 'purchases' ? '#10b981' : '#64748b'} />
            <span>Compras Sugeridas por Demanda</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('waste')}
            style={{
              flex: 1,
              padding: '10px 16px',
              borderRadius: '8px',
              border: 'none',
              background: activeTab === 'waste' ? '#ffffff' : 'transparent',
              color: activeTab === 'waste' ? '#0f172a' : '#64748b',
              fontWeight: activeTab === 'waste' ? 700 : 500,
              fontSize: '0.9rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              boxShadow: activeTab === 'waste' ? '0 1px 3px rgba(0,0,0,0.08)' : 'none',
              transition: 'all 0.15s ease',
            }}
          >
            <AlertTriangle size={16} color={activeTab === 'waste' ? '#ef4444' : '#64748b'} />
            <span>Auditoría de Mermas y Fugas</span>
          </button>
        </div>

        {/* TAB 1: SUGGESTED PURCHASES */}
        {activeTab === 'purchases' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div
              style={{
                display: 'flex',
                flexWrap: 'wrap',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '12px 18px',
                background: '#f0fdf4',
                borderRadius: '12px',
                border: '1px solid #bbf7d0',
                gap: '12px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.85rem', color: '#166534' }}>
                <ShieldCheck size={18} color="#16a34a" />
                <span>Proyección matemática basada en recetas y rotación histórica de ventas.</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <span style={{ fontSize: '0.82rem', fontWeight: 600, color: '#334155' }}>Días a cubrir:</span>
                <select
                  value={daysAhead}
                  onChange={(e) => setDaysAhead(Number(e.target.value))}
                  style={{
                    background: '#ffffff',
                    border: '1px solid #cbd5e1',
                    borderRadius: '8px',
                    padding: '6px 12px',
                    fontSize: '0.85rem',
                    fontWeight: 600,
                    color: '#0f172a',
                    cursor: 'pointer',
                  }}
                >
                  <option value={3}>3 días</option>
                  <option value={7}>7 días (1 semana)</option>
                  <option value={15}>15 días (quincena)</option>
                  <option value={30}>30 días (1 mes)</option>
                </select>
                <button
                  type="button"
                  onClick={() => refetchPurchases()}
                  style={{
                    padding: '8px',
                    borderRadius: '8px',
                    border: '1px solid #cbd5e1',
                    background: '#ffffff',
                    cursor: 'pointer',
                    color: '#475569',
                    display: 'grid',
                    placeItems: 'center',
                  }}
                  title="Actualizar sugerencias"
                >
                  <RefreshCw size={15} />
                </button>
              </div>
            </div>

            {loadingPurchases ? (
              <div style={{ padding: '40px', textAlign: 'center', color: '#64748b', fontSize: '0.95rem' }}>
                Calculando necesidades de compra para {daysAhead} días...
              </div>
            ) : purchasesData?.proposals && purchasesData.proposals.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                {purchasesData.proposals.map((prop, idx) => (
                  <div
                    key={idx}
                    style={{
                      background: '#ffffff',
                      borderRadius: '14px',
                      border: '1px solid #e2e8f0',
                      padding: '18px 20px',
                      boxShadow: '0 2px 6px rgba(0,0,0,0.04)',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '14px',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <div style={{ padding: '8px', background: '#eff6ff', borderRadius: '8px', color: '#3b82f6' }}>
                          <Building2 size={18} />
                        </div>
                        <div>
                          <h4 style={{ margin: 0, fontSize: '1rem', fontWeight: 800, color: '#0f172a' }}>
                            {prop.supplier_name}
                          </h4>
                          <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                            Código: {prop.supplier_code}
                          </span>
                        </div>
                      </div>
                      <div style={{ textAlign: 'right' }}>
                        <span style={{ fontSize: '0.75rem', color: '#64748b', display: 'block' }}>Total Estimado</span>
                        <strong style={{ fontSize: '1.15rem', color: '#16a34a', fontWeight: 800 }}>
                          {formatMoney(prop.estimated_total_cents)}
                        </strong>
                      </div>
                    </div>

                    {/* Lines Table */}
                    <div style={{ overflowX: 'auto', borderRadius: '10px', border: '1px solid #f1f5f9' }}>
                      <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.85rem' }}>
                        <thead style={{ background: '#f8fafc', color: '#475569', fontSize: '0.78rem', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                          <tr>
                            <th style={{ padding: '10px 14px', width: '38%' }}>Insumo</th>
                            <th style={{ padding: '10px 14px', width: '15%' }}>SKU</th>
                            <th style={{ padding: '10px 14px', textAlign: 'right', width: '15%' }}>Cant. Sugerida</th>
                            <th style={{ padding: '10px 14px', textAlign: 'right', width: '16%' }}>Costo Unit.</th>
                            <th style={{ padding: '10px 14px', textAlign: 'right', width: '16%' }}>Subtotal</th>
                          </tr>
                        </thead>
                        <tbody>
                          {prop.lines.map((l, lIdx) => (
                            <tr key={lIdx} style={{ borderBottom: '1px solid #f1f5f9' }}>
                              <td style={{ padding: '10px 14px', fontWeight: 600, color: '#0f172a' }}>
                                {l.item_name}
                              </td>
                              <td style={{ padding: '10px 14px', color: '#94a3b8', fontSize: '0.8rem' }}>
                                {l.sku}
                              </td>
                              <td style={{ padding: '10px 14px', textAlign: 'right', fontWeight: 700, color: '#0f172a' }}>
                                {l.suggested_quantity}
                              </td>
                              <td style={{ padding: '10px 14px', textAlign: 'right', color: '#64748b' }}>
                                {formatMoney(l.unit_cost_cents)}
                              </td>
                              <td style={{ padding: '10px 14px', textAlign: 'right', fontWeight: 700, color: '#16a34a' }}>
                                {formatMoney(l.line_total_cents)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ padding: '40px', textAlign: 'center', color: '#64748b', background: '#f8fafc', borderRadius: '12px', border: '1px dashed #cbd5e1' }}>
                <CheckCircle2 size={32} color="#10b981" style={{ margin: '0 auto 10px' }} />
                <p style={{ margin: 0, fontWeight: 700, color: '#0f172a' }}>Inventario en niveles óptimos</p>
                <span style={{ fontSize: '0.85rem', color: '#64748b' }}>No se requieren compras urgentes para los próximos {daysAhead} días.</span>
              </div>
            )}
          </div>
        )}

        {/* TAB 2: WASTE AUDIT */}
        {activeTab === 'waste' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '12px 18px',
                background: '#fffbeb',
                borderRadius: '12px',
                border: '1px solid #fde68a',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.85rem', color: '#92400e' }}>
                <AlertTriangle size={18} color="#d97706" />
                <span>Auditoría de mermas vs consumo teórico de recetas en los últimos 30 días.</span>
              </div>
              <button
                type="button"
                onClick={() => refetchWaste()}
                style={{
                  padding: '8px',
                  borderRadius: '8px',
                  border: '1px solid #fde68a',
                  background: '#ffffff',
                  cursor: 'pointer',
                  color: '#92400e',
                  display: 'grid',
                  placeItems: 'center',
                }}
                title="Actualizar auditoría"
              >
                <RefreshCw size={15} />
              </button>
            </div>

            {loadingWaste ? (
              <div style={{ padding: '40px', textAlign: 'center', color: '#64748b', fontSize: '0.95rem' }}>
                Auditando registros de almacén y mermas...
              </div>
            ) : wasteData?.audit_records && wasteData.audit_records.length > 0 ? (
              <div style={{ overflowX: 'auto', borderRadius: '12px', border: '1px solid #e2e8f0', background: '#ffffff' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.85rem' }}>
                  <thead style={{ background: '#f8fafc', color: '#475569', fontSize: '0.78rem', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                    <tr>
                      <th style={{ padding: '12px 16px' }}>Insumo</th>
                      <th style={{ padding: '12px 16px', textAlign: 'right' }}>Cant. Merma</th>
                      <th style={{ padding: '12px 16px', textAlign: 'right' }}>Costo Total</th>
                      <th style={{ padding: '12px 16px', textAlign: 'center' }}>Nivel de Riesgo</th>
                      <th style={{ padding: '12px 16px' }}>Recomendación</th>
                    </tr>
                  </thead>
                  <tbody>
                    {wasteData.audit_records.map((r, rIdx) => {
                      const riskColor =
                        r.risk_level === 'HIGH'
                          ? { bg: '#fee2e2', text: '#991b1b', border: '#fecaca' }
                          : r.risk_level === 'MEDIUM'
                          ? { bg: '#fef3c7', text: '#92400e', border: '#fde68a' }
                          : { bg: '#f0fdf4', text: '#166534', border: '#bbf7d0' };

                      return (
                        <tr key={rIdx} style={{ borderBottom: '1px solid #f1f5f9' }}>
                          <td style={{ padding: '12px 16px', fontWeight: 600, color: '#0f172a' }}>
                            {r.item_name}
                          </td>
                          <td style={{ padding: '12px 16px', textAlign: 'right', fontWeight: 700 }}>
                            {r.total_waste_quantity}
                          </td>
                          <td style={{ padding: '12px 16px', textAlign: 'right', fontWeight: 700, color: '#ef4444' }}>
                            {formatMoney(r.total_waste_cents)}
                          </td>
                          <td style={{ padding: '12px 16px', textAlign: 'center' }}>
                            <span
                              style={{
                                padding: '4px 10px',
                                borderRadius: '9999px',
                                fontSize: '0.75rem',
                                fontWeight: 700,
                                background: riskColor.bg,
                                color: riskColor.text,
                                border: `1px solid ${riskColor.border}`,
                              }}
                            >
                              {r.risk_level}
                            </span>
                          </td>
                          <td style={{ padding: '12px 16px', color: '#475569', fontSize: '0.82rem' }}>
                            {r.recommendation}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <div style={{ padding: '40px', textAlign: 'center', color: '#64748b', background: '#f8fafc', borderRadius: '12px', border: '1px dashed #cbd5e1' }}>
                <CheckCircle2 size={32} color="#10b981" style={{ margin: '0 auto 10px' }} />
                <p style={{ margin: 0, fontWeight: 700, color: '#0f172a' }}>Sin mermas críticas registradas</p>
                <span style={{ fontSize: '0.85rem', color: '#64748b' }}>El rendimiento de recetas se mantiene dentro de los márgenes estándar.</span>
              </div>
            )}
          </div>
        )}
      </div>
    </Modal>
  );
};
