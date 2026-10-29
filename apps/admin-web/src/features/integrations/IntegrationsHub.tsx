import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button, Badge, Modal } from '@restaurantos/ui';
import { fetchApi, downloadFiscalInvoice, hasAdminCapability } from '@restaurantos/api-client';
import { useAdminSession } from '../../lib/adminSession';
import {
  Share2,
  Copy,
  Check,
  Building2,
  Activity,
  Key,
  Trash2,
  Play,
  FileText,
  Download,
  Send,
  Zap,
  Globe,
  QrCode,
  Eye,
  EyeOff,
} from 'lucide-react';
import '../../premium-catalogs.css';

interface ChannelConfig {
  id?: string;
  is_enabled: boolean;
  environment: string;
  client_id: string;
  client_secret: string;
  webhook_secret: string;
  return_url?: string;
  master_prompt?: string;
  auto_accept: boolean;
  default_prep_time_minutes: number;
}

interface FacturapiConfig {
  id?: string | null;
  organization_id: string;
  legal_entity_id: string;
  version: number;
  is_enabled: boolean;
  environment: string;
  api_key_configured: boolean;
  organization_legal_name: string;
  organization_rfc: string;
  organization_tax_system: string;
  organization_zip: string;
  default_product_sat_key: string;
  default_unit_sat_key: string;
  series: string;
  enable_self_invoicing: boolean;
  self_invoicing_domain: string;
  self_invoicing_days_valid: number | null;
  print_qr_on_ticket: boolean;
}

