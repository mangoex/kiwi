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

const renderFormattedText = (text: string) => {
  if (!text) return null;

  const paragraphs = text.split(/\n\s*\n/);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', lineHeight: 1.6 }}>
      {paragraphs.map((para, pIdx) => {
        const trimmed = para.trim();
        if (!trimmed) return null;

        if (trimmed.startsWith('###') || trimmed.startsWith('##')) {
          const headingText = trimmed.replace(/^#+\s*/, '').replace(/\*\*/g, '');
          return (
            <h4
              key={pIdx}
              style={{
                fontSize: '1rem',
                fontWeight: 800,
                color: '#38bdf8',
                marginTop: '8px',
                marginBottom: '4px',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
              }}
            >
              <Sparkles size={16} color="#38bdf8" />
              {headingText}
            </h4>
          );
        }

        if (trimmed.includes('\n* ') || trimmed.includes('\n- ') || trimmed.startsWith('* ') || trimmed.startsWith('- ') || /^\d+\.\s/.test(trimmed)) {
          const lines = trimmed.split('\n');
          return (
            <div key={pIdx} style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {lines.map((line, lIdx) => {
                const lineTrimmed = line.trim();
                if (!lineTrimmed) return null;
                const cleanLine = lineTrimmed.replace(/^[\*\-\d\.]+\s*/, '');

                const parts = cleanLine.split(/(\?\*\*[^*]+\*\*)/g);
                return (
                  <div
                    key={lIdx}
                    style={{
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: '8px',
                      background: 'rgba(30, 41, 59, 0.5)',
                      padding: '8px 12px',
                      borderRadius: '8px',
                      border: '1px solid rgba(51, 65, 85, 0.4)',
                    }}
                  >
                    <span style={{ color: '#10b981', fontWeight: 800, fontSize: '0.9rem' }}>•</span>
                    <span style={{ fontSize: '0.88rem', color: '#cbd5e1' }}>
                      {parts.map((part, partIdx) => {
                        if (part.startsWith('**') && part.endsWith('**')) {
                          return (
                            <strong key={partIdx} style={{ color: '#f8fafc', fontWeight: 700 }}>
                              {part.slice(2, -2)}
                            </strong>
                          );
                        }
                        return part;
                      })}
                    </span>
                  </div>
                );
              })}
            </div>
          );
        }

        const parts = trimmed.split(/(\?\*\*[^*]+\*\*)/g);
        return (
          <p key={pIdx} style={{ margin: 0, fontSize: '0.9rem', color: '#cbd5e1' }}>
            {parts.map((part, partIdx) => {
              if (part.startsWith('**') && part.endsWith('**')) {
                return (
                  <strong key={partIdx} style={{ color: '#ffffff', fontWeight: 700 }}>
                    {part.slice(2, -2)}
                  </strong>
                );
              }
              return part;
            })}
          </p>
        );
      })}
    </div>
  );
};

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
    <div
      style={{
        background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)',
        borderRadius: '20px',
        padding: '24px 28px',
        color: '#ffffff',
        boxShadow: '0 12px 30px rgba(0, 0, 0, 0.25)',
        border: '1px solid rgba(99, 102, 241, 0.25)',
        marginBottom: '32px',
        fontFamily: 'inherit',
      }}
    >
      {/* Header */}
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '16px',
          paddingBottom: '20px',
          borderBottom: '1px solid rgba(51, 65, 85, 0.6)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div
            style={{
              padding: '12px',
              background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
              borderRadius: '14px',
              color: '#ffffff',
              display: 'grid',
              placeItems: 'center',
              boxShadow: '0 4px 14px rgba(16, 185, 129, 0.35)',
            }}
          >
            <Sparkles size={24} />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <h2 style={{ fontSize: '1.25rem', fontWeight: 800, color: '#f8fafc', margin: 0, letterSpacing: '-0.02em' }}>
                Copiloto Ejecutivo & BI
              </h2>
              <span
                style={{
                  padding: '2px 8px',
                  fontSize: '0.72rem',
                  fontWeight: 700,
                  background: 'rgba(16, 185, 129, 0.15)',
                  color: '#34d399',
                  border: '1px solid rgba(16, 185, 129, 0.3)',
                  borderRadius: '9999px',
                }}
              >
                AI + Determinismo
              </span>
            </div>
            <p style={{ fontSize: '0.85rem', color: '#94a3b8', margin: '3px 0 0' }}>
              Consultas en lenguaje natural con agregaciones matemáticas autoritarias en centavos.
            </p>
          </div>
        </div>

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            fontSize: '0.78rem',
            color: '#94a3b8',
            background: 'rgba(30, 41, 59, 0.8)',
            padding: '8px 14px',
            borderRadius: '10px',
            border: '1px solid #334155',
          }}
        >
          <ShieldCheck size={16} style={{ color: '#34d399' }} />
          <span>PostgreSQL & Python Verificado</span>
        </div>
      </div>

      {/* Quick Prompt Chips */}
      <div style={{ marginTop: '16px', display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
        {QUICK_PROMPTS.map((item, idx) => {
          const Icon = item.icon;
          return (
            <button
              key={idx}
              onClick={() => handleAsk(item.prompt)}
              disabled={loading}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                padding: '8px 14px',
                borderRadius: '10px',
                fontSize: '0.82rem',
                fontWeight: 600,
                background: 'rgba(30, 41, 59, 0.9)',
                color: '#e2e8f0',
                border: '1px solid #475569',
                cursor: loading ? 'not-allowed' : 'pointer',
                transition: 'all 0.15s ease',
              }}
            >
              <Icon size={15} style={{ color: '#34d399' }} />
              <span>{item.label}</span>
              <span
                style={{
                  fontSize: '0.68rem',
                  background: 'rgba(15, 23, 42, 0.7)',
                  color: '#94a3b8',
                  padding: '2px 6px',
                  borderRadius: '4px',
                }}
              >
                {item.badge}
              </span>
            </button>
          );
        })}
      </div>

      {/* Search Bar Input */}
      <div style={{ marginTop: '16px', display: 'flex', gap: '10px' }}>
        <div style={{ flex: 1, position: 'relative' }}>
          <input
            type="text"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Escribe tu consulta ejecutiva... ej. ¿Cuáles fueron los productos con mejor margen?"
            disabled={loading}
            style={{
              width: '100%',
              boxSizing: 'border-box',
              background: 'rgba(15, 23, 42, 0.85)',
              border: '1.5px solid #475569',
              color: '#f8fafc',
              borderRadius: '12px',
              padding: '13px 18px',
              fontSize: '0.92rem',
              outline: 'none',
              transition: 'border-color 0.15s ease',
            }}
          />
        </div>
        <button
          onClick={() => handleAsk()}
          disabled={loading || !prompt.trim()}
          style={{
            padding: '13px 22px',
            background: loading || !prompt.trim() ? '#475569' : 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
            color: '#ffffff',
            fontWeight: 700,
            borderRadius: '12px',
            border: 'none',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            fontSize: '0.9rem',
            cursor: loading || !prompt.trim() ? 'not-allowed' : 'pointer',
            boxShadow: '0 4px 12px rgba(16, 185, 129, 0.25)',
            transition: 'all 0.15s ease',
          }}
        >
          {loading ? (
            <>
              <Loader2 size={16} className="animate-spin" />
              <span>Analizando...</span>
            </>
          ) : (
            <>
              <Send size={16} />
              <span>Consultar</span>
            </>
          )}
        </button>
      </div>

      {/* Error display */}
      {error && (
        <div
          style={{
            marginTop: '16px',
            padding: '12px 16px',
            background: 'rgba(136, 19, 55, 0.4)',
            border: '1px solid rgba(244, 63, 94, 0.5)',
            borderRadius: '12px',
            color: '#fecdd3',
            fontSize: '0.85rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <span>{error}</span>
          <button
            onClick={() => handleAsk()}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              color: '#fda4af',
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
              textDecoration: 'underline',
            }}
          >
            <RotateCcw size={14} /> Reintentar
          </button>
        </div>
      )}

      {/* Insights Display */}
      {insights && !loading && (
        <div
          style={{
            marginTop: '24px',
            background: 'rgba(15, 23, 42, 0.75)',
            border: '1px solid rgba(51, 65, 85, 0.8)',
            borderRadius: '16px',
            padding: '24px',
          }}
        >
          {/* Executive Answer Formatted Text */}
          <div style={{ marginBottom: '20px' }}>
            {renderFormattedText(insights.answer)}
          </div>

          {/* Data Points Table / Breakdown */}
          {insights.data_points && insights.data_points.length > 0 && (
            <div
              style={{
                marginTop: '18px',
                overflowX: 'auto',
                borderRadius: '12px',
                border: '1px solid #334155',
                background: 'rgba(30, 41, 59, 0.6)',
              }}
            >
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.82rem', color: '#e2e8f0' }}>
                <thead style={{ background: '#1e293b', color: '#94a3b8', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  <tr>
                    {insights.data_points[0].product_name && (
                      <>
                        <th style={{ padding: '12px 16px' }}>Producto</th>
                        <th style={{ padding: '12px 16px', textAlign: 'right' }}>Unidades</th>
                        <th style={{ padding: '12px 16px', textAlign: 'right' }}>Ingresos</th>
                        <th style={{ padding: '12px 16px', textAlign: 'right' }}>Costo Estimado</th>
                        <th style={{ padding: '12px 16px', textAlign: 'right' }}>Margen ($)</th>
                        <th style={{ padding: '12px 16px', textAlign: 'right' }}>Margen (%)</th>
                      </>
                    )}
                    {insights.data_points[0].branch_name && (
                      <>
                        <th style={{ padding: '12px 16px' }}>Sucursal</th>
                        <th style={{ padding: '12px 16px' }}>Código</th>
                        <th style={{ padding: '12px 16px', textAlign: 'right' }}>Pedidos</th>
                        <th style={{ padding: '12px 16px', textAlign: 'right' }}>Venta Total</th>
                        <th style={{ padding: '12px 16px', textAlign: 'right' }}>Ticket Promedio</th>
                      </>
                    )}
                    {insights.data_points[0].channel && (
                      <>
                        <th style={{ padding: '12px 16px' }}>Canal</th>
                        <th style={{ padding: '12px 16px', textAlign: 'right' }}>Pedidos</th>
                        <th style={{ padding: '12px 16px', textAlign: 'right' }}>Venta Total</th>
                      </>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {insights.data_points.map((row: any, rIdx: number) => (
                    <tr
                      key={rIdx}
                      style={{
                        borderBottom: '1px solid rgba(51, 65, 85, 0.4)',
                        background: rIdx % 2 === 0 ? 'transparent' : 'rgba(15, 23, 42, 0.3)',
                      }}
                    >
                      {row.product_name && (
                        <>
                          <td style={{ padding: '12px 16px', fontWeight: 600, color: '#ffffff' }}>{row.product_name}</td>
                          <td style={{ padding: '12px 16px', textAlign: 'right' }}>{row.units_sold}</td>
                          <td style={{ padding: '12px 16px', textAlign: 'right', fontWeight: 700, color: '#34d399' }}>
                            {formatMoney(row.revenue_cents)}
                          </td>
                          <td style={{ padding: '12px 16px', textAlign: 'right', color: '#94a3b8' }}>
                            {formatMoney(row.estimated_cost_cents || 0)}
                          </td>
                          <td style={{ padding: '12px 16px', textAlign: 'right', fontWeight: 600, color: '#f8fafc' }}>
                            {formatMoney(row.gross_margin_cents || 0)}
                          </td>
                          <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                            <span
                              style={{
                                padding: '3px 8px',
                                background: 'rgba(16, 185, 129, 0.15)',
                                color: '#34d399',
                                borderRadius: '9999px',
                                fontWeight: 700,
                              }}
                            >
                              {row.margin_pct}%
                            </span>
                          </td>
                        </>
                      )}
                      {row.branch_name && (
                        <>
                          <td style={{ padding: '12px 16px', fontWeight: 600, color: '#ffffff' }}>{row.branch_name}</td>
                          <td style={{ padding: '12px 16px', color: '#94a3b8' }}>{row.branch_code}</td>
                          <td style={{ padding: '12px 16px', textAlign: 'right' }}>{row.total_orders}</td>
                          <td style={{ padding: '12px 16px', textAlign: 'right', fontWeight: 700, color: '#34d399' }}>
                            {formatMoney(row.total_sales_cents)}
                          </td>
                          <td style={{ padding: '12px 16px', textAlign: 'right', color: '#cbd5e1' }}>
                            {formatMoney(row.average_ticket_cents)}
                          </td>
                        </>
                      )}
                      {row.channel && (
                        <>
                          <td style={{ padding: '12px 16px', fontWeight: 600, color: '#ffffff', textTransform: 'uppercase' }}>{row.channel}</td>
                          <td style={{ padding: '12px 16px', textAlign: 'right' }}>{row.orders}</td>
                          <td style={{ padding: '12px 16px', textAlign: 'right', fontWeight: 700, color: '#34d399' }}>
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
            <div style={{ marginTop: '20px', paddingTop: '16px', borderTop: '1px solid rgba(51, 65, 85, 0.6)' }}>
              <h4
                style={{
                  fontSize: '0.82rem',
                  fontWeight: 700,
                  color: '#94a3b8',
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                  marginBottom: '10px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                <Lightbulb size={16} style={{ color: '#fbbf24' }} />
                Acciones Estratégicas Sugeridas
              </h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {insights.suggested_actions.map((act: string, aIdx: number) => (
                  <div
                    key={aIdx}
                    style={{
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: '8px',
                      fontSize: '0.85rem',
                      color: '#cbd5e1',
                    }}
                  >
                    <ArrowRight size={15} style={{ color: '#34d399', flexShrink: 0, marginTop: '2px' }} />
                    <span>{act}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Grounding and Sources Footer */}
          {insights.sources && (
            <div
              style={{
                marginTop: '16px',
                paddingTop: '12px',
                borderTop: '1px solid rgba(51, 65, 85, 0.4)',
                display: 'flex',
                flexWrap: 'wrap',
                justifyContent: 'space-between',
                alignItems: 'center',
                fontSize: '0.74rem',
                color: '#64748b',
                gap: '8px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <CheckCircle2 size={13} style={{ color: '#10b981' }} />
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
