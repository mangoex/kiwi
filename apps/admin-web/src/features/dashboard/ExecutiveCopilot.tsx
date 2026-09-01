import React, { useState } from 'react';
import {
  Sparkles,
  Send,
  Loader2,
  TrendingUp,
  Building2,
  PieChart,
  ShoppingBag,
  ShieldCheck,
  Lightbulb,
  ArrowRight,
  RotateCcw,
  CheckCircle2,
} from 'lucide-react';
import { fetchApi } from '@restaurantos/api-client';

type ExecutiveInsightsResponse = {
  answer: string;
  data_points?: any[];
  sources?: string[];
  suggested_actions?: string[];
};

interface ExecutiveCopilotProps {
  selectedBranchId?: string;
  branches?: { id: string; name: string }[];
}

const QUICK_PROMPTS = [
  {
    label: 'Top Productos por Margen',
    prompt: '¿Cuáles son los productos con mejor margen de ganancia y rentabilidad?',
    icon: TrendingUp,
    badge: 'Rentabilidad',
  },
  {
    label: 'Comparativa de Sucursales',
    prompt: 'Compara el desempeño y ventas entre todas las sucursales activas.',
    icon: Building2,
    badge: 'Sucursales',
  },
  {
    label: 'Ventas por Canal de Delivery',
    prompt: 'Muestra el desglose de pedidos por canal (POS, Rappi, Uber Eats, DiDi).',
    icon: PieChart,
    badge: 'Canales',
  },
  {
    label: 'Resumen General del Negocio',
    prompt: 'Dame un resumen ejecutivo de las ventas totales, pedidos y ticket promedio.',
    icon: ShoppingBag,
    badge: 'KPIs',
  },
];

