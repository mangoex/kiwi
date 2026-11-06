import React, { useState } from 'react';
import { Modal, Button } from '@restaurantos/ui';
import { Copy, Printer, Check, ChefHat, Receipt } from 'lucide-react';
import {
  formatTicketText,
  formatKitchenText,
  type TicketPrintData,
  type KitchenPrintData,
} from './receiptFormatter';
import './receipt.css';

interface ThermalReceiptModalProps {
  isOpen: boolean;
  onClose: () => void;
  ticketData: TicketPrintData;
  kitchenData?: KitchenPrintData | null;
  defaultTab?: 'ticket' | 'kitchen';
  onPrintDirect?: (kind: 'ticket' | 'kitchen') => Promise<void> | void;
}

export function ThermalReceiptModal({
  isOpen,
  onClose,
  ticketData,
  kitchenData,
  defaultTab = 'ticket',
  onPrintDirect,
}: ThermalReceiptModalProps) {
  const [activeTab, setActiveTab] = useState<'ticket' | 'kitchen'>(defaultTab);
  const [copied, setCopied] = useState(false);
  const [printingDirect, setPrintingDirect] = useState(false);

  if (!isOpen) return null;

  // Si no se proporcionó cocina explícitamente, derivarla del ticket
  const activeKitchenData: KitchenPrintData = kitchenData || {
    folio: ticketData.folio,
    orderNumber: ticketData.orderNumber,
    createdAt: ticketData.createdAt,
    serviceTypeLabel: ticketData.serviceTypeLabel,
    customerName: ticketData.customerName,
    customerPhone: ticketData.customerPhone,
    driverName: ticketData.driverName,
    lines: ticketData.lines,
  };

  const currentText =
    activeTab === 'ticket'
      ? formatTicketText(ticketData, 42)
      : formatKitchenText(activeKitchenData, 42);

  const handleBrowserPrint = () => {
    window.print();
  };

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(currentText);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback silencioso si el portapapeles está bloqueado
    }
  };

  const handleDirectEscPos = async () => {
    if (!onPrintDirect || printingDirect) return;
    setPrintingDirect(true);
    try {
      await onPrintDirect(activeTab);
    } finally {
      setPrintingDirect(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`Impresión de Comanda · Folio ${ticketData.folio}`}
    >
      <div className="thermal-receipt-modal-content">
        {/* Selector de tipo de comanda */}
        <div className="thermal-receipt-tabs" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'ticket'}
            className={`thermal-tab-btn ${activeTab === 'ticket' ? 'active' : ''}`}
            onClick={() => setActiveTab('ticket')}
          >
            <Receipt size={16} style={{ display: 'inline', marginRight: 6, verticalAlign: -2 }} />
            Ticket de Venta / Cuenta
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'kitchen'}
            className={`thermal-tab-btn ${activeTab === 'kitchen' ? 'active' : ''}`}
            onClick={() => setActiveTab('kitchen')}
          >
            <ChefHat size={16} style={{ display: 'inline', marginRight: 6, verticalAlign: -2 }} />
            Comanda de Cocina
          </button>
        </div>

        {/* Papel simulado en pantalla y contenedor de impresión */}
        <div className="thermal-paper-scroll">
          <pre id="thermal-receipt-printable" className="thermal-paper" tabIndex={0}>
            {currentText}
          </pre>
        </div>

        {/* Acciones */}
        <div className="thermal-receipt-actions">
          <Button
            type="button"
            variant="secondary"
            onClick={() => void handleCopy()}
            title="Copiar texto monoespaciado al portapapeles"
          >
            {copied ? <Check size={16} /> : <Copy size={16} />}
            {copied ? 'Copiado' : 'Copiar texto'}
          </Button>

          {onPrintDirect && (
            <Button
              type="button"
              variant="secondary"
              disabled={printingDirect}
              onClick={() => void handleDirectEscPos()}
              title="Mandar orden directa a la impresora térmica local (ESC/POS)"
            >
              <Printer size={16} />
              {printingDirect ? 'Enviando…' : 'Impresora local'}
            </Button>
          )}

          <Button
            type="button"
            variant="primary"
            onClick={handleBrowserPrint}
            title="Imprimir ticket térmico en 80mm"
          >
            <Printer size={16} />
            Imprimir ({activeTab === 'ticket' ? 'Ticket' : 'Cocina'})
          </Button>

          <Button type="button" variant="secondary" onClick={onClose}>
            Cerrar
          </Button>
        </div>
      </div>
    </Modal>
  );
}
