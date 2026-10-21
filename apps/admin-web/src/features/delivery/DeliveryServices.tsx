import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchApi, parseDeliveryAmount, type DeliveryPolicy, type DeliveryTariff } from '@restaurantos/api-client';
import { Button, Input } from '@restaurantos/ui';
import { Truck, Plus, Pencil, Globe2, Store, Gift, Check, X, ChevronDown, ShieldCheck, Info } from 'lucide-react';
import './DeliveryServices.css';
import { useAdminPermission } from '../../lib/adminSession';

const amountText = (cents: number) => `${Math.floor(cents / 100)}.${String(cents % 100).padStart(2, '0')}`;
const money = (cents: number) => `$${amountText(cents)}`;
const emptyTariff = { code: '', name: '', amount: '28.00', product_key: '', unit_key: '', emitter_id: '' };

export default function DeliveryServices() {
  const allowed = useAdminPermission('catalog.manage');
  const cache = useQueryClient();
  const tariffs = useQuery({ queryKey: ['delivery-tariffs'], enabled: allowed,
    queryFn: () => fetchApi<{ items: DeliveryTariff[] }>('/delivery-tariffs') });
  const branches = useQuery({ queryKey: ['delivery-policy-branches'], enabled: allowed,
    queryFn: () => fetchApi<Array<{ id: string; name: string; status: string }>>('/delivery-scopes') });
  const [scope, setScope] = useState('*');
  const [form, setForm] = useState(emptyTariff);
  const [editing, setEditing] = useState<DeliveryTariff | null>(null);
  const [active, setActive] = useState(true);
  const [policy, setPolicy] = useState<DeliveryPolicy | null>(null);
  const [enabled, setEnabled] = useState(false);
  const [defaultId, setDefaultId] = useState('');
  const [eligible, setEligible] = useState<string[]>([]);
  const [free, setFree] = useState(false);
  const [threshold, setThreshold] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [loadingPolicy, setLoadingPolicy] = useState(true);
  const [loadedScope, setLoadedScope] = useState('');
  const [policyReadFailed, setPolicyReadFailed] = useState(false);
  const [revision, setRevision] = useState(0);
  const [tariffOpen, setTariffOpen] = useState(false);
  const [feedbackTarget, setFeedbackTarget] = useState<'tariff' | 'policy'>('policy');
  const dialogRef = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (tariffOpen && !dialog.open) {
      dialog.showModal();
      dialog.querySelector<HTMLInputElement>('input:not(:disabled)')?.focus();
    }
    if (!tariffOpen && dialog.open) dialog.close();
  }, [tariffOpen, allowed]);
  useEffect(() => {
    if (!allowed) return;
    const controller = new AbortController();
    setLoadingPolicy(true); setPolicyReadFailed(false); setError(''); setNotice(''); setPolicy(null);
    fetchApi<{ policy: DeliveryPolicy | null }>(`/delivery-policies${scope === '*' ? '' : `?branch_id=${encodeURIComponent(scope)}`}`,
      { signal: controller.signal }).then(({ policy: found }) => {
        if (controller.signal.aborted) return;
        setPolicy(found); setEnabled(found?.enabled || false);
        setDefaultId(found?.default_tariff_id || ''); setEligible(found?.eligible_tariff_ids || []);
        setFree(found?.free_threshold_cents != null);
        setThreshold(found?.free_threshold_cents != null ? amountText(found.free_threshold_cents) : '');
        setLoadingPolicy(false); setLoadedScope(scope);
      }).catch((reason: unknown) => {
        if (!controller.signal.aborted) { setError(reason instanceof Error ? reason.message : 'No se pudo leer la política.'); setFeedbackTarget('policy'); setPolicyReadFailed(true); setLoadingPolicy(false); }
      });
    return () => controller.abort();
  }, [allowed, scope, revision]);
  if (!allowed) return <p role="alert">No tienes permiso para administrar tarifas de domicilio.</p>;

  async function saveTariff(event: React.FormEvent) {
    event.preventDefault(); setFeedbackTarget('tariff'); setError(''); setNotice(''); setBusy(true);
    try {
      const mapping = Object.fromEntries(['product_key', 'unit_key', 'emitter_id'].flatMap((key) => {
        const value = form[key as keyof typeof form].trim(); return value ? [[key, value]] : [];
      }));
      await fetchApi(editing ? `/delivery-tariffs/${editing.id}/revisions` : '/delivery-tariffs', {
        method: 'POST', headers: { 'Idempotency-Key': crypto.randomUUID() },
        body: JSON.stringify({ ...(editing ? { expected_version: editing.version } : { code: form.code }),
          name: form.name, amount_cents: parseDeliveryAmount(form.amount), active, fiscal_mapping: mapping }),
      });
      await cache.invalidateQueries({ queryKey: ['delivery-tariffs'] });
      setTariffOpen(false); setForm(emptyTariff); setEditing(null); setActive(true); setNotice('Tarifa guardada. Los pedidos anteriores conservan su precio.');
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'No se pudo guardar la tarifa.'); }
    finally { setBusy(false); }
  }
  async function savePolicy(event: React.FormEvent) {
    if (loadedScope !== scope || policyReadFailed || loadingPolicy) { event.preventDefault(); return; }
    event.preventDefault(); setFeedbackTarget('policy'); setError(''); setNotice(''); setBusy(true);
    try {
      const result = await fetchApi<DeliveryPolicy>('/delivery-policies', {
        method: 'POST', headers: { 'Idempotency-Key': crypto.randomUUID() },
        body: JSON.stringify({ branch_id: scope === '*' ? null : scope,
          expected_version: policy?.scope_key === scope ? policy.version : 0,
          enabled, eligible_tariff_ids: eligible, default_tariff_id: defaultId || null,
          free_threshold_cents: free ? parseDeliveryAmount(threshold) : null }),
      });
      setPolicy(result); setNotice(result.scope_key === '*' ? 'Configuración general guardada.' : 'Configuración guardada para esta sucursal.');
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'No se pudo guardar la configuración.'); }
    finally { setBusy(false); }
  }
  function openTariff(tariff?: DeliveryTariff) {
    setFeedbackTarget('tariff'); setError(''); setNotice('');
    setEditing(tariff || null); setActive(tariff?.active ?? true);
    setForm(tariff ? { code: tariff.code, name: tariff.name, amount: amountText(tariff.amount_cents),
      product_key: tariff.fiscal_mapping.product_key || '', unit_key: tariff.fiscal_mapping.unit_key || '',
      emitter_id: tariff.fiscal_mapping.emitter_id || '' } : emptyTariff);
    setTariffOpen(true);
  }
  function trapDialogFocus(event: React.KeyboardEvent<HTMLDialogElement>) {
    if (event.key !== 'Tab') return;
    const fields = Array.from(event.currentTarget.querySelectorAll<HTMLElement>(
      'button, input, select, textarea, summary, [tabindex]',
    )).filter((field) => !field.matches(':disabled') && field.tabIndex >= 0 && field.getClientRects().length > 0);
    const first = fields[0];
    const last = fields[fields.length - 1];
    if (event.shiftKey && document.activeElement === first && last) {
      event.preventDefault(); last.focus();
    } else if (!event.shiftKey && document.activeElement === last && first) {
      event.preventDefault(); first.focus();
    }
  }
  const items = tariffs.data?.items || [];
  const activeTariffs = items.filter((tariff) => tariff.active);
  const defaultTariff = activeTariffs.find((tariff) => tariff.id === defaultId);
  let thresholdPreview: number | null = null;
  if (free) {
    try {
      const parsed = parseDeliveryAmount(threshold);
      if (parsed > 0) thresholdPreview = parsed;
    } catch { /* An incomplete draft has no monetary preview. */ }
  }
  return <main className="delivery-services">
    <header className="delivery-services__header">
      <div className="delivery-services__heading-icon"><Truck size={26} aria-hidden="true" /></div>
      <div><span className="delivery-services__eyebrow">Catálogo y menú</span>
        <h1>Servicios de domicilio</h1>
        <p>Define tus tarifas y cuándo ofrecer envío gratis.</p>
      </div>
      <span className="delivery-services__tax-note">IVA 16% incluido</span>
    </header>
    <div className="delivery-services__grid">
      <div className="delivery-services__catalog-column">
        <section className="delivery-panel" aria-label="Catálogo de tarifas">
          <header className="delivery-panel__header">
            <div><h2>Tarifas de envío</h2><p>Los precios disponibles para tus pedidos.</p></div>
            <Button type="button" size="sm" disabled={busy} onClick={() => openTariff()}><Plus size={16} aria-hidden="true" />Agregar tarifa</Button>
          </header>
          {tariffs.error ? <div className="delivery-panel__body"><p role="alert">No se pudo cargar el catálogo.</p>
            <Button type="button" variant="secondary" onClick={() => void tariffs.refetch()}>Reintentar</Button></div>
            : tariffs.isPending ? <p className="delivery-panel__body" role="status">Cargando tarifas…</p>
              : !items.length ? <div className="delivery-services__empty"><Truck size={32} aria-hidden="true" /><h3>Tu primera tarifa de envío</h3><p>Agrega un precio para empezar a configurarlo en tus sucursales.</p></div>
                : <ul className="delivery-tariff-list" aria-label="Tarifas de envío">{items.map((tariff) => <li key={tariff.id}>
                  <div className="delivery-tariff-list__identity"><strong>{tariff.name}</strong><small>{tariff.code} · Versión {tariff.version}</small>
                    <span className={`delivery-status${tariff.active ? '' : ' delivery-status--muted'}`}><span aria-hidden="true" />{tariff.active ? 'Activa' : 'Archivada'}</span></div>
                  <div className="delivery-tariff-list__price"><strong>{money(tariff.amount_cents)}</strong><small>IVA incluido</small></div>
                  <Button type="button" variant="ghost" size="sm" aria-label={`Editar ${tariff.name}`} disabled={busy} onClick={() => openTariff(tariff)}><Pencil size={16} aria-hidden="true" /><span>Editar</span></Button>
                </li>)}</ul>}
          {feedbackTarget === 'tariff' && notice && <p className="delivery-feedback" role="status"><Check size={16} aria-hidden="true" />{notice}</p>}
        </section>
        <aside className="delivery-services__guide" aria-label="Cómo funcionan las tarifas"><Info size={19} aria-hidden="true" /><div>
          <strong>Una tarifa por pedido</strong><p>El cajero puede elegir otra tarifa disponible o quitar el envío desde la comanda.</p>
          <p>Para cobrar por zona, agrega sus tarifas y habilítalas en las reglas. La selección es manual.</p>
        </div></aside>
      </div>
      <section className="delivery-panel delivery-policy" aria-label="Reglas de envío">
        <header className="delivery-panel__header"><div><h2>Reglas de envío</h2><p>Elige dónde se aplican y cómo se cobra.</p></div></header>
        <div className="delivery-policy__scope">
          <label className="delivery-field" htmlFor="delivery-scope"><span>Sucursal o configuración general</span>
            <div className="delivery-select"><Globe2 size={17} aria-hidden="true" /><select id="delivery-scope" aria-label="Sucursal o configuración general" value={scope} disabled={busy} onChange={(event) => setScope(event.target.value)}>
              <option value="*">General · Todas las sucursales</option>
              {(branches.data || []).filter((branch) => branch.status === 'active').map((branch) => <option key={branch.id} value={branch.id}>{branch.name}</option>)}
            </select><ChevronDown size={16} aria-hidden="true" /></div>
          </label>
          {scope === '*' ? <p>Las sucursales con reglas propias conservan su configuración.</p>
            : !loadingPolicy && !policyReadFailed && <p className="delivery-policy__source"><Store size={14} aria-hidden="true" />{policy?.scope_key === '*' ? 'Hereda la configuración general. Al guardar crearás reglas propias para esta sucursal.' : policy?.scope_key === scope ? 'Configuración propia de la sucursal' : 'Sin configuración guardada para esta sucursal'}</p>}
          {branches.error && <p role="alert">No se pudieron consultar las sucursales.</p>}
        </div>
        {loadingPolicy ? <p className="delivery-panel__body" role="status">Cargando configuración…</p>
          : policyReadFailed ? <div className="delivery-panel__body"><p role="alert">{error || 'No se pudo cargar la configuración.'}</p><Button type="button" variant="secondary" onClick={() => setRevision((value) => value + 1)}>Reintentar configuración</Button></div>
            : <form onSubmit={(event) => void savePolicy(event)} onChange={() => { if (feedbackTarget === 'policy') setNotice(''); }}>
              <fieldset className="delivery-policy__fields" disabled={busy || loadedScope !== scope}>
                <label className="delivery-toggle-row" htmlFor="delivery-enabled"><span><strong>Aplicar cargo en pedidos a domicilio del POS</strong><small>Se agrega la tarifa predeterminada al elegir Domicilio.</small></span>
                  <input id="delivery-enabled" type="checkbox" role="switch" aria-label="Aplicar cargo en pedidos a domicilio del POS" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} /><span className="delivery-switch" aria-hidden="true" /></label>
                <fieldset className="delivery-tariff-choices"><legend>Tarifas disponibles para elegir</legend><p>Activa las opciones que verá el cajero.</p>
                  {!activeTariffs.length && <p>Agrega una tarifa activa para poder seleccionarla aquí.</p>}
                  {activeTariffs.map((tariff) => <label key={tariff.id} className={eligible.includes(tariff.id) ? 'is-selected' : ''}>
                    <input type="checkbox" checked={eligible.includes(tariff.id)} onChange={(event) => setEligible(event.target.checked ? [...eligible, tariff.id] : eligible.filter((id) => id !== tariff.id))} />
                    <span>{tariff.name}</span><strong>{money(tariff.amount_cents)}</strong>
                  </label>)}
                </fieldset>
                <label className="delivery-field" htmlFor="delivery-default"><span>Tarifa predeterminada</span><div className="delivery-select"><select id="delivery-default" aria-label="Tarifa predeterminada" aria-describedby="delivery-default-help" value={defaultId} onChange={(event) => setDefaultId(event.target.value)}>
                  <option value="">Selecciona una tarifa</option>{activeTariffs.filter((tariff) => eligible.includes(tariff.id)).map((tariff) => <option key={tariff.id} value={tariff.id}>{tariff.name}</option>)}
                </select><ChevronDown size={16} aria-hidden="true" /></div><small id="delivery-default-help">Será la primera opción al crear un pedido a domicilio.</small></label>
                <div className="delivery-policy__free">
                  <label className="delivery-toggle-row" htmlFor="delivery-free"><span><strong>Envío gratis desde un monto</strong><small>Ofrece el envío al alcanzar una compra mínima.</small></span>
                    <input id="delivery-free" type="checkbox" role="switch" aria-label="Envío gratis desde un monto" checked={free} onChange={(event) => setFree(event.target.checked)} /><span className="delivery-switch" aria-hidden="true" /></label>
                  {free && <div className="delivery-policy__threshold"><label className="delivery-field" htmlFor="delivery-threshold"><span>Subtotal mínimo después de descuentos</span><Input id="delivery-threshold" aria-label="Subtotal mínimo después de descuentos" aria-describedby="delivery-threshold-help" required inputMode="decimal" icon={<span aria-hidden="true">$</span>} value={threshold} onChange={(event) => setThreshold(event.target.value)} /></label><p id="delivery-threshold-help">Se aplica desde ese monto, incluido. No cuenta envío ni propina.</p></div>}
                </div>
              </fieldset>
              <aside className="delivery-policy__preview" aria-label="Vista previa del envío"><div className="delivery-policy__preview-icon">{free ? <Gift size={21} aria-hidden="true" /> : <Truck size={21} aria-hidden="true" />}</div><div>
                <small>Vista previa del envío</small>
                <strong>{!enabled ? 'Envío automático desactivado' : defaultTariff ? `Envío de ${money(defaultTariff.amount_cents)}` : 'Selecciona una tarifa predeterminada'}</strong>
                {enabled && free && <span>{thresholdPreview !== null ? `Gratis desde ${money(thresholdPreview)}` : 'Completa un monto mínimo válido'}</span>}
              </div></aside>
              <footer className="delivery-policy__footer">
                {feedbackTarget === 'policy' && error && <p className="delivery-feedback delivery-feedback--error" role="alert">{error}</p>}
                {feedbackTarget === 'policy' && notice && <p className="delivery-feedback" role="status"><Check size={16} aria-hidden="true" />{notice}</p>}
                <p>Los pedidos confirmados conservan su configuración.</p>
                <Button type="submit" disabled={busy || loadedScope !== scope || !tariffs.data}><Check size={16} aria-hidden="true" />{busy ? 'Guardando…' : 'Guardar configuración'}</Button>
                {feedbackTarget === 'policy' && error && <Button type="button" variant="secondary" onClick={() => setRevision((value) => value + 1)}>Recargar configuración</Button>}
              </footer>
            </form>}
      </section>
    </div>
    <dialog ref={dialogRef} className="delivery-tariff-dialog" aria-labelledby="delivery-tariff-title" onKeyDown={trapDialogFocus} onCancel={(event) => { event.preventDefault(); if (!busy) setTariffOpen(false); }} onClose={() => setTariffOpen(false)}>
      <header className="delivery-tariff-dialog__header"><div><span className="delivery-services__eyebrow">Catálogo de envío</span><h2 id="delivery-tariff-title">{editing ? 'Editar tarifa' : 'Agregar tarifa'}</h2></div>
        <Button type="button" variant="ghost" aria-label="Cerrar editor de tarifa" disabled={busy} onClick={() => setTariffOpen(false)}><X size={20} aria-hidden="true" /></Button></header>
      <form onSubmit={(event) => void saveTariff(event)} className="delivery-tariff-form">
        <p>El precio incluye IVA 16%. Los pedidos anteriores conservan su importe.</p>
        <div className="delivery-tariff-form__identity"><label className="delivery-field"><span>Código</span><Input required disabled={Boolean(editing) || busy} placeholder="Ej. DOMICILIO" value={form.code} onChange={(event) => setForm({ ...form, code: event.target.value })} /></label>
          <label className="delivery-field"><span>Nombre</span><Input required disabled={busy} placeholder="Ej. Entrega a domicilio" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></label></div>
        <label className="delivery-field"><span>Precio con IVA incluido</span><Input aria-label="Precio con IVA incluido" aria-describedby="delivery-price-help" required inputMode="decimal" disabled={busy} icon={<span aria-hidden="true">$</span>} value={form.amount} onChange={(event) => setForm({ ...form, amount: event.target.value })} /><small id="delivery-price-help">Pesos mexicanos · Hasta dos decimales</small></label>
        <label className="delivery-toggle-row" htmlFor="delivery-tariff-active"><span><strong>Tarifa activa</strong><small>Disponible para elegir en las reglas de envío.</small></span><input id="delivery-tariff-active" type="checkbox" role="switch" aria-label="Tarifa activa" disabled={busy} checked={active} onChange={(event) => setActive(event.target.checked)} /><span className="delivery-switch" aria-hidden="true" /></label>
        <details className="delivery-tariff-fiscal"><summary><ShieldCheck size={18} aria-hidden="true" /><span>Configuración fiscal<span>Claves SAT y emisor para CFDI</span></span><ChevronDown size={16} aria-hidden="true" /></summary>
          <div><p>Captura los datos aprobados por el emisor antes de emitir CFDI del servicio.</p>
            <label className="delivery-field"><span>Clave SAT del servicio</span><Input disabled={busy} value={form.product_key} onChange={(event) => setForm({ ...form, product_key: event.target.value })} /></label>
            <label className="delivery-field"><span>Clave de unidad SAT</span><Input disabled={busy} value={form.unit_key} onChange={(event) => setForm({ ...form, unit_key: event.target.value })} /></label>
            <label className="delivery-field"><span>ID del emisor configurado</span><Input disabled={busy} value={form.emitter_id} onChange={(event) => setForm({ ...form, emitter_id: event.target.value })} /></label>
          </div>
        </details>
        {feedbackTarget === 'tariff' && error && <p className="delivery-feedback delivery-feedback--error" role="alert">{error}</p>}
        <footer className="delivery-tariff-form__footer"><Button type="button" variant="secondary" disabled={busy} onClick={() => setTariffOpen(false)}>Cancelar</Button><Button type="submit" disabled={busy}>{busy ? 'Guardando…' : 'Guardar tarifa'}</Button></footer>
      </form>
    </dialog>
  </main>;
}
