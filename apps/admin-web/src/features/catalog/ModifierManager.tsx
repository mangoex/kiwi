import React, { useEffect, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, fetchApi } from '@restaurantos/api-client';
import { Button } from '@restaurantos/ui';
import { ArrowDown, ArrowUp, Plus, RotateCcw, Save, Trash2 } from 'lucide-react';
import { centsToMxn, mxnToCentsExact } from './ingredientVariationMoney';
import '../../premium-catalogs.css';
import './ModifierManager.css';
import { CompoundCopyPanel, CompoundSelectionPreview } from './CompoundCopyPanel';

type Candidate = { id: string; name: string; sku: string };
type InventoryCandidate = Candidate & { unit_code: string };
const effects = [
  ['product_component', 'Producto componente'], ['instruction', 'Instrucción de cocina'],
  ['add', 'Agregar insumo'], ['remove', 'Quitar insumo'], ['quantity', 'Cambiar cantidad'],
  ['substitute', 'Sustituir insumo'], ['variant', 'Variante de insumo'],
] as const;
const wholeComponentQuantity = (value: unknown) => {
  const text = String(value ?? '').trim();
  return /^\d+(?:\.0+)?$/.test(text) && Number(text) > 0 && Number(text) <= 999999;
};
const inventoryQuantity = (value: unknown) => {
  const text = String(value ?? '0').trim();
  return /^\d+(?:\.\d{1,6})?$/.test(text)
    && text.split('.')[0].replace(/^0+(?=\d)/, '').length <= 12;
};

type ModifierOption = {
  id?: string;
  name: string;
  effect_type: string;
  price_delta_cents: number;
  price_mxn: string;
  component_product_id?: string | null;
  component_quantity?: string | number | null;
  affected_item_id?: string | null;
  replacement_item_id?: string | null;
  remove_quantity?: string | number;
  add_quantity?: string | number;
  inventory_effect?: boolean;
  kitchen_text?: string;
  station?: string | null;
};

type ModifierGroup = {
  id?: string;
  name: string;
  is_required: boolean;
  minimum_selections: number;
  maximum_selections: number;
  included_selections: number;
  station?: string | null;
  options: ModifierOption[];
};

type Configuration = {
  product: { id: string; name: string; sku: string; station: string };
  expected_version: number;
  groups: Array<Omit<ModifierGroup, 'options'> & { options: Array<Omit<ModifierOption, 'price_mxn'>> }>;
  component_candidates: Candidate[];
  inventory_candidates?: InventoryCandidate[];
};

type SaveResult = { version: number; groups: Configuration['groups']; result: 'applied' | 'replay' };

const hydrateGroups = (groups: Configuration['groups']): ModifierGroup[] => groups.map((group) => ({
  id: group.id,
  name: group.name,
  is_required: group.is_required,
  minimum_selections: group.minimum_selections,
  maximum_selections: group.maximum_selections,
  included_selections: group.included_selections || 0,
  station: group.station,
  options: group.options.map((option) => ({
    ...option,
    price_mxn: centsToMxn(option.price_delta_cents || 0),
  })),
}));

const blankGroup = (): ModifierGroup => ({
  name: 'Nuevo grupo',
  is_required: true,
  minimum_selections: 1,
  maximum_selections: 1,
  included_selections: 1,
  options: [],
});

const blankOption = (): ModifierOption => ({
  name: '',
  effect_type: 'product_component',
  price_delta_cents: 0,
  price_mxn: '0.00',
  component_product_id: '',
  component_quantity: '1',
  inventory_effect: true,
  kitchen_text: '',
});

const requiredMinimumError = (group: ModifierGroup): string => (
  group.is_required && group.minimum_selections < 1
    ? `${group.name.trim() || 'Este grupo'} está marcado como obligatorio pero tiene mínimo 0. Cambia el mínimo a 1 o desmarca Grupo obligatorio.`
    : ''
);

const move = <T,>(rows: T[], from: number, to: number): T[] => {
  if (to < 0 || to >= rows.length) return rows;
  const next = [...rows];
  const [row] = next.splice(from, 1);
  next.splice(to, 0, row);
  return next;
};