export const ExecutiveCopilot: React.FC<ExecutiveCopilotProps> = ({
  selectedBranchId,
}) => {
  const [prompt, setPrompt] = useState('');
  const [loading, setLoading] = useState(false);
  const [insights, setInsights] = useState<ExecutiveInsightsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleAsk = async (queryText?: string) => {
    const q = (queryText || prompt).trim();
    if (!q) return;

    setLoading(true);
    setError(null);

    try {
      const payload: { prompt: string; branch_id?: string } = { prompt: q };
      if (selectedBranchId) {
        payload.branch_id = selectedBranchId;
      }

      const res = await fetchApi<ExecutiveInsightsResponse>(
        '/admin-ai/executive-insights',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        }
      );

      setInsights(res);
      if (queryText) {
        setPrompt(queryText);
      }
    } catch (err: any) {
      console.error('Error fetching executive insights:', err);
      setError(err?.message || 'No fue posible generar el informe ejecutivo.');
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !loading) {
      e.preventDefault();
      handleAsk();
    }
  };

  const formatMoney = (cents: number) => {
    return (cents / 100).toLocaleString('es-MX', {
      style: 'currency',
      currency: 'MXN',
    });
  };

  return (
    <div className="bg-gradient-to-br from-slate-900 via-slate-800 to-indigo-950 rounded-2xl p-6 text-white shadow-xl border border-indigo-500/20 mb-8 transition-all">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-5 border-b border-slate-700/60">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-gradient-to-tr from-emerald-500 to-teal-400 rounded-xl text-slate-950 shadow-lg shadow-emerald-500/20">
            <Sparkles className="w-6 h-6 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-bold tracking-tight text-slate-100">
                Copiloto Ejecutivo & BI
              </h2>
              <span className="px-2 py-0.5 text-xs font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 rounded-full">
                AI + Determinismo
              </span>
            </div>
            <p className="text-sm text-slate-400 mt-0.5">
              Consultas en lenguaje natural con agregaciones matemáticas autoritarias en centavos.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 text-xs text-slate-400 bg-slate-800/80 px-3 py-1.5 rounded-lg border border-slate-700">
          <ShieldCheck className="w-4 h-4 text-emerald-400" />
          <span>PostgreSQL & Python Verificado</span>
        </div>
      </div>

      {/* Quick Prompt Chips */}
      <div className="mt-4 flex flex-wrap gap-2">
        {QUICK_PROMPTS.map((item, idx) => {
          const Icon = item.icon;
          return (
            <button
              key={idx}
              onClick={() => handleAsk(item.prompt)}
              disabled={loading}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800/90 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700 hover:border-slate-600 transition-all hover:shadow cursor-pointer disabled:opacity-50"
            >
              <Icon className="w-3.5 h-3.5 text-emerald-400" />
              <span>{item.label}</span>
              <span className="text-[10px] bg-slate-900/60 text-slate-400 px-1.5 py-0.5 rounded">
                {item.badge}
              </span>
            </button>
          );
        })}
      </div>

      {/* Search Bar Input */}
      <div className="mt-4 flex gap-2">
        <div className="relative flex-1">
          <input
            type="text"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Escribe tu consulta ejecutiva... ej. ¿Cuáles fueron los productos con mejor margen?"
            className="w-full bg-slate-950/70 border border-slate-700 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 text-slate-100 placeholder-slate-500 rounded-xl px-4 py-3 text-sm transition outline-none"
            disabled={loading}
          />
        </div>
        <button
          onClick={() => handleAsk()}
          disabled={loading || !prompt.trim()}
          className="px-5 py-3 bg-emerald-500 hover:bg-emerald-400 disabled:bg-slate-700 text-slate-950 font-semibold rounded-xl flex items-center gap-2 text-sm shadow-md transition disabled:cursor-not-allowed cursor-pointer"
        >
          {loading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Analizando...</span>
            </>
          ) : (
            <>
              <Send className="w-4 h-4" />
              <span>Consultar</span>
            </>
          )}
        </button>
      </div>

      {/* Error display */}
      {error && (
        <div className="mt-4 p-3 bg-rose-950/60 border border-rose-800/80 rounded-xl text-rose-300 text-xs flex items-center justify-between">
          <span>{error}</span>
          <button
            onClick={() => handleAsk()}
            className="flex items-center gap-1 text-rose-200 hover:underline cursor-pointer"
          >
            <RotateCcw className="w-3.5 h-3.5" /> Reintentar
          </button>
        </div>
      )}

      {/* Insights Display */}
      {insights && !loading && (
        <div className="mt-6 bg-slate-950/60 border border-slate-800 rounded-xl p-5 animate-in fade-in duration-300">
          {/* Executive Answer Text */}
          <div className="text-slate-200 text-sm leading-relaxed whitespace-pre-line mb-4 font-normal">
            {insights.answer}
          </div>

          {/* Data Points Table / Breakdown */}
          {insights.data_points && insights.data_points.length > 0 && (
            <div className="mt-4 overflow-x-auto rounded-lg border border-slate-800 bg-slate-900/50">
              <table className="w-full text-left text-xs text-slate-300">
                <thead className="bg-slate-800/80 text-slate-400 font-semibold uppercase tracking-wider text-[10px]">
                  <tr>
                    {insights.data_points[0].product_name && (
                      <>
                        <th className="px-4 py-2.5">Producto</th>
                        <th className="px-4 py-2.5 text-right">Unidades</th>
                        <th className="px-4 py-2.5 text-right">Ingresos</th>
                        <th className="px-4 py-2.5 text-right">Costo Estimado</th>
                        <th className="px-4 py-2.5 text-right">Margen ($)</th>
                        <th className="px-4 py-2.5 text-right">Margen (%)</th>
                      </>
                    )}
                    {insights.data_points[0].branch_name && (
                      <>
                        <th className="px-4 py-2.5">Sucursal</th>
                        <th className="px-4 py-2.5">Código</th>
                        <th className="px-4 py-2.5 text-right">Pedidos</th>
                        <th className="px-4 py-2.5 text-right">Venta Total</th>
                        <th className="px-4 py-2.5 text-right">Ticket Promedio</th>
                      </>
                    )}
                    {insights.data_points[0].channel && (
                      <>
                        <th className="px-4 py-2.5">Canal</th>
                        <th className="px-4 py-2.5 text-right">Pedidos</th>
                        <th className="px-4 py-2.5 text-right">Venta Total</th>
                      </>
                    )}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {insights.data_points.map((row: any, rIdx: number) => (
                    <tr key={rIdx} className="hover:bg-slate-800/40 transition">
                      {row.product_name && (
                        <>
                          <td className="px-4 py-2 font-medium text-slate-100">{row.product_name}</td>
                          <td className="px-4 py-2 text-right">{row.units_sold}</td>
                          <td className="px-4 py-2 text-right font-semibold text-emerald-400">
                            {formatMoney(row.revenue_cents)}
                          </td>
                          <td className="px-4 py-2 text-right text-slate-400">
                            {formatMoney(row.estimated_cost_cents || 0)}
                          </td>
                          <td className="px-4 py-2 text-right font-medium text-slate-200">
                            {formatMoney(row.gross_margin_cents || 0)}
                          </td>
                          <td className="px-4 py-2 text-right">
                            <span className="px-2 py-0.5 bg-emerald-500/10 text-emerald-400 rounded-full font-semibold">
                              {row.margin_pct}%
                            </span>
                          </td>
                        </>
                      )}
                      {row.branch_name && (
                        <>
                          <td className="px-4 py-2 font-medium text-slate-100">{row.branch_name}</td>
                          <td className="px-4 py-2 text-slate-400">{row.branch_code}</td>
                          <td className="px-4 py-2 text-right">{row.total_orders}</td>
                          <td className="px-4 py-2 text-right font-semibold text-emerald-400">
                            {formatMoney(row.total_sales_cents)}
                          </td>
                          <td className="px-4 py-2 text-right text-slate-300">
                            {formatMoney(row.average_ticket_cents)}
                          </td>
                        </>
                      )}
                      {row.channel && (
                        <>
                          <td className="px-4 py-2 font-medium text-slate-100 uppercase">{row.channel}</td>
                          <td className="px-4 py-2 text-right">{row.orders}</td>
                          <td className="px-4 py-2 text-right font-semibold text-emerald-400">
                            {formatMoney(row.total_sales_cents)}
                          </td>
                        </>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Suggested Actions */}
          {insights.suggested_actions && insights.suggested_actions.length > 0 && (
            <div className="mt-4 pt-3 border-t border-slate-800">
              <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <Lightbulb className="w-3.5 h-3.5 text-amber-400" />
                Acciones Estratégicas Sugeridas
              </h4>
              <ul className="space-y-1.5 text-xs text-slate-300">
                {insights.suggested_actions.map((act: string, aIdx: number) => (
                  <li key={aIdx} className="flex items-start gap-2">
                    <ArrowRight className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
                    <span>{act}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Grounding and Sources Footer */}
          {insights.sources && (
            <div className="mt-4 pt-3 border-t border-slate-800/60 flex items-center justify-between text-[11px] text-slate-500">
              <div className="flex items-center gap-1.5">
                <CheckCircle2 className="w-3 h-3 text-emerald-500" />
                <span>Fuentes autoritarias: {insights.sources.join(', ')}</span>
              </div>
              <span>Generado con cálculos deterministas de RestaurantOS</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
