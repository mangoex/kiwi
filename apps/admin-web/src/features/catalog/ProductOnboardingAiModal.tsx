import React, { useState, useRef, useEffect } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Button, Badge, Modal } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';
import {
  Sparkles,
  Send,
  ChefHat,
  Package,
  Layers,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  RotateCcw,
  Utensils,
  DollarSign,
  Info,
} from 'lucide-react';
import '../../premium-catalogs.css';

interface OnboardingIngredient {
  raw_name: string;
  normalized_name: string;
  net_quantity: string;
  unit: string;
  waste_rate: string;
  gross_quantity: string;
  matched_item_id: string | null;
  unit_cost: string;
  line_cost_cents: number;
  line_cost: string;
  is_new_supply: boolean;
  is_subrecipe: boolean;
  supplier_name?: string | null;
  presentation_name?: string | null;
}

interface OnboardingSummary {
  theoretical_cost_cents: number;
  theoretical_cost: string | number;
  food_cost_percentage?: string | number | null;
  gross_margin_percentage?: string | number | null;
}

interface OnboardingState {
  session_id: string;
  product_name: string | null;
  category_name: string | null;
  station: string;
  price_cents: number | null;
  ingredients: OnboardingIngredient[];
  missing_fields: string[];
  next_question: string;
  is_ready_for_review: boolean;
  summary: OnboardingSummary | null;
  conversation_history: Array<{ role: string; content: string }>;
}

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

const QUICK_SUGGESTIONS = [
  'Hamburguesa con queso cheddar, 200g carne sirloin y tocino',
  'Pizza margarita con salsa marinara y 150g mozzarella',
  'Orden de 3 tacos de arrachera con cebolla y cilantro',
  'Agua fresca de fresa con limón 500ml',
];

