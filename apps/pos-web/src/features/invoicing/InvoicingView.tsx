import React, { useState, useEffect, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button, Badge, Modal } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';
import {
  FileText,
  Search,
  CheckSquare,
  Square,
  Download,
  Send,
  QrCode,
  AlertCircle,
  CheckCircle2,
  Calendar,
  Filter,
  Building,
  RefreshCw,
  X,
  ExternalLink,
  ShieldCheck,
} from 'lucide-react';
import { usePosSession } from '../../session';

interface OrderAccount {
  id: string;
  folio: string;
  status: string;
  payment_status?: 'PENDING' | 'CONFIRMED';
  total_cents: number;
  created_at: string;
  customer_label: string | null;
  service_type: string | null;
  register_code: string | null;
}

interface InvoiceRecord {
  id: string;
  folio_number: string;
  uuid_sat?: string;
  rfc_receptor: string;
  nombre_receptor: string;
  total_cents: number;
  currency: string;
  status: string;
  created_at: string;
  pdf_url?: string;
  xml_url?: string;
  verification_url?: string;
}

interface FacturapiConfig {
  is_enabled: boolean;
  environment: string;
  organization_legal_name: string;
  organization_rfc: string;
  series: string;
  enable_self_invoicing: boolean;
  self_invoicing_domain: string;
}

const SAT_TAX_SYSTEMS = [
  { code: '601', label: '601 - General de Ley Personas Morales' },
  { code: '612', label: '612 - Personas Físicas con Actividades Empresariales y Profesionales' },
  { code: '626', label: '626 - Régimen Simplificado de Confianza (RESICO)' },
  { code: '605', label: '605 - Sueldos y Salarios e Ingresos Asimilados a Salarios' },
  { code: '608', label: '608 - Demás ingresos' },
  { code: '616', label: '616 - Sin obligaciones fiscales' },
  { code: '621', label: '621 - Incorporación Fiscal (RIF)' },
];

const SAT_CFDI_USES = [
  { code: 'G03', label: 'G03 - Gastos en general' },
  { code: 'G01', label: 'G01 - Adquisición de mercancías' },
  { code: 'S01', label: 'S01 - Sin efectos fiscales' },
  { code: 'CP01', label: 'CP01 - Pagos' },
  { code: 'D01', label: 'D01 - Honorarios médicos, dentales y gastos hospitalarios' },
];

const SAT_PAYMENT_FORMS = [
  { code: '01', label: '01 - Efectivo' },
  { code: '04', label: '04 - Tarjeta de crédito' },
  { code: '28', label: '28 - Tarjeta de débito' },
  { code: '03', label: '03 - Transferencia electrónica de fondos' },
  { code: '31', label: '31 - Intermediario pagos (Uber/Marketplace)' },
];

