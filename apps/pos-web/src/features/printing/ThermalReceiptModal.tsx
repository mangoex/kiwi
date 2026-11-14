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
  resolveKitchenJobsForOrder,
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
  const [selectedAreaCode, setSelectedAreaCode] = useState<string>('all');
  const [copied, setCopied] = useState(false);
  const [printingDirect, setPrintingDirect] = useState(false);
  const [printStatus, setPrintStatus] = useState<string>('');

  if (!isOpen) return null;

  const printerConfig = loadPrinterConfig();

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

  const kitchenJobs = resolveKitchenJobsForOrder(
    ticketData,
    activeKitchenData,
    printerConfig
  );

  const visibleKitchenJobs =
    selectedAreaCode === 'all'
      ? kitchenJobs
      : kitchenJobs.filter((j) => j.areaCode === selectedAreaCode);

  const effectiveKitchenJobs =
    visibleKitchenJobs.length > 0 ? visibleKitchenJobs : kitchenJobs;

  const currentText =
    activeTab === 'ticket'
      ? formatTicketText(ticketData, 42)
      : effectiveKitchenJobs
          .map((job) => formatKitchenText(job, 42))
          .join('\n\n' + '· '.repeat(21).trim() + '\n[ CORTE DE COMANDA POR AREA ]\n' + '· '.repeat(21).trim() + '\n\n');

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
      const targetAreaCode =
        copies === 'kitchen' && selectedAreaCode !== 'all' ? selectedAreaCode : null;
      const result = await dispatchPosPrintJob({
        ticketData,
        kitchenData: activeKitchenData,
        copies,
        targetAreaCode,
      });
      setPrintStatus(result.ok ? `✓ ${result.message}` : result.message);
    } catch {
      const config = loadPrinterConfig();
      const pages =
        copies === 'both'
          ? [
              formatTicketText(ticketData, 42),
              ...kitchenJobs.map((j) => formatKitchenText(j, 42)),
            ]
          : copies === 'ticket'
            ? [formatTicketText(ticketData, 42)]
            : effectiveKitchenJobs.map((j) => formatKitchenText(j, 42));
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
            Ticket de Venta ({printerConfig.ticketPrinterName || 'caja'})
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'kitchen'}
            className={`thermal-tab-btn ${activeTab === 'kitchen' ? 'active' : ''}`}
            onClick={() => setActiveTab('kitchen')}
          >
            <ChefHat size={16} style={{ display: 'inline', marginRight: 6, verticalAlign: -2 }} />
            Comanda de Cocina ({kitchenJobs.length} {kitchenJobs.length === 1 ? 'área' : 'áreas'})
          </button>
        </div>

        {/* Sub-selector de áreas de impresión cuando hay comandas de cocina */}
        {activeTab === 'kitchen' && kitchenJobs.length > 0 && (
          <div
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: '6px',
              width: '100%',
              padding: '4px 0',
            }}
          >
            {kitchenJobs.length > 1 && (
              <button
                type="button"
                onClick={() => setSelectedAreaCode('all')}
                style={{
                  padding: '4px 10px',
                  fontSize: '0.76rem',
                  fontWeight: 700,
                  borderRadius: 999,
                  border: '1px solid #cbd5e1',
                  cursor: 'pointer',
                  background: selectedAreaCode === 'all' ? '#0f172a' : '#f1f5f9',
                  color: selectedAreaCode === 'all' ? '#ffffff' : '#334155',
                }}
              >
                Todas las áreas ({kitchenJobs.length})
              </button>
            )}
            {kitchenJobs.map((job) => {
              const code = job.areaCode || 'kitchen';
              const targetPrinter =
                printerConfig.areaPrinters?.[code]?.printerName ||
                printerConfig.areaPrinters?.[code]?.host ||
                printerConfig.kitchenPrinterName ||
                'barra';
              const isSelected =
                kitchenJobs.length === 1 || selectedAreaCode === code;
              return (
                <button
                  key={code}
                  type="button"
                  onClick={() => setSelectedAreaCode(code)}
                  style={{
                    padding: '4px 10px',
                    fontSize: '0.76rem',
                    fontWeight: 700,
                    borderRadius: 999,
                    border: '1px solid #cbd5e1',
                    cursor: 'pointer',
                    background: isSelected ? '#059669' : '#f8fafc',
                    color: isSelected ? '#ffffff' : '#334155',
                  }}
                >
                  {job.areaName || code.toUpperCase()} ({job.lines.length}) → {targetPrinter}
                </button>
              );
            })}
          </div>
        )}

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
            Imprimir (
            {activeTab === 'ticket'
              ? 'Ticket'
              : selectedAreaCode !== 'all'
                ? `Área ${selectedAreaCode.toUpperCase()}`
                : 'Cocina'}
            )
          </Button>

          <Button
            type="button"
            variant="primary"
            disabled={printingDirect}
            onClick={() => void handlePrintCopy('both')}
            title="Imprimir Ticket de Venta en Caja y Comandas por Área en sus impresoras"
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
