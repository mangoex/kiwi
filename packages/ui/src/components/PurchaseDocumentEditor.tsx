import React, { useEffect, useReducer, useRef, useState } from 'react';
import { Plus, Sparkles, Trash2 } from 'lucide-react';
import { Button } from './Button';
import { Modal } from './Modal';
import { branchLocalDate, initialPurchaseDraft, purchaseDraftReducer, purchasePayload, restorePurchaseDraft, type PurchaseDraft } from './purchaseDraft';
import { usePythonPreview, type WorkspaceRequest } from './usePythonPreview';
import './PurchaseDocumentEditor.css';
import { registerWorkspaceNavigationGuard, confirmWorkspaceNavigation } from './workspaceNavigation';
import { isWorkspaceRejection } from './workspaceRecovery';
import { registerWorkspaceSnapshot, readWorkspaceSnapshot, discardWorkspaceSnapshot } from './workspaceSessionRecovery';

export interface WorkspaceSupplier { id: string; commercial_name: string }
export interface WorkspacePresentation { id: string; supplier_id: string; item_id: string; name: string; item_name: string; item_sku: string; supplier_name: string; last_net_price: string | number; base_unit_yield?: string | number; base_unit_code?: string }
export interface PurchaseAiExtractResponse {
  source_kind: string;
  status: 'ready' | 'needs_review' | 'insufficient_data';
  supplier_id: string;
  supplier_name: string;
  folio: string;
  document_date: string;
  delivered_by_name: string;
  payment_method: string;
  notes: string;
  lines: {
    presentation_id: string;
    presentation_name: string;
    item_name: string;
    raw_description: string;
    quantity: string;
    unit_price: string;
    discount: string;
    tax: string;
    match_status: 'matched' | 'cross_supplier' | 'unmatched';
  }[];
  warnings: { line_number: number; code: string; raw: string }[];
}
export interface PurchasePreview {
  context_fingerprint: string;
  source: 'python'; subtotal: string; discount_total: string; tax_total: string; total: string;
  lines: { presentation_snapshot: { name: string; base_unit_code?: string; base_unit_yield: string }; base_quantity: string; inventory_cost: string; cost_per_base_unit: string; line_total: string }[];
}
export interface PurchaseDocumentEditorProps {
  scope: string; branchId: string; branchTimeZone: string; isOpen: boolean; onClose: () => void;
  suppliers: WorkspaceSupplier[]; presentations: WorkspacePresentation[];
  request: WorkspaceRequest; onCreated: () => void | Promise<void>; initialSupplierId?: string;
  catalogTools?: (supplierId: string, done: () => void) => React.ReactNode;
}
export function PurchaseDocumentEditor(props: PurchaseDocumentEditorProps) {
  const { scope, branchId, branchTimeZone, isOpen, onClose, suppliers, presentations, request, onCreated, initialSupplierId = '', catalogTools } = props;
  const recoveryKey = 'purchase:' + scope;
  const [draft, dispatch] = useReducer(purchaseDraftReducer, null, () => {
    const saved = readWorkspaceSnapshot<PurchaseDraft>(recoveryKey);
    return saved && saved.scope === scope && saved.branch_id === branchId
      ? restorePurchaseDraft(saved)
      : { ...initialPurchaseDraft(scope, branchId, '', 'purchase-create-' + crypto.randomUUID(), crypto.randomUUID()), supplier_id: initialSupplierId };
  });
  const recoveryDraft = useRef(draft);
  recoveryDraft.current = draft;
  const presentationRefs = useRef(new Map<string, HTMLSelectElement>());
  const pendingLineFocus = useRef<string | null>(null);
  useEffect(() => {
    if (isOpen) dispatch({ type: 'defaultDate', value: branchLocalDate(branchTimeZone) });
  }, [isOpen, branchTimeZone]);
  useEffect(() => {
    const id = pendingLineFocus.current;
    const target = id ? presentationRefs.current.get(id) : undefined;
    if (target) { target.focus(); pendingLineFocus.current = null; }
  }, [draft.lines]);
  useEffect(() => {
    discardWorkspaceSnapshot(recoveryKey);
    return registerWorkspaceSnapshot(recoveryKey, () => recoveryDraft.current.dirty || recoveryDraft.current.phase !== 'editing' ? recoveryDraft.current : null);
  }, [recoveryKey]);
  const [catalogOpen, setCatalogOpen] = useState(false);
  const [aiOpen, setAiOpen] = useState(false);
  const [aiRawText, setAiRawText] = useState('');
  const [aiFile, setAiFile] = useState<File | null>(null);
  const [aiPending, setAiPending] = useState(false);
  const [aiError, setAiError] = useState('');
  const [aiNotice, setAiNotice] = useState('');
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const submitting = useRef(false);
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  useEffect(() => { if (initialSupplierId) dispatch({ type: 'header', key: 'supplier_id', value: initialSupplierId }); }, [initialSupplierId]);
  const payload = purchasePayload(draft);
  const preview = usePythonPreview<PurchasePreview>(request, '/purchases/preview', payload, isOpen && draft.phase === 'editing' && Boolean(draft.document_date));
  const locked = draft.phase !== 'editing';
  const hasCapture = draft.dirty || Boolean(draft.supplier_id);
  useEffect(() => {
    if (!hasCapture && !locked) return;
    const unregister = registerWorkspaceNavigationGuard(() => {
      if (locked) { window.alert('Recupera el resultado de la nota antes de cambiar de página o sucursal.'); return false; }
      return window.confirm('Tienes una nota de compra sin terminar. ¿Confirmas abandonar esta captura?');
    });
    const unload = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ''; };
    const navigate = (event: MouseEvent) => {
      const link = (event.target as Element)?.closest?.('a[href]') as HTMLAnchorElement | null;
      if (link && link.target !== '_blank' && !event.ctrlKey && !event.metaKey && !event.shiftKey && !confirmWorkspaceNavigation()) { event.preventDefault(); event.stopPropagation(); }
    };
    window.addEventListener('beforeunload', unload);
    document.addEventListener('click', navigate, true);
    return () => { unregister(); window.removeEventListener('beforeunload', unload); document.removeEventListener('click', navigate, true); };
  }, [hasCapture, locked]);
  const exceptionReasonValid = !draft.supplier_catalog_exception || Boolean(draft.supplier_catalog_exception_reason.trim());
  const compatible = Boolean(draft.document_date) && exceptionReasonValid && draft.lines.every(line => presentations.some(pres => (
    pres.id === line.presentation_id
    && (pres.supplier_id === draft.supplier_id || draft.supplier_catalog_exception)
  )));
  const close = () => { if (!locked) onClose(); };
  const runAiExtraction = async () => {
    if (locked || aiPending || (!aiFile && !aiRawText.trim())) return;
    setAiPending(true);
    setAiError('');
    setAiNotice('');
    try {
      let fileBase64 = '';
      let mimeType = '';
      let filename = '';
      if (aiFile) {
        filename = aiFile.name;
        mimeType = aiFile.type || '';
        fileBase64 = await new Promise<string>((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = () => resolve(String(reader.result || ''));
          reader.onerror = () => reject(new Error('No se pudo leer el archivo seleccionado.'));
          reader.readAsDataURL(aiFile);
        });
      }
      const response = await request('/purchases/ai-extract', {
        method: 'POST',
        body: JSON.stringify({
          branch_id: branchId,
          ...(aiRawText.trim() ? { raw_text: aiRawText.trim() } : {}),
          ...(fileBase64 ? { file_base64: fileBase64, mime_type: mimeType, filename } : {}),
        }),
      }) as PurchaseAiExtractResponse;
      if (!alive.current) return;
      if (!response.lines || response.lines.length === 0) {
        setAiError('No se detectaron partidas válidas en el documento o lista. Verifica el archivo o texto e intenta nuevamente.');
        return;
      }
      dispatch({
        type: 'applyExtraction',
        extraction: {
          supplier_id: response.supplier_id,
          folio: response.folio,
          document_date: response.document_date,
          delivered_by_name: response.delivered_by_name,
          payment_method: response.payment_method,
          notes: response.notes,
          lines: response.lines.map(item => ({
            id: crypto.randomUUID(),
            presentation_id: item.presentation_id,
            quantity: item.quantity,
            unit_price: item.unit_price,
            discount: item.discount,
            tax: item.tax,
            ai_description: item.raw_description,
            ai_match_status: item.match_status,
          })),
        },
      });
      const unmatchedCount = response.lines.filter(item => item.match_status !== 'matched').length;
      const warningCount = response.warnings?.length || 0;
      setAiNotice(
        unmatchedCount > 0 || warningCount > 0
          ? `Se cargaron ${response.lines.length} partida(s) al borrador (${unmatchedCount} por conciliar manualmente${warningCount > 0 ? `, ${warningCount} renglón(es) omitidos por formato` : ''}). Revisa antes de guardar.`
          : `Se autocompletaron ${response.lines.length} partida(s) conciliadas con el catálogo. Revisa los importes antes de guardar.`
      );
    } catch (cause) {
      if (alive.current) {
        setAiError(cause instanceof Error ? cause.message : 'No fue posible extraer los datos del comprobante.');
      }
    } finally {
      if (alive.current) setAiPending(false);
    }
  };
  const submit = async () => {
    if (submitting.current || (!preview.data && draft.phase !== 'uncertain')) return;
    submitting.current = true;
    const fingerprint = draft.phase === 'uncertain' ? draft.reviewFingerprint : preview.data?.context_fingerprint;
    dispatch({ type: 'submit', fingerprint });
    recoveryDraft.current = purchaseDraftReducer(draft, { type: 'submit', fingerprint });
    let applied = false;
    try {
      await request('/purchases', { method: 'POST', headers: { 'Idempotency-Key': draft.creationKey, 'If-Purchase-Preview': fingerprint || '' }, body: JSON.stringify(payload) });
      applied = true;
      if (!alive.current) return;
      await onCreated();
      // Caller remounts on creation; the successful result is never retried as a new intent.
      onClose();
    } catch (cause) {
      const status = (cause as { status?: number }).status;
      const code = (cause as { code?: string }).code || '';
      const rejected = !applied && isWorkspaceRejection(status, code, draft.phase === 'uncertain', 'purchase');
      dispatch({ type: rejected ? 'resolved' : 'uncertain', message: cause instanceof Error ? cause.message : 'No se pudo recuperar el resultado.' });
    } finally { submitting.current = false; }
  };
  return <Modal isOpen={isOpen} onClose={close} title="Registrar nota de compra" maxWidth="1120px" contentClassName="purchase-document-modal">
    <div className="purchase-workspace">
      {draft.message && <p role="alert">{draft.message}</p>}
      {draft.phase === 'uncertain' && <p role="status">La respuesta no se confirmó. Recupera la misma nota antes de continuar; conserva esta ventana abierta.</p>}
      <section className="purchase-ai-box" aria-label="Asistente de autocompletado de compra">
        <div className="purchase-ai-header">
          <div>
            <strong><Sparkles size={15} aria-hidden="true" /> Autocompletar con IA (Foto, PDF, XML o lista en papel)</strong>
            <p className="purchase-ai-subtitle">Sube una foto/PDF/XML de tu nota o factura, o pega tu lista de compras para prellenar cabecera y partidas.</p>
          </div>
          <Button type="button" size="sm" variant="secondary" disabled={locked} onClick={() => setAiOpen(prev => !prev)}>
            {aiOpen ? 'Ocultar asistente' : 'Subir archivo o pegar lista'}
          </Button>
        </div>
        {aiOpen && <div className="purchase-ai-body">
          <div className="purchase-ai-inputs">
            <label>Archivo de factura, nota o foto (JPG, PNG, WEBP, PDF o XML CFDI)
              <input
                ref={fileInputRef}
                type="file"
                disabled={locked || aiPending}
                accept="image/jpeg,image/png,image/webp,application/pdf,application/xml,text/xml,.xml,.pdf,.png,.jpg,.jpeg,.webp"
                onChange={e => {
                  const selected = e.target.files?.[0] || null;
                  setAiFile(selected);
                  setAiError('');
                }}
              />
            </label>
            <label>Lista de compras en papel o texto del comprobante (opcional)
              <textarea
                rows={3}
                disabled={locked || aiPending}
                value={aiRawText}
                onChange={e => { setAiRawText(e.target.value); setAiError(''); }}
                placeholder={'Ejemplo:\nProveedor: Panadería del Pacífico\nFolio: NOTA-104\n- 2 Caja Pan Brioche x 50 $500.00'}
              />
            </label>
          </div>
          <div className="purchase-ai-actions">
            {(aiFile || aiRawText) && <Button type="button" size="sm" variant="ghost" disabled={locked || aiPending} onClick={() => {
              setAiFile(null);
              setAiRawText('');
              setAiError('');
              setAiNotice('');
              if (fileInputRef.current) fileInputRef.current.value = '';
            }}>Limpiar entrada</Button>}
            <Button type="button" size="sm" disabled={locked || aiPending || (!aiFile && !aiRawText.trim())} onClick={() => void runAiExtraction()}>
              {aiPending ? 'Analizando comprobante…' : 'Extraer y llenar captura'}
            </Button>
          </div>
        </div>}
        {aiNotice && <p role="status" className="purchase-ai-notice">{aiNotice}</p>}
        {aiError && <p role="alert" className="purchase-ai-error">{aiError}</p>}
      </section>
      <fieldset disabled={locked} className="purchase-fields">
        <label>Proveedor<select value={draft.supplier_id} onChange={e => dispatch({ type: 'header', key: 'supplier_id', value: e.target.value })}><option value="">Selecciona proveedor</option>{suppliers.map(item => <option key={item.id} value={item.id}>{item.commercial_name}</option>)}</select></label>
        <label>Tipo de documento<select value={draft.document_type} onChange={e => dispatch({ type: 'header', key: 'document_type', value: e.target.value })}>{[['invoice', 'Factura'], ['ticket', 'Ticket'], ['note', 'Nota'], ['receipt', 'Recibo']].map(([value, text]) => <option key={value} value={value}>{text}</option>)}</select></label>
        <label>Folio<input maxLength={80} value={draft.folio} onChange={e => dispatch({ type: 'header', key: 'folio', value: e.target.value })} /></label>
        <label>Fecha del comprobante<input type="date" value={draft.document_date} onChange={e => dispatch({ type: 'header', key: 'document_date', value: e.target.value })} /></label>
        <label>Nombre de quien entrega<input maxLength={160} autoComplete="off" value={draft.delivered_by_name} onChange={e => dispatch({ type: 'header', key: 'delivered_by_name', value: e.target.value })} /></label>
        <label>Forma de pago<select value={draft.payment_method} onChange={e => dispatch({ type: 'header', key: 'payment_method', value: e.target.value })}><option value="cash">Efectivo de caja</option><option value="transfer">Transferencia</option><option value="card">Tarjeta</option><option value="other">Otro</option></select></label>
        <label>Notas<input maxLength={600} value={draft.notes} onChange={e => dispatch({ type: 'header', key: 'notes', value: e.target.value })} /></label>
        <label>Referencia de evidencia<input maxLength={600} value={draft.evidence_url} onChange={e => dispatch({ type: 'header', key: 'evidence_url', value: e.target.value })} /></label>
        <label className="purchase-exception-toggle"><input type="checkbox" checked={Boolean(draft.supplier_catalog_exception)} onChange={e => dispatch({ type: 'supplierException', value: e.target.checked })} /> Compra excepcional con presentación de otro proveedor</label>
        {draft.supplier_catalog_exception && <label>Motivo de la excepción<input required maxLength={240} value={draft.supplier_catalog_exception_reason || ''} onChange={e => dispatch({ type: 'header', key: 'supplier_catalog_exception_reason', value: e.target.value })} placeholder="Ej. compra urgente por desabasto" /></label>}
      </fieldset>
      <h4>Partidas de Compra</h4>
      <fieldset disabled={locked} className="purchase-lines">
        {draft.lines.map((line, index) => {
          const supplierChoices = presentations.filter(item => item.supplier_id === draft.supplier_id);
          const choices = draft.supplier_catalog_exception ? presentations : supplierChoices;
          const groupedChoices = choices.reduce<Map<string, { label: string; presentations: WorkspacePresentation[] }>>((groups, item) => {
            const itemName = item.item_name || 'Producto sin nombre';
            const groupKey = item.item_id || `${itemName}:${item.item_sku}`;
            const current = groups.get(groupKey);
            groups.set(groupKey, {
              label: `${itemName} · SKU ${item.item_sku || 'sin SKU'}`,
              presentations: [...(current?.presentations || []), item],
            });
            return groups;
          }, new Map());
          const mismatch = Boolean(line.presentation_id && !supplierChoices.some(item => item.id === line.presentation_id));
          const calc = preview.data?.lines[index];
          return <div key={line.id} className="purchase-line">
            <label>Presentación · renglón {index + 1}<select ref={element => { if (element) presentationRefs.current.set(line.id, element); else presentationRefs.current.delete(line.id); }} value={line.presentation_id} onChange={e => {
              dispatch({ type: 'line', id: line.id, key: 'presentation_id', value: e.target.value });
              const selected = presentations.find(item => item.id === e.target.value);
              const keepExtractedPrice = Boolean(line.ai_description && line.unit_price);
              if (!keepExtractedPrice) {
                dispatch({ type: 'line', id: line.id, key: 'unit_price', value: selected ? String(selected.last_net_price) : '' });
              }
            }}><option value="">Selecciona producto y presentación</option>{mismatch && !draft.supplier_catalog_exception && <option value={line.presentation_id}>Revisar: presentación de otro proveedor</option>}{Array.from(groupedChoices.entries()).map(([itemId, group]) => <optgroup key={itemId} label={group.label}>{group.presentations.map(item => <option key={item.id} value={item.id}>{item.name} · {item.base_unit_yield} {item.base_unit_code}{draft.supplier_catalog_exception ? ` · ${item.supplier_name}` : ''}</option>)}</optgroup>)}</select></label>
            {(['quantity', 'unit_price', 'discount', 'tax'] as const).map((key, i) => <label key={key}>{['Cantidad', 'Precio por presentación antes de descuento ($)', 'Descuento ($)', 'Impuesto ($)'][i]}<input inputMode="decimal" value={line[key]} onChange={e => dispatch({ type: 'line', id: line.id, key, value: e.target.value })} /></label>)}
            <div className="purchase-line-actions" role="group" aria-label={`Acciones del renglón ${index + 1}`}>
              <Button type="button" size="sm" variant="secondary" className="purchase-line-action" aria-label={`Agregar renglón después del ${index + 1}`} title="Agregar renglón" disabled={draft.lines.length >= 200} onClick={() => {
                const id = crypto.randomUUID(); pendingLineFocus.current = id;
                dispatch({ type: 'add', id, afterId: line.id });
              }}><Plus size={17} aria-hidden="true" /></Button>
              <Button type="button" size="sm" variant="ghost" className="purchase-line-action purchase-line-action--danger" aria-label={`Eliminar renglón ${index + 1}`} title="Eliminar renglón" disabled={draft.lines.length === 1} onClick={() => {
                pendingLineFocus.current = draft.lines[index + 1]?.id || draft.lines[index - 1]?.id || null;
                dispatch({ type: 'remove', id: line.id });
              }}><Trash2 size={17} aria-hidden="true" /></Button>
            </div>
            {line.ai_description && !line.presentation_id && <p role="status" className="purchase-ai-hint">Concepto detectado en comprobante: <strong>{line.ai_description}</strong>. Selecciona su presentación del catálogo para conciliarlo.</p>}
            {mismatch && !draft.supplier_catalog_exception && <p role="alert">La presentación no pertenece al proveedor elegido. Selecciona una presentación compatible o activa la excepción.</p>}
            {mismatch && draft.supplier_catalog_exception && <p role="status">Esta partida se registrará como excepción con la presentación del proveedor de catálogo.</p>}
            {calc && <p className="purchase-conversion">Entrada: {calc.base_quantity} {calc.presentation_snapshot.base_unit_code} · costo de inventario: ${calc.inventory_cost} · costo base: ${calc.cost_per_base_unit} · importe: ${calc.line_total}</p>}
          </div>;
        })}
        {catalogTools && <Button variant="secondary" disabled={!draft.supplier_id} onClick={() => setCatalogOpen(true)}>Registrar presentación sin perder la nota</Button>}
      </fieldset>
      {catalogOpen && catalogTools?.(draft.supplier_id, () => setCatalogOpen(false))}
      {preview.pending && <p role="status">Consultando importes…</p>}
      {preview.error && <p role="alert">{preview.error}</p>}
      {preview.data && <div className="purchase-summary" aria-live="polite">Subtotal: ${preview.data.subtotal} · descuentos: ${preview.data.discount_total} · impuestos: ${preview.data.tax_total}<br /><strong>Total: ${preview.data.total}</strong></div>}
      <p>El impuesto no integra el costo de inventario. Guardar registra el documento; confirmar después realiza la recepción y, cuando corresponde, el retiro de caja.</p>
      <div className="purchase-actions"><Button variant="secondary" disabled={locked} onClick={close}>Cerrar captura</Button><Button disabled={draft.phase === 'submitting' || (draft.phase === 'editing' && (!compatible || !preview.data))} onClick={() => void submit()}>{draft.phase === 'uncertain' ? 'Recuperar nota registrada' : draft.phase === 'submitting' ? 'Guardando…' : 'Guardar borrador'}</Button></div>
    </div>
  </Modal>;
}
