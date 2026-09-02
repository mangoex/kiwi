import React, { useState } from 'react';
import {
  ArrowRight,
  BarChart3,
  Building2,
  CheckCircle2,
  Lightbulb,
  Loader2,
  PieChart,
  RotateCcw,
  Send,
  ShieldCheck,
  ShoppingBag,
  Sparkles,
  TrendingUp,
} from 'lucide-react';
import { fetchApi } from '@restaurantos/api-client';
import './ExecutiveCopilot.css';

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
    label: 'Top productos por margen',
    description: 'Detecta los productos más rentables.',
    prompt: '¿Cuáles son los productos con mejor margen de ganancia y rentabilidad?',
    icon: TrendingUp,
    badge: 'Rentabilidad',
  },
  {
    label: 'Comparar sucursales',
    description: 'Contrasta ventas, pedidos y ticket.',
    prompt: 'Compara el desempeño y ventas entre todas las sucursales activas.',
    icon: Building2,
    badge: 'Sucursales',
  },
  {
    label: 'Ventas por canal',
    description: 'Revisa POS y plataformas de delivery.',
    prompt: 'Muestra el desglose de pedidos por canal (POS, Rappi, Uber Eats, DiDi).',
    icon: PieChart,
    badge: 'Canales',
  },
  {
    label: 'Resumen del negocio',
    description: 'Obtén una lectura ejecutiva general.',
    prompt: 'Dame un resumen ejecutivo de las ventas totales, pedidos y ticket promedio.',
    icon: ShoppingBag,
    badge: 'KPIs',
  },
];

const renderInlineText = (text: string) => {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);

  return parts.map((part, index) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={index}>{part.slice(2, -2)}</strong>;
    }
    return part;
  });
};

