import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button, Badge, Modal } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';
import {
  Share2,
  Copy,
  Check,
  Building2,
  Activity,
  Key,
  Trash2,
  Play,
} from 'lucide-react';
import '../../premium-catalogs.css';

interface ChannelConfig {
  id?: string;
  is_enabled: boolean;
  environment: string;
  client_id: string;
  client_secret: string;
  webhook_secret: string;
  auto_accept: boolean;
  default_prep_time_minutes: number;
}

interface StoreMapping {
  id: string;
  branch_id: string;
  branch_name: string;
  branch_code: string;
  provider: string;
  external_store_id: string;
  is_active: boolean;
  created_at: string;
}

interface Branch {
  id: string;
  name: string;
  code: string;
  status: string;
}

interface WebhookLog {
  id: string;
  provider: string;
  event_type: string;
  event_id?: string;
  signature?: string;
  payload_raw: any;
  status: string;
  error_message?: string;
  created_at: string;
}

export default function IntegrationsHub() {
  const queryClient = useQueryClient();
  const [selectedProvider, setSelectedProvider] = useState<'UBER_EATS' | 'DIDI_FOOD' | 'RAPPI'>('UBER_EATS');
  const [activeTab, setActiveTab] = useState<'config' | 'stores' | 'logs'>('config');
  const [copied, setCopied] = useState(false);
  const [testOrderModalOpen, setTestOrderModalOpen] = useState(false);
  const [testOrderItemsCount, setTestOrderItemsCount] = useState(2);
  const [testOrderCustomer, setTestOrderCustomer] = useState('Carlos M. (Prueba)');
  const [testOrderResult, setTestOrderResult] = useState<string | null>(null);

  const [mappingModalOpen, setMappingModalOpen] = useState(false);
  const [newMappingBranchId, setNewMappingBranchId] = useState('');
  const [newMappingStoreId, setNewMappingStoreId] = useState('');

  const { data: config } = useQuery<ChannelConfig>({
    queryKey: ['integrations', selectedProvider, 'config'],
    queryFn: () => fetchApi('/integrations/' + selectedProvider.toLowerCase().replace('_', '-') + '/config'),
  });

  const { data: branches = [] } = useQuery<Branch[]>({
    queryKey: ['branches'],
    queryFn: () => fetchApi('/branches'),
  });

  const { data: storeMappings = [] } = useQuery<StoreMapping[]>({
    queryKey: ['integrations', selectedProvider, 'stores'],
    queryFn: () => fetchApi('/integrations/' + selectedProvider.toLowerCase().replace('_', '-') + '/stores'),
  });

  const { data: logs = [] } = useQuery<WebhookLog[]>({
    queryKey: ['integrations', selectedProvider, 'logs'],
    queryFn: () => fetchApi('/integrations/' + selectedProvider.toLowerCase().replace('_', '-') + '/logs'),
    refetchInterval: activeTab === 'logs' ? 5000 : false,
  });

  const [formData, setFormData] = useState<Partial<ChannelConfig>>({});

  React.useEffect(() => {
    if (config) {
      setFormData(config);
    }
  }, [config]);

  const saveConfigMutation = useMutation({
    mutationFn: (payload: Partial<ChannelConfig>) =>
      fetchApi('/integrations/' + selectedProvider.toLowerCase().replace('_', '-') + '/config', {
        method: 'PUT',
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['integrations', selectedProvider, 'config'] });
      alert('Configuración guardada exitosamente.');
    },
  });

  const saveMappingMutation = useMutation({
    mutationFn: (payload: { branch_id: string; external_store_id: string }) =>
      fetchApi('/integrations/' + selectedProvider.toLowerCase().replace('_', '-') + '/stores', {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['integrations', selectedProvider, 'stores'] });
      setMappingModalOpen(false);
      setNewMappingBranchId('');
      setNewMappingStoreId('');
    },
  });

  const deleteMappingMutation = useMutation({
    mutationFn: (mappingId: string) =>
      fetchApi('/integrations/' + selectedProvider.toLowerCase().replace('_', '-') + '/stores/' + mappingId, {
        method: 'DELETE',
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['integrations', selectedProvider, 'stores'] });
    },
  });

  const simulateOrderMutation = useMutation({
    mutationFn: (payload: { customer_name: string; items_count: number; store_id?: string }) =>
      fetchApi('/integrations/' + selectedProvider.toLowerCase().replace('_', '-') + '/test-order', {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
    onSuccess: (data: any) => {
      setTestOrderResult('¡Orden de prueba generada con éxito! Folio: ' + (data.result?.folio || 'UBER-XXXX'));
      queryClient.invalidateQueries({ queryKey: ['integrations', selectedProvider, 'logs'] });
    },
    onError: (err: any) => {
      setTestOrderResult('Error al generar orden: ' + (err.message || 'Desconocido'));
    },
  });

  const webhookUrl = window.location.origin + '/v1/integrations/uber-eats/webhook';

  const copyToClipboard = () => {
    navigator.clipboard.writeText(webhookUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  };

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', paddingBottom: 40 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 32 }}>
        <div>
          <h1 className="premium-header-title" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Share2 size={26} style={{ color: '#10b981' }} />
            Hub de Integraciones Omnicanal
          </h1>
          <p className="premium-header-subtitle">
            Conecta plataformas de delivery como Uber Eats, DiDi Food y Rappi directamente al sistema sin tabletas adicionales.
          </p>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 16, marginBottom: 28 }}>
        <div
          onClick={() => setSelectedProvider('UBER_EATS')}
          style={{
            background: selectedProvider === 'UBER_EATS' ? '#064e3b' : '#fff',
            color: selectedProvider === 'UBER_EATS' ? '#fff' : '#0f172a',
            border: selectedProvider === 'UBER_EATS' ? '2px solid #10b981' : '1px solid #e2e8f0',
            borderRadius: 14,
            padding: '20px 24px',
            cursor: 'pointer',
            boxShadow: selectedProvider === 'UBER_EATS' ? '0 10px 20px -5px rgba(16, 185, 129, 0.3)' : '0 2px 4px rgba(0,0,0,0.02)',
            transition: 'all 0.2s',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <span style={{ fontSize: 20 }}>🟢</span>
              <strong style={{ fontSize: '1.1rem' }}>Uber Eats Marketplace</strong>
            </div>
            <p style={{ margin: 0, fontSize: '0.8125rem', opacity: 0.85 }}>
              API Oficial v2 · Webhooks en vivo
            </p>
          </div>
          <Badge variant={formData.is_enabled ? 'success' : 'default'}>
            {formData.is_enabled ? 'Conectado' : 'Configurar'}
          </Badge>
        </div>

        <div
          onClick={() => setSelectedProvider('DIDI_FOOD')}
          style={{
            background: selectedProvider === 'DIDI_FOOD' ? '#7c2d12' : '#fff',
            color: selectedProvider === 'DIDI_FOOD' ? '#fff' : '#0f172a',
            border: selectedProvider === 'DIDI_FOOD' ? '2px solid #f97316' : '1px solid #e2e8f0',
            borderRadius: 14,
            padding: '20px 24px',
            cursor: 'pointer',
            opacity: 0.85,
            transition: 'all 0.2s',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <span style={{ fontSize: 20 }}>🟠</span>
              <strong style={{ fontSize: '1.1rem' }}>DiDi Food</strong>
            </div>
            <p style={{ margin: 0, fontSize: '0.8125rem', opacity: 0.85 }}>
              OpenPlatform API
            </p>
          </div>
          <Badge variant="info">Próximamente</Badge>
        </div>

        <div
          onClick={() => setSelectedProvider('RAPPI')}
          style={{
            background: selectedProvider === 'RAPPI' ? '#831843' : '#fff',
            color: selectedProvider === 'RAPPI' ? '#fff' : '#0f172a',
            border: selectedProvider === 'RAPPI' ? '2px solid #ec4899' : '1px solid #e2e8f0',
            borderRadius: 14,
            padding: '20px 24px',
            cursor: 'pointer',
            opacity: 0.85,
            transition: 'all 0.2s',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <span style={{ fontSize: 20 }}>🔴</span>
              <strong style={{ fontSize: '1.1rem' }}>Rappi Integraciones</strong>
            </div>
            <p style={{ margin: 0, fontSize: '0.8125rem', opacity: 0.85 }}>
              Rappi Partners API v3
            </p>
          </div>
          <Badge variant="info">Próximamente</Badge>
        </div>
      </div>

      <div className="premium-card" style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ display: 'flex', borderBottom: '1px solid #e2e8f0', background: '#f8fafc', padding: '0 16px' }}>
          <button
            type="button"
            onClick={() => setActiveTab('config')}
            style={{
              padding: '16px 20px',
              border: 'none',
              background: 'transparent',
              fontWeight: 600,
              fontSize: '0.9375rem',
              color: activeTab === 'config' ? '#10b981' : '#64748b',
              borderBottom: activeTab === 'config' ? '3px solid #10b981' : '3px solid transparent',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
            }}
          >
            <Key size={18} />
            Credenciales & Webhook
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('stores')}
            style={{
              padding: '16px 20px',
              border: 'none',
              background: 'transparent',
              fontWeight: 600,
              fontSize: '0.9375rem',
              color: activeTab === 'stores' ? '#10b981' : '#64748b',
              borderBottom: activeTab === 'stores' ? '3px solid #10b981' : '3px solid transparent',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
            }}
          >
            <Building2 size={18} />
            Mapeo de Sucursales ({storeMappings.length})
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('logs')}
            style={{
              padding: '16px 20px',
              border: 'none',
              background: 'transparent',
              fontWeight: 600,
              fontSize: '0.9375rem',
              color: activeTab === 'logs' ? '#10b981' : '#64748b',
              borderBottom: activeTab === 'logs' ? '3px solid #10b981' : '3px solid transparent',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
            }}
          >
            <Activity size={18} />
            Monitor de Webhooks & Logs
          </button>
        </div>

        {activeTab === 'config' && (
          <div style={{ padding: 28 }}>
            <div
              style={{
                background: '#f0fdf4',
                border: '1px solid #bbf7d0',
                borderRadius: 12,
                padding: '20px 24px',
                marginBottom: 28,
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
                <div>
                  <h3 style={{ margin: '0 0 6px', color: '#166534', fontSize: '1.05rem', fontWeight: 700 }}>
                    URL Oficial de Webhook para Uber Developer Dashboard
                  </h3>
                  <p style={{ margin: 0, color: '#15803d', fontSize: '0.875rem' }}>
                    Pega esta dirección en tu panel de Uber (developer.uber.com &gt; Webhooks &gt; Add Webhook) con el tipo <strong>orders.notification</strong>:
                  </p>
                </div>
                <button
                  type="button"
                  onClick={copyToClipboard}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    padding: '10px 18px',
                    borderRadius: 8,
                    background: copied ? '#15803d' : '#16a34a',
                    color: '#fff',
                    border: 'none',
                    fontWeight: 600,
                    cursor: 'pointer',
                    fontSize: '0.875rem',
                  }}
                >
                  {copied ? <Check size={16} /> : <Copy size={16} />}
                  {copied ? '¡URL Copiada!' : 'Copiar URL'}
                </button>
              </div>
              <div
                style={{
                  background: '#fff',
                  border: '1px solid #cbd5e1',
                  borderRadius: 8,
                  padding: '10px 14px',
                  marginTop: 12,
                  fontFamily: 'monospace',
                  fontSize: '0.9rem',
                  color: '#0f172a',
                  wordBreak: 'break-all',
                }}
              >
                {webhookUrl}
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 20, marginBottom: 28 }}>
              <div>
                <label style={{ display: 'block', fontWeight: 600, fontSize: '0.875rem', marginBottom: 6 }}>
                  Client ID (de Uber Developer Portal &gt; Setup)
                </label>
                <input
                  type="text"
                  placeholder="ej. JuxD8ds3rEe5fOPWz-d0TLRmjRThELCr"
                  value={formData.client_id || ''}
                  onChange={(e) => setFormData({ ...formData, client_id: e.target.value })}
                  style={{ width: '100%', padding: '10px 14px', borderRadius: 8, border: '1px solid #cbd5e1' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontWeight: 600, fontSize: '0.875rem', marginBottom: 6 }}>
                  Client Secret (de Uber Developer Portal &gt; Setup)
                </label>
                <input
                  type="password"
                  placeholder="••••••••••••"
                  value={formData.client_secret || ''}
                  onChange={(e) => setFormData({ ...formData, client_secret: e.target.value })}
                  style={{ width: '100%', padding: '10px 14px', borderRadius: 8, border: '1px solid #cbd5e1' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontWeight: 600, fontSize: '0.875rem', marginBottom: 6 }}>
                  Webhook Secret (para validar firma HMAC-SHA256)
                </label>
                <input
                  type="password"
                  placeholder="••••••••••••"
                  value={formData.webhook_secret || ''}
                  onChange={(e) => setFormData({ ...formData, webhook_secret: e.target.value })}
                  style={{ width: '100%', padding: '10px 14px', borderRadius: 8, border: '1px solid #cbd5e1' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontWeight: 600, fontSize: '0.875rem', marginBottom: 6 }}>
                  Entorno de Ejecución
                </label>
                <select
                  value={formData.environment || 'sandbox'}
                  onChange={(e) => setFormData({ ...formData, environment: e.target.value })}
                  style={{ width: '100%', padding: '10px 14px', borderRadius: 8, border: '1px solid #cbd5e1', background: '#fff' }}
                >
                  <option value="sandbox">Sandbox (Pruebas de desarrollo)</option>
                  <option value="production">Producción (Tiendas en vivo)</option>
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontWeight: 600, fontSize: '0.875rem', marginBottom: 6 }}>
                  Tiempo Estimado de Preparación (Minutos)
                </label>
                <input
                  type="number"
                  min="5"
                  max="120"
                  value={formData.default_prep_time_minutes || 20}
                  onChange={(e) => setFormData({ ...formData, default_prep_time_minutes: parseInt(e.target.value) || 20 })}
                  style={{ width: '100%', padding: '10px 14px', borderRadius: 8, border: '1px solid #cbd5e1' }}
                />
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 12, paddingTop: 26 }}>
                <input
                  type="checkbox"
                  id="auto_accept"
                  checked={formData.auto_accept ?? true}
                  onChange={(e) => setFormData({ ...formData, auto_accept: e.target.checked })}
                  style={{ width: 18, height: 18, accentColor: '#10b981', cursor: 'pointer' }}
                />
                <label htmlFor="auto_accept" style={{ fontWeight: 600, fontSize: '0.875rem', cursor: 'pointer' }}>
                  Aceptar pedidos automáticamente e imprimir en cocina
                </label>
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: 20, borderTop: '1px solid #e2e8f0', flexWrap: 'wrap', gap: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <input
                  type="checkbox"
                  id="is_enabled"
                  checked={formData.is_enabled ?? false}
                  onChange={(e) => setFormData({ ...formData, is_enabled: e.target.checked })}
                  style={{ width: 20, height: 20, accentColor: '#10b981', cursor: 'pointer' }}
                />
                <label htmlFor="is_enabled" style={{ fontWeight: 700, fontSize: '0.95rem', color: formData.is_enabled ? '#16a34a' : '#64748b', cursor: 'pointer' }}>
                  {formData.is_enabled ? '🟢 Conexión Activa (Recibiendo pedidos)' : '⚪ Conexión Desactivada'}
                </label>
              </div>

              <div style={{ display: 'flex', gap: 12 }}>
                <Button
                  variant="secondary"
                  onClick={() => {
                    setTestOrderResult(null);
                    setTestOrderModalOpen(true);
                  }}
                >
                  <Play size={16} />
                  Simular Pedido de Prueba
                </Button>

                <Button
                  variant="primary"
                  onClick={() => saveConfigMutation.mutate(formData)}
                  disabled={saveConfigMutation.isPending}
                >
                  {saveConfigMutation.isPending ? 'Guardando...' : 'Guardar Configuración'}
                </Button>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'stores' && (
          <div style={{ padding: 28 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
              <div>
                <h3 style={{ margin: '0 0 4px', fontSize: '1.1rem', fontWeight: 700 }}>
                  Vincular Sucursales con Tiendas Uber Eats
                </h3>
                <p style={{ margin: 0, color: '#64748b', fontSize: '0.875rem' }}>
                  Asocia el <strong>Store UUID</strong> que te proporciona Uber a cada sucursal física de RestaurantOS.
                </p>
              </div>
              <Button variant="primary" onClick={() => setMappingModalOpen(true)}>
                + Vincular Nueva Sucursal
              </Button>
            </div>

            {storeMappings.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '40px 20px', background: '#f8fafc', borderRadius: 12, border: '1px dashed #cbd5e1' }}>
                <Building2 size={40} style={{ color: '#94a3b8', marginBottom: 12 }} />
                <h4 style={{ margin: '0 0 6px', fontSize: '1rem', fontWeight: 600 }}>No hay sucursales vinculadas aún</h4>
                <p style={{ color: '#64748b', fontSize: '0.875rem', marginBottom: 16 }}>
                  Vincula al menos una sucursal para que los pedidos de Uber Eats se asignen al almacén y cocina correcta.
                </p>
                <Button variant="primary" onClick={() => setMappingModalOpen(true)}>
                  Vincular Primera Sucursal
                </Button>
              </div>
            ) : (
              <div className="premium-table-wrap">
                <table className="premium-table">
                  <thead>
                    <tr>
                      <th>Sucursal Kiwi</th>
                      <th>Código</th>
                      <th>Store UUID (Uber Eats)</th>
                      <th>Estado</th>
                      <th style={{ textAlign: 'right' }}>Acciones</th>
                    </tr>
                  </thead>
                  <tbody>
                    {storeMappings.map((m) => (
                      <tr key={m.id}>
                        <td>
                          <strong>{m.branch_name}</strong>
                        </td>
                        <td>
                          <code>{m.branch_code}</code>
                        </td>
                        <td>
                          <code style={{ background: '#f1f5f9', padding: '3px 8px', borderRadius: 6 }}>
                            {m.external_store_id}
                          </code>
                        </td>
                        <td>
                          <Badge variant={m.is_active ? 'success' : 'default'}>
                            {m.is_active ? 'Activo' : 'Inactivo'}
                          </Badge>
                        </td>
                        <td style={{ textAlign: 'right' }}>
                          <button
                            type="button"
                            onClick={() => {
                              if (confirm('Desvincular la sucursal ' + m.branch_name + '?')) {
                                deleteMappingMutation.mutate(m.id);
                              }
                            }}
                            style={{ background: 'transparent', border: 'none', color: '#ef4444', cursor: 'pointer', padding: 6 }}
                            title="Eliminar mapeo"
                          >
                            <Trash2 size={16} />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {activeTab === 'logs' && (
          <div style={{ padding: 28 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
              <div>
                <h3 style={{ margin: '0 0 4px', fontSize: '1.1rem', fontWeight: 700 }}>
                  Bitácora de Webhooks en Vivo
                </h3>
                <p style={{ margin: 0, color: '#64748b', fontSize: '0.875rem' }}>
                  Auditoría y diagnóstico de los eventos recibidos desde los servidores de Uber Eats.
                </p>
              </div>
              <Button variant="secondary" onClick={() => queryClient.invalidateQueries({ queryKey: ['integrations', selectedProvider, 'logs'] })}>
                Refrescar
              </Button>
            </div>

            {logs.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '40px 20px', background: '#f8fafc', borderRadius: 12, border: '1px dashed #cbd5e1' }}>
                <Activity size={40} style={{ color: '#94a3b8', marginBottom: 12 }} />
                <h4 style={{ margin: '0 0 6px', fontSize: '1rem', fontWeight: 600 }}>No se han registrado webhooks aún</h4>
                <p style={{ color: '#64748b', fontSize: '0.875rem' }}>
                  Cuando Uber Eats envíe una notificación de orden, aparecerá aquí en tiempo real.
                </p>
              </div>
            ) : (
              <div className="premium-table-wrap">
                <table className="premium-table">
                  <thead>
                    <tr>
                      <th>Fecha / Hora</th>
                      <th>Evento</th>
                      <th>ID de Evento</th>
                      <th>Estado</th>
                      <th>Detalle / Error</th>
                    </tr>
                  </thead>
                  <tbody>
                    {logs.map((log) => (
                      <tr key={log.id}>
                        <td style={{ whiteSpace: 'nowrap', fontSize: '0.8125rem', color: '#64748b' }}>
                          {new Date(log.created_at).toLocaleString('es-MX')}
                        </td>
                        <td>
                          <strong>{log.event_type}</strong>
                        </td>
                        <td>
                          <code>{log.event_id || '-'}</code>
                        </td>
                        <td>
                          <Badge variant={log.status === 'received' || log.status === 'processed' ? 'success' : 'danger'}>
                            {log.status}
                          </Badge>
                        </td>
                        <td style={{ fontSize: '0.8125rem', color: log.error_message ? '#dc2626' : '#64748b' }}>
                          {log.error_message || 'Procesado exitosamente'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>

      <Modal isOpen={mappingModalOpen} onClose={() => setMappingModalOpen(false)} title="Vincular Sucursal con Uber Eats">
        <div style={{ display: 'grid', gap: 16 }}>
          <div>
            <label style={{ display: 'block', fontWeight: 600, fontSize: '0.875rem', marginBottom: 6 }}>
              Selecciona la Sucursal Kiwi
            </label>
            <select
              value={newMappingBranchId}
              onChange={(e) => setNewMappingBranchId(e.target.value)}
              style={{ width: '100%', padding: '10px 14px', borderRadius: 8, border: '1px solid #cbd5e1', background: '#fff' }}
            >
              <option value="">-- Elige una sucursal --</option>
              {branches.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name} ({b.code})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label style={{ display: 'block', fontWeight: 600, fontSize: '0.875rem', marginBottom: 6 }}>
              Store UUID de Uber Eats
            </label>
            <input
              type="text"
              placeholder="ej. d0e94168-bf1b-49cb-a49b-02df1ff9b68e"
              value={newMappingStoreId}
              onChange={(e) => setNewMappingStoreId(e.target.value)}
              style={{ width: '100%', padding: '10px 14px', borderRadius: 8, border: '1px solid #cbd5e1' }}
            />
            <small style={{ display: 'block', marginTop: 4, color: '#64748b' }}>
              Lo encuentras en la URL de tu panel de Uber Developer / Stores.
            </small>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12, marginTop: 12 }}>
            <Button variant="secondary" onClick={() => setMappingModalOpen(false)}>
              Cancelar
            </Button>
            <Button
              variant="primary"
              disabled={!newMappingBranchId || !newMappingStoreId || saveMappingMutation.isPending}
              onClick={() =>
                saveMappingMutation.mutate({
                  branch_id: newMappingBranchId,
                  external_store_id: newMappingStoreId,
                })
              }
            >
              {saveMappingMutation.isPending ? 'Guardando...' : 'Vincular Sucursal'}
            </Button>
          </div>
        </div>
      </Modal>

      <Modal isOpen={testOrderModalOpen} onClose={() => setTestOrderModalOpen(false)} title="Simular Pedido de Prueba (Sandbox)">
        <div style={{ display: 'grid', gap: 16 }}>
          <p style={{ margin: 0, fontSize: '0.875rem', color: '#64748b' }}>
            Genera un webhook simulado de Uber Eats para comprobar que la comanda ingresa correctamente al POS y KDS sin esperar un pedido real.
          </p>

          <div>
            <label style={{ display: 'block', fontWeight: 600, fontSize: '0.875rem', marginBottom: 6 }}>
              Nombre del Comensal
            </label>
            <input
              type="text"
              value={testOrderCustomer}
              onChange={(e) => setTestOrderCustomer(e.target.value)}
              style={{ width: '100%', padding: '10px 14px', borderRadius: 8, border: '1px solid #cbd5e1' }}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontWeight: 600, fontSize: '0.875rem', marginBottom: 6 }}>
              Cantidad de Hamburguesas en el Pedido
            </label>
            <input
              type="number"
              min="1"
              max="10"
              value={testOrderItemsCount}
              onChange={(e) => setTestOrderItemsCount(parseInt(e.target.value) || 1)}
              style={{ width: '100%', padding: '10px 14px', borderRadius: 8, border: '1px solid #cbd5e1' }}
            />
          </div>

          {testOrderResult && (
            <div
              style={{
                padding: '12px 16px',
                borderRadius: 8,
                background: testOrderResult.includes('éxito') ? '#f0fdf4' : '#fef2f2',
                color: testOrderResult.includes('éxito') ? '#166534' : '#991b1b',
                fontSize: '0.875rem',
                fontWeight: 600,
              }}
            >
              {testOrderResult}
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12, marginTop: 12 }}>
            <Button variant="secondary" onClick={() => setTestOrderModalOpen(false)}>
              Cerrar
            </Button>
            <Button
              variant="primary"
              disabled={simulateOrderMutation.isPending}
              onClick={() =>
                simulateOrderMutation.mutate({
                  customer_name: testOrderCustomer,
                  items_count: testOrderItemsCount,
                })
              }
            >
              {simulateOrderMutation.isPending ? 'Enviando...' : 'Disparar Orden de Prueba'}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