export default function InvoicingView() {
  const queryClient = useQueryClient();
  const { session } = usePosSession();
  const branchId = session?.active_branch?.id || '';

  const [activeTab, setActiveTab] = useState<'tickets' | 'invoices'>('tickets');
  const [searchTerm, setSearchTerm] = useState('');
  const [dateFilter, setDateFilter] = useState<'today' | 'yesterday' | 'all'>('today');
  const [selectedOrderIds, setSelectedOrderIds] = useState<string[]>([]);

  // Modal de Emisión
  const [issueModalOpen, setIssueModalOpen] = useState(false);
  const [issuedInvoiceResult, setIssuedInvoiceResult] = useState<InvoiceRecord | null>(null);

  // Formulario Receptor
  const [receptorRfc, setReceptorRfc] = useState('');
  const [receptorName, setReceptorName] = useState('');
  const [receptorZip, setReceptorZip] = useState('');
  const [receptorTaxSystem, setReceptorTaxSystem] = useState('601');
  const [receptorUse, setReceptorUse] = useState('G03');
  const [paymentForm, setPaymentForm] = useState('01');
  const [paymentMethod, setPaymentMethod] = useState('PUE');
  const [receptorEmail, setReceptorEmail] = useState('');

  // Modal de Autofactura QR
  const [qrModalOpen, setQrModalOpen] = useState(false);
  const [activeQrReceipt, setActiveQrReceipt] = useState<{ url: string; folio: string; key?: string } | null>(null);

  // Queries
  const { data: config } = useQuery<FacturapiConfig>({
    queryKey: ['integrations', 'facturapi', 'config'],
    queryFn: () => fetchApi('/integrations/facturapi/config'),
  });

  const { data: accountsData, isLoading: loadingOrders, refetch: refetchOrders } = useQuery<{ items: OrderAccount[] }>({
    queryKey: ['orders', 'accounts', branchId],
    queryFn: () => fetchApi(`/orders/accounts?branch_id=${encodeURIComponent(branchId)}&limit=100`),
    enabled: !!branchId,
  });

  const { data: invoices = [], isLoading: loadingInvoices, refetch: refetchInvoices } = useQuery<InvoiceRecord[]>({
    queryKey: ['invoicing', 'invoices', branchId],
    queryFn: () => fetchApi(`/invoicing/invoices?branch_id=${encodeURIComponent(branchId)}`),
    enabled: !!branchId,
  });

  const orders = accountsData?.items || [];

  // Invoiced Order IDs map
  const invoicedSet = useMemo(() => {
    return new Set(invoices.map((inv) => inv.id));
  }, [invoices]);

  // Filtered orders
  const filteredOrders = useMemo(() => {
    return orders.filter((o) => {
      const matchSearch =
        o.folio.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (o.customer_label && o.customer_label.toLowerCase().includes(searchTerm.toLowerCase()));
      return matchSearch;
    });
  }, [orders, searchTerm]);

  // Selected orders summary
  const selectedOrders = useMemo(() => {
    return orders.filter((o) => selectedOrderIds.includes(o.id));
  }, [orders, selectedOrderIds]);

  const totalSelectedCents = useMemo(() => {
    return selectedOrders.reduce((sum, o) => sum + o.total_cents, 0);
  }, [selectedOrders]);

  // Toggle selection
  const toggleSelectOrder = (orderId: string) => {
    setSelectedOrderIds((prev) =>
      prev.includes(orderId) ? prev.filter((id) => id !== orderId) : [...prev, orderId]
    );
  };

  const toggleSelectAll = () => {
    if (selectedOrderIds.length === filteredOrders.length) {
      setSelectedOrderIds([]);
    } else {
      setSelectedOrderIds(filteredOrders.map((o) => o.id));
    }
  };

  // Helper Público en General
  const fillPublicGeneral = () => {
    setReceptorRfc('XAXX010101000');
    setReceptorName('PUBLICO EN GENERAL');
    setReceptorZip(session?.active_branch?.code ? '80000' : '80000');
    setReceptorTaxSystem('616');
    setReceptorUse('S01');
    setPaymentForm('01');
  };

  // Mutation Emisión
  const issueInvoiceMutation = useMutation({
    mutationFn: (payload: any) =>
      fetchApi<InvoiceRecord>('/invoicing/invoices/issue', {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
    onSuccess: (data) => {
      setIssuedInvoiceResult(data);
      queryClient.invalidateQueries({ queryKey: ['invoicing', 'invoices'] });
      queryClient.invalidateQueries({ queryKey: ['orders', 'accounts'] });
      setSelectedOrderIds([]);
    },
    onError: (err: any) => {
      alert(`Error al emitir factura: ${err.message || 'Verifica los datos fiscales'}`);
    },
  });

  // Mutation Receipt QR
  const generateReceiptMutation = useMutation({
    mutationFn: (orderId: string) =>
      fetchApi<{ self_invoice_url: string; key?: string }>(`/invoicing/orders/${orderId}/receipt`, {
        method: 'POST',
      }),
    onSuccess: (data, orderId) => {
      const order = orders.find((o) => o.id === orderId);
      setActiveQrReceipt({
        url: data.self_invoice_url,
        key: data.key,
        folio: order?.folio || 'TICKET',
      });
      setQrModalOpen(true);
    },
    onError: (err: any) => {
      alert(`Error al generar QR de autofactura: ${err.message}`);
    },
  });

  const handleOpenIssueModal = () => {
    if (selectedOrderIds.length === 0) {
      alert('Selecciona al menos un ticket para facturar.');
      return;
    }
    setIssuedInvoiceResult(null);
    setIssueModalOpen(true);
  };

  const handleEmitCfdi = () => {
    if (!receptorRfc.trim() || !receptorName.trim() || !receptorZip.trim()) {
      alert('Por favor completa el RFC, Razón Social y Código Postal del receptor.');
      return;
    }

    issueInvoiceMutation.mutate({
      order_ids: selectedOrderIds,
      branch_id: branchId,
      receptor: {
        rfc: receptorRfc.trim().toUpperCase(),
        legal_name: receptorName.trim().toUpperCase(),
        zip: receptorZip.trim(),
        tax_system: receptorTaxSystem,
        use: receptorUse,
        payment_form: paymentForm,
        payment_method: paymentMethod,
        email: receptorEmail.trim() || undefined,
      },
    });
  };

  return (
    <div style={{ maxWidth: 1400, margin: '0 auto', padding: '24px 20px 80px' }}>
      {/* Header Banner */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          background: '#fff',
          padding: '20px 24px',
          borderRadius: 16,
          border: '1px solid #e2e8f0',
          boxShadow: '0 2px 4px rgba(0,0,0,0.02)',
          marginBottom: 24,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <div
            style={{
              width: 48,
              height: 48,
              borderRadius: 12,
              background: '#f3e8ff',
              color: '#7e22ce',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <FileText size={28} />
          </div>
          <div>
            <h1 style={{ fontSize: '1.4rem', fontWeight: 800, margin: '0 0 4px', color: '#0f172a' }}>
              Facturación Electrónica (CFDI 4.0)
            </h1>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: '0.875rem', color: '#64748b' }}>
              <span>
                Emisor: <strong>{config?.organization_legal_name || 'Restaurante'}</strong> ({config?.organization_rfc || 'RFC'})
              </span>
              <span>•</span>
              <Badge variant={config?.is_enabled ? 'success' : 'default'}>
                {config?.is_enabled ? (config?.environment === 'sandbox' ? '🟢 Modo Sandbox (Pruebas)' : '🟢 Timbrado en Vivo SAT') : '⚪ Deshabilitado'}
              </Badge>
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 12 }}>
          <Button
            variant="secondary"
            onClick={() => { refetchOrders(); refetchInvoices(); }}
            style={{ display: 'flex', alignItems: 'center', gap: 8 }}
          >
            <RefreshCw size={16} />
            Actualizar
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 20 }}>
        <button
          type="button"
          onClick={() => setActiveTab('tickets')}
          style={{
            padding: '12px 24px',
            borderRadius: 10,
            border: 'none',
            fontWeight: 700,
            fontSize: '0.9375rem',
            cursor: 'pointer',
            background: activeTab === 'tickets' ? '#7e22ce' : '#fff',
            color: activeTab === 'tickets' ? '#fff' : '#475569',
            boxShadow: activeTab === 'tickets' ? '0 4px 12px rgba(126, 34, 206, 0.25)' : '0 1px 3px rgba(0,0,0,0.05)',
            transition: 'all 0.2s',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}
        >
          <CheckSquare size={18} />
          Tickets y Comandas ({filteredOrders.length})
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('invoices')}
          style={{
            padding: '12px 24px',
            borderRadius: 10,
            border: 'none',
            fontWeight: 700,
            fontSize: '0.9375rem',
            cursor: 'pointer',
            background: activeTab === 'invoices' ? '#7e22ce' : '#fff',
            color: activeTab === 'invoices' ? '#fff' : '#475569',
            boxShadow: activeTab === 'invoices' ? '0 4px 12px rgba(126, 34, 206, 0.25)' : '0 1px 3px rgba(0,0,0,0.05)',
            transition: 'all 0.2s',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}
        >
          <FileText size={18} />
          Facturas Emitidas ({invoices.length})
        </button>
      </div>

      {/* Tab: Tickets */}
      {activeTab === 'tickets' && (
        <div style={{ background: '#fff', borderRadius: 16, border: '1px solid #e2e8f0', overflow: 'hidden' }}>
          {/* Filter Bar */}
          <div
            style={{
              padding: '16px 20px',
              borderBottom: '1px solid #e2e8f0',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              background: '#f8fafc',
              flexWrap: 'wrap',
              gap: 12,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, flex: 1, minWidth: 280 }}>
              <div style={{ position: 'relative', width: '100%', maxWidth: 360 }}>
                <Search size={18} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: '#94a3b8' }} />
                <input
                  type="text"
                  placeholder="Buscar por folio o cliente..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px 12px 8px 38px',
                    borderRadius: 8,
                    border: '1px solid #cbd5e1',
                    fontSize: '0.875rem',
                  }}
                />
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <Button
                variant="secondary"
                onClick={toggleSelectAll}
                style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.8125rem' }}
              >
                {selectedOrderIds.length === filteredOrders.length && filteredOrders.length > 0 ? (
                  <CheckSquare size={16} />
                ) : (
                  <Square size={16} />
                )}
                {selectedOrderIds.length === filteredOrders.length && filteredOrders.length > 0
                  ? 'Deseleccionar Todos'
                  : 'Seleccionar Todos'}
              </Button>
            </div>
          </div>

          {/* Orders Table */}
          {filteredOrders.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '60px 20px', color: '#64748b' }}>
              <FileText size={48} style={{ opacity: 0.3, margin: '0 auto 12px' }} />
              <p style={{ fontWeight: 600, margin: '0 0 4px' }}>No hay comandas registradas</p>
              <p style={{ fontSize: '0.875rem', margin: 0 }}>
                Los tickets cobrados en caja aparecerán aquí para ser facturados.
              </p>
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.875rem' }}>
                <thead>
                  <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0', color: '#475569' }}>
                    <th style={{ padding: '12px 16px', width: 40 }}></th>
                    <th style={{ padding: '12px 16px' }}>Folio</th>
                    <th style={{ padding: '12px 16px' }}>Cliente / Mesa</th>
                    <th style={{ padding: '12px 16px' }}>Fecha</th>
                    <th style={{ padding: '12px 16px' }}>Total</th>
                    <th style={{ padding: '12px 16px' }}>Estado Cobro</th>
                    <th style={{ padding: '12px 16px' }}>Autofactura</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredOrders.map((order) => {
                    const isSelected = selectedOrderIds.includes(order.id);
                    return (
                      <tr
                        key={order.id}
                        onClick={() => toggleSelectOrder(order.id)}
                        style={{
                          borderBottom: '1px solid #f1f5f9',
                          cursor: 'pointer',
                          background: isSelected ? '#faf5ff' : 'transparent',
                          transition: 'background 0.15s',
                        }}
                      >
                        <td style={{ padding: '14px 16px', textAlign: 'center' }}>
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => {}}
                            style={{ width: 18, height: 18, accentColor: '#7e22ce', cursor: 'pointer' }}
                          />
                        </td>
                        <td style={{ padding: '14px 16px' }}>
                          <strong style={{ color: '#0f172a' }}>{order.folio}</strong>
                        </td>
                        <td style={{ padding: '14px 16px', color: '#475569' }}>
                          {order.customer_label || 'Comensal en Mostrador'}
                        </td>
                        <td style={{ padding: '14px 16px', color: '#64748b' }}>
                          {new Date(order.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </td>
                        <td style={{ padding: '14px 16px' }}>
                          <strong style={{ color: '#0f172a' }}>${(order.total_cents / 100).toFixed(2)} MXN</strong>
                        </td>
                        <td style={{ padding: '14px 16px' }}>
                          <Badge variant={order.status === 'COMPLETED' ? 'success' : 'default'}>
                            {order.status}
                          </Badge>
                        </td>
                        <td style={{ padding: '14px 16px' }} onClick={(e) => e.stopPropagation()}>
                          <Button
                            variant="secondary"
                            onClick={() => generateReceiptMutation.mutate(order.id)}
                            disabled={generateReceiptMutation.isPending}
                            style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.75rem', padding: '4px 10px' }}
                          >
                            <QrCode size={14} />
                            QR Ticket
                          </Button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Tab: Facturas Emitidas */}
      {activeTab === 'invoices' && (
        <div style={{ background: '#fff', borderRadius: 16, border: '1px solid #e2e8f0', overflow: 'hidden' }}>
          {invoices.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '60px 20px', color: '#64748b' }}>
              <FileText size={48} style={{ opacity: 0.3, margin: '0 auto 12px' }} />
              <p style={{ fontWeight: 600, margin: '0 0 4px' }}>No hay facturas timbradas aún</p>
              <p style={{ fontSize: '0.875rem', margin: 0 }}>
                Selecciona uno o más tickets en la pestaña anterior para emitir tu primer CFDI 4.0.
              </p>
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.875rem' }}>
                <thead>
                  <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0', color: '#475569' }}>
                    <th style={{ padding: '12px 16px' }}>Folio</th>
                    <th style={{ padding: '12px 16px' }}>Folio Fiscal SAT (UUID)</th>
                    <th style={{ padding: '12px 16px' }}>Receptor</th>
                    <th style={{ padding: '12px 16px' }}>Fecha</th>
                    <th style={{ padding: '12px 16px' }}>Total</th>
                    <th style={{ padding: '12px 16px' }}>Estado</th>
                    <th style={{ padding: '12px 16px' }}>Descargas</th>
                  </tr>
                </thead>
                <tbody>
                  {invoices.map((inv) => (
                    <tr key={inv.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                      <td style={{ padding: '14px 16px' }}><strong>{inv.folio_number}</strong></td>
                      <td style={{ padding: '14px 16px', fontFamily: 'monospace', fontSize: '0.8125rem', color: '#475569' }}>
                        {inv.uuid_sat || 'En proceso'}
                      </td>
                      <td style={{ padding: '14px 16px' }}>
                        <div><strong>{inv.nombre_receptor}</strong></div>
                        <span style={{ fontSize: '0.75rem', color: '#64748b' }}>RFC: {inv.rfc_receptor}</span>
                      </td>
                      <td style={{ padding: '14px 16px', color: '#64748b' }}>
                        {new Date(inv.created_at).toLocaleDateString()}
                      </td>
                      <td style={{ padding: '14px 16px' }}>
                        <strong>${(inv.total_cents / 100).toFixed(2)} {inv.currency}</strong>
                      </td>
                      <td style={{ padding: '14px 16px' }}>
                        <Badge variant={inv.status === 'issued' ? 'success' : 'danger'}>
                          {inv.status === 'issued' ? 'Válida SAT' : 'Cancelada'}
                        </Badge>
                      </td>
                      <td style={{ padding: '14px 16px' }}>
                        <div style={{ display: 'flex', gap: 8 }}>
                          {inv.pdf_url && (
                            <a
                              href={inv.pdf_url}
                              target="_blank"
                              rel="noreferrer"
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 4,
                                textDecoration: 'none',
                                padding: '4px 8px',
                                fontSize: '0.75rem',
                                border: '1px solid #cbd5e1',
                                borderRadius: 6,
                                color: '#0f172a',
                              }}
                            >
                              <Download size={14} /> PDF
                            </a>
                          )}
                          {inv.xml_url && (
                            <a
                              href={inv.xml_url}
                              target="_blank"
                              rel="noreferrer"
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 4,
                                textDecoration: 'none',
                                padding: '4px 8px',
                                fontSize: '0.75rem',
                                border: '1px solid #cbd5e1',
                                borderRadius: 6,
                                color: '#0f172a',
                              }}
                            >
                              <Download size={14} /> XML
                            </a>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Floating Action Bar */}
      {selectedOrderIds.length > 0 && activeTab === 'tickets' && (
        <div
          style={{
            position: 'fixed',
            bottom: 24,
            left: '50%',
            transform: 'translateX(-50%)',
            background: '#0f172a',
            color: '#fff',
            padding: '14px 24px',
            borderRadius: 50,
            display: 'flex',
            alignItems: 'center',
            gap: 20,
            boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.4)',
            zIndex: 100,
          }}
        >
          <div style={{ fontSize: '0.9375rem' }}>
            <strong>{selectedOrderIds.length}</strong> ticket{selectedOrderIds.length > 1 ? 's' : ''} seleccionado{selectedOrderIds.length > 1 ? 's' : ''} •{' '}
            <strong style={{ color: '#4ade80' }}>${(totalSelectedCents / 100).toFixed(2)} MXN</strong>
          </div>

          <Button
            variant="primary"
            onClick={handleOpenIssueModal}
            style={{
              background: '#a855f7',
              borderColor: '#9333ea',
              borderRadius: 30,
              padding: '8px 20px',
              fontWeight: 700,
              display: 'flex',
              alignItems: 'center',
              gap: 8,
            }}
          >
            <FileText size={18} />
            Facturar Selección
          </Button>

          <button
            type="button"
            onClick={() => setSelectedOrderIds([])}
            style={{
              background: 'none',
              border: 'none',
              color: '#94a3b8',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
            }}
          >
            <X size={18} />
          </button>
        </div>
      )}

      {/* Modal: Emisión CFDI 4.0 */}
      <Modal
        isOpen={issueModalOpen}
        onClose={() => setIssueModalOpen(false)}
        title={issuedInvoiceResult ? '¡CFDI 4.0 Timbrado con Éxito!' : 'Emitir Factura Electrónica (CFDI 4.0)'}
      >
        <div style={{ padding: '8px 0', maxHeight: '75vh', overflowY: 'auto' }}>
          {issuedInvoiceResult ? (
            <div style={{ textAlign: 'center', padding: '16px 0' }}>
              <CheckCircle2 size={56} style={{ color: '#16a34a', margin: '0 auto 16px' }} />
              <h3 style={{ fontSize: '1.25rem', fontWeight: 800, margin: '0 0 8px', color: '#0f172a' }}>
                Factura {issuedInvoiceResult.folio_number} Emitida
              </h3>
              <p style={{ fontSize: '0.875rem', color: '#64748b', marginBottom: 20 }}>
                Folio Fiscal SAT (UUID):<br />
                <code style={{ fontSize: '0.9375rem', color: '#0f172a', fontWeight: 700 }}>
                  {issuedInvoiceResult.uuid_sat}
                </code>
              </p>

              <div style={{ display: 'flex', justifyContent: 'center', gap: 12, marginBottom: 24 }}>
                {issuedInvoiceResult.pdf_url && (
                  <a
                    href={issuedInvoiceResult.pdf_url}
                    target="_blank"
                    rel="noreferrer"
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      background: '#7e22ce',
                      color: '#fff',
                      padding: '10px 20px',
                      borderRadius: 8,
                      textDecoration: 'none',
                      fontWeight: 600,
                    }}
                  >
                    <Download size={18} /> Descargar PDF Oficial
                  </a>
                )}
                {issuedInvoiceResult.xml_url && (
                  <a
                    href={issuedInvoiceResult.xml_url}
                    target="_blank"
                    rel="noreferrer"
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      background: '#f8fafc',
                      color: '#0f172a',
                      border: '1px solid #cbd5e1',
                      padding: '10px 20px',
                      borderRadius: 8,
                      textDecoration: 'none',
                      fontWeight: 600,
                    }}
                  >
                    <Download size={18} /> Descargar XML
                  </a>
                )}
              </div>

              <Button variant="secondary" onClick={() => setIssueModalOpen(false)}>
                Cerrar Ventana
              </Button>
            </div>
          ) : (
            <div>
              {/* Summary of Selected Tickets */}
              <div style={{ background: '#f8fafc', padding: 14, borderRadius: 10, marginBottom: 20, border: '1px solid #e2e8f0' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.875rem', color: '#64748b' }}>
                    Tickets incluidos: <strong>{selectedOrders.map((o) => o.folio).join(', ')}</strong>
                  </span>
                  <span style={{ fontSize: '1rem', fontWeight: 800, color: '#0f172a' }}>
                    Total: ${(totalSelectedCents / 100).toFixed(2)} MXN
                  </span>
                </div>
              </div>

              {/* Botón Rápido Público en General */}
              <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 16 }}>
                <Button
                  variant="secondary"
                  onClick={fillPublicGeneral}
                  style={{ fontSize: '0.8125rem', borderColor: '#a855f7', color: '#7e22ce' }}
                >
                  ⚡ Llenar como Público en General
                </Button>
              </div>

              {/* Formulario */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 14 }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, color: '#475569', marginBottom: 4 }}>
                    RFC Receptor *
                  </label>
                  <input
                    type="text"
                    placeholder="XAXX010101000"
                    value={receptorRfc}
                    onChange={(e) => setReceptorRfc(e.target.value.toUpperCase())}
                    style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid #cbd5e1', fontSize: '0.875rem' }}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, color: '#475569', marginBottom: 4 }}>
                    Código Postal Fiscal *
                  </label>
                  <input
                    type="text"
                    placeholder="80000"
                    value={receptorZip}
                    onChange={(e) => setReceptorZip(e.target.value)}
                    style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid #cbd5e1', fontSize: '0.875rem' }}
                  />
                </div>
              </div>

              <div style={{ marginBottom: 14 }}>
                <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, color: '#475569', marginBottom: 4 }}>
                  Nombre o Razón Social (Exacto como en Constancia SAT) *
                </label>
                <input
                  type="text"
                  placeholder="PUBLICO EN GENERAL"
                  value={receptorName}
                  onChange={(e) => setReceptorName(e.target.value.toUpperCase())}
                  style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid #cbd5e1', fontSize: '0.875rem' }}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 14 }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, color: '#475569', marginBottom: 4 }}>
                    Régimen Fiscal *
                  </label>
                  <select
                    value={receptorTaxSystem}
                    onChange={(e) => setReceptorTaxSystem(e.target.value)}
                    style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid #cbd5e1', fontSize: '0.875rem' }}
                  >
                    {SAT_TAX_SYSTEMS.map((ts) => (
                      <option key={ts.code} value={ts.code}>{ts.label}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, color: '#475569', marginBottom: 4 }}>
                    Uso de CFDI *
                  </label>
                  <select
                    value={receptorUse}
                    onChange={(e) => setReceptorUse(e.target.value)}
                    style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid #cbd5e1', fontSize: '0.875rem' }}
                  >
                    {SAT_CFDI_USES.map((u) => (
                      <option key={u.code} value={u.code}>{u.label}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 14 }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, color: '#475569', marginBottom: 4 }}>
                    Forma de Pago SAT
                  </label>
                  <select
                    value={paymentForm}
                    onChange={(e) => setPaymentForm(e.target.value)}
                    style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid #cbd5e1', fontSize: '0.875rem' }}
                  >
                    {SAT_PAYMENT_FORMS.map((pf) => (
                      <option key={pf.code} value={pf.code}>{pf.label}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, color: '#475569', marginBottom: 4 }}>
                    Método de Pago
                  </label>
                  <select
                    value={paymentMethod}
                    onChange={(e) => setPaymentMethod(e.target.value)}
                    style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid #cbd5e1', fontSize: '0.875rem' }}
                  >
                    <option value="PUE">PUE - Pago en una sola exhibición</option>
                    <option value="PPD">PPD - Pago en parcialidades o diferido</option>
                  </select>
                </div>
              </div>

              <div style={{ marginBottom: 24 }}>
                <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, color: '#475569', marginBottom: 4 }}>
                  Enviar por Correo Electrónico (Opcional)
                </label>
                <input
                  type="email"
                  placeholder="cliente@empresa.com"
                  value={receptorEmail}
                  onChange={(e) => setReceptorEmail(e.target.value)}
                  style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid #cbd5e1', fontSize: '0.875rem' }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12 }}>
                <Button variant="secondary" onClick={() => setIssueModalOpen(false)}>
                  Cancelar
                </Button>
                <Button
                  variant="primary"
                  onClick={handleEmitCfdi}
                  disabled={issueInvoiceMutation.isPending}
                  style={{ background: '#7e22ce', borderColor: '#6b21a8', display: 'flex', alignItems: 'center', gap: 8 }}
                >
                  <FileText size={16} />
                  {issueInvoiceMutation.isPending ? 'Timbrando ante el SAT...' : 'Emitir y Timbrar CFDI'}
                </Button>
              </div>
            </div>
          )}
        </div>
      </Modal>

      {/* Modal: QR Autofactura */}
      <Modal
        isOpen={qrModalOpen}
        onClose={() => setQrModalOpen(false)}
        title={`Autofactura en Línea - Ticket ${activeQrReceipt?.folio}`}
      >
        <div style={{ textAlign: 'center', padding: '16px 0' }}>
          <div
            style={{
              width: 160,
              height: 160,
              margin: '0 auto 16px',
              background: '#f8fafc',
              border: '2px dashed #cbd5e1',
              borderRadius: 16,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#7e22ce',
            }}
          >
            <QrCode size={96} />
          </div>

          <p style={{ fontSize: '0.9375rem', fontWeight: 600, color: '#0f172a', margin: '0 0 6px' }}>
            El comensal puede escanear este código o visitar:
          </p>
          <p style={{ fontSize: '0.875rem', color: '#7e22ce', wordBreak: 'break-all', fontWeight: 700, marginBottom: 20 }}>
            {activeQrReceipt?.url}
          </p>

          <div style={{ display: 'flex', justifyContent: 'center', gap: 12 }}>
            <Button
              variant="secondary"
              onClick={() => {
                if (activeQrReceipt?.url) {
                  navigator.clipboard.writeText(activeQrReceipt.url);
                  alert('Enlace copiado al portapapeles.');
                }
              }}
            >
              Copiar Enlace
            </Button>
            <Button variant="secondary" onClick={() => setQrModalOpen(false)}>
              Cerrar
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
