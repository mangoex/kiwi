import React from 'react';
import { CheckCircle2, MessageCircle, X, ShoppingBag } from 'lucide-react';
import { CreatedOrderResult } from '../types';
import { formatMoney } from '../api';

interface OrderSuccessModalProps {
  orderResult: CreatedOrderResult;
  onClose: () => void;
  onNewOrder: () => void;
}

export const OrderSuccessModal: React.FC<OrderSuccessModalProps> = ({
  orderResult,
  onClose,
  onNewOrder,
}) => {
  return (
    <div className="modal-overlay">
      <div className="modal-sheet" style={{ maxHeight: '90vh', overflowY: 'auto' }}>
        <div style={{ display: 'flex', justifyContent: 'flex-end', padding: '16px 20px 0' }}>
          <button
            type="button"
            className="modal-close-btn"
            style={{ position: 'static', background: '#f1f5f9', color: '#0f172a' }}
            onClick={onClose}
            aria-label="Cerrar"
          >
            <X size={18} />
          </button>
        </div>

        <div className="success-modal">
          <div className="success-icon-wrapper">
            <CheckCircle2 size={42} />
          </div>

          <h2 style={{ fontSize: '22px', fontWeight: 800, color: '#0f172a' }}>
            ¡Pedido Registrado con Éxito!
          </h2>

          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '4px' }}>
            <span style={{ fontSize: '13px', color: '#64748b', fontWeight: 600 }}>Folio de Orden</span>
            <span className="folio-chip">#{orderResult.folio}</span>
          </div>

          <p style={{ fontSize: '14px', color: '#64748b', lineHeight: 1.5, maxWidth: '320px' }}>
            Tu pedido ha quedado registrado en el sistema. Para una confirmación inmediata, toca el botón de abajo para enviar el resumen a la sucursal por WhatsApp.
          </p>

          <a
            href={orderResult.whatsapp_url}
            target="_blank"
            rel="noopener noreferrer"
            className="btn-whatsapp-action"
          >
            <MessageCircle size={22} />
            <span>Enviar Pedido por WhatsApp</span>
          </a>

          <div style={{ width: '100%', background: '#f8fafc', padding: '16px', borderRadius: '16px', border: '1px solid #e2e8f0', textAlign: 'left', display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #e2e8f0', paddingBottom: '8px' }}>
              <strong style={{ fontSize: '13px' }}>Cliente:</strong>
              <span style={{ fontSize: '13px' }}>{orderResult.customer_info.name}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #e2e8f0', paddingBottom: '8px' }}>
              <strong style={{ fontSize: '13px' }}>Modalidad:</strong>
              <span style={{ fontSize: '13px' }}>
                {orderResult.customer_info.order_type === 'takeaway' ? '🏃 Recoger en Tienda' : '🛵 Envío a Domicilio'}
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #e2e8f0', paddingBottom: '8px' }}>
              <strong style={{ fontSize: '13px' }}>Productos ({orderResult.items.length}):</strong>
              <span style={{ fontSize: '13px', fontWeight: 700, color: '#10b981' }}>{formatMoney(orderResult.total_cents)}</span>
            </div>
          </div>

          <button
            type="button"
            onClick={onNewOrder}
            style={{
              width: '100%',
              padding: '12px',
              borderRadius: '9999px',
              border: '1px solid #e2e8f0',
              background: 'white',
              color: '#0f172a',
              fontWeight: 700,
              fontSize: '14px',
              fontFamily: 'inherit',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
            }}
          >
            <ShoppingBag size={16} />
            <span>Hacer Otro Pedido</span>
          </button>
        </div>
      </div>
    </div>
  );
};