export const ProductOnboardingAiModal: React.FC<Props> = ({ isOpen, onClose }) => {
  const queryClient = useQueryClient();
  const [inputText, setInputText] = useState('');
  const [state, setState] = useState<OnboardingState | null>(null);
  const [errorMsg, setErrorMsg] = useState('');
  const [successMsg, setSuccessMsg] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const idempotencyKey = useRef(`onboard-${crypto.randomUUID()}`);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [state?.conversation_history]);

  useEffect(() => {
    if (isOpen) {
      setState(null);
      setInputText('');
      setErrorMsg('');
      setSuccessMsg('');
      idempotencyKey.current = `onboard-${crypto.randomUUID()}`;
    }
  }, [isOpen]);

  const sendMutation = useMutation({
    mutationFn: (messageToSend: string) =>
      fetchApi<OnboardingState>('/catalog/onboarding-ai/message', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: state?.session_id,
          message: messageToSend,
          state: state || undefined,
        }),
      }),
    onSuccess: (updatedState) => {
      setState(updatedState);
      setInputText('');
      setErrorMsg('');
    },
    onError: (err: any) => {
      setErrorMsg(err?.message || 'Error al comunicarse con el asistente culinario.');
    },
  });

  const confirmMutation = useMutation({
    mutationFn: () => {
      if (!state) throw new Error('No hay sesión activa.');
      return fetchApi('/catalog/onboarding-ai/confirm', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Idempotency-Key': idempotencyKey.current,
        },
        body: JSON.stringify({
          session_id: state.session_id,
          state,
        }),
      });
    },
    onSuccess: () => {
      setSuccessMsg('¡Producto y receta creados exitosamente en el catálogo!');
      queryClient.invalidateQueries({ queryKey: ['products'] });
      queryClient.invalidateQueries({ queryKey: ['recipes'] });
      queryClient.invalidateQueries({ queryKey: ['recipes-workspace'] });
      setTimeout(() => {
        onClose();
      }, 1200);
    },
    onError: (err: any) => {
      setErrorMsg(err?.message || 'No fue posible confirmar el registro del producto.');
    },
  });

  const handleSend = (text?: string) => {
    const msg = (text || inputText).trim();
    if (!msg) return;
    sendMutation.mutate(msg);
  };

  const handleReset = () => {
    setState(null);
    setInputText('');
    setErrorMsg('');
    setSuccessMsg('');
    idempotencyKey.current = `onboard-${crypto.randomUUID()}`;
  };

  if (!isOpen) return null;

  const foodCostVal = state?.summary?.food_cost_percentage ? Number(state.summary.food_cost_percentage) : null;
  const foodCostBadgeVariant = foodCostVal === null ? 'default' : foodCostVal <= 35 ? 'success' : foodCostVal <= 50 ? 'warning' : 'default';

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Asistente Culinario IA: Alta Inversa de Producto y Receta"
      size="xl"
      maxWidth="1100px"
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {errorMsg && (
          <div role="alert" style={{ padding: 12, borderRadius: 8, background: 'rgba(239, 68, 68, 0.1)', color: 'var(--color-red)', fontWeight: 500 }}>
            ⚠️ {errorMsg}
          </div>
        )}

        {successMsg && (
          <div role="status" style={{ padding: 14, borderRadius: 8, background: 'rgba(34, 197, 94, 0.15)', color: 'var(--color-green)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8 }}>
            <CheckCircle2 size={20} />
            {successMsg}
          </div>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: 20, minHeight: 460 }}>
          {/* Left Column: Chat / Interview */}
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              background: 'var(--color-surface, #f8fafc)',
              borderRadius: 12,
              border: '1px solid var(--color-border, #e2e8f0)',
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                padding: '12px 16px',
                background: '#fff',
                borderBottom: '1px solid var(--color-border, #e2e8f0)',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{ padding: 6, borderRadius: 6, background: '#eff6ff', color: '#2563eb' }}>
                  <ChefHat size={18} />
                </div>
                <div>
                  <h4 style={{ margin: 0, fontSize: '0.9375rem', fontWeight: 600 }}>Entrevista Culinaria</h4>
                  <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted, #64748b)' }}>
                    Responde en lenguaje natural
                  </span>
                </div>
              </div>
              {state && (
                <Button variant="secondary" size="sm" onClick={handleReset} title="Reiniciar entrevista">
                  <RotateCcw size={14} style={{ marginRight: 4 }} /> Reiniciar
                </Button>
              )}
            </div>

            {/* Conversation Stream */}
            <div style={{ flex: 1, padding: 16, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 12, maxHeight: 380 }}>
              {!state && (
                <div style={{ textAlign: 'center', padding: '24px 12px' }}>
                  <div
                    style={{
                      width: 48,
                      height: 48,
                      borderRadius: '50%',
                      background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                      color: '#fff',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      margin: '0 auto 12px',
                    }}
                  >
                    <Sparkles size={24} />
                  </div>
                  <h4 style={{ margin: '0 0 6px', fontWeight: 600 }}>¿Qué platillo vas a registrar?</h4>
                  <p style={{ margin: 0, fontSize: '0.875rem', color: 'var(--color-text-muted, #64748b)' }}>
                    Dime el nombre del producto, qué ingredientes lleva y su precio sugerido. Te guiaré paso a paso.
                  </p>

                  <div style={{ marginTop: 20, display: 'flex', flexDirection: 'column', gap: 8 }}>
                    <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--color-text-muted, #64748b)', textAlign: 'left' }}>
                      Sugerencias de inicio:
                    </span>
                    {QUICK_SUGGESTIONS.map((sug, idx) => (
                      <button
                        key={idx}
                        onClick={() => handleSend(`Quiero dar de alta un ${sug}`)}
                        style={{
                          textAlign: 'left',
                          padding: '8px 12px',
                          borderRadius: 8,
                          border: '1px solid #cbd5e1',
                          background: '#fff',
                          fontSize: '0.8125rem',
                          cursor: 'pointer',
                          color: '#334155',
                          transition: 'all 0.15s',
                        }}
                      >
                        👉 {sug}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {state?.conversation_history.map((msg, idx) => (
                <div
                  key={idx}
                  style={{
                    alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                    maxWidth: '85%',
                    padding: '10px 14px',
                    borderRadius: 12,
                    fontSize: '0.875rem',
                    lineHeight: 1.45,
                    whiteSpace: 'pre-wrap',
                    background: msg.role === 'user' ? '#2563eb' : '#fff',
                    color: msg.role === 'user' ? '#fff' : '#1e293b',
                    border: msg.role === 'user' ? 'none' : '1px solid var(--color-border, #e2e8f0)',
                    boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
                  }}
                >
                  {msg.content}
                </div>
              ))}

              {sendMutation.isPending && (
                <div
                  style={{
                    alignSelf: 'flex-start',
                    padding: '8px 12px',
                    borderRadius: 8,
                    background: '#fff',
                    border: '1px solid #e2e8f0',
                    fontSize: '0.8125rem',
                    color: '#64748b',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                  }}
                >
                  <Sparkles size={14} className="animate-spin" /> Analizando receta y calculando mermas...
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* Input Bar */}
            <div
              style={{
                padding: 12,
                background: '#fff',
                borderTop: '1px solid var(--color-border, #e2e8f0)',
                display: 'flex',
                gap: 8,
              }}
            >
              <input
                type="text"
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                  }
                }}
                placeholder={state ? 'Escribe tu respuesta...' : 'Ej. Hamburguesa Doble con 2 carnes de 150g...'}
                disabled={sendMutation.isPending || confirmMutation.isPending}
                style={{
                  flex: 1,
                  padding: '9px 12px',
                  borderRadius: 8,
                  border: '1px solid #cbd5e1',
                  fontSize: '0.875rem',
                  outline: 'none',
                }}
              />
              <Button
                variant="primary"
                onClick={() => handleSend()}
                disabled={!inputText.trim() || sendMutation.isPending || confirmMutation.isPending}
              >
                <Send size={16} />
              </Button>
            </div>
          </div>

          {/* Right Column: Live Technical Sheet & Financials */}
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              background: '#fff',
              borderRadius: 12,
              border: '1px solid var(--color-border, #e2e8f0)',
              padding: 16,
              overflowY: 'auto',
              maxHeight: 460,
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <h4 style={{ margin: 0, fontSize: '0.9375rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
                <Utensils size={18} style={{ color: '#16a34a' }} />
                Ficha Técnica en Vivo
              </h4>
              {state?.is_ready_for_review && (
                <Badge variant="success">Lista para crear</Badge>
              )}
            </div>

            {/* Product Meta Card */}
            <div
              style={{
                background: '#f8fafc',
                border: '1px solid #e2e8f0',
                borderRadius: 8,
                padding: '10px 14px',
                marginBottom: 16,
                display: 'grid',
                gridTemplateColumns: 'repeat(2, 1fr)',
                gap: 8,
                fontSize: '0.8125rem',
              }}
            >
              <div>
                <span style={{ color: '#64748b', display: 'block', fontSize: '0.75rem' }}>Platillo</span>
                <strong>{state?.product_name || 'Pendiente de definir'}</strong>
              </div>
              <div>
                <span style={{ color: '#64748b', display: 'block', fontSize: '0.75rem' }}>Categoría</span>
                <span style={{ fontWeight: 500 }}>{state?.category_name || 'Automática'}</span>
              </div>
              <div>
                <span style={{ color: '#64748b', display: 'block', fontSize: '0.75rem' }}>Estación KDS</span>
                <span style={{ fontWeight: 500 }}>{state?.station || 'Cocina'}</span>
              </div>
              <div>
                <span style={{ color: '#64748b', display: 'block', fontSize: '0.75rem' }}>Precio de Venta</span>
                <strong style={{ color: '#0f172a' }}>
                  {state?.price_cents ? `$${(state.price_cents / 100).toFixed(2)} MXN` : 'Sin precio'}
                </strong>
              </div>
            </div>

            {/* Ingredients Table */}
            <div style={{ flex: 1, marginBottom: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: '#334155' }}>
                  Ingredientes ({state?.ingredients.length || 0})
                </span>
                <span style={{ fontSize: '0.75rem', color: '#64748b' }}>Cálculo bruto con merma</span>
              </div>

              {!state?.ingredients || state.ingredients.length === 0 ? (
                <div style={{ padding: 24, textAlign: 'center', border: '1px dashed #e2e8f0', borderRadius: 8, color: '#94a3b8', fontSize: '0.8125rem' }}>
                  Los ingredientes se desglosarán aquí conforme respondas al asistente.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {state.ingredients.map((ing, idx) => (
                    <div
                      key={idx}
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        padding: '8px 10px',
                        background: '#f8fafc',
                        border: '1px solid #e2e8f0',
                        borderRadius: 6,
                        fontSize: '0.8125rem',
                      }}
                    >
                      <div>
                        <div style={{ fontWeight: 600, color: '#1e293b' }}>
                          {ing.normalized_name}
                          {ing.is_subrecipe && (
                            <span style={{ marginLeft: 6, fontSize: '0.6875rem', padding: '1px 5px', borderRadius: 4, background: '#fef3c7', color: '#b45309' }}>
                              Subreceta
                            </span>
                          )}
                          {ing.is_new_supply && (
                            <span style={{ marginLeft: 6, fontSize: '0.6875rem', padding: '1px 5px', borderRadius: 4, background: '#eff6ff', color: '#2563eb' }}>
                              Nuevo insumo
                            </span>
                          )}
                        </div>
                        <span style={{ fontSize: '0.75rem', color: '#64748b' }}>
                          Neto: {ing.net_quantity} {ing.unit} | Merma: {Number(ing.waste_rate) * 100}% (Bruto: {ing.gross_quantity})
                        </span>
                      </div>
                      <div style={{ textAlign: 'right', fontWeight: 600, color: '#047857' }}>
                        ${ing.line_cost}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Financial Summary */}
            {state?.summary && (
              <div
                style={{
                  borderTop: '2px solid #e2e8f0',
                  paddingTop: 12,
                  marginTop: 'auto',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 8,
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.875rem' }}>
                  <span style={{ color: '#64748b' }}>Costo Teórico Total:</span>
                  <strong>${state.summary.theoretical_cost} MXN</strong>
                </div>

                {state.summary.food_cost_percentage && (
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.875rem' }}>
                    <span style={{ color: '#64748b' }}>Food Cost (%):</span>
                    <Badge variant={foodCostBadgeVariant}>
                      {state.summary.food_cost_percentage}%
                    </Badge>
                  </div>
                )}

                {state.summary.gross_margin_percentage && (
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.875rem' }}>
                    <span style={{ color: '#64748b' }}>Margen de Utilidad:</span>
                    <strong style={{ color: '#16a34a' }}>{state.summary.gross_margin_percentage}%</strong>
                  </div>
                )}

                {state.is_ready_for_review && (
                  <Button
                    variant="primary"
                    onClick={() => confirmMutation.mutate()}
                    disabled={confirmMutation.isPending}
                    style={{
                      marginTop: 8,
                      width: '100%',
                      padding: '11px',
                      background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                      borderColor: '#059669',
                      fontWeight: 600,
                    }}
                  >
                    <Sparkles size={16} style={{ marginRight: 6 }} />
                    {confirmMutation.isPending ? 'Guardando en Catálogo...' : 'Aprobar y Registrar en Catálogo'}
                  </Button>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </Modal>
  );
};
