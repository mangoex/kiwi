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
      fetchApi(`/admin-ai/inventory-yield-audit${branchId ? `?branch_id=${branchId}` : ''}`),
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
      <div className="space-y-4 max-h-[80vh] overflow-y-auto pr-1">
        {/* Tab Navigation */}
        <div className="flex border-b border-slate-200 dark:border-slate-800 gap-4">
          <button
            onClick={() => setActiveTab('purchases')}
            className={`pb-3 text-sm font-semibold flex items-center gap-2 border-b-2 transition cursor-pointer ${
              activeTab === 'purchases'
                ? 'border-emerald-500 text-emerald-600 dark:text-emerald-400'
                : 'border-transparent text-slate-500 hover:text-slate-700'
            }`}
          >
            <Sparkles className="w-4 h-4" />
            Compras Sugeridas por Demanda
          </button>
          <button
            onClick={() => setActiveTab('waste')}
            className={`pb-3 text-sm font-semibold flex items-center gap-2 border-b-2 transition cursor-pointer ${
              activeTab === 'waste'
                ? 'border-emerald-500 text-emerald-600 dark:text-emerald-400'
                : 'border-transparent text-slate-500 hover:text-slate-700'
            }`}
          >
            <AlertTriangle className="w-4 h-4" />
            Auditoría de Mermas y Fugas
          </button>
        </div>

        {/* TAB 1: SUGGESTED PURCHASES */}
        {activeTab === 'purchases' && (
          <div className="space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3 bg-emerald-50 dark:bg-emerald-950/40 rounded-xl border border-emerald-200 dark:border-emerald-800/40">
              <div className="flex items-center gap-2 text-xs text-emerald-800 dark:text-emerald-300">
                <ShieldCheck className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
                <span>Proyección matemática basada en recetas y rotación histórica.</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-slate-600 dark:text-slate-400">Días a cubrir:</span>
                <select
                  value={daysAhead}
                  onChange={(e) => setDaysAhead(Number(e.target.value))}
                  className="bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg px-2.5 py-1 text-xs font-semibold outline-none"
                >
                  <option value={3}>3 días</option>
                  <option value={7}>7 días (1 semana)</option>
                  <option value={15}>15 días (quincena)</option>
                  <option value={30}>30 días (1 mes)</option>
                </select>
                <button
                  onClick={() => refetchPurchases()}
                  className="p-1.5 hover:bg-slate-200 dark:hover:bg-slate-800 rounded-lg text-slate-600 dark:text-slate-300 transition cursor-pointer"
                  title="Actualizar sugerencias"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>

            {loadingPurchases ? (
              <div className="p-8 text-center text-slate-500 text-sm">
                Calculando necesidades de compra para {daysAhead} días...
              </div>
            ) : purchasesData?.proposals && purchasesData.proposals.length > 0 ? (
              <div className="space-y-4">
                {purchasesData.proposals.map((prop, idx) => (
                  <div
                    key={idx}
                    className="p-4 bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-3"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Building2 className="w-4 h-4 text-indigo-500" />
                        <h4 className="font-bold text-sm text-slate-900 dark:text-slate-100">
                          {prop.supplier_name}
                        </h4>
                        <Badge variant="default">{prop.supplier_code}</Badge>
                      </div>
                      <div className="text-right">
                        <span className="text-xs text-slate-500 block">Total Estimado</span>
                        <span className="font-bold text-sm text-emerald-600 dark:text-emerald-400">
                          {formatMoney(prop.estimated_total_cents)}
                        </span>
                      </div>
                    </div>

                    {/* Lines Table */}
                    <div className="overflow-x-auto rounded-lg border border-slate-100 dark:border-slate-800/80">
                      <table className="w-full text-left text-xs">
                        <thead className="bg-slate-50 dark:bg-slate-800/50 text-slate-500 uppercase tracking-wider text-[10px]">
                          <tr>
                            <th className="px-3 py-2">Insumo</th>
                            <th className="px-3 py-2">SKU</th>
                            <th className="px-3 py-2 text-right">Cant. Sugerida</th>
                            <th className="px-3 py-2 text-right">Costo Unit.</th>
                            <th className="px-3 py-2 text-right">Subtotal</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                          {prop.lines.map((l, lIdx) => (
                            <tr key={lIdx} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30">
                              <td className="px-3 py-2 font-medium text-slate-800 dark:text-slate-200">
                                {l.item_name}
                              </td>
                              <td className="px-3 py-2 text-slate-400">{l.sku}</td>
                              <td className="px-3 py-2 text-right font-semibold text-slate-900 dark:text-slate-100">
                                {l.suggested_quantity}
                              </td>
                              <td className="px-3 py-2 text-right text-slate-500">
                                {formatMoney(l.unit_cost_cents)}
                              </td>
                              <td className="px-3 py-2 text-right font-semibold text-emerald-600 dark:text-emerald-400">
                                {formatMoney(l.line_total_cents)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>

                    {onSelectSupplierForPurchase && (
                      <div className="flex justify-end pt-1">
                        <Button
                          variant="secondary"
                          onClick={() => {
                            onSelectSupplierForPurchase(prop.supplier_id);
                            onClose();
                          }}
                        >
                          <PackageCheck className="w-3.5 h-3.5 mr-1.5 text-emerald-500" />
                          Generar Compra con {prop.supplier_name}
                        </Button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-8 text-center text-slate-500 text-sm">
                No hay sugerencias de compra urgentes para el periodo seleccionado.
              </div>
            )}
          </div>
        )}

        {/* TAB 2: WASTE & YIELD AUDIT */}
        {activeTab === 'waste' && (
          <div className="space-y-4">
            <div className="p-3 bg-amber-50 dark:bg-amber-950/40 rounded-xl border border-amber-200 dark:border-amber-800/40 text-xs text-amber-800 dark:text-amber-300 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0" />
              <span>Detección de mermas acumuladas y posibles fugas operativas en los últimos 30 días.</span>
            </div>

            {loadingWaste ? (
              <div className="p-8 text-center text-slate-500 text-sm">
                Auditando registros de mermas y salidas de almacén...
              </div>
            ) : wasteData?.audit_records && wasteData.audit_records.length > 0 ? (
              <div className="space-y-2">
                {wasteData.audit_records.map((rec, rIdx) => (
                  <div
                    key={rIdx}
                    className="p-3.5 bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 flex items-center justify-between"
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className="font-semibold text-sm text-slate-900 dark:text-slate-100">
                          {rec.item_name}
                        </h4>
                        <Badge variant={rec.risk_level === 'HIGH' ? 'danger' : rec.risk_level === 'MEDIUM' ? 'warning' : 'success'}>
                          Riesgo {rec.risk_level}
                        </Badge>
                      </div>
                      <p className="text-xs text-slate-500 mt-0.5">
                        {rec.recommendation} • Merma total: {rec.total_waste_quantity} unidades
                      </p>
                    </div>
                    <div className="text-right font-bold text-rose-600 dark:text-rose-400 text-sm">
                      -{formatMoney(rec.total_waste_cents)}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-8 text-center text-slate-500 text-sm">
                No se han registrado mermas críticas en el periodo analizado.
              </div>
            )}
          </div>
        )}

        <div className="flex justify-end pt-3 border-t border-slate-200 dark:border-slate-800">
          <Button variant="secondary" onClick={onClose}>
            Cerrar
          </Button>
        </div>
      </div>
    </Modal>
  );
};
