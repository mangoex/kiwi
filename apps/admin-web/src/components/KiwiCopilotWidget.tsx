import React, { useState } from 'react';
import { Bot, Mic, Send, X, Sparkles, Check, CornerDownLeft, AlertCircle, RefreshCw } from 'lucide-react';

export interface CopilotMessage {
  id: string;
  sender: 'ai' | 'user' | 'system';
  text: string;
  timestamp?: string;
  actionDraft?: {
    title: string;
    description: string;
    details: Array<{ label: string; value: string }>;
    applied?: boolean;
    onConfirm?: () => void;
  };
}

export interface KiwiCopilotWidgetProps {
  initialPromptSuggestion?: string;
  contextModule?: string;
  onApplyAction?: (actionData: any) => Promise<void> | void;
}

export const KiwiCopilotWidget: React.FC<KiwiCopilotWidgetProps> = ({
  initialPromptSuggestion = 'Dime cómo mejorar el margen de este producto...',
  contextModule = 'Catálogo',
  onApplyAction,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [inputText, setInputText] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);

  const [messages, setMessages] = useState<CopilotMessage[]>([
    {
      id: '1',
      sender: 'ai',
      text: `¡Hola! Soy tu asistente Kiwi IA en el módulo de ${contextModule}. Puedes dictarme o escribirme cualquier ajuste, alta de insumo o cálculo de margen.`,
    },
    {
      id: '2',
      sender: 'ai',
      text: 'Sugerencia: "Dar de alta el insumo Miel de Abeja en caja de 5kg a $120."',
    },
  ]);

  const handleSend = (textToSend?: string) => {
    const prompt = (textToSend || inputText).trim();
    if (!prompt) return;

    const userMsg: CopilotMessage = {
      id: Date.now().toString(),
      sender: 'user',
      text: prompt,
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputText('');
    setIsProcessing(true);

    // Simulate smart AI response with Human-in-the-loop action draft
    setTimeout(() => {
      setIsProcessing(false);
      const aiResponse: CopilotMessage = {
        id: (Date.now() + 1).toString(),
        sender: 'ai',
        text: `He preparado la propuesta solicitada para: "${prompt}". Revisa los datos y confirma para aplicar los cambios de manera segura.`,
        actionDraft: {
          title: 'Propuesta de Ajuste (Human-in-the-loop)',
          description: 'Esta acción requiere confirmación humana antes de registrarse en la base de datos central.',
          details: [
            { label: 'Operación', value: 'Registro de Insumo / Recalculo' },
            { label: 'Insumo Detectado', value: prompt.includes('Miel') ? 'Miel de Abeja 5kg' : 'Ajuste de Margen' },
            { label: 'Costo Unitario', value: '$120.00 MXN' },
            { label: 'Impacto Teórico', value: 'Food Cost +0.4%' },
          ],
          applied: false,
        },
      };
      setMessages((prev) => [...prev, aiResponse]);
    }, 700);
  };

  const handleConfirmAction = async (msgId: string) => {
    setMessages((prev) =>
      prev.map((msg) =>
        msg.id === msgId && msg.actionDraft
          ? {
              ...msg,
              actionDraft: { ...msg.actionDraft, applied: true },
            }
          : msg
      )
    );

    if (onApplyAction) {
      await onApplyAction({});
    }
  };

  const toggleRecording = () => {
    if (!isRecording) {
      setIsRecording(true);
      // Simulate voice capture
      setTimeout(() => {
        setIsRecording(false);
        setInputText('Miel de Abeja, caja de 5kg, $120');
      }, 2000);
    } else {
      setIsRecording(false);
    }
  };

  return (
    <div className="fixed bottom-4 right-4 z-40 flex flex-col items-end">
      {/* Floating Prompt Pill when collapsed */}
      {!isOpen && (
        <div
          onClick={() => setIsOpen(true)}
          className="mb-2 bg-white/95 backdrop-blur-xs border border-violet-200 shadow-md hover:shadow-lg rounded-full py-2 px-4 flex items-center gap-3 cursor-pointer transition-all hover:scale-102 group max-w-sm"
        >
          <div className="w-6 h-6 rounded-full bg-violet-600 flex items-center justify-center text-white shrink-0">
            <Sparkles size={12} />
          </div>
          <span className="text-xs text-gray-700 truncate font-medium">
            {initialPromptSuggestion}
          </span>
          <span className="text-violet-600 text-xs font-bold shrink-0">›</span>
        </div>
      )}

      {/* Main Trigger Button */}
      {!isOpen && (
        <button
          type="button"
          onClick={() => setIsOpen(true)}
          className="bg-violet-700 hover:bg-violet-800 text-white p-3.5 rounded-full shadow-xl flex items-center justify-center transition-all hover:scale-105 active:scale-95"
          aria-label="Abrir asistente Kiwi IA"
        >
          <Bot size={22} />
        </button>
      )}

      {/* Expanded Copilot Panel (Morado Copilot Panel) */}
      {isOpen && (
        <div className="w-[380px] h-[520px] bg-white rounded-2xl shadow-2xl border border-violet-100 flex flex-col overflow-hidden animate-in fade-in slide-in-from-bottom-4 duration-200">
          {/* Header */}
          <div className="bg-violet-700 text-white px-4 py-3 flex items-center justify-between shadow-xs shrink-0">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-lg bg-violet-600/80 flex items-center justify-center border border-violet-400/40">
                <Bot size={16} />
              </div>
              <div>
                <h3 className="text-xs font-bold tracking-wide">Kiwi IA Copilot</h3>
                <span className="text-[10px] text-violet-200 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 inline-block animate-pulse" />
                  Multi-turno activo
                </span>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setIsOpen(false)}
              className="text-violet-200 hover:text-white p-1 rounded-md transition-colors"
              aria-label="Cerrar Copilot"
            >
              <X size={16} />
            </button>
          </div>

          {/* Conversation history */}
          <div className="flex-1 overflow-y-auto p-3.5 space-y-3 bg-gray-50/50">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex flex-col ${
                  msg.sender === 'user' ? 'items-end' : 'items-start'
                }`}
              >
                <div
                  className={`text-xs px-3.5 py-2.5 rounded-xl max-w-[90%] leading-relaxed ${
                    msg.sender === 'user'
                      ? 'bg-violet-600 text-white rounded-br-xs'
                      : 'bg-white text-gray-800 border border-gray-200/80 shadow-2xs rounded-bl-xs'
                  }`}
                >
                  {msg.text}
                </div>

                {/* Human-in-the-loop action draft card */}
                {msg.actionDraft && (
                  <div className="mt-2 w-[92%] bg-violet-50/80 border border-violet-200 rounded-xl p-3 shadow-xs">
                    <div className="flex items-center gap-1.5 text-violet-900 font-bold text-xs mb-1">
                      <Sparkles size={13} className="text-violet-600" />
                      <span>{msg.actionDraft.title}</span>
                    </div>
                    <p className="text-[11px] text-violet-700/90 mb-2 leading-tight">
                      {msg.actionDraft.description}
                    </p>

                    <div className="space-y-1 bg-white p-2 rounded-lg border border-violet-100 text-[11px] mb-2.5">
                      {msg.actionDraft.details.map((d, i) => (
                        <div key={i} className="flex justify-between items-center text-gray-700">
                          <span className="text-gray-400">{d.label}:</span>
                          <span className="font-semibold">{d.value}</span>
                        </div>
                      ))}
                    </div>

                    {msg.actionDraft.applied ? (
                      <div className="flex items-center gap-1.5 text-emerald-700 bg-emerald-50 px-2 py-1.5 rounded-md text-xs font-semibold">
                        <Check size={14} /> Cambio confirmado y aplicado con éxito
                      </div>
                    ) : (
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => handleConfirmAction(msg.id)}
                          className="flex-1 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold py-1.5 px-3 rounded-lg shadow-2xs flex items-center justify-center gap-1.5 transition-colors cursor-pointer"
                        >
                          <Check size={13} /> Confirmar y Aplicar
                        </button>
                        <button
                          type="button"
                          onClick={() => handleSend('Ajustar la propuesta...')}
                          className="bg-white hover:bg-gray-100 text-gray-700 border border-gray-200 text-xs font-medium py-1.5 px-2.5 rounded-lg transition-colors cursor-pointer"
                        >
                          Ajustar
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}

            {isProcessing && (
              <div className="flex items-center gap-2 text-xs text-gray-400 italic">
                <RefreshCw size={12} className="animate-spin text-violet-600" />
                Kiwi IA está pensando...
              </div>
            )}
          </div>

          {/* Quick chips */}
          <div className="px-3 py-1.5 bg-gray-100/70 border-t border-gray-200/60 flex items-center gap-1.5 overflow-x-auto text-[11px] shrink-0">
            <span className="text-gray-400 text-[10px] uppercase font-bold shrink-0">Quick:</span>
            <button
              type="button"
              onClick={() => handleSend('Mejorar margen bruto')}
              className="bg-white hover:bg-violet-50 text-gray-700 hover:text-violet-700 px-2 py-0.5 rounded-full border border-gray-200 whitespace-nowrap transition-colors"
            >
              Margen %
            </button>
            <button
              type="button"
              onClick={() => handleSend('Auditar mermas de insumos')}
              className="bg-white hover:bg-violet-50 text-gray-700 hover:text-violet-700 px-2 py-0.5 rounded-full border border-gray-200 whitespace-nowrap transition-colors"
            >
              Mermas
            </button>
            <button
              type="button"
              onClick={() => handleSend('Generar Menú QR')}
              className="bg-white hover:bg-violet-50 text-gray-700 hover:text-violet-700 px-2 py-0.5 rounded-full border border-gray-200 whitespace-nowrap transition-colors"
            >
              Menú QR
            </button>
          </div>

          {/* Input field with voice & send */}
          <div className="p-2.5 bg-white border-t border-gray-200 flex items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={toggleRecording}
              className={`p-2 rounded-lg transition-colors ${
                isRecording
                  ? 'bg-rose-500 text-white animate-pulse'
                  : 'text-gray-400 hover:text-violet-700 hover:bg-violet-50'
              }`}
              title={isRecording ? 'Grabando... (clic para parar)' : 'Dictar por voz'}
              aria-label="Dictado por voz"
            >
              <Mic size={16} />
            </button>

            <input
              type="text"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              placeholder="Escribe o dicta a Kiwi IA..."
              className="flex-1 text-xs bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-gray-900 focus:outline-hidden focus:ring-1 focus:ring-violet-500 focus:bg-white transition-all"
            />

            <button
              type="button"
              onClick={() => handleSend()}
              disabled={!inputText.trim()}
              className="bg-violet-700 hover:bg-violet-800 disabled:opacity-40 text-white p-2 rounded-lg transition-colors cursor-pointer disabled:cursor-not-allowed"
              aria-label="Enviar mensaje"
            >
              <Send size={15} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default KiwiCopilotWidget;
