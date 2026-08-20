import React from 'react';
import { CheckCircle2, X, ShoppingBag, ArrowLeft, Clock, ChefHat } from 'lucide-react';
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
            <CheckCircle2 size={46} />
          </div>

          <h2 style={{ fontSize: '22px', fontWeight: 800, color: '#0f172a', margin: '4px 0' }}>
            ¡Pedido Registrado y Enviado!
          </h2>

          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '4px' }}>
            <span style={{ fontSize: '13px', color: '#64748b', fontWeight: 600 }}>Folio de Orden</span>
            <span className="folio-chip">#{orderResult.folio}</span>
          </div>

          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              background: '#ecfdf5',
              border: '1px solid #a7f3d0',
              color: '#047857',
              padding: '6px 14px',
              borderRadius: '9999px',
              fontSize: '13px',
              fontWeight: 700,
            }}
          >
            <ChefHat size={16} />
            <span>Enviado al Punto de Venta y Cocina</span>
          </div>

          <p style={{ fontSize: '14px', color: '#64748b', lineHeight: 1.5, maxWidth: '320px' }}>
            Tu pedido ha quedado registrado en el sistema y enviado a la sucursal. ¡Estamos preparando tu orden!
          </p>

          <div style={{ width: '100%', background: '#f8fafc', padding: '16px', borderRadius: '16px', border: '1px solid #e2e8f0', textAlign: 'left', display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #e2e8f0', paddingBottom: '8px' }}>
              <strong style={{ fontSize: '13px', color: '#64748b' }}>Cliente:</strong>
              <span style={{ fontSize: '13px', fontWeight: 700, color: '#0f172a' }}>{orderResult.customer_info.name}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #e2e8f0', paddingBottom: '8px' }}>
              <strong style={{ fontSize: '13px', color: '#64748b' }}>Modalidad:</strong>
              <span style={{ fontSize: '13px', fontWeight: 700, color: '#0f172a' }}>
                {orderResult.customer_info.order_type === 'takeaway' ? '🏃 Recoger en Sucursal' : '🛵 Envío a Domicilio'}
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #e2e8f0', paddingBottom: '8px' }}>
              <strong style={{ fontSize: '13px', color: '#64748b' }}>Total a Pagar:</strong>
              <span style={{ fontSize: '14px', fontWeight: 800, color: '#10b981' }}>{formatMoney(orderResult.total_cents)}</span>
            </div>
          </div>

          <button
            type="button"
            onClick={onNewOrder}
            style={{
              width: '100%',
              padding: '14px',
              borderRadius: '9999px',
              border: 'none',
              background: '#0f172a',
              color: '#ffffff',
              fontWeight: 800,
              fontSize: '15px',
              fontFamily: 'inherit',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              boxShadow: '0 4px 12px rgba(15, 23, 42, 0.15)',
            }}
          >
            <ShoppingBag size={18} />
            <span>Hacer Otro Pedido</span>
          </button>

          <button
            type="button"
            onClick={onClose}
            style={{
              width: '100%',
              padding: '10px',
              borderRadius: '9999px',
              border: '1px solid #e2e8f0',
              background: '#ffffff',
              color: '#64748b',
              fontWeight: 700,
              fontSize: '14px',
              fontFamily: 'inherit',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
            }}
          >
            <ArrowLeft size={16} />
            <span>Volver al Menú</span>
          </button>
        </div>
      </div>
    </div>
  );
};