const renderFormattedText = (text: string) => {
  if (!text) return null;

  const normalized = text
    .replace(/\r\n/g, '\n')
    .replace(/(?:^|\s)\*(?!\*)\s+/g, '\n* ')
    .split('\n')
    .map(line => line.trim())
    .filter(Boolean);

  return (
    <div className="executive-copilot__answer-copy">
      {normalized.map((line, index) => {
        const heading = line.match(/^#{2,4}\s+(.+)$/);
        if (heading) {
          return <h4 key={index}>{renderInlineText(heading[1])}</h4>;
        }

        const numbered = line.match(/^(\d+)\.\s+(.+)$/);
        if (numbered) {
          return (
            <div className="executive-copilot__insight" key={index}>
              <span className="executive-copilot__insight-index">{numbered[1]}</span>
              <p>{renderInlineText(numbered[2])}</p>
            </div>
          );
        }

        const bullet = line.match(/^[*-]\s+(.+)$/);
        if (bullet) {
          return (
            <div className="executive-copilot__bullet" key={index}>
              <span aria-hidden="true" />
              <p>{renderInlineText(bullet[1])}</p>
            </div>
          );
        }

        return <p key={index}>{renderInlineText(line)}</p>;
      })}
    </div>
  );
};

export const ExecutiveCopilot: React.FC<ExecutiveCopilotProps> = ({
  selectedBranchId,
  branches = [],
}) => {
  const [prompt, setPrompt] = useState('');
  const [loading, setLoading] = useState(false);
  const [insights, setInsights] = useState<ExecutiveInsightsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selectedBranchName = selectedBranchId
    ? branches.find(branch => branch.id === selectedBranchId)?.name || 'Sucursal seleccionada'
    : 'Todas las sucursales';

  const handleAsk = async (queryText?: string) => {
    const q = (queryText || prompt).trim();
    if (!q) return;

    if (queryText) setPrompt(queryText);
    setLoading(true);
    setError(null);

    try {
      const payload: { prompt: string; branch_id?: string } = { prompt: q };
      if (selectedBranchId) payload.branch_id = selectedBranchId;

      const response = await fetchApi<ExecutiveInsightsResponse>(
        '/admin-ai/executive-insights',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        },
      );

      setInsights(response);
    } catch (requestError: any) {
      console.error('Error fetching executive insights:', requestError);
      setError(requestError?.message || 'No fue posible generar el informe ejecutivo.');
    } finally {
      setLoading(false);
    }
  };

  const formatMoney = (cents: number) => (cents / 100).toLocaleString('es-MX', {
    style: 'currency',
    currency: 'MXN',
  });

  return (
    <section
      className="executive-copilot"
      aria-labelledby="executive-copilot-title"
      aria-busy={loading}
    >
      <header className="executive-copilot__header">
        <div className="executive-copilot__identity">
          <div className="executive-copilot__mark" aria-hidden="true">
            <Sparkles size={23} />
          </div>
          <div>
            <span className="executive-copilot__eyebrow">Inteligencia ejecutiva</span>
            <div className="executive-copilot__title-row">
              <h2 id="executive-copilot-title">Copiloto Ejecutivo</h2>
              <span className="executive-copilot__ai-badge">IA + datos verificados</span>
            </div>
            <p>Pregunta por ventas, rentabilidad y desempeño con cálculos autoritarios.</p>
          </div>
        </div>

        <div className="executive-copilot__trust">
          <div className="executive-copilot__scope">
            <Building2 size={16} aria-hidden="true" />
            <span><small>Alcance</small>{selectedBranchName}</span>
          </div>
          <div className="executive-copilot__verified">
            <ShieldCheck size={16} aria-hidden="true" />
            <span>Fuentes verificadas</span>
          </div>
        </div>
      </header>

      <div className="executive-copilot__body">
        <section className="executive-copilot__starter" aria-labelledby="executive-copilot-starters">
          <div className="executive-copilot__section-heading">
            <div>
              <h3 id="executive-copilot-starters">Empieza con una consulta</h3>
              <p>Selecciona una sugerencia o escribe una pregunta propia.</p>
            </div>
          </div>

          <div className="executive-copilot__quick-grid">
            {QUICK_PROMPTS.map(item => {
              const Icon = item.icon;
              return (
                <button
                  className="executive-copilot__quick-action"
                  key={item.label}
                  type="button"
                  onClick={() => handleAsk(item.prompt)}
                  disabled={loading}
                  aria-label={`${item.label}: ${item.description}`}
                >
                  <span className="executive-copilot__quick-icon" aria-hidden="true">
                    <Icon size={18} />
                  </span>
                  <span className="executive-copilot__quick-copy">
                    <strong>{item.label}</strong>
                    <small>{item.description}</small>
                  </span>
                  <span className="executive-copilot__quick-badge">{item.badge}</span>
                  <ArrowRight className="executive-copilot__quick-arrow" size={17} aria-hidden="true" />
                </button>
              );
            })}
          </div>

          <form
            className="executive-copilot__composer"
            onSubmit={event => {
              event.preventDefault();
              handleAsk();
            }}
          >
            <label htmlFor="executive-copilot-query">Haz una consulta al copiloto</label>
            <div className="executive-copilot__composer-row">
              <input
                id="executive-copilot-query"
                type="text"
                value={prompt}
                onChange={event => setPrompt(event.target.value)}
                placeholder="Ej. ¿Qué sucursales requieren atención esta semana?"
                disabled={loading}
                aria-label="Consulta para el Copiloto Ejecutivo"
                autoComplete="off"
              />
              <button type="submit" disabled={loading || !prompt.trim()}>
                {loading ? <Loader2 className="executive-copilot__spinner" size={17} aria-hidden="true" /> : <Send size={17} aria-hidden="true" />}
                <span>{loading ? 'Analizando' : 'Consultar'}</span>
              </button>
            </div>
            <p className="executive-copilot__helper">La respuesta usa el alcance seleccionado en el panel.</p>
          </form>

          <span className="executive-copilot__sr-only" aria-live="polite">
            {loading ? 'Generando análisis ejecutivo.' : insights ? 'Análisis ejecutivo actualizado.' : ''}
          </span>

          {error && (
            <div className="executive-copilot__error" role="alert">
              <div>
                <strong>No pudimos generar el análisis</strong>
                <span>{error}</span>
              </div>
              <button type="button" onClick={() => handleAsk()}>
                <RotateCcw size={15} aria-hidden="true" /> Reintentar
              </button>
            </div>
          )}
        </section>

        <section className="executive-copilot__workspace" aria-label="Resultado del Copiloto Ejecutivo">
          {!insights && !loading && (
            <div className="executive-copilot__empty">
              <span aria-hidden="true"><BarChart3 size={24} /></span>
              <div>
                <h3>Tu análisis aparecerá aquí</h3>
                <p>Recibirás un resumen legible, el detalle numérico y acciones sugeridas cuando estén disponibles.</p>
              </div>
            </div>
          )}

          {loading && (
            <div className="executive-copilot__loading" role="status">
              <span><Loader2 className="executive-copilot__spinner" size={22} /></span>
              <div>
                <strong>Analizando información del negocio</strong>
                <p>Estamos contrastando los datos y preparando una respuesta ejecutiva.</p>
              </div>
            </div>
          )}

          {insights && !loading && (
            <article className="executive-copilot__result">
              <header className="executive-copilot__result-header">
                <div>
                  <span className="executive-copilot__result-kicker">Resultado</span>
                  <h3>Informe ejecutivo</h3>
                </div>
                <span className="executive-copilot__result-status">
                  <CheckCircle2 size={16} aria-hidden="true" /> Análisis completado
                </span>
              </header>

              {renderFormattedText(insights.answer)}

              {insights.data_points && insights.data_points.length > 0 && (
                <div className="executive-copilot__data">
                  <div className="executive-copilot__data-heading">
                    <div>
                      <span>Detalle</span>
                      <h4>Datos que sustentan el análisis</h4>
                    </div>
                    <small>{insights.data_points.length} registros</small>
                  </div>
                  <div className="executive-copilot__table-shell">
                    <table aria-label="Datos que sustentan el informe ejecutivo">
                      <thead>
                        <tr>
                          {insights.data_points[0].product_name && (
                            <><th>Producto</th><th>Unidades</th><th>Ingresos</th><th>Costo estimado</th><th>Margen</th><th>Margen %</th></>
                          )}
                          {insights.data_points[0].branch_name && (
                            <><th>Sucursal</th><th>Código</th><th>Pedidos</th><th>Venta total</th><th>Ticket promedio</th></>
                          )}
                          {insights.data_points[0].channel && (
                            <><th>Canal</th><th>Pedidos</th><th>Venta total</th></>
                          )}
                        </tr>
                      </thead>
                      <tbody>
                        {insights.data_points.map((row: any, rowIndex: number) => (
                          <tr key={rowIndex}>
                            {row.product_name && (
                              <>
                                <td>{row.product_name}</td><td>{row.units_sold}</td>
                                <td className="executive-copilot__money">{formatMoney(row.revenue_cents)}</td>
                                <td>{formatMoney(row.estimated_cost_cents || 0)}</td>
                                <td>{formatMoney(row.gross_margin_cents || 0)}</td>
                                <td><span className="executive-copilot__margin">{row.margin_pct}%</span></td>
                              </>
                            )}
                            {row.branch_name && (
                              <>
                                <td>{row.branch_name}</td><td>{row.branch_code}</td><td>{row.total_orders}</td>
                                <td className="executive-copilot__money">{formatMoney(row.total_sales_cents)}</td>
                                <td>{formatMoney(row.average_ticket_cents)}</td>
                              </>
                            )}
                            {row.channel && (
                              <>
                                <td>{row.channel}</td><td>{row.orders}</td>
                                <td className="executive-copilot__money">{formatMoney(row.total_sales_cents)}</td>
                              </>
                            )}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {insights.suggested_actions && insights.suggested_actions.length > 0 && (
                <section className="executive-copilot__suggested-actions" aria-labelledby="executive-actions-title">
                  <div className="executive-copilot__actions-heading">
                    <span aria-hidden="true"><Lightbulb size={18} /></span>
                    <div>
                      <small>Siguientes pasos</small>
                      <h4 id="executive-actions-title">Acciones estratégicas sugeridas</h4>
                    </div>
                  </div>
                  <ol>
                    {insights.suggested_actions.map((action, index) => (
                      <li key={index}><span>{index + 1}</span><p>{renderInlineText(action)}</p></li>
                    ))}
                  </ol>
                </section>
              )}

              {insights.sources && insights.sources.length > 0 && (
                <footer className="executive-copilot__sources">
                  <span><ShieldCheck size={15} aria-hidden="true" /> Fuentes: {insights.sources.join(', ')}</span>
                  <span>Cálculos deterministas de RestaurantOS</span>
                </footer>
              )}
            </article>
          )}
        </section>
      </div>
    </section>
  );
};
