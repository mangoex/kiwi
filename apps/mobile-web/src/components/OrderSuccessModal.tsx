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
  const pendingReview = orderResult.kind === 'public_order_intent';
  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        background: 'rgba(15, 23, 42, 0.7)',
        backdropFilter: 'blur(8px)',
        WebkitBackdropFilter: 'blur(8px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '20px',
        animation: 'fadeIn 0.25s ease-out',
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: '#ffffff',
          borderRadius: '28px',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.35)',
          maxWidth: '430px',
          width: '100%',
          maxHeight: '90vh',
          overflowY: 'auto',
          position: 'relative',
          padding: '32px 24px 28px',
          boxSizing: 'border-box',
          animation: 'popIn 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Top-Right Close Button */}
        <button
          type="button"
          onClick={onClose}
          aria-label="Cerrar"
          style={{
            position: 'absolute',
            top: '18px',
            right: '18px',
            width: '38px',
            height: '38px',
            borderRadius: '50%',
            background: '#f1f5f9',
            border: 'none',
            color: '#475569',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            transition: 'all 0.2s ease',
            zIndex: 10,
          }}
        >
          <X size={20} />
        </button>

        <div className="success-modal" style={{ padding: 0 }}>
          <div className="success-icon-wrapper" style={{ marginTop: '8px' }}>
            <CheckCircle2 size={46} />
          </div>

          <h2 style={{ fontSize: '22px', fontWeight: 800, color: '#0f172a', margin: '8px 0 4px' }}>
            {pendingReview ? '¡Solicitud recibida!' : '¡Pedido Registrado y Enviado!'}
          </h2>

          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '4px', margin: '4px 0 8px' }}>
            <span style={{ fontSize: '13px', color: '#64748b', fontWeight: 600 }}>{pendingReview ? 'Referencia' : 'Folio de Orden'}</span>
            <span className="folio-chip">#{pendingReview ? orderResult.public_reference : orderResult.folio}</span>
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
              marginBottom: '10px',
            }}
          >
            {pendingReview ? <Clock size={16} /> : <ChefHat size={16} />}
            <span>{pendingReview ? 'Pendiente de revisión en sucursal' : 'Enviado al Punto de Venta y Cocina'}</span>
          </div>

          <p style={{ fontSize: '14px', color: '#64748b', lineHeight: 1.5, maxWidth: '340px', margin: '0 auto 16px' }}>
            {pendingReview ? 'Tu solicitud ha quedado registrada y será revisada de inmediato en el mostrador del restaurante.' : 'Tu pedido ha quedado registrado en el sistema y enviado a la sucursal. ¡Estamos preparando tu orden!'}
          </p>

          <div style={{ width: '100%', background: '#f8fafc', padding: '16px', borderRadius: '16px', border: '1px solid #e2e8f0', textAlign: 'left', display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '18px', boxSizing: 'border-box' }}>
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
              marginBottom: '10px',
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
              padding: '12px',
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
