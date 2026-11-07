import React, { useState } from 'react';
import { Modal, Button } from '@restaurantos/ui';
import { Copy, Printer, Check, ChefHat, Receipt } from 'lucide-react';
import {
  formatTicketText,
  formatKitchenText,
  type TicketPrintData,
  type KitchenPrintData,
} from './receiptFormatter';
import {
  dispatchPosPrintJob,
  loadPrinterConfig,
  printThermalIframe,
} from './printerService';
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
  const [printStatus, setPrintStatus] = useState<string>('');

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

  const handlePrintCopy = async (copies: 'ticket' | 'kitchen' | 'both') => {
    if (printingDirect) return;
    setPrintingDirect(true);
    setPrintStatus('');
    try {
      if (onPrintDirect && copies !== 'both') {
        await onPrintDirect(copies);
        setPrintStatus('✓ Enviado a impresora local.');
        return;
      }
      const result = await dispatchPosPrintJob({
        ticketData,
        kitchenData: activeKitchenData,
        copies,
      });
      setPrintStatus(result.ok ? `✓ ${result.message}` : result.message);
    } catch {
      const config = loadPrinterConfig();
      const pages =
        copies === 'both'
          ? [formatTicketText(ticketData, 42), formatKitchenText(activeKitchenData, 42)]
          : [currentText];
      printThermalIframe(pages, config.paperWidthMm);
      setPrintStatus('✓ Enviado a impresión térmica (80mm).');
    } finally {
      setPrintingDirect(false);
    }
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

        {printStatus && (
          <p
            role="status"
            style={{
              margin: 0,
              width: '100%',
              fontSize: '0.85rem',
              fontWeight: 600,
              color: '#059669',
              textAlign: 'right',
            }}
          >
            {printStatus}
          </p>
        )}

        {/* Acciones */}
        <div className="thermal-receipt-actions" style={{ flexWrap: 'wrap' }}>
          <Button
            type="button"
            variant="secondary"
            onClick={() => void handleCopy()}
            title="Copiar texto monoespaciado al portapapeles"
          >
            {copied ? <Check size={16} /> : <Copy size={16} />}
            {copied ? 'Copiado' : 'Copiar texto'}
          </Button>

          <Button
            type="button"
            variant="secondary"
            disabled={printingDirect}
            onClick={() => void handlePrintCopy(activeTab)}
            title="Imprimir únicamente la vista seleccionada en 80mm"
          >
            <Printer size={16} />
            Imprimir ({activeTab === 'ticket' ? 'Ticket' : 'Cocina'})
          </Button>

          <Button
            type="button"
            variant="primary"
            disabled={printingDirect}
            onClick={() => void handlePrintCopy('both')}
            title="Imprimir Ticket de Venta y Comanda de Cocina automáticamente"
          >
            <Printer size={16} />
            {printingDirect ? 'Imprimiendo…' : 'Imprimir Ticket + Comanda'}
          </Button>

          <Button type="button" variant="secondary" onClick={onClose}>
            Cerrar
          </Button>
        </div>
      </div>
    </Modal>
  );
}