const saveError = (reason: unknown): string => {
  if (reason instanceof ApiError && reason.code === 'modifier_configuration_version_conflict') {
    return 'La configuración cambió en otra sesión. Tu borrador se conserva; revisa la versión vigente antes de volver a guardar.';
  }
  return reason instanceof ApiError ? reason.message : 'No fue posible guardar el producto compuesto.';
};

const payloadGroups = (groups: ModifierGroup[]) => groups.map((group) => ({
  ...(group.id ? { id: group.id } : {}),
  name: group.name.trim(),
  is_required: group.is_required,
  minimum_selections: group.minimum_selections,
  maximum_selections: group.maximum_selections,
  included_selections: group.included_selections,
  ...(group.station ? { station: group.station } : {}),
  options: group.options.map((option) => ({
    ...(option.id ? { id: option.id } : {}),
    name: option.name.trim(),
    effect_type: option.effect_type,
    price_delta_cents: mxnToCentsExact(option.price_mxn),
    component_product_id: option.effect_type === 'product_component' ? option.component_product_id : null,
    component_quantity: option.effect_type === 'product_component' ? option.component_quantity || '1' : null,
    affected_item_id: option.affected_item_id || null,
    replacement_item_id: option.replacement_item_id || null,
    remove_quantity: option.remove_quantity || '0',
    add_quantity: option.add_quantity || '0',
    inventory_effect: option.effect_type === 'instruction' ? false
      : option.effect_type === 'product_component' ? true : option.inventory_effect ?? true,
    kitchen_text: (option.kitchen_text || option.name).trim(),
    ...(option.station ? { station: option.station } : {}),
  })),
}));

