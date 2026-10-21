import { useEffect, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchApi, parseDeliveryAmount, type DeliveryPolicy, type DeliveryTariff } from '@restaurantos/api-client';
import { Button, Input } from '@restaurantos/ui';
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
        if (!controller.signal.aborted) { setError(reason instanceof Error ? reason.message : 'No se pudo leer la política.'); setPolicyReadFailed(true); setLoadingPolicy(false); }
      });
    return () => controller.abort();
  }, [allowed, scope, revision]);
  if (!allowed) return <p role="alert">No tienes permiso para administrar tarifas de domicilio.</p>;

  async function saveTariff(event: React.FormEvent) {
    event.preventDefault(); setError(''); setNotice(''); setBusy(true);
    try {
      const mapping = Object.fromEntries(['product_key', 'unit_key', 'emitter_id'].flatMap((key) => {
        const value = form[key as keyof typeof form].trim(); return value ? [[key, value]] : [];
      }));
      await fetchApi(editing ? `/delivery-tariffs/${editing.id}/revisions` : '/delivery-tariffs', {
        method: 'POST', headers: { 'Idempotency-Key': crypto.randomUUID() },
        body: JSON.stringify({ ...(editing ? { expected_version: editing.version } : { code: form.code }),
          name: form.name, amount_cents: parseDeliveryAmount(form.amount), active, fiscal_mapping: mapping }),
      });
      setForm(emptyTariff); setEditing(null); setActive(true); setNotice('Tarifa guardada. Los pedidos anteriores conservan su precio.');
      await cache.invalidateQueries({ queryKey: ['delivery-tariffs'] });
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'No se pudo guardar la tarifa.'); }
    finally { setBusy(false); }
  }
  async function savePolicy(event: React.FormEvent) {
    if (loadedScope !== scope || policyReadFailed || loadingPolicy) { event.preventDefault(); return; }
    event.preventDefault(); setError(''); setNotice(''); setBusy(true);
    try {
      const result = await fetchApi<DeliveryPolicy>('/delivery-policies', {
        method: 'POST', headers: { 'Idempotency-Key': crypto.randomUUID() },
        body: JSON.stringify({ branch_id: scope === '*' ? null : scope,
          expected_version: policy?.scope_key === scope ? policy.version : 0,
          enabled, eligible_tariff_ids: eligible, default_tariff_id: defaultId || null,
          free_threshold_cents: free ? parseDeliveryAmount(threshold) : null }),
      });
      setPolicy(result); setNotice('Configuración guardada para el destino seleccionado.');
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'No se pudo guardar la configuración.'); }
    finally { setBusy(false); }
  }
  return <main style={{ padding: 24, maxWidth: 1100, margin: 'auto' }}>
    <h1>Servicios de domicilio</h1>
    <p>Tarifas de envío con IVA 16% incluido. Se elige una por pedido; no requieren receta.</p>
    {error && <p role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}
    {tariffs.error && <p role="alert">No se pudo cargar el catálogo. <Button onClick={() => void tariffs.refetch()}>Reintentar</Button></p>}
    <section aria-label="Catálogo de tarifas">
      <h2>Tarifas</h2>
      {tariffs.isPending ? <p>Cargando tarifas…</p> : !tariffs.data?.items.length ? <p>No hay tarifas registradas.</p> :
        <div style={{ overflowX: 'auto' }}><table style={{ width: '100%' }}><thead><tr><th>Nombre</th><th>Precio final</th><th>Versión</th><th>Estado</th><th>Acciones</th></tr></thead>
          <tbody>{tariffs.data.items.map((tariff) => <tr key={tariff.id}>
            <td>{tariff.name}</td><td>{money(tariff.amount_cents)}</td><td>{tariff.version}</td><td>{tariff.active ? 'Activa' : 'Archivada'}</td>
            <td><Button variant="secondary" disabled={busy} onClick={() => {
              setEditing(tariff); setActive(tariff.active); setForm({ code: tariff.code, name: tariff.name,
                amount: amountText(tariff.amount_cents), product_key: tariff.fiscal_mapping.product_key || '',
                unit_key: tariff.fiscal_mapping.unit_key || '', emitter_id: tariff.fiscal_mapping.emitter_id || '' });
            }}>Editar {tariff.name}</Button></td>
          </tr>)}</tbody></table></div>}
      <form onSubmit={(event) => void saveTariff(event)} style={{ display: 'grid', gap: 12, margin: '24px 0', maxWidth: 560 }}>
        <h3>{editing ? 'Nueva revisión de tarifa' : 'Agregar tarifa'}</h3>
        <label>Código<Input required disabled={Boolean(editing)} value={form.code} onChange={(event) => setForm({ ...form, code: event.target.value })} /></label>
        <label>Nombre<Input required value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></label>
        <label>Precio con IVA incluido<Input required inputMode="decimal" value={form.amount} onChange={(event) => setForm({ ...form, amount: event.target.value })} /></label>
        <label><input type="checkbox" checked={active} onChange={(event) => setActive(event.target.checked)} /> Tarifa activa</label>
        <details><summary>Configuración fiscal aprobada por el emisor</summary>
          <p>Completar antes de emitir CFDI del servicio. No se asignan claves automáticamente.</p>
          <label>Clave SAT del servicio<Input value={form.product_key} onChange={(event) => setForm({ ...form, product_key: event.target.value })} /></label>
          <label>Clave de unidad SAT<Input value={form.unit_key} onChange={(event) => setForm({ ...form, unit_key: event.target.value })} /></label>
          <label>ID del emisor configurado<Input value={form.emitter_id} onChange={(event) => setForm({ ...form, emitter_id: event.target.value })} /></label>
        </details>
        <Button type="submit" disabled={busy}>Guardar tarifa</Button>
        {editing && <Button variant="secondary" onClick={() => { setEditing(null); setForm(emptyTariff); setActive(true); }}>Cancelar edición</Button>}
      </form>
    </section>
    <section aria-label="Política de envío"><h2>Configuración por destino</h2>
      <label>Destino de configuración<select value={scope} disabled={busy} onChange={(event) => setScope(event.target.value)}>
        <option value="*">Predeterminada corporativa</option>
        {(branches.data || []).filter((branch) => branch.status === 'active').map((branch) => <option key={branch.id} value={branch.id}>{branch.name}</option>)}
      </select></label>
      {branches.error && <p role="alert">No se pudieron consultar las sucursales.</p>}
      {loadingPolicy ? <p>Cargando configuración…</p> : <form onSubmit={(event) => void savePolicy(event)} style={{ display: 'grid', gap: 12, marginTop: 16 }}>
        {policy?.scope_key === '*' && scope !== '*' && <p>La sucursal hereda la política corporativa. Guardar creará una excepción para esta sucursal.</p>}
        <label><input type="checkbox" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} /> Aplicar cargo en pedidos a domicilio del POS</label>
        <fieldset><legend>Tarifas disponibles para elegir</legend>{(tariffs.data?.items || []).filter((tariff) => tariff.active).map((tariff) => <label key={tariff.id} style={{ display: 'block' }}>
          <input type="checkbox" checked={eligible.includes(tariff.id)} onChange={(event) => setEligible(event.target.checked ? [...eligible, tariff.id] : eligible.filter((id) => id !== tariff.id))} /> {tariff.name} · {money(tariff.amount_cents)}
        </label>)}</fieldset>
        <label>Tarifa predeterminada<select value={defaultId} onChange={(event) => setDefaultId(event.target.value)}>
          <option value="">Selecciona una tarifa</option>{(tariffs.data?.items || []).filter((tariff) => tariff.active && eligible.includes(tariff.id)).map((tariff) => <option key={tariff.id} value={tariff.id}>{tariff.name}</option>)}
        </select></label>
        <label><input type="checkbox" checked={free} onChange={(event) => setFree(event.target.checked)} /> Envío gratis desde un monto</label>
        {free && <label>Subtotal mínimo después de descuentos<Input required inputMode="decimal" value={threshold} onChange={(event) => setThreshold(event.target.value)} /></label>}
        <p>Al alcanzar ese subtotal de productos, el envío será gratis. No incluye envío ni propina.</p>
        <Button type="submit" disabled={busy || policyReadFailed || loadedScope !== scope || !tariffs.data || loadingPolicy}>Guardar configuración</Button>
        {error && <Button variant="secondary" onClick={() => setRevision((value) => value + 1)}>Recargar configuración</Button>}
      </form>}
    </section>
  </main>;
}