function publicFiscalConfiguration(data: FacturapiConfig): FacturapiConfig {
  return {id:data.id, organization_id:data.organization_id, legal_entity_id:data.legal_entity_id,version:data.version,
    is_enabled:data.is_enabled, environment:data.environment, api_key_configured:data.api_key_configured,
    organization_legal_name:data.organization_legal_name, organization_rfc:data.organization_rfc,
    organization_tax_system:data.organization_tax_system, organization_zip:data.organization_zip,
    default_product_sat_key:data.default_product_sat_key, default_unit_sat_key:data.default_unit_sat_key,
    series:data.series, enable_self_invoicing:data.enable_self_invoicing,
    self_invoicing_domain:data.self_invoicing_domain, self_invoicing_days_valid:data.self_invoicing_days_valid,
    print_qr_on_ticket:data.print_qr_on_ticket};
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

type GrokBotProfile = 'administrator' | 'kitchen' | 'inventory' | 'purchasing';

interface GrokBotIdentity {
  id?: string;
  profile: GrokBotProfile;
  client_id?: string;
  is_enabled: boolean;
  corporate_scope: boolean;
  authorization_version: number;
  capabilities: string[];
  branch_ids: string[];
  last_rotated_at?: string;
}

interface GrokBotConfig {
  id?: string;
  provider: 'GROKBOT';
  orchestrator_label: string;
  display_name: string;
  base_url?: string;
  callback_url?: string;
  has_callback_secret_ref: boolean;
  is_enabled: boolean;
  state: 'DISCONNECTED' | 'CONNECTED' | 'DEGRADED' | 'DRAINING' | 'PAUSED';
  identities: GrokBotIdentity[];
}

interface RotatedAgentCredential {
  profile: GrokBotProfile;
  client_id: string;
  client_secret: string;
  authorization_version: number;
  warning: string;
}

export default function IntegrationsHub() {
  const queryClient = useQueryClient();
  const { session, assertCurrentAuthority } = useAdminSession();
  const canManageIntegrations = hasAdminCapability(session, 'admin.manage');
  const canReadFiscal = hasAdminCapability(session, 'invoicing.read');
  const canConfigureFiscal = hasAdminCapability(session, 'invoicing.config.manage');
  const fiscalQueryScope = [session.organization_id, session.user.id, session.scope.authorization_version,
    session.active_branch.id, session.branch_workspace_context_id];
  const fiscalCorporateScope = [session.organization_id, session.user.id, session.scope.authorization_version];
  const [selectedEmitterId, setSelectedEmitterId] = useState('');
  const [newFiscalKey, setNewFiscalKey] = useState('');
  const [fiscalSaveMessage, setFiscalSaveMessage] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const grokBotAgentToolsEnabled = import.meta.env.VITE_GROKBOT_AGENT_TOOLS_ENABLED === 'true';
  const [selectedProvider, setSelectedProvider] = useState<'GROKBOT' | 'WHATSAPP' | 'UBER_EATS' | 'DIDI_FOOD' | 'RAPPI' | 'FACTURAPI'>(
    !canManageIntegrations ? 'FACTURAPI' : grokBotAgentToolsEnabled ? 'GROKBOT' : 'WHATSAPP',
  );
  const [activeTab, setActiveTab] = useState<'config' | 'agents' | 'stores' | 'logs' | 'invoices'>(
    canManageIntegrations || canConfigureFiscal ? 'config' : 'invoices');
  const fiscalDraftScope = JSON.stringify([...fiscalCorporateScope, selectedEmitterId, selectedProvider]);
  const currentFiscalDraft = React.useRef(fiscalDraftScope);
  currentFiscalDraft.current = fiscalDraftScope;
  const isDeliveryProvider = selectedProvider === 'UBER_EATS' || selectedProvider === 'DIDI_FOOD' || selectedProvider === 'RAPPI' || selectedProvider === 'WHATSAPP';
  const providerPath = selectedProvider === 'WHATSAPP' ? 'whatsapp' : selectedProvider.toLowerCase().replace('_', '-');
  const [copied, setCopied] = useState(false);
  const [copiedSecret, setCopiedSecret] = useState(false);
  const [showWebhookSecret, setShowWebhookSecret] = useState(false);
  const [showApiKey, setShowApiKey] = useState(false);
  const [testOrderModalOpen, setTestOrderModalOpen] = useState(false);
  const [testOrderItemsCount, setTestOrderItemsCount] = useState(2);
  const [testOrderCustomer, setTestOrderCustomer] = useState('Carlos M. (Prueba)');
  const [testOrderResult, setTestOrderResult] = useState<string | null>(null);
  const [facturapiTestResult, setFacturapiTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [grokBotForm, setGrokBotForm] = useState<Partial<GrokBotConfig>>({});
  const [rotatedCredential, setRotatedCredential] = useState<RotatedAgentCredential | null>(null);

  const [mappingModalOpen, setMappingModalOpen] = useState(false);
  const [newMappingBranchId, setNewMappingBranchId] = useState('');
  const [newMappingStoreId, setNewMappingStoreId] = useState('');

  // Queries for Uber/Delivery Channels
  const { data: config } = useQuery<ChannelConfig>({
    queryKey: ['integrations', selectedProvider, 'config'],
    queryFn: () => fetchApi('/integrations/' + providerPath + '/config'),
    enabled: isDeliveryProvider && canManageIntegrations,
  });

  const { data: branches = [] } = useQuery<Branch[]>({
    queryKey: ['branches'],
    queryFn: () => fetchApi('/branches'),
    enabled: canManageIntegrations,
  });

  const { data: storeMappings = [] } = useQuery<StoreMapping[]>({
    queryKey: ['integrations', selectedProvider, 'stores'],
    queryFn: () => fetchApi('/integrations/' + providerPath + '/stores'),
    enabled: isDeliveryProvider && canManageIntegrations,
  });

  const { data: logs = [] } = useQuery<WebhookLog[]>({
    queryKey: ['integrations', selectedProvider, 'logs'],
    queryFn: () => fetchApi('/integrations/' + providerPath + '/logs'),
    refetchInterval: activeTab === 'logs' && isDeliveryProvider ? 5000 : false,
    enabled: isDeliveryProvider && canManageIntegrations,
  });

  // Queries for Facturapi
  const { data: fiscalEmitters = [], error: fiscalEmittersError } = useQuery<{id:string;name:string;tax_id:string|null}[]>({
    queryKey: ['invoicing', 'emitters', ...fiscalCorporateScope],
    queryFn: () => fetchApi('/invoicing/emitters'),
    enabled: selectedProvider === 'FACTURAPI' && canConfigureFiscal,
  });
  const { data: facturapiConfig, error: fiscalConfigurationError } = useQuery<FacturapiConfig>({
    queryKey: ['integrations', 'facturapi', 'config', ...fiscalCorporateScope, selectedEmitterId],
    queryFn: async () => {
      const data = await fetchApi<FacturapiConfig>(`/invoicing/emitters/${encodeURIComponent(selectedEmitterId)}/configuration`);
      return publicFiscalConfiguration(data);
    },
    enabled: selectedProvider === 'FACTURAPI' && canConfigureFiscal && !!selectedEmitterId,
  });

  const { data: invoiceList = [] } = useQuery<InvoiceRecord[]>({
    queryKey: ['invoicing', 'invoices', ...fiscalQueryScope],
    queryFn: () => fetchApi('/invoicing/invoices'),
    enabled: selectedProvider === 'FACTURAPI' && activeTab === 'invoices' && canReadFiscal,
  });

  const { data: grokBotConfig } = useQuery<GrokBotConfig>({
    queryKey: ['integrations', 'grokbot', 'config'],
    queryFn: () => fetchApi('/integrations/grokbot/config'),
    enabled: grokBotAgentToolsEnabled && selectedProvider === 'GROKBOT' && canManageIntegrations,
  });

  const [formData, setFormData] = useState<Partial<ChannelConfig>>({});
  const [facturapiForm, setFacturapiForm] = useState<Partial<FacturapiConfig>>({});
  const [loadedFiscalDraftScope, setLoadedFiscalDraftScope] = useState('');
  const fiscalFormReady = loadedFiscalDraftScope === fiscalDraftScope
    && facturapiConfig?.legal_entity_id === selectedEmitterId
    && facturapiForm.legal_entity_id === selectedEmitterId
    && facturapiForm.version === facturapiConfig.version;

  React.useEffect(() => {
    setFacturapiForm({}); setLoadedFiscalDraftScope('');
    setNewFiscalKey(''); setShowApiKey(false); setFiscalSaveMessage(null); setFacturapiTestResult(null);
  }, [fiscalDraftScope]);

  React.useEffect(() => {
    if (config && isDeliveryProvider) {
      setFormData(config);
    }
  }, [config, isDeliveryProvider]);

  React.useEffect(() => {
    if (loadedFiscalDraftScope !== fiscalDraftScope
      && facturapiConfig?.legal_entity_id === selectedEmitterId && selectedProvider === 'FACTURAPI') {
      setFacturapiForm(facturapiConfig);
      setLoadedFiscalDraftScope(fiscalDraftScope);
    }
  }, [facturapiConfig, selectedEmitterId, selectedProvider, fiscalDraftScope, loadedFiscalDraftScope]);

  React.useEffect(() => {
    if (grokBotConfig && selectedProvider === 'GROKBOT') {
      setGrokBotForm(grokBotConfig);
    }
  }, [grokBotConfig, selectedProvider]);

  const saveConfigMutation = useMutation({
    mutationFn: (payload: Partial<ChannelConfig>) =>
      fetchApi('/integrations/' + providerPath + '/config', {
        method: 'PUT',
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['integrations', selectedProvider, 'config'] });
      alert('Configuración guardada exitosamente.');
    },
  });

  const downloadFiscalMutation = useMutation({
    mutationFn: async ({id, format}:{id:string; format:'pdf'|'xml'}) => {
      assertCurrentAuthority();
      if (!canReadFiscal) throw new Error('No tienes permiso para consultar documentos fiscales.');
      await downloadFiscalInvoice(id, format);
    },
    onMutate: () => setDownloadError(null),
    onError: (error:Error) => setDownloadError(error.message),
  });

  const saveFacturapiMutation = useMutation({
    mutationFn: async ({payload,scope,key}:{payload:Partial<FacturapiConfig>;scope:string;key:string}) => {
      assertCurrentAuthority();
      if (!canConfigureFiscal) throw new Error('No tienes permiso para configurar facturación.');
      if (scope !== currentFiscalDraft.current || !fiscalFormReady || !selectedEmitterId
        || payload.legal_entity_id !== selectedEmitterId) {
        throw new Error('Selecciona un emisor y espera a que cargue su configuración.');
      }
      const body = {...payload};
      delete body.id; delete body.api_key_configured;
      delete body.organization_id; delete body.legal_entity_id; delete body.version;
      const data = await fetchApi<FacturapiConfig>(`/invoicing/emitters/${encodeURIComponent(selectedEmitterId)}/configuration`, {
        method: 'PUT',
        body: JSON.stringify({...body, expected_version:payload.version,
          ...(key.trim() ? {api_key:key.trim()} : {})}),
      });
      assertCurrentAuthority();
      return {data:publicFiscalConfiguration(data),scope};
    },
    onMutate: () => setFiscalSaveMessage(null),
    onSuccess: ({data,scope}) => {
      if (currentFiscalDraft.current !== scope) return;
      setNewFiscalKey(''); setShowApiKey(false);
      setFacturapiForm(data); setLoadedFiscalDraftScope(scope);
      queryClient.invalidateQueries({ queryKey: ['integrations', 'facturapi', 'config'] });
      setFiscalSaveMessage('Configuración guardada.');
    },
    onError: (_error,{scope}) => {
      if (currentFiscalDraft.current === scope) { setNewFiscalKey(''); setShowApiKey(false); }
    },
  });

  const saveGrokBotMutation = useMutation({
    mutationFn: (payload: Partial<GrokBotConfig>) =>
      fetchApi<GrokBotConfig>('/integrations/grokbot/config', {
        method: 'PUT',
        body: JSON.stringify({
          display_name: payload.display_name || 'Administrador Kiwi',
          base_url: payload.base_url || null,
          callback_url: payload.callback_url || null,
          is_enabled: payload.is_enabled ?? false,
        }),
      }),
    onSuccess: (data) => {
      setGrokBotForm(data);
      queryClient.invalidateQueries({ queryKey: ['integrations', 'grokbot', 'config'] });
    },
  });

  const updateGrokBotIdentityMutation = useMutation({
    mutationFn: (identity: GrokBotIdentity) =>
      fetchApi(`/integrations/grokbot/identities/${identity.profile}`, {
        method: 'PUT',
        body: JSON.stringify({
          is_enabled: identity.is_enabled,
          corporate_scope: identity.corporate_scope,
          capabilities: identity.capabilities,
          branch_ids: identity.branch_ids,
          expected_authorization_version: identity.authorization_version,
        }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['integrations', 'grokbot', 'config'] });
    },
    onError: () => {
      queryClient.invalidateQueries({ queryKey: ['integrations', 'grokbot', 'config'] });
    },
  });

  const rotateGrokBotIdentityMutation = useMutation({
    mutationFn: (profile: GrokBotProfile) =>
      fetchApi<RotatedAgentCredential>(`/integrations/grokbot/identities/${profile}/rotate-secret`, {
        method: 'POST',
      }),
    onSuccess: (data) => {
      setRotatedCredential(data);
      queryClient.invalidateQueries({ queryKey: ['integrations', 'grokbot', 'config'] });
    },
  });

  const testFacturapiMutation = useMutation({
    mutationFn: async (scope:string) => {
      assertCurrentAuthority();
      if (!canConfigureFiscal) throw new Error('No tienes permiso para configurar facturación.');
      if (scope !== currentFiscalDraft.current || !fiscalFormReady || !selectedEmitterId || !facturapiConfig?.version) {
        throw new Error('Guarda primero la configuración del emisor seleccionado.');
      }
      const data = await fetchApi<{success:boolean;message:string}>(`/invoicing/emitters/${encodeURIComponent(selectedEmitterId)}/test-connection`, {
        method: 'POST',
      });
      assertCurrentAuthority();
      return {data,scope};
    },
    onSuccess: ({data,scope}) => {
      if (currentFiscalDraft.current === scope) setFacturapiTestResult(data);
    },
    onError: (err: any,scope) => {
      if (currentFiscalDraft.current !== scope) return;
      setFacturapiTestResult({
        success: false,
        message: `Error de conexión: ${err.message || 'Verifica la Secret Key'}`,
      });
    },
  });

  const saveMappingMutation = useMutation({
    mutationFn: (payload: { branch_id: string; external_store_id: string }) =>
      fetchApi('/integrations/' + providerPath + '/stores', {
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
      fetchApi('/integrations/' + providerPath + '/stores/' + mappingId, {
        method: 'DELETE',
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['integrations', selectedProvider, 'stores'] });
    },
  });

  const simulateOrderMutation = useMutation({
    mutationFn: (payload: { customer_name: string; items_count: number; store_id?: string }) =>
      fetchApi('/integrations/' + providerPath + '/test-order', {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
    onSuccess: (data: any) => {
      const providerLabel = selectedProvider === 'WHATSAPP' ? 'WhatsApp' : selectedProvider === 'UBER_EATS' ? 'Uber Eats' : selectedProvider === 'DIDI_FOOD' ? 'DiDi Food' : selectedProvider === 'RAPPI' ? 'Rappi' : 'Delivery';
      setTestOrderResult(`¡Orden de prueba de ${providerLabel} generada con éxito! Folio: ` + (data.result?.folio || 'ORD-XXXX'));
      queryClient.invalidateQueries({ queryKey: ['integrations', selectedProvider, 'logs'] });
    },
    onError: (err: any) => {
      setTestOrderResult('Error al generar orden: ' + (err.message || 'Desconocido'));
    },
  });

  const webhookPath =
    selectedProvider === 'WHATSAPP'
      ? 'whatsapp'
      : selectedProvider === 'UBER_EATS'
      ? 'uber-eats'
      : selectedProvider === 'DIDI_FOOD'
      ? 'didi-food'
      : selectedProvider === 'RAPPI'
      ? 'rappi'
      : selectedProvider.toLowerCase().replace('_', '-');
  const webhookUrl = `${window.location.origin}/api/v1/integrations/${webhookPath}/webhook`;

  const copyToClipboard = () => {
    navigator.clipboard.writeText(webhookUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  };

  const copySecretToClipboard = (secretValue?: string) => {
    const val = secretValue || formData.webhook_secret || '';
    if (val) {
      navigator.clipboard.writeText(val);
      setCopiedSecret(true);
      setTimeout(() => setCopiedSecret(false), 2500);
    }
  };

  const regenerateSecretMutation = useMutation({
    mutationFn: () =>
      fetchApi<{ webhook_secret: string; config: ChannelConfig }>('/integrations/whatsapp/regenerate-secret', {
        method: 'POST',
      }),
    onSuccess: (data) => {
      setFormData((prev) => ({ ...prev, webhook_secret: data.webhook_secret }));
      queryClient.invalidateQueries({ queryKey: ['integrations', 'WHATSAPP', 'config'] });
      alert('Nuevo Webhook Secret generado con éxito. Cópialo y pégalo en Asistto.');
    },
    onError: (err: any) => {
      alert('Error al regenerar secreto: ' + (err.message || 'Desconocido'));
    },
  });

  const grokBotProfileLabels: Record<GrokBotProfile, string> = {
    administrator: 'Administrador',
    kitchen: 'Cocinero',
    inventory: 'Inventarios',
    purchasing: 'Compras',
  };

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', paddingBottom: 40 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 32 }}>
        <div>
          <h1 className="premium-header-title" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Share2 size={26} style={{ color: '#10b981' }} />
            Hub de Integraciones & Facturación CFDI
          </h1>
          <p className="premium-header-subtitle">
            Conecta plataformas de delivery (Uber Eats, DiDi Food, Rappi) y el servicio oficial de timbrado ante el SAT (Facturapi CFDI 4.0).
          </p>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 16, marginBottom: 28 }}>
        {/* GrokBot: one visible orchestrator, four private technical identities. */}
        {grokBotAgentToolsEnabled && canManageIntegrations && <div
          onClick={() => { setSelectedProvider('GROKBOT'); setActiveTab('config'); setRotatedCredential(null); }}
          style={{
            background: selectedProvider === 'GROKBOT' ? '#172554' : '#fff',
            color: selectedProvider === 'GROKBOT' ? '#fff' : '#0f172a',
            border: selectedProvider === 'GROKBOT' ? '2px solid #60a5fa' : '1px solid #e2e8f0',
            borderRadius: 14,
            padding: '20px 24px',
            cursor: 'pointer',
            boxShadow: selectedProvider === 'GROKBOT' ? '0 10px 20px -5px rgba(59, 130, 246, 0.3)' : '0 2px 4px rgba(0,0,0,0.02)',
            transition: 'all 0.2s',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <span style={{ fontSize: 20 }}>🤖</span>
              <strong style={{ fontSize: '1.1rem' }}>GrokBot</strong>
            </div>
            <p style={{ margin: 0, fontSize: '0.8125rem', opacity: 0.85 }}>
              Administrador Kiwi · Orquestador
            </p>
          </div>
          <Badge variant={grokBotConfig?.is_enabled ? 'success' : 'default'}>
            {grokBotConfig?.is_enabled ? 'Habilitado' : 'Configurar'}
          </Badge>
        </div>}

        {/* WhatsApp (Asistto Tech Provider) */}
        {canManageIntegrations && <div
          onClick={() => { setSelectedProvider('WHATSAPP'); setActiveTab('config'); }}
          style={{
            background: selectedProvider === 'WHATSAPP' ? '#064e3b' : '#fff',
            color: selectedProvider === 'WHATSAPP' ? '#fff' : '#0f172a',
            border: selectedProvider === 'WHATSAPP' ? '2px solid #25d366' : '1px solid #e2e8f0',
            borderRadius: 14,
            padding: '20px 24px',
            cursor: 'pointer',
            boxShadow: selectedProvider === 'WHATSAPP' ? '0 10px 20px -5px rgba(37, 211, 102, 0.3)' : '0 2px 4px rgba(0,0,0,0.02)',
            transition: 'all 0.2s',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <span style={{ fontSize: 20 }}>💬</span>
              <strong style={{ fontSize: '1.1rem' }}>WhatsApp</strong>
            </div>
            <p style={{ margin: 0, fontSize: '0.8125rem', opacity: 0.85 }}>
              Asistto Tech Provider · Coexistencia
            </p>
          </div>
          <Badge variant={selectedProvider === 'WHATSAPP' && formData.is_enabled ? 'success' : 'default'}>
            {selectedProvider === 'WHATSAPP' && formData.is_enabled ? 'Conectado' : 'Configurar'}
          </Badge>
        </div>}

        {/* Uber Eats */}
        {canManageIntegrations && <div
          onClick={() => { setSelectedProvider('UBER_EATS'); setActiveTab('config'); }}
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
              <strong style={{ fontSize: '1.1rem' }}>Uber Eats</strong>
            </div>
            <p style={{ margin: 0, fontSize: '0.8125rem', opacity: 0.85 }}>
              API Oficial v2 · Webhooks en vivo
            </p>
          </div>
          <Badge variant={selectedProvider === 'UBER_EATS' && formData.is_enabled ? 'success' : 'default'}>
            {selectedProvider === 'UBER_EATS' && formData.is_enabled ? 'Conectado' : 'Configurar'}
          </Badge>
        </div>}

        {/* DiDi Food */}
        {canManageIntegrations && <div
          onClick={() => { setSelectedProvider('DIDI_FOOD'); setActiveTab('config'); }}
          style={{
            background: selectedProvider === 'DIDI_FOOD' ? '#7c2d12' : '#fff',
            color: selectedProvider === 'DIDI_FOOD' ? '#fff' : '#0f172a',
            border: selectedProvider === 'DIDI_FOOD' ? '2px solid #f97316' : '1px solid #e2e8f0',
            borderRadius: 14,
            padding: '20px 24px',
            cursor: 'pointer',
            boxShadow: selectedProvider === 'DIDI_FOOD' ? '0 10px 20px -5px rgba(249, 115, 22, 0.3)' : '0 2px 4px rgba(0,0,0,0.02)',
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
              OpenPlatform API · Pedidos & Menú
            </p>
          </div>
          <Badge variant={selectedProvider === 'DIDI_FOOD' && formData.is_enabled ? 'success' : 'default'}>
            {selectedProvider === 'DIDI_FOOD' && formData.is_enabled ? 'Conectado' : 'Configurar'}
          </Badge>
        </div>}

        {/* Facturapi */}
        {(canReadFiscal || canConfigureFiscal) && <div
          onClick={() => { setSelectedProvider('FACTURAPI'); setActiveTab(canConfigureFiscal ? 'config' : 'invoices'); }}
          style={{
            background: selectedProvider === 'FACTURAPI' ? '#3b0764' : '#fff',
            color: selectedProvider === 'FACTURAPI' ? '#fff' : '#0f172a',
            border: selectedProvider === 'FACTURAPI' ? '2px solid #a855f7' : '1px solid #e2e8f0',
            borderRadius: 14,
            padding: '20px 24px',
            cursor: 'pointer',
            boxShadow: selectedProvider === 'FACTURAPI' ? '0 10px 20px -5px rgba(168, 85, 247, 0.3)' : '0 2px 4px rgba(0,0,0,0.02)',
            transition: 'all 0.2s',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <span style={{ fontSize: 20 }}>🟣</span>
              <strong style={{ fontSize: '1.1rem' }}>Facturapi (CFDI 4.0)</strong>
            </div>
            <p style={{ margin: 0, fontSize: '0.8125rem', opacity: 0.85 }}>
              Timbrado SAT & Autofactura QR
            </p>
          </div>
          <Badge variant={facturapiForm.is_enabled ? 'success' : 'default'}>
            {!canConfigureFiscal ? 'Documentos' : facturapiForm.is_enabled ? 'Activo' : 'Configurar'}
          </Badge>
        </div>}

        {/* Rappi */}
        {canManageIntegrations && <div
          onClick={() => { setSelectedProvider('RAPPI'); setActiveTab('config'); }}
          style={{
            background: selectedProvider === 'RAPPI' ? '#831843' : '#fff',
            color: selectedProvider === 'RAPPI' ? '#fff' : '#0f172a',
            border: selectedProvider === 'RAPPI' ? '2px solid #ec4899' : '1px solid #e2e8f0',
            borderRadius: 14,
            padding: '20px 24px',
            cursor: 'pointer',
            boxShadow: selectedProvider === 'RAPPI' ? '0 10px 20px -5px rgba(236, 72, 153, 0.3)' : '0 2px 4px rgba(0,0,0,0.02)',
            transition: 'all 0.2s',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <span style={{ fontSize: 20 }}>🔴</span>
              <strong style={{ fontSize: '1.1rem' }}>Rappi</strong>
            </div>
            <p style={{ margin: 0, fontSize: '0.8125rem', opacity: 0.85 }}>
              Rappi Partners API · Pedidos & Webhooks
            </p>
          </div>
          <Badge variant={selectedProvider === 'RAPPI' && formData.is_enabled ? 'success' : 'default'}>
            {selectedProvider === 'RAPPI' && formData.is_enabled ? 'Conectado' : 'Configurar'}
          </Badge>
        </div>}
      </div>

      {/* Main Panel Content */}
      <div className="premium-card" style={{ padding: 0, overflow: 'hidden' }}>
        {/* Navigation Tabs */}
        <div style={{ display: 'flex', borderBottom: '1px solid #e2e8f0', background: '#f8fafc', padding: '0 16px' }}>
          {(selectedProvider !== 'FACTURAPI' || canConfigureFiscal) && <button
            type="button"
            onClick={() => setActiveTab('config')}
            style={{
              padding: '16px 20px',
              border: 'none',
              background: 'transparent',
              fontWeight: 600,
              fontSize: '0.9375rem',
              color: activeTab === 'config' ? (selectedProvider === 'FACTURAPI' ? '#a855f7' : selectedProvider === 'GROKBOT' ? '#2563eb' : '#10b981') : '#64748b',
              borderBottom: activeTab === 'config' ? `3px solid ${selectedProvider === 'FACTURAPI' ? '#a855f7' : selectedProvider === 'GROKBOT' ? '#2563eb' : '#10b981'}` : '3px solid transparent',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
            }}
          >
            <Key size={18} />
            {selectedProvider === 'FACTURAPI' ? 'Configuración Fiscal & API' : selectedProvider === 'GROKBOT' ? 'Orquestador' : 'Credenciales & Webhook'}
          </button>}

          {selectedProvider === 'GROKBOT' ? (
            <button
              type="button"
              onClick={() => setActiveTab('agents')}
              style={{
                padding: '16px 20px',
                border: 'none',
                background: 'transparent',
                fontWeight: 600,
                fontSize: '0.9375rem',
                color: activeTab === 'agents' ? '#2563eb' : '#64748b',
                borderBottom: activeTab === 'agents' ? '3px solid #2563eb' : '3px solid transparent',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 8,
              }}
            >
              <Building2 size={18} />
              Especialistas técnicos ({grokBotConfig?.identities.length ?? 4})
            </button>
          ) : selectedProvider === 'FACTURAPI' ? (
            canReadFiscal && <button
              type="button"
              onClick={() => setActiveTab('invoices')}
              style={{
                padding: '16px 20px',
                border: 'none',
                background: 'transparent',
                fontWeight: 600,
                fontSize: '0.9375rem',
                color: activeTab === 'invoices' ? '#a855f7' : '#64748b',
                borderBottom: activeTab === 'invoices' ? '3px solid #a855f7' : '3px solid transparent',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 8,
              }}
            >
              <FileText size={18} />
              Historial de Facturas
            </button>
          ) : (
            <>
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
                Bitácora de Webhooks ({logs.length})
              </button>
            </>
          )}
        </div>

        {/* GrokBot orchestrator configuration */}
        {selectedProvider === 'GROKBOT' && activeTab === 'config' && (
          <div style={{ padding: '32px 28px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 20, marginBottom: 24, flexWrap: 'wrap' }}>
              <div style={{ maxWidth: 720 }}>
                <h2 style={{ fontSize: '1.35rem', fontWeight: 800, margin: '0 0 6px', color: '#0f172a' }}>
                  Administrador Kiwi · GrokBot
                </h2>
                <p style={{ margin: 0, color: '#64748b', lineHeight: 1.5 }}>
                  Un solo asistente coordina cuatro especialistas privados. Kiwi valida por separado las facultades de Administrador, Cocinero, Inventarios y Compras.
                </p>
              </div>
              <Badge variant={grokBotForm.is_enabled ? 'success' : 'default'}>
                {grokBotForm.is_enabled ? 'Habilitado' : 'Deshabilitado por defecto'}
              </Badge>
            </div>

            <div style={{ background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: 12, padding: 16, marginBottom: 24, color: '#1e3a8a' }}>
              La conexión no concede acceso por sí sola. Cada especialista necesita una credencial rotada, capacidades acotadas y sucursales explícitas.
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 18 }}>
              <label style={{ fontSize: '0.85rem', fontWeight: 700, color: '#334155' }}>
                Nombre visible del orquestador
                <input
                  className="premium-input"
                  value={grokBotForm.display_name || 'Administrador Kiwi'}
                  onChange={(event) => setGrokBotForm({ ...grokBotForm, display_name: event.target.value })}
                  style={{ marginTop: 7 }}
                />
              </label>
              <label style={{ fontSize: '0.85rem', fontWeight: 700, color: '#334155' }}>
                URL base de GrokBot
                <input
                  className="premium-input"
                  type="url"
                  placeholder="https://grokbot.example.com"
                  value={grokBotForm.base_url || ''}
                  onChange={(event) => setGrokBotForm({ ...grokBotForm, base_url: event.target.value })}
                  style={{ marginTop: 7 }}
                />
              </label>
              <label style={{ fontSize: '0.85rem', fontWeight: 700, color: '#334155' }}>
                Callback HTTPS de estados
                <input
                  className="premium-input"
                  type="url"
                  placeholder="https://grokbot.example.com/kiwi/callback"
                  value={grokBotForm.callback_url || ''}
                  onChange={(event) => setGrokBotForm({ ...grokBotForm, callback_url: event.target.value })}
                  style={{ marginTop: 7 }}
                />
              </label>
              <label style={{ alignSelf: 'end', display: 'flex', gap: 10, alignItems: 'center', minHeight: 44, padding: '10px 12px', border: '1px solid #dbeafe', borderRadius: 10, background: '#f8fafc', fontWeight: 700 }}>
                <input
                  type="checkbox"
                  checked={grokBotForm.is_enabled ?? false}
                  onChange={(event) => setGrokBotForm({ ...grokBotForm, is_enabled: event.target.checked })}
                />
                Habilitar conector GrokBot
              </label>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 24 }}>
              <Button
                variant="primary"
                disabled={saveGrokBotMutation.isPending}
                onClick={() => saveGrokBotMutation.mutate(grokBotForm)}
                style={{ background: '#2563eb', borderColor: '#1d4ed8' }}
              >
                {saveGrokBotMutation.isPending ? 'Guardando...' : 'Guardar orquestador'}
              </Button>
            </div>
            {saveGrokBotMutation.isError && (
              <p role="alert" style={{ margin: '12px 0 0', color: '#b91c1c', textAlign: 'right' }}>
                No se pudo guardar la configuración de GrokBot. Revisa las URL y vuelve a intentar.
              </p>
            )}
          </div>
        )}

        {/* GrokBot specialist identities */}
        {selectedProvider === 'GROKBOT' && activeTab === 'agents' && (
          <div style={{ padding: '28px' }}>
            <div style={{ marginBottom: 22 }}>
              <h2 style={{ fontSize: '1.25rem', fontWeight: 800, margin: '0 0 5px', color: '#0f172a' }}>
                Especialistas técnicos
              </h2>
              <p style={{ margin: 0, color: '#64748b' }}>
                No son cuatro conversaciones: son cuatro límites de permisos detrás del Administrador Kiwi.
              </p>
            </div>

            {rotatedCredential && (
              <div role="alert" style={{ padding: 16, marginBottom: 20, borderRadius: 12, background: '#fff7ed', border: '1px solid #fdba74', color: '#9a3412' }}>
                <strong>{grokBotProfileLabels[rotatedCredential.profile]} — Se mostrará una sola vez</strong>
                <p style={{ margin: '8px 0 4px' }}>Client ID: <code>{rotatedCredential.client_id}</code></p>
                <p style={{ margin: 0 }}>Client secret: <code>{rotatedCredential.client_secret}</code></p>
                <Button
                  variant="secondary"
                  onClick={() => setRotatedCredential(null)}
                  style={{ marginTop: 12 }}
                >
                  Ya lo guardé; ocultar
                </Button>
              </div>
            )}
            {(updateGrokBotIdentityMutation.isError || rotateGrokBotIdentityMutation.isError) && (
              <p role="alert" style={{ padding: 12, borderRadius: 10, background: '#fef2f2', color: '#b91c1c' }}>
                No se pudo actualizar el especialista. La configuración anterior sigue vigente.
              </p>
            )}

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 18 }}>
              {(grokBotConfig?.identities || []).map((identity) => (
                <section key={identity.profile} style={{ border: '1px solid #e2e8f0', borderRadius: 14, padding: 18, background: '#fff' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center', marginBottom: 14 }}>
                    <div>
                      <strong style={{ color: '#0f172a' }}>{grokBotProfileLabels[identity.profile]}</strong>
                      <p style={{ margin: '3px 0 0', fontSize: '0.78rem', color: '#64748b' }}>{identity.profile}</p>
                    </div>
                    <Badge variant={identity.is_enabled ? 'success' : 'default'}>
                      {identity.is_enabled ? 'Activo' : 'Inactivo'}
                    </Badge>
                  </div>

                  <div style={{ fontSize: '0.78rem', color: '#475569', marginBottom: 14 }}>
                    {identity.capabilities.map((capability) => <div key={capability}>• {capability}</div>)}
                  </div>

                  {identity.profile === 'purchasing' && (
                    <label style={{ display: 'flex', gap: 9, alignItems: 'center', marginBottom: 10, fontSize: '0.85rem' }}>
                      <input
                        type="checkbox"
                        aria-label="Permitir leer costos e historial de compras"
                        checked={identity.capabilities.includes('agent.purchases.read')}
                        disabled={!grokBotConfig?.id || updateGrokBotIdentityMutation.isPending}
                        onChange={(event) => updateGrokBotIdentityMutation.mutate({
                          ...identity,
                          capabilities: event.target.checked
                            ? [...identity.capabilities, 'agent.purchases.read']
                            : identity.capabilities.filter((capability) => capability !== 'agent.purchases.read'),
                        })}
                      />
                      Permitir leer costos e historial de compras
                    </label>
                  )}

                  {identity.profile === 'administrator' && (
                    <>
                      {(
                        [
                          ['agent.cash_cuts.read', 'Permitir leer cortes de caja finalizados'],
                          ['agent.operating_expenses.read', 'Permitir leer gastos operativos'],
                          ['agent.payment_methods.read', 'Permitir leer ventas por método de pago'],
                          ['agent.cash_reconciliation.read', 'Permitir leer conciliación diaria de caja'],
                          ['agent.cash_personal_data.read', 'Permitir leer nombres y teléfonos de conciliación'],
                        ] as const
                      ).map(([capability, label]) => (
                        <label key={capability} style={{ display: 'flex', gap: 9, alignItems: 'center', marginBottom: 10, fontSize: '0.85rem' }}>
                          <input
                            type="checkbox"
                            aria-label={label}
                            checked={identity.capabilities.includes(capability)}
                            disabled={!grokBotConfig?.id || updateGrokBotIdentityMutation.isPending}
                            onChange={(event) => updateGrokBotIdentityMutation.mutate({
                              ...identity,
                              capabilities: event.target.checked
                                ? [...identity.capabilities, capability]
                                : identity.capabilities.filter((current) => current !== capability),
                            })}
                          />
                          {label}
                        </label>
                      ))}
                    </>
                  )}

                  <label style={{ display: 'flex', gap: 9, alignItems: 'center', marginBottom: 10, fontSize: '0.85rem' }}>
                    <input
                      type="checkbox"
                      checked={identity.corporate_scope}
                      onChange={(event) => updateGrokBotIdentityMutation.mutate({ ...identity, corporate_scope: event.target.checked })}
                    />
                    Permitir alcance corporativo
                  </label>
                  <label style={{ display: 'flex', gap: 9, alignItems: 'center', marginBottom: 14, fontSize: '0.85rem' }}>
                    <input
                      type="checkbox"
                      checked={identity.is_enabled}
                      onChange={(event) => updateGrokBotIdentityMutation.mutate({ ...identity, is_enabled: event.target.checked })}
                    />
                    Habilitar especialista
                  </label>

                  <fieldset style={{ border: 0, padding: 0, margin: '0 0 14px' }}>
                    <legend style={{ fontSize: '0.8rem', fontWeight: 700, marginBottom: 7 }}>Sucursales permitidas</legend>
                    {branches.map((branch) => {
                      const checked = identity.branch_ids.includes(branch.id);
                      return (
                        <label key={branch.id} style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: '0.82rem', marginBottom: 5 }}>
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={() => updateGrokBotIdentityMutation.mutate({
                              ...identity,
                              branch_ids: checked
                                ? identity.branch_ids.filter((id) => id !== branch.id)
                                : [...identity.branch_ids, branch.id],
                            })}
                          />
                          {branch.name}
                        </label>
                      );
                    })}
                  </fieldset>

                  <Button
                    variant="secondary"
                    disabled={!grokBotConfig?.id || rotateGrokBotIdentityMutation.isPending}
                    onClick={() => {
                      const confirmed = window.confirm(
                        `¿Rotar la credencial de ${grokBotProfileLabels[identity.profile]}? La credencial anterior dejará de funcionar de inmediato.`,
                      );
                      if (confirmed) {
                        setRotatedCredential(null);
                        rotateGrokBotIdentityMutation.mutate(identity.profile);
                      }
                    }}
                    style={{ width: '100%' }}
                  >
                    <Key size={16} /> Rotar credencial
                  </Button>
                </section>
              ))}
            </div>
          </div>
        )}

        {/* Facturapi Config Tab */}
        {selectedProvider === 'FACTURAPI' && activeTab === 'config' && canConfigureFiscal && (
          <div style={{ padding: '32px 28px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 28, flexWrap: 'wrap', gap: 16 }}>
              <div>
                <h2 style={{ fontSize: '1.35rem', fontWeight: 800, margin: '0 0 6px', color: '#0f172a', display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ fontSize: '1.5rem' }}>🟣</span>
                  Conector Oficial Facturapi v2 (CFDI 4.0)
                </h2>
                <p style={{ margin: 0, fontSize: '0.9rem', color: '#64748b' }}>
                  Configura las credenciales y los datos fiscales de cada razón social.
                </p>
              </div>
              <div style={{ display: 'flex', gap: 12 }}>
                <Button
                  variant="secondary"
                  onClick={() => testFacturapiMutation.mutate(fiscalDraftScope)}
                  disabled={testFacturapiMutation.isPending || !fiscalFormReady || !facturapiConfig?.version}
                  style={{ display: 'flex', alignItems: 'center', gap: 8, borderColor: '#c084fc', color: '#7e22ce', borderRadius: 10, padding: '10px 18px', fontWeight: 600 }}
                >
                  <Zap size={17} />
                  {testFacturapiMutation.isPending ? 'Probando...' : 'Probar Conexión'}
                </Button>
                <Button
                  variant="primary"
                  onClick={() => saveFacturapiMutation.mutate({payload:facturapiForm,
                    scope:fiscalDraftScope,key:newFiscalKey})}
                  disabled={saveFacturapiMutation.isPending || !fiscalFormReady}
                  style={{ background: '#7e22ce', borderColor: '#6b21a8', borderRadius: 10, padding: '10px 22px', fontWeight: 700, boxShadow: '0 4px 14px rgba(126, 34, 206, 0.3)' }}
                >
                  {saveFacturapiMutation.isPending ? 'Guardando...' : 'Guardar Configuración'}
                </Button>
              </div>
            </div>

            <label htmlFor="fiscal-emitter" style={{display:'block',marginBottom:8}}>Razón social emisora</label>
            <select id="fiscal-emitter" className="premium-select" value={selectedEmitterId}
              onChange={event => setSelectedEmitterId(event.target.value)}>
              <option value="">Selecciona una razón social</option>
              {fiscalEmitters.map(emitter => <option key={emitter.id} value={emitter.id}>
                {emitter.name} — {emitter.tax_id || 'RFC pendiente'}
              </option>)}
            </select>
            <p>La configuración corresponde a la razón social seleccionada.
              {fiscalFormReady && ` Versión ${facturapiConfig?.version}.`}</p>
            {(fiscalEmittersError || fiscalConfigurationError) && <p role="alert">
              No se pudo cargar la configuración fiscal. Vuelve a intentarlo.
            </p>}
            {loadedFiscalDraftScope === fiscalDraftScope && facturapiConfig
              && facturapiForm.version !== facturapiConfig.version && <div role="alert">
              La configuración cambió. Recárgala y revisa la nueva versión antes de guardar.
              <Button variant="secondary" onClick={() => {
                setNewFiscalKey(''); setShowApiKey(false); setFacturapiForm(facturapiConfig);
                setFiscalSaveMessage(null); setFacturapiTestResult(null);
              }}>Recargar configuración</Button>
            </div>}
            {saveFacturapiMutation.error && <p role="alert">{saveFacturapiMutation.error.message}</p>}
            {fiscalSaveMessage && <p role="status">{fiscalSaveMessage}</p>}
            {facturapiTestResult && (
              <div
                style={{
                  padding: '14px 18px',
                  borderRadius: 12,
                  marginBottom: 28,
                  fontSize: '0.9rem',
                  fontWeight: 600,
                  background: facturapiTestResult.success ? '#f0fdf4' : '#fef2f2',
                  border: `1.5px solid ${facturapiTestResult.success ? '#86efac' : '#fca5a5'}`,
                  color: facturapiTestResult.success ? '#15803d' : '#b91c1c',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  boxShadow: '0 2px 6px rgba(0,0,0,0.03)',
                }}
              >
                <span style={{ fontSize: '1.2rem' }}>{facturapiTestResult.success ? '✅' : '❌'}</span>
                {facturapiTestResult.message}
              </div>
            )}

            <fieldset disabled={!fiscalFormReady} style={{border:0,padding:0,margin:0}}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 460px), 1fr))', gap: 24 }}>
              {/* Sección 1: Credenciales & Entorno */}
              <div style={{ background: '#ffffff', padding: 24, borderRadius: 16, border: '1.5px solid #e2e8f0', boxShadow: '0 4px 16px -2px rgba(0, 0, 0, 0.04)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
                  <div style={{ width: 40, height: 40, borderRadius: 10, background: '#f3e8ff', color: '#7e22ce', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <Key size={20} />
                  </div>
                  <div>
                    <h3 style={{ fontSize: '1.05rem', fontWeight: 700, margin: 0, color: '#0f172a' }}>
                      1. Credenciales & Entorno
                    </h3>
                    <p style={{ margin: 0, fontSize: '0.8rem', color: '#64748b' }}>
                      Llave API de acceso a Facturapi
                    </p>
                  </div>
                </div>

                <div style={{ marginBottom: 18 }}>
                  <label
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 12,
                      cursor: 'pointer',
                      fontWeight: 600,
                      fontSize: '0.9rem',
                      background: facturapiForm.is_enabled ? '#faf5ff' : '#f8fafc',
                      padding: '14px 16px',
                      borderRadius: 12,
                      border: facturapiForm.is_enabled ? '1.5px solid #d8b4fe' : '1.5px solid #e2e8f0',
                      color: facturapiForm.is_enabled ? '#581c87' : '#475569',
                      transition: 'all 0.2s',
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={facturapiForm.is_enabled ?? false}
                      onChange={(e) => setFacturapiForm({ ...facturapiForm, is_enabled: e.target.checked })}
                      style={{ width: 19, height: 19, accentColor: '#7e22ce', cursor: 'pointer' }}
                    />
                    <span>Habilitar facturación para esta razón social</span>
                  </label>
                </div>

                <div style={{ marginBottom: 18 }}>
                  <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 700, color: '#334155', marginBottom: 6 }}>
                    Entorno de Timbrado SAT
                  </label>
                  <select
                    className="premium-select"
                    value={facturapiForm.environment ?? ''}
                    onChange={(e) => setFacturapiForm({ ...facturapiForm, environment: e.target.value })}
                  >
                    <option value="">Selecciona el ambiente</option>
                    <option value="sandbox">🧪 Sandbox (Ambiente de Pruebas / Sin validez fiscal)</option>
                    <option value="live">🚀 Producción en Vivo (Timbrado Oficial SAT)</option>
                  </select>
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 700, color: '#334155', marginBottom: 6 }}>
                    Facturapi Secret Key ({facturapiForm.environment === 'sandbox' ? 'sk_test_...' : 'sk_live_...'})
                  </label>
                  <div style={{ position: 'relative' }}>
                    <input
                      type={showApiKey ? 'text' : 'password'}
                      className="premium-input"
                      placeholder="Dejar en blanco conserva la clave"
                      aria-label="Nueva clave de Facturapi"
                      autoComplete="new-password"
                      value={newFiscalKey}
                      onChange={(e) => setNewFiscalKey(e.target.value)}
                      style={{ paddingRight: 44 }}
                    />
                    <button
                      type="button"
                      aria-label={showApiKey ? 'Ocultar nueva clave' : 'Mostrar nueva clave'}
                      onClick={() => setShowApiKey(!showApiKey)}
                      style={{
                        position: 'absolute',
                        right: 12,
                        top: '50%',
                        transform: 'translateY(-50%)',
                        background: 'none',
                        border: 'none',
                        cursor: 'pointer',
                        color: '#64748b',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                    >
                      {showApiKey ? <EyeOff size={18} /> : <Eye size={18} />}
                    </button>
                  </div>
                  <p style={{fontSize: '0.8125rem'}}>{facturapiConfig?.api_key_configured ? 'Clave configurada' : 'Sin clave configurada'}</p>
                  <span style={{ fontSize: '0.75rem', color: '#64748b', marginTop: 6, display: 'block' }}>
                    Obtén tu llave secreta en el panel de <a href="https://dashboard.facturapi.io" target="_blank" rel="noreferrer" style={{ color: '#7e22ce', fontWeight: 600 }}>Facturapi Dashboard</a>.
                  </span>
                </div>
              </div>

              {/* Sección 2: Datos Fiscales del Emisor */}
              <div style={{ background: '#ffffff', padding: 24, borderRadius: 16, border: '1.5px solid #e2e8f0', boxShadow: '0 4px 16px -2px rgba(0, 0, 0, 0.04)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
                  <div style={{ width: 40, height: 40, borderRadius: 10, background: '#f3e8ff', color: '#7e22ce', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <Building2 size={20} />
                  </div>
                  <div>
                    <h3 style={{ fontSize: '1.05rem', fontWeight: 700, margin: 0, color: '#0f172a' }}>
                      2. Datos Fiscales del Emisor
                    </h3>
                    <p style={{ margin: 0, fontSize: '0.8rem', color: '#64748b' }}>
                      Razón social y RFC registrado ante el SAT
                    </p>
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 0.8fr', gap: 14, marginBottom: 16 }}>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 700, color: '#334155', marginBottom: 6 }}>
                      RFC del Emisor (Restaurante) *
                    </label>
                    <input
                      type="text"
                      className="premium-input"
                      placeholder="KIW210101ABC"
                      value={facturapiForm.organization_rfc ?? ''}
                      onChange={(e) => setFacturapiForm({ ...facturapiForm, organization_rfc: e.target.value.toUpperCase() })}
                    />
                  </div>

                  <div>
                    <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 700, color: '#334155', marginBottom: 6 }}>
                      C.P. Fiscal *
                    </label>
                    <input
                      type="text"
                      className="premium-input"
                      placeholder="80000"
                      value={facturapiForm.organization_zip ?? ''}
                      onChange={(e) => setFacturapiForm({ ...facturapiForm, organization_zip: e.target.value })}
                    />
                  </div>
                </div>

                <div style={{ marginBottom: 16 }}>
                  <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 700, color: '#334155', marginBottom: 6 }}>
                    Nombre o Razón Social (Emisor) *
                  </label>
                  <input
                    type="text"
                    className="premium-input"
                    placeholder="RESTAURANTE KIWI SA DE CV"
                    value={facturapiForm.organization_legal_name ?? ''}
                    onChange={(e) => setFacturapiForm({ ...facturapiForm, organization_legal_name: e.target.value.toUpperCase() })}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 700, color: '#334155', marginBottom: 6 }}>
                    Régimen Fiscal del Emisor *
                  </label>
                  <select
                    className="premium-select"
                    value={facturapiForm.organization_tax_system ?? ''}
                    onChange={(e) => setFacturapiForm({ ...facturapiForm, organization_tax_system: e.target.value })}
                  >
                    <option value="">Selecciona el régimen fiscal</option>
                    <option value="601">601 - General de Ley Personas Morales</option>
                    <option value="612">612 - Personas Físicas con Actividades Empresariales</option>
                    <option value="626">626 - Régimen Simplificado de Confianza (RESICO)</option>
                    <option value="605">605 - Sueldos y Salarios e Ingresos Asimilados</option>
                    <option value="616">616 - Sin obligaciones fiscales</option>
                  </select>
                </div>
              </div>

              {/* Sección 3: Parámetros del CFDI */}
              <div style={{ background: '#ffffff', padding: 24, borderRadius: 16, border: '1.5px solid #e2e8f0', boxShadow: '0 4px 16px -2px rgba(0, 0, 0, 0.04)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
                  <div style={{ width: 40, height: 40, borderRadius: 10, background: '#f3e8ff', color: '#7e22ce', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <FileText size={20} />
                  </div>
                  <div>
                    <h3 style={{ fontSize: '1.05rem', fontWeight: 700, margin: 0, color: '#0f172a' }}>
                      3. Parámetros del Comprobante CFDI
                    </h3>
                    <p style={{ margin: 0, fontSize: '0.8rem', color: '#64748b' }}>
                      Series y claves del catálogo SAT
                    </p>
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 16 }}>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 700, color: '#334155', marginBottom: 6 }}>
                      Serie de Factura
                    </label>
                    <input
                      type="text"
                      className="premium-input"
                      placeholder="F"
                      value={facturapiForm.series ?? ''}
                      onChange={(e) => setFacturapiForm({ ...facturapiForm, series: e.target.value.toUpperCase() })}
                    />
                  </div>

                  <div>
                    <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 700, color: '#334155', marginBottom: 6 }}>
                      Clave SAT Producto
                    </label>
                    <input
                      type="text"
                      className="premium-input"
                      placeholder="90101501"
                      value={facturapiForm.default_product_sat_key ?? ''}
                      onChange={(e) => setFacturapiForm({ ...facturapiForm, default_product_sat_key: e.target.value })}
                    />
                  </div>
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 700, color: '#334155', marginBottom: 6 }}>
                    Clave Unidad SAT
                  </label>
                  <input
                    type="text"
                    className="premium-input"
                    placeholder="E48"
                    value={facturapiForm.default_unit_sat_key ?? ''}
                    onChange={(e) => setFacturapiForm({ ...facturapiForm, default_unit_sat_key: e.target.value.toUpperCase() })}
                  />
                  <span style={{ fontSize: '0.75rem', color: '#64748b', marginTop: 6, display: 'block' }}>
                    💡 Clave <code>90101501</code> (Restaurantes) y <code>E48</code> (Unidad de servicio).
                  </span>
                </div>
              </div>

              {/* Sección 4: Autofacturación en Línea */}
              <div style={{ background: '#ffffff', padding: 24, borderRadius: 16, border: '1.5px solid #e2e8f0', boxShadow: '0 4px 16px -2px rgba(0, 0, 0, 0.04)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
                  <div style={{ width: 40, height: 40, borderRadius: 10, background: '#f3e8ff', color: '#7e22ce', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <Globe size={20} />
                  </div>
                  <div>
                    <h3 style={{ fontSize: '1.05rem', fontWeight: 700, margin: 0, color: '#0f172a' }}>
                      4. Portal de Autofactura (Comensales)
                    </h3>
                    <p style={{ margin: 0, fontSize: '0.8rem', color: '#64748b' }}>
                      Facturación en línea vía código QR en ticket
                    </p>
                  </div>
                </div>

                <div style={{ marginBottom: 18 }}>
                  <label
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 12,
                      cursor: 'pointer',
                      fontWeight: 600,
                      fontSize: '0.9rem',
                      background: facturapiForm.enable_self_invoicing ? '#faf5ff' : '#f8fafc',
                      padding: '14px 16px',
                      borderRadius: 12,
                      border: facturapiForm.enable_self_invoicing ? '1.5px solid #d8b4fe' : '1.5px solid #e2e8f0',
                      color: facturapiForm.enable_self_invoicing ? '#581c87' : '#475569',
                      transition: 'all 0.2s',
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={facturapiForm.enable_self_invoicing ?? false}
                      onChange={(e) => setFacturapiForm({ ...facturapiForm, enable_self_invoicing: e.target.checked })}
                      style={{ width: 19, height: 19, accentColor: '#7e22ce', cursor: 'pointer' }}
                    />
                    <span>Habilitar Autofacturación vía QR / E-Receipts</span>
                  </label>
                </div>

                <div style={{ marginBottom: 16 }}>
                  <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 700, color: '#334155', marginBottom: 6 }}>
                    Subdominio en Factura.space
                  </label>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: '0.875rem', color: '#64748b', fontWeight: 600, background: '#f1f5f9', padding: '10px 12px', borderRadius: 8, border: '1px solid #cbd5e1' }}>
                      factura.space/
                    </span>
                    <input
                      type="text"
                      className="premium-input"
                      placeholder="demo"
                      value={facturapiForm.self_invoicing_domain ?? ''}
                      onChange={(e) => setFacturapiForm({ ...facturapiForm, self_invoicing_domain: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '') })}
                      style={{ flex: 1 }}
                    />
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 700, color: '#334155', marginBottom: 6 }}>
                      Días de Vigencia
                    </label>
                    <input
                      type="number"
                      className="premium-input"
                      value={facturapiForm.self_invoicing_days_valid ?? ''}
                      onChange={(e) => setFacturapiForm({ ...facturapiForm,
                        self_invoicing_days_valid: e.target.value === '' ? null : Number(e.target.value) })}
                    />
                  </div>

                  <div>
                    <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 700, color: '#334155', marginBottom: 6 }}>
                      QR en Ticket
                    </label>
                    <select
                      className="premium-select"
                      value={facturapiForm.print_qr_on_ticket ? 'yes' : 'no'}
                      onChange={(e) => setFacturapiForm({ ...facturapiForm, print_qr_on_ticket: e.target.value === 'yes' })}
                    >
                      <option value="yes">Imprimir en Comanda</option>
                      <option value="no">No Imprimir</option>
                    </select>
                  </div>
                </div>
              </div>
            </div>
            </fieldset>
          </div>
        )}

        {/* Facturapi Invoices Tab */}
        {selectedProvider === 'FACTURAPI' && activeTab === 'invoices' && canReadFiscal && (
          <div style={{ padding: 28 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
              <div>
                <h2 style={{ fontSize: '1.25rem', fontWeight: 700, margin: '0 0 4px', color: '#0f172a' }}>
                  Comprobantes Fiscales Digitales (CFDI 4.0)
                </h2>
                <p style={{ margin: 0, fontSize: '0.875rem', color: '#64748b' }}>
                  Consulta el estado de cada comprobante. Los archivos están disponibles cuando se confirma su emisión.
                </p>
              </div>
            </div>

            {downloadError && <p role="alert">{downloadError}</p>}
            {invoiceList.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '48px 20px', color: '#64748b', background: '#f8fafc', borderRadius: 12 }}>
                <FileText size={48} style={{ opacity: 0.3, margin: '0 auto 12px' }} />
                <p style={{ fontWeight: 600, margin: '0 0 4px' }}>No hay facturas emitidas todavía</p>
                <p style={{ fontSize: '0.875rem', margin: 0 }}>
                  Las facturas emitidas desde la pestaña de <strong>Facturación</strong> en el POS aparecerán aquí.
                </p>
              </div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table className="premium-table" style={{ width: '100%' }}>
                  <thead>
                    <tr>
                      <th>Folio</th>
                      <th>Folio Fiscal (UUID SAT)</th>
                      <th>Receptor</th>
                      <th>Fecha</th>
                      <th>Total</th>
                      <th>Estado</th>
                      <th>Descargas</th>
                    </tr>
                  </thead>
                  <tbody>
                    {invoiceList.map((inv) => (
                      <tr key={inv.id}>
                        <td><strong>{inv.folio_number}</strong></td>
                        <td style={{ fontSize: '0.8125rem', fontFamily: 'monospace', color: '#475569' }}>
                          {inv.uuid_sat || 'En proceso'}
                        </td>
                        <td>
                          <div><strong>{inv.nombre_receptor}</strong></div>
                          <span style={{ fontSize: '0.75rem', color: '#64748b' }}>RFC: {inv.rfc_receptor}</span>
                        </td>
                        <td style={{ fontSize: '0.8125rem' }}>{new Date(inv.created_at).toLocaleString()}</td>
                        <td><strong>${(inv.total_cents / 100).toFixed(2)} {inv.currency}</strong></td>
                        <td>
                          <Badge variant={inv.status === 'issued' ? 'success' : inv.status === 'cancelled' ? 'danger' : 'warning'}>
                            {{issued:'Válida',cancelled:'Cancelada',pending:'Pendiente',
                              cancellation_pending:'Cancelación pendiente',rejected:'Rechazada',needs_review:'Revisión requerida'}[inv.status] || 'Estado por verificar'}
                          </Badge>
                        </td>
                        <td>
                          <div style={{ display: 'flex', gap: 8 }}>
                            {inv.pdf_url && (
                              <button type="button" aria-label={`Descargar PDF de ${inv.folio_number}`}
                                onClick={() => downloadFiscalMutation.mutate({id:inv.id,format:'pdf'})}
                                disabled={downloadFiscalMutation.isPending}
                                className="btn btn-outline btn-sm" style={{display:'flex',alignItems:'center',gap:4,minHeight:44,padding:'8px 12px'}}>
                                <Download size={14} /> PDF
                              </button>
                            )}
                            {inv.xml_url && (
                              <button type="button" aria-label={`Descargar XML de ${inv.folio_number}`}
                                onClick={() => downloadFiscalMutation.mutate({id:inv.id,format:'xml'})}
                                disabled={downloadFiscalMutation.isPending}
                                className="btn btn-outline btn-sm" style={{display:'flex',alignItems:'center',gap:4,minHeight:44,padding:'8px 12px'}}>
                                <Download size={14} /> XML
                              </button>
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

        {/* Uber Eats / DiDi / Rappi / WhatsApp Tabs */}
        {isDeliveryProvider && activeTab === 'config' && (
          <div style={{ padding: 28 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24, flexWrap: 'wrap', gap: 16 }}>
              <div>
                <h2 style={{ fontSize: '1.25rem', fontWeight: 700, margin: '0 0 4px', color: '#0f172a' }}>
                  {selectedProvider === 'WHATSAPP'
                    ? 'Configuración de WhatsApp (Asistto Tech Provider)'
                    : `Configuración de API & Webhooks (${selectedProvider})`}
                </h2>
                <p style={{ margin: 0, fontSize: '0.875rem', color: '#64748b' }}>
                  {selectedProvider === 'WHATSAPP'
                    ? 'Conecta RestaurantOS directamente con WhatsApp Business mediante Asistto en modo Coexistencia. Configura el Webhook, URL de retorno y el Prompt Maestro del agente.'
                    : `Registra estas credenciales en el Developer Portal de ${selectedProvider} para recibir pedidos en vivo.`}
                </p>
              </div>
              <div style={{ display: 'flex', gap: 12 }}>
                <Button
                  variant="secondary"
                  onClick={() => setTestOrderModalOpen(true)}
                  style={{ display: 'flex', alignItems: 'center', gap: 8 }}
                >
                  <Play size={16} />
                  {selectedProvider === 'WHATSAPP' ? 'Simular Pedido / Mensaje' : 'Simular Pedido de Prueba'}
                </Button>
                <Button
                  variant="primary"
                  onClick={() => saveConfigMutation.mutate(formData)}
                  disabled={saveConfigMutation.isPending}
                >
                  {saveConfigMutation.isPending ? 'Guardando...' : 'Guardar Cambios'}
                </Button>
              </div>
            </div>

            {/* Webhook URL Box */}
            <div style={{ background: selectedProvider === 'WHATSAPP' ? '#f0fdf4' : '#f0fdf4', border: selectedProvider === 'WHATSAPP' ? '1px solid #86efac' : '1px solid #bbf7d0', borderRadius: 12, padding: '16px 20px', marginBottom: 24 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
                <div>
                  <strong style={{ color: '#166534', fontSize: '0.875rem', display: 'block', marginBottom: 4 }}>
                    {selectedProvider === 'WHATSAPP'
                      ? 'URL Oficial del Webhook de RestaurantOS (Para registrar en Asistto Tech Provider):'
                      : `URL Oficial del Webhook de RestaurantOS (Para registrar en el Developer Portal de ${selectedProvider === 'UBER_EATS' ? 'Uber Eats' : selectedProvider === 'DIDI_FOOD' ? 'DiDi Food' : selectedProvider}):`}
                  </strong>
                  <code style={{ fontSize: '0.875rem', color: '#15803d', wordBreak: 'break-all' }}>{webhookUrl}</code>
                </div>
                <Button
                  variant="secondary"
                  onClick={copyToClipboard}
                  style={{ display: 'flex', alignItems: 'center', gap: 6, borderColor: '#10b981', color: '#047857' }}
                >
                  {copied ? <Check size={16} /> : <Copy size={16} />}
                  {copied ? '¡Copiado!' : 'Copiar URL'}
                </Button>
              </div>

              {selectedProvider === 'WHATSAPP' && (
                <div style={{ marginTop: 14, paddingTop: 14, borderTop: '1px dashed #86efac', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
                  <div>
                    <strong style={{ color: '#166534', fontSize: '0.875rem', display: 'block', marginBottom: 4 }}>
                      Webhook Secret de Entrada (Cópialo y pégalo en Asistto en &quot;Encabezado / Token de Salida&quot;):
                    </strong>
                    <code style={{ fontSize: '0.875rem', color: '#15803d', wordBreak: 'break-all', fontWeight: 700, background: '#dcfce7', padding: '3px 8px', borderRadius: 6 }}>
                      {formData.webhook_secret || 'Generando secreto...'}
                    </code>
                  </div>
                  <Button
                    variant="secondary"
                    onClick={() => copySecretToClipboard(formData.webhook_secret)}
                    style={{ display: 'flex', alignItems: 'center', gap: 6, borderColor: '#10b981', color: '#047857', background: '#fff' }}
                  >
                    {copiedSecret ? <Check size={16} /> : <Copy size={16} />}
                    {copiedSecret ? '¡Copiado!' : 'Copiar Secret'}
                  </Button>
                </div>
              )}
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 20 }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, color: '#475569', marginBottom: 6 }}>
                  Estado de la Integración
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={formData.is_enabled ?? false}
                    onChange={(e) => setFormData({ ...formData, is_enabled: e.target.checked })}
                    style={{ width: 18, height: 18, accentColor: '#10b981' }}
                  />
                  <span style={{ fontWeight: 600 }}>
                    {selectedProvider === 'WHATSAPP'
                      ? 'Activar Agente de WhatsApp en Coexistencia Meta Cloud API'
                      : 'Activar recepción de pedidos en tiempo real'}
                  </span>
                </label>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, color: '#475569', marginBottom: 6 }}>
                  Ambiente
                </label>
                <select
                  className="premium-input"
                  value={formData.environment ?? (selectedProvider === 'WHATSAPP' ? 'production' : 'sandbox')}
                  onChange={(e) => setFormData({ ...formData, environment: e.target.value })}
                >
                  <option value="sandbox">Sandbox (Pruebas de desarrollo)</option>
                  <option value="production">Producción en Vivo</option>
                </select>
              </div>

              {selectedProvider === 'WHATSAPP' ? (
                <>
                  <div style={{ gridColumn: 'span 2' }}>
                    <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, color: '#475569', marginBottom: 6 }}>
                      Return URL de Asistto (URL de Salida para Meta WhatsApp Cloud API)
                    </label>
                    <input
                      type="url"
                      className="premium-input"
                      placeholder="https://asistto.humanio.ai/api/v1/meta/whatsapp/webhook/kiwi-return"
                      value={formData.return_url ?? ''}
                      onChange={(e) => setFormData({ ...formData, return_url: e.target.value })}
                    />
                    <span style={{ fontSize: '0.75rem', color: '#64748b', marginTop: 4, display: 'block' }}>
                      URL provista por Asistto donde Kiwi despacha las respuestas conversacionales y confirmaciones de pedidos.
                    </span>
                  </div>

                  <div>
                    <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, color: '#475569', marginBottom: 6 }}>
                      Token de Autorización de Salida (Bearer para Asistto)
                    </label>
                    <input
                      type="password"
                      className="premium-input"
                      placeholder="asistto_sec_••••••••••••••••"
                      value={formData.client_secret ?? ''}
                      onChange={(e) => setFormData({ ...formData, client_secret: e.target.value })}
                    />
                  </div>

                  <div style={{ gridColumn: 'span 2', background: '#f8fafc', padding: 16, borderRadius: 10, border: '1px solid #e2e8f0' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6, flexWrap: 'wrap', gap: 8 }}>
                      <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 700, color: '#0f172a' }}>
                        Webhook Secret de Entrada (Te lo da Kiwi · Empieza con whsec_...)
                      </label>
                      <div style={{ display: 'flex', gap: 8 }}>
                        <Button
                          variant="secondary"
                          type="button"
                          onClick={() => setShowWebhookSecret(!showWebhookSecret)}
                          style={{ fontSize: '0.75rem', padding: '4px 8px', display: 'flex', alignItems: 'center', gap: 4 }}
                        >
                          {showWebhookSecret ? <EyeOff size={14} /> : <Eye size={14} />}
                          {showWebhookSecret ? 'Ocultar' : 'Revelar'}
                        </Button>
                        <Button
                          variant="secondary"
                          type="button"
                          onClick={() => copySecretToClipboard(formData.webhook_secret)}
                          style={{ fontSize: '0.75rem', padding: '4px 8px', display: 'flex', alignItems: 'center', gap: 4, borderColor: '#10b981', color: '#047857' }}
                        >
                          {copiedSecret ? <Check size={14} /> : <Copy size={14} />}
                          {copiedSecret ? 'Copiado' : 'Copiar'}
                        </Button>
                        <Button
                          variant="secondary"
                          type="button"
                          disabled={regenerateSecretMutation.isPending}
                          onClick={() => {
                            if (window.confirm('¿Seguro que deseas regenerar el Webhook Secret? Deberás actualizar el nuevo valor en Asistto para que los pedidos continúen sincronizando.')) {
                              regenerateSecretMutation.mutate();
                            }
                          }}
                          style={{ fontSize: '0.75rem', padding: '4px 8px', color: '#b91c1c', borderColor: '#fca5a5' }}
                        >
                          {regenerateSecretMutation.isPending ? 'Regenerando...' : 'Regenerar'}
                        </Button>
                      </div>
                    </div>
                    <input
                      type={showWebhookSecret ? 'text' : 'password'}
                      className="premium-input"
                      readOnly
                      placeholder="whsec_••••••••••••••••"
                      value={formData.webhook_secret ?? ''}
                      style={{ fontFamily: 'monospace', fontWeight: 600, background: '#f1f5f9' }}
                    />
                    <span style={{ fontSize: '0.75rem', color: '#64748b', marginTop: 6, display: 'block', lineHeight: 1.4 }}>
                      Este valor criptográfico único lo genera automáticamente RestaurantOS. Cópialo y pégalo en Asistto en el campo <strong>&quot;Encabezado / Token de Salida (hacia tu Sistema)&quot;</strong> para autenticar y firmar las peticiones entrantes.
                    </span>
                  </div>

                  <div>
                    <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, color: '#475569', marginBottom: 6 }}>
                      WABA Phone ID / Número de WhatsApp del Negocio
                    </label>
                    <input
                      type="text"
                      className="premium-input"
                      placeholder="+523312345678 o Phone Number ID"
                      value={formData.client_id ?? ''}
                      onChange={(e) => setFormData({ ...formData, client_id: e.target.value })}
                    />
                  </div>

                  <div>
                    <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, color: '#475569', marginBottom: 6 }}>
                      Tiempo Estimado de Preparación por Defecto
                    </label>
                    <input
                      type="number"
                      className="premium-input"
                      value={formData.default_prep_time_minutes ?? 25}
                      onChange={(e) => setFormData({ ...formData, default_prep_time_minutes: parseInt(e.target.value) || 25 })}
                    />
                  </div>

                  <div style={{ gridColumn: 'span 2' }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer', padding: '12px 14px', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 10 }}>
                      <input
                        type="checkbox"
                        checked={formData.auto_accept ?? false}
                        onChange={(e) => setFormData({ ...formData, auto_accept: e.target.checked })}
                        style={{ width: 18, height: 18, accentColor: '#10b981' }}
                      />
                      <div>
                        <span style={{ fontWeight: 600, color: '#0f172a', display: 'block' }}>
                          Aceptación automática de pedidos
                        </span>
                        <span style={{ fontSize: '0.78rem', color: '#64748b' }}>
                          Si está desactivado (recomendado), los pedidos de WhatsApp entran en estado PENDIENTE incluso con la caja cerrada para ser revisados por un humano en la apertura del turno.
                        </span>
                      </div>
                    </label>
                  </div>

                  <div style={{ gridColumn: '1 / -1', marginTop: 8, borderTop: '1px solid #e2e8f0', paddingTop: 20 }}>
                    <label style={{ display: 'block', fontSize: '0.9375rem', fontWeight: 700, color: '#0f172a', marginBottom: 6 }}>
                      Prompt Maestro del Agente Conversacional (Kiwi en WhatsApp)
                    </label>
                    <p style={{ margin: '0 0 10px', fontSize: '0.8125rem', color: '#64748b', lineHeight: 1.5 }}>
                      Instrucciones canónicas que guían las respuestas del agente, el tono de voz y las recomendaciones de platillos.
                      Variables disponibles en tiempo de ejecución:
                      <code style={{ background: '#f1f5f9', color: '#0f766e', padding: '2px 6px', borderRadius: 4, margin: '0 4px', fontWeight: 600 }}>{'{customer_name}'}</code>,
                      <code style={{ background: '#f1f5f9', color: '#0f766e', padding: '2px 6px', borderRadius: 4, margin: '0 4px', fontWeight: 600 }}>{'{past_orders}'}</code>,
                      <code style={{ background: '#f1f5f9', color: '#0f766e', padding: '2px 6px', borderRadius: 4, margin: '0 4px', fontWeight: 600 }}>{'{favorite_dishes}'}</code>,
                      <code style={{ background: '#f1f5f9', color: '#0f766e', padding: '2px 6px', borderRadius: 4, margin: '0 4px', fontWeight: 600 }}>{'{delivery_address}'}</code>,
                      <code style={{ background: '#f1f5f9', color: '#0f766e', padding: '2px 6px', borderRadius: 4, margin: '0 4px', fontWeight: 600 }}>{'{menu_items}'}</code>,
                      <code style={{ background: '#f1f5f9', color: '#0f766e', padding: '2px 6px', borderRadius: 4, margin: '0 4px', fontWeight: 600 }}>{'{active_branch}'}</code>.
                    </p>
                    <textarea
                      className="premium-input"
                      rows={8}
                      placeholder="Eres el anfitrión y sommelier virtual de Kiwi. Saluda cálidamente al cliente por su nombre {customer_name} si ya está registrado, confirma si desea recibir su pedido en su dirección habitual {delivery_address}, y recomiéndale sus favoritos como {favorite_dishes}. Cotiza únicamente con los precios oficiales vigentes en centavos sin inventar montos ni promociones no autorizadas..."
                      value={formData.master_prompt ?? ''}
                      onChange={(e) => setFormData({ ...formData, master_prompt: e.target.value })}
                      style={{ width: '100%', fontFamily: 'monospace', fontSize: '0.875rem', lineHeight: 1.5, resize: 'vertical' }}
                    />
                  </div>
                </>
              ) : (
                <>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, color: '#475569', marginBottom: 6 }}>
                      {selectedProvider === 'UBER_EATS' ? 'Client ID (App ID de Uber)' : selectedProvider === 'DIDI_FOOD' ? 'App ID (DiDi Food OpenPlatform)' : selectedProvider === 'RAPPI' ? 'Client ID (Rappi Partners API)' : 'Client ID'}
                    </label>
                    <input
                      type="text"
                      className="premium-input"
                      placeholder={selectedProvider === 'UBER_EATS' ? 'ub_client_id_...' : selectedProvider === 'DIDI_FOOD' ? 'didi_app_...' : selectedProvider === 'RAPPI' ? 'rp_client_id_...' : 'client_id_...'}
                      value={formData.client_id ?? ''}
                      onChange={(e) => setFormData({ ...formData, client_id: e.target.value })}
                    />
                  </div>

                  <div>
                    <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, color: '#475569', marginBottom: 6 }}>
                      {selectedProvider === 'UBER_EATS' ? 'Client Secret' : selectedProvider === 'DIDI_FOOD' ? 'App Secret' : selectedProvider === 'RAPPI' ? 'Client Secret (Rappi Partners)' : 'Client Secret'}
                    </label>
                    <input
                      type="password"
                      className="premium-input"
                      placeholder="••••••••••••••••"
                      value={formData.client_secret ?? ''}
                      onChange={(e) => setFormData({ ...formData, client_secret: e.target.value })}
                    />
                  </div>

                  <div>
                    <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, color: '#475569', marginBottom: 6 }}>
                      Webhook Signing Secret (Firma HMAC-SHA256)
                    </label>
                    <input
                      type="password"
                      className="premium-input"
                      placeholder="whsec_••••••••••••••••"
                      value={formData.webhook_secret ?? ''}
                      onChange={(e) => setFormData({ ...formData, webhook_secret: e.target.value })}
                    />
                  </div>

                  <div>
                    <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, color: '#475569', marginBottom: 6 }}>
                      Tiempo Estimado de Preparación por Defecto
                    </label>
                    <input
                      type="number"
                      className="premium-input"
                      value={formData.default_prep_time_minutes ?? 20}
                      onChange={(e) => setFormData({ ...formData, default_prep_time_minutes: parseInt(e.target.value) || 20 })}
                    />
                  </div>
                </>
              )}
            </div>
          </div>
        )}

        {/* Stores Mappings Tab */}
        {isDeliveryProvider && activeTab === 'stores' && (
          <div style={{ padding: 28 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
              <div>
                <h2 style={{ fontSize: '1.25rem', fontWeight: 700, margin: '0 0 4px', color: '#0f172a' }}>
                  Vinculación de Sucursales Físicas con {selectedProvider === 'UBER_EATS' ? 'Uber Eats' : selectedProvider === 'DIDI_FOOD' ? 'DiDi Food' : selectedProvider === 'RAPPI' ? 'Rappi' : selectedProvider}
                </h2>
                <p style={{ margin: 0, fontSize: '0.875rem', color: '#64748b' }}>
                  Asocia el {selectedProvider === 'UBER_EATS' ? 'Store UUID' : selectedProvider === 'DIDI_FOOD' ? 'Shop ID / Store ID' : selectedProvider === 'RAPPI' ? 'Store ID de Rappi' : 'Store ID'} de cada tienda en la plataforma externa con la sucursal de Kiwi.
                </p>
              </div>
              <Button variant="primary" onClick={() => setMappingModalOpen(true)}>
                + Vincular Sucursal
              </Button>
            </div>

            {storeMappings.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '48px 20px', color: '#64748b', background: '#f8fafc', borderRadius: 12 }}>
                <Building2 size={48} style={{ opacity: 0.3, margin: '0 auto 12px' }} />
                <p style={{ fontWeight: 600, margin: '0 0 4px' }}>No hay sucursales vinculadas aún</p>
                <p style={{ fontSize: '0.875rem', margin: 0 }}>
                  Agrega una vinculación para que los pedidos de {selectedProvider === 'UBER_EATS' ? 'Uber' : selectedProvider === 'DIDI_FOOD' ? 'DiDi' : selectedProvider === 'RAPPI' ? 'Rappi' : 'Delivery'} se dirijan a la cocina correcta.
                </p>
              </div>
            ) : (
              <table className="premium-table" style={{ width: '100%' }}>
                <thead>
                  <tr>
                    <th>Sucursal Local</th>
                    <th>Código</th>
                    <th>{selectedProvider === 'UBER_EATS' ? 'Store UUID Externo' : selectedProvider === 'DIDI_FOOD' ? 'Shop ID / Store ID' : selectedProvider === 'RAPPI' ? 'Store ID Rappi' : 'Store ID Externo'}</th>
                    <th>Estado</th>
                    <th>Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {storeMappings.map((m) => (
                    <tr key={m.id}>
                      <td><strong>{m.branch_name}</strong></td>
                      <td><Badge variant="default">{m.branch_code}</Badge></td>
                      <td><code style={{ fontSize: '0.8125rem' }}>{m.external_store_id}</code></td>
                      <td><Badge variant={m.is_active ? 'success' : 'default'}>{m.is_active ? 'Activa' : 'Inactiva'}</Badge></td>
                      <td>
                        <Button
                          variant="secondary"
                          onClick={() => deleteMappingMutation.mutate(m.id)}
                          style={{ color: '#ef4444', borderColor: '#fca5a5', padding: '4px 8px' }}
                        >
                          <Trash2 size={16} />
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}

        {/* Logs Tab */}
        {isDeliveryProvider && activeTab === 'logs' && (
          <div style={{ padding: 28 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
              <div>
                <h2 style={{ fontSize: '1.25rem', fontWeight: 700, margin: '0 0 4px', color: '#0f172a' }}>
                  Bitácora de Webhooks en Vivo ({selectedProvider === 'UBER_EATS' ? 'Uber Eats' : selectedProvider === 'DIDI_FOOD' ? 'DiDi Food' : selectedProvider})
                </h2>
                <p style={{ margin: 0, fontSize: '0.875rem', color: '#64748b' }}>
                  Monitorea las notificaciones HTTP enviadas por la plataforma en tiempo real.
                </p>
              </div>
            </div>

            {logs.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '48px 20px', color: '#64748b', background: '#f8fafc', borderRadius: 12 }}>
                <Activity size={48} style={{ opacity: 0.3, margin: '0 auto 12px' }} />
                <p style={{ fontWeight: 600, margin: '0 0 4px' }}>No hay eventos registrados</p>
                <p style={{ fontSize: '0.875rem', margin: 0 }}>
                  Los webhooks recibidos aparecerán aquí automáticamente.
                </p>
              </div>
            ) : (
              <table className="premium-table" style={{ width: '100%' }}>
                <thead>
                  <tr>
                    <th>Fecha / Hora</th>
                    <th>Evento</th>
                    <th>Estado</th>
                    <th>ID Externo</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map((log) => (
                    <tr key={log.id}>
                      <td style={{ fontSize: '0.8125rem' }}>{new Date(log.created_at).toLocaleString()}</td>
                      <td><strong>{log.event_type}</strong></td>
                      <td>
                        <Badge variant={log.status === 'processed' ? 'success' : log.status === 'failed' ? 'danger' : 'default'}>
                          {log.status}
                        </Badge>
                      </td>
                      <td><code style={{ fontSize: '0.8125rem' }}>{log.event_id || '-'}</code></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>

      {/* Modal Vincular Sucursal */}
      <Modal
        isOpen={mappingModalOpen}
        onClose={() => setMappingModalOpen(false)}
        title={`Vincular Sucursal con ${selectedProvider === 'UBER_EATS' ? 'Uber Eats' : selectedProvider === 'DIDI_FOOD' ? 'DiDi Food' : selectedProvider === 'RAPPI' ? 'Rappi' : selectedProvider}`}
      >
        <div style={{ padding: '8px 0' }}>
          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, color: '#475569', marginBottom: 6 }}>
              Sucursal Local
            </label>
            <select
              className="premium-input"
              value={newMappingBranchId}
              onChange={(e) => setNewMappingBranchId(e.target.value)}
            >
              <option value="">Selecciona una sucursal...</option>
              {branches.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name} ({b.code})
                </option>
              ))}
            </select>
          </div>

          <div style={{ marginBottom: 20 }}>
            <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, color: '#475569', marginBottom: 6 }}>
              {selectedProvider === 'UBER_EATS' ? 'Store UUID de Uber Eats' : selectedProvider === 'DIDI_FOOD' ? 'Shop ID / Store ID de DiDi Food' : selectedProvider === 'RAPPI' ? 'Store ID de Rappi' : 'Store ID Externo'}
            </label>
            <input
              type="text"
              className="premium-input"
              placeholder={selectedProvider === 'UBER_EATS' ? 'e.g. 7c32e189-9e8a-495f-9e84-18349281a812' : selectedProvider === 'DIDI_FOOD' ? 'e.g. didi_shop_guadalajara_01' : selectedProvider === 'RAPPI' ? 'e.g. rappi_store_guadalajara_01' : 'e.g. store_id_01'}
              value={newMappingStoreId}
              onChange={(e) => setNewMappingStoreId(e.target.value)}
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12 }}>
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
              {saveMappingMutation.isPending ? 'Vinculando...' : 'Guardar Vinculación'}
            </Button>
          </div>
        </div>
      </Modal>

      {/* Modal Simular Pedido */}
      <Modal
        isOpen={testOrderModalOpen}
        onClose={() => { setTestOrderModalOpen(false); setTestOrderResult(null); }}
        title={`Simular Pedido de ${selectedProvider === 'UBER_EATS' ? 'Uber Eats' : selectedProvider === 'DIDI_FOOD' ? 'DiDi Food' : selectedProvider === 'RAPPI' ? 'Rappi' : selectedProvider} (Sandbox)`}
      >
        <div style={{ padding: '8px 0' }}>
          <p style={{ fontSize: '0.875rem', color: '#64748b', marginBottom: 16 }}>
            Esta herramienta genera una orden simulada que viajará por el mismo flujo que un pedido real de {selectedProvider === 'UBER_EATS' ? 'Uber Eats' : selectedProvider === 'DIDI_FOOD' ? 'DiDi Food' : selectedProvider === 'RAPPI' ? 'Rappi' : selectedProvider}.
          </p>

          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, color: '#475569', marginBottom: 6 }}>
              Nombre del Cliente Simulado
            </label>
            <input
              type="text"
              className="premium-input"
              value={testOrderCustomer}
              onChange={(e) => setTestOrderCustomer(e.target.value)}
            />
          </div>

          <div style={{ marginBottom: 20 }}>
            <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, color: '#475569', marginBottom: 6 }}>
              Cantidad de Productos
            </label>
            <select
              className="premium-input"
              value={testOrderItemsCount}
              onChange={(e) => setTestOrderItemsCount(parseInt(e.target.value) || 1)}
            >
              <option value={1}>1 Producto aleatorio</option>
              <option value={2}>2 Productos aleatorios</option>
              <option value={3}>3 Productos aleatorios</option>
            </select>
          </div>

          {testOrderResult && (
            <div style={{ padding: 12, background: '#f8fafc', borderRadius: 8, border: '1px solid #e2e8f0', marginBottom: 20, fontSize: '0.875rem', fontWeight: 500 }}>
              {testOrderResult}
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12 }}>
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
              {simulateOrderMutation.isPending ? 'Enviando...' : 'Disparar Pedido'}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