export function ModifierManager({ productId, productName }: { productId: string; productName: string }) {
  const client = useQueryClient();
  const [groups, setGroups] = useState<ModifierGroup[]>([]);
  const [expectedVersion, setExpectedVersion] = useState(0);
  const [dirty, setDirty] = useState(false);
  const [copyBusy, setCopyBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [requiresReview, setRequiresReview] = useState(false);
  const idempotencyKey = useRef('');

  useEffect(() => {
    setGroups([]);
    setExpectedVersion(0);
    setDirty(false);
    setMessage('');
    setRequiresReview(false);
    idempotencyKey.current = '';
  }, [productId]);

  const configuration = useQuery<Configuration>({
    queryKey: ['modifier-configuration', productId],
    queryFn: () => fetchApi(`/products/${productId}/modifier-configuration`),
    retry: false,
  });

  useEffect(() => {
    if (!configuration.data || dirty) return;
    setGroups(hydrateGroups(configuration.data.groups));
    setExpectedVersion(configuration.data.expected_version);
    idempotencyKey.current = '';
  }, [configuration.data, dirty]);

  const change = (next: ModifierGroup[]) => {
    setGroups(next);
    setDirty(true);
    setMessage('');
    setRequiresReview(false);
    idempotencyKey.current = '';
  };

  const reviewCurrentVersion = async () => {
    const current = await configuration.refetch();
    if (!current.isSuccess || !current.data) return;
    setExpectedVersion(current.data.expected_version);
    setRequiresReview(false);
    idempotencyKey.current = '';
    setMessage(`Versión vigente revisada: v${current.data.expected_version}. Tu borrador se conserva para que lo confirmes.`);
  };

  const save = useMutation({
    mutationFn: () => {
      if (!idempotencyKey.current) idempotencyKey.current = crypto.randomUUID();
      return fetchApi<SaveResult>(`/products/${productId}/modifier-configuration`, {
        method: 'PUT',
        headers: { 'Idempotency-Key': idempotencyKey.current },
        body: JSON.stringify({ expected_version: expectedVersion, groups: payloadGroups(groups) }),
      });
    },
    onSuccess: (response) => {
      setGroups(hydrateGroups(response.groups));
      setExpectedVersion(response.version);
      setDirty(false);
      setRequiresReview(false);
      setMessage(`Configuración guardada como versión ${response.version}. Los pedidos anteriores conservan su selección original.`);
      idempotencyKey.current = '';
      client.setQueryData<Configuration>(['modifier-configuration', productId], (previous) => previous ? ({
        ...previous,
        expected_version: response.version,
        groups: response.groups,
      }) : previous);
      void client.invalidateQueries({ queryKey: ['product-modifiers', productId] });
    },
    onError: (reason) => {
      setRequiresReview(reason instanceof ApiError && reason.code === 'modifier_configuration_version_conflict');
      setMessage(saveError(reason));
    },
  });

  const updateGroup = (groupIndex: number, update: Partial<ModifierGroup>) => change(
    groups.map((group, index) => index === groupIndex ? { ...group, ...update } : group),
  );
  const updateOption = (groupIndex: number, optionIndex: number, update: Partial<ModifierOption>) => change(
    groups.map((group, index) => index === groupIndex ? {
      ...group,
      options: group.options.map((option, rowIndex) => rowIndex === optionIndex ? { ...option, ...update } : option),
    } : group),
  );

  const candidates = configuration.data?.component_candidates || [];
  const inventoryCandidates = configuration.data?.inventory_candidates || [];
  const unavailableItems = groups.flatMap((group) => group.options).some((option) =>
    !['instruction', 'product_component'].includes(option.effect_type)
    && [option.affected_item_id, option.replacement_item_id].some((id) => id && !inventoryCandidates.some((item) => item.id === id)),
  );
  const requiredMinimumConflictIndex = groups.findIndex((group) => requiredMinimumError(group));
  const requiredMinimumConflict = groups[requiredMinimumConflictIndex];
  let validation = '';
  try {
    payloadGroups(groups);
    const invalidGroup = groups.find((group) => !group.name.trim()
      || ![group.minimum_selections, group.maximum_selections, group.included_selections].every(Number.isInteger)
      || group.minimum_selections < 0
      || group.maximum_selections < 1
      || group.minimum_selections > group.maximum_selections
      || group.included_selections < 0
      || group.included_selections > group.maximum_selections
      || (group.is_required && group.minimum_selections < 1)
      || group.minimum_selections > group.options.length);
    const invalidOption = groups.flatMap((group) => group.options).find((option) => !option.name.trim()
      || !effects.some(([type]) => type === option.effect_type)
      || (option.effect_type === 'product_component' && (!option.component_product_id || !wholeComponentQuantity(option.component_quantity)))
      || (['remove', 'quantity', 'substitute', 'variant'].includes(option.effect_type) && !option.affected_item_id)
      || (['substitute', 'variant'].includes(option.effect_type) && !option.replacement_item_id)
      || (option.effect_type === 'add' && !option.affected_item_id && !option.replacement_item_id)
      || !inventoryQuantity(option.remove_quantity) || !inventoryQuantity(option.add_quantity));
    if (requiredMinimumConflict) validation = requiredMinimumError(requiredMinimumConflict);
    else if (unavailableItems) validation = 'Reemplaza los insumos no disponibles: están archivados o fuera del catálogo de este producto.';
    else if (invalidGroup) validation = 'Revisa nombre, obligatoriedad, mínimos, máximos y selecciones incluidas del grupo.';
    else if (invalidOption) validation = 'Revisa las opciones: nombre, producto y cantidad entera positiva, o insumos requeridos y cantidades no negativas con hasta seis decimales.';
  } catch (reason) {
    validation = reason instanceof Error ? reason.message : 'Revisa los importes de las opciones.';
  }

  if (configuration.isLoading && !configuration.data) return <p role="status">Cargando configuración de {productName}…</p>;
  if (configuration.isError && !configuration.data) return <p role="alert">No fue posible cargar la configuración administrativa. No se habilita el guardado sin su versión vigente.</p>;

  return <section className="modifier-manager" aria-label={`Producto compuesto ${productName}`}>
    <div className="modifier-manager__header">
      <div>
        <h2>Grupos y productos seleccionables</h2>
        <p>Configura las elecciones del cajero: insumos, instrucciones o productos simples. Mínimo y máximo indican cuántas opciones debe elegir. Las selecciones incluidas no suman recargo.</p>
      </div>
      <span className="modifier-version">Versión {expectedVersion}</span>
    </div>

    {configuration.isError && configuration.data && <p role="alert">No fue posible actualizar la lectura. Se conserva tu borrador y la última versión conocida.</p>}
    {message && <p className="admin-catalog-message" role={requiresReview ? 'alert' : 'status'}>{message}</p>}
    {requiresReview && <div className="admin-catalog-message" role="alert"><p>Revisa la versión vigente antes de confirmar nuevamente. No reemplazaremos tu borrador.</p><Button variant="secondary" onClick={() => void reviewCurrentVersion()}><RotateCcw size={15} /> Revisar versión vigente</Button></div>}

    <div className="modifier-manager__section-heading">
      <h3>Editar grupos y opciones</h3>
      <p>Los cambios sólo se aplican al guardar esta configuración.</p>
    </div>
    <fieldset disabled={copyBusy || save.isPending} style={{ border: 0, padding: 0, minWidth: 0 }}>
    {groups.length === 0 && <div className="modifier-empty-state">Este producto todavía no tiene grupos seleccionables.</div>}

    {groups.map((group, groupIndex) => <article key={group.id || `new-${groupIndex}`} className="modifier-group-card">
      <header className="modifier-group-card__header">
        <div className="modifier-group-fields">
          <label className="premium-form-group">Nombre del grupo
            <input className="modifier-control" value={group.name} onChange={(event) => updateGroup(groupIndex, { name: event.target.value })} />
          </label>
          <label className="premium-form-group">Mínimo
            <input
              id={`modifier-group-${groupIndex}-minimum`}
              className="modifier-control"
              type="number"
              min="0"
              aria-invalid={Boolean(requiredMinimumError(group))}
              aria-describedby={requiredMinimumError(group) ? `modifier-group-${groupIndex}-required-error` : undefined}
              value={group.minimum_selections}
              onChange={(event) => {
                const minimum = Number(event.target.value);
                updateGroup(groupIndex, { minimum_selections: minimum, is_required: minimum > 0 });
              }}
            />
          </label>
          <label className="premium-form-group">Máximo
            <input className="modifier-control" type="number" min="1" value={group.maximum_selections} onChange={(event) => updateGroup(groupIndex, { maximum_selections: Number(event.target.value) })} />
          </label>
          <label className="premium-form-group">Selecciones incluidas
            <input className="modifier-control" type="number" min="0" value={group.included_selections} onChange={(event) => updateGroup(groupIndex, { included_selections: Number(event.target.value) })} />
          </label>
          <div className="modifier-row-actions">
            <button type="button" className="modifier-row-action" aria-label="Subir grupo" disabled={groupIndex === 0} onClick={() => change(move(groups, groupIndex, groupIndex - 1))}><ArrowUp size={16} /></button>
            <button type="button" className="modifier-row-action" aria-label="Bajar grupo" disabled={groupIndex === groups.length - 1} onClick={() => change(move(groups, groupIndex, groupIndex + 1))}><ArrowDown size={16} /></button>
            <button type="button" className="modifier-row-action modifier-row-action--danger" aria-label="Eliminar grupo" onClick={() => change(groups.filter((_, index) => index !== groupIndex))}><Trash2 size={16} /></button>
          </div>
        </div>
        <label className="modifier-required-toggle">
          <input type="checkbox" checked={group.is_required} onChange={(event) => updateGroup(groupIndex, {
            is_required: event.target.checked,
            minimum_selections: event.target.checked ? Math.max(1, group.minimum_selections) : 0,
          })} /> Grupo obligatorio
        </label>
        {requiredMinimumError(group) && <p id={`modifier-group-${groupIndex}-required-error`} className="admin-catalog-message" role="alert">{requiredMinimumError(group)}</p>}
      </header>

      <div className="modifier-group-card__body">
        {group.options.map((option, optionIndex) => {
          const ingredientEffect = !['product_component', 'instruction'].includes(option.effect_type);
          const substitution = ['substitute', 'variant'].includes(option.effect_type);
          const itemSelect = (field: 'affected_item_id' | 'replacement_item_id', label: string) => <label className="premium-form-group">{label}
            <select aria-label={label} className="modifier-control" value={option[field] || ''} onChange={(event) => updateOption(groupIndex, optionIndex, { [field]: event.target.value || null })}>
              <option value="">Selecciona un insumo</option>
              {option[field] && !inventoryCandidates.some((item) => item.id === option[field]) && <option value={option[field]!}>Insumo no disponible ({option[field]})</option>}
              {inventoryCandidates.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.unit_code}</option>)}
            </select>
          </label>;
          const unit = (id: string | null | undefined) => inventoryCandidates.find((item) => item.id === id)?.unit_code || 'unidad base';
          return <div key={option.id || `new-option-${optionIndex}`} className="modifier-option-row">
            <label className="premium-form-group">Tipo
              <select aria-label="Tipo" className="modifier-control" value={option.effect_type} onChange={(event) => updateOption(groupIndex, optionIndex, {
                effect_type: event.target.value,
                component_product_id: event.target.value === 'product_component' ? '' : null,
                component_quantity: event.target.value === 'product_component' ? '1' : null,
                ...(!['product_component', 'instruction'].includes(option.effect_type)
                    && !['product_component', 'instruction'].includes(event.target.value)
                  ? {}
                  : { affected_item_id: null, replacement_item_id: null,
                    remove_quantity: '0', add_quantity: '0',
                    inventory_effect: event.target.value !== 'instruction' }),
              })}>
                {effects.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </label>
            {option.effect_type === 'product_component' ? <label className="premium-form-group">Producto
              <select aria-label="Producto" className="modifier-control" value={option.component_product_id || ''} onChange={(event) => {
                const candidate = candidates.find((row) => row.id === event.target.value);
                updateOption(groupIndex, optionIndex, { component_product_id: event.target.value, name: candidate?.name.slice(0, 120) || option.name, kitchen_text: candidate?.name.slice(0, 240) || option.kitchen_text });
              }}>
                <option value="">Selecciona un producto simple</option>
                {candidates.map((candidate) => <option key={candidate.id} value={candidate.id}>{candidate.name} ({candidate.sku})</option>)}
              </select>
            </label> : <label className="premium-form-group">Nombre / instrucción
              <input className="modifier-control" maxLength={120} value={option.name} onChange={(event) => updateOption(groupIndex, optionIndex, { name: event.target.value })} />
            </label>}
            <label className="premium-form-group">Cantidad
              <input className="modifier-control" inputMode="numeric" disabled={option.effect_type !== 'product_component'} value={option.effect_type === 'product_component' ? String(option.component_quantity || '') : '—'} onChange={(event) => updateOption(groupIndex, optionIndex, { component_quantity: event.target.value })} />
            </label>
            <label className="premium-form-group">Precio extra MXN
              <input className="modifier-control" inputMode="decimal" value={option.price_mxn} onChange={(event) => updateOption(groupIndex, optionIndex, { price_mxn: event.target.value })} />
            </label>
            <div className="modifier-row-actions">
              <button type="button" className="modifier-row-action" aria-label="Subir opción" disabled={optionIndex === 0} onClick={() => updateGroup(groupIndex, { options: move(group.options, optionIndex, optionIndex - 1) })}><ArrowUp size={16} /></button>
              <button type="button" className="modifier-row-action" aria-label="Bajar opción" disabled={optionIndex === group.options.length - 1} onClick={() => updateGroup(groupIndex, { options: move(group.options, optionIndex, optionIndex + 1) })}><ArrowDown size={16} /></button>
              <button type="button" className="modifier-row-action modifier-row-action--danger" aria-label="Eliminar opción" onClick={() => updateGroup(groupIndex, { options: group.options.filter((_, index) => index !== optionIndex) })}><Trash2 size={16} /></button>
            </div>
            <div className="modifier-option-details">
              {ingredientEffect && <>
                {itemSelect('affected_item_id', substitution ? 'Insumo a sustituir' : option.replacement_item_id ? 'Insumo a quitar' : 'Insumo')}
                {(substitution || Boolean(option.replacement_item_id)) && itemSelect('replacement_item_id', substitution ? 'Insumo de reemplazo' : 'Insumo a agregar')}
                <label className="premium-form-group">Cantidad a quitar
                  <input className="modifier-control" inputMode="decimal" value={String(option.remove_quantity ?? '0')} onChange={(event) => updateOption(groupIndex, optionIndex, { remove_quantity: event.target.value })} />
                  <small>{unit(option.affected_item_id)}{['remove', 'substitute', 'variant'].includes(option.effect_type) ? ' · 0 retira todo el insumo de la receta.' : ''}</small>
                </label>
                <label className="premium-form-group">Cantidad a agregar
                  <input className="modifier-control" inputMode="decimal" value={String(option.add_quantity ?? '0')} onChange={(event) => updateOption(groupIndex, optionIndex, { add_quantity: event.target.value })} />
                  <small>{unit(option.replacement_item_id || option.affected_item_id)} por producto.</small>
                </label>
                <label className="modifier-required-toggle">
                  <input type="checkbox" checked={option.inventory_effect ?? true} onChange={(event) => updateOption(groupIndex, optionIndex, { inventory_effect: event.target.checked })} /> Afecta inventario
                </label>
              </>}
              <label className="premium-form-group">Texto para cocina
                <input className="modifier-control" maxLength={240} value={option.kitchen_text || ''} placeholder={option.name} onChange={(event) => updateOption(groupIndex, optionIndex, { kitchen_text: event.target.value })} />
              </label>
            </div>
          </div>;
        })}
        <button type="button" className="modifier-add-button modifier-add-button--option" onClick={() => updateGroup(groupIndex, { options: [...group.options, blankOption()] })}><Plus size={16} /> Agregar producto u opción</button>
      </div>
    </article>)}

    <button type="button" className="modifier-add-button modifier-add-button--group" onClick={() => change([...groups, blankGroup()])}><Plus size={16} /> Agregar grupo de selección</button>
    {validation && requiredMinimumConflictIndex < 0 && <p role="alert">{validation}</p>}
    {!dirty && <p role="status">Sin cambios pendientes. Edita un campo o agrega una opción para habilitar Guardar configuración.</p>}
    <div className="premium-footer-actions modifier-manager__footer">
      <Button variant="secondary" disabled={!dirty || save.isPending} onClick={() => {
        if (!configuration.data) return;
        setGroups(hydrateGroups(configuration.data.groups));
        setExpectedVersion(configuration.data.expected_version);
        setDirty(false);
        setMessage('Cambios locales descartados.');
        setRequiresReview(false);
        idempotencyKey.current = '';
      }}><RotateCcw size={15} /> Deshacer cambios</Button>
      <Button variant="primary" disabled={!dirty || save.isPending || requiresReview || (Boolean(validation) && requiredMinimumConflictIndex < 0)} onClick={() => {
        if (validation) {
          setMessage('No se guardó. Corrige los campos señalados antes de intentarlo de nuevo.');
          if (requiredMinimumConflictIndex >= 0) document.getElementById(`modifier-group-${requiredMinimumConflictIndex}-minimum`)?.focus();
          return;
        }
        save.mutate();
      }}><Save size={15} /> {save.isPending ? 'Guardando…' : 'Guardar configuración'}</Button>
    </div>
    </fieldset>

    <div className="modifier-manager__section-heading modifier-manager__section-heading--tools">
      <h3>Probar o copiar la configuración</h3>
      <p>Estas herramientas usan únicamente la versión guardada y no sustituyen el editor.</p>
    </div>
    <CompoundSelectionPreview
      key={productId + ':' + expectedVersion}
      productId={productId}
      groups={configuration.data?.groups || []}
      disabled={dirty || copyBusy || save.isPending}
    />
    <CompoundCopyPanel
      key={productId}
      productId={productId}
      expectedVersion={expectedVersion}
      disabled={dirty || save.isPending}
      onBusyChange={setCopyBusy}
      onCopied={async result => {
        const current = await fetchApi<Configuration>('/products/' + productId + '/modifier-configuration');
        setGroups(hydrateGroups(current.groups));
        setExpectedVersion(current.expected_version);
        setDirty(false);
        setRequiresReview(false);
        if (current.expected_version !== result.version) {
          setMessage('La copia quedó registrada; el destino tiene cambios posteriores. Se muestra su versión vigente para revisión.');
        }
        client.setQueryData<Configuration>(['modifier-configuration', productId], current);
        void client.invalidateQueries({ queryKey: ['product-modifiers', productId] });
      }}
    />
  </section>;
}
