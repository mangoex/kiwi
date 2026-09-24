import React, { useEffect, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, fetchApi } from '@restaurantos/api-client';
import { Button } from '@restaurantos/ui';
import { ArrowDown, ArrowUp, Plus, RotateCcw, Save, Trash2 } from 'lucide-react';
import { centsToMxn, mxnToCentsExact } from './ingredientVariationMoney';
import '../../premium-catalogs.css';
import './ModifierManager.css';

type Candidate = { id: string; name: string; sku: string };

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
    inventory_effect: option.effect_type !== 'instruction',
    kitchen_text: (option.kitchen_text || option.name).trim(),
    ...(option.station ? { station: option.station } : {}),
  })),
}));

export function ModifierManager({ productId, productName }: { productId: string; productName: string }) {
  const client = useQueryClient();
  const [groups, setGroups] = useState<ModifierGroup[]>([]);
  const [expectedVersion, setExpectedVersion] = useState(0);
  const [dirty, setDirty] = useState(false);
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
  let validation = '';
  try {
    payloadGroups(groups);
    const invalidGroup = groups.find((group) => !group.name.trim()
      || group.minimum_selections < 0
      || group.maximum_selections < 1
      || group.minimum_selections > group.maximum_selections
      || group.included_selections < 0
      || group.included_selections > group.maximum_selections
      || (group.is_required && group.minimum_selections < 1)
      || group.minimum_selections > group.options.length);
    const invalidOption = groups.flatMap((group) => group.options).find((option) => !option.name.trim()
      || (option.effect_type === 'product_component' && (!option.component_product_id || !/^[1-9]\d*$/.test(String(option.component_quantity || '')))));
    if (invalidGroup) validation = 'Revisa nombre, obligatoriedad, mínimos, máximos y selecciones incluidas del grupo.';
    else if (invalidOption) validation = 'Cada opción necesita nombre; un producto componente también requiere producto y cantidad entera positiva.';
  } catch (reason) {
    validation = reason instanceof Error ? reason.message : 'Revisa los importes de las opciones.';
  }

  if (configuration.isLoading && !configuration.data) return <p role="status">Cargando configuración de {productName}…</p>;
  if (configuration.isError && !configuration.data) return <p role="alert">No fue posible cargar la configuración administrativa. No se habilita el guardado sin su versión vigente.</p>;

  return <section className="modifier-manager" aria-label={`Producto compuesto ${productName}`}>
    <div className="modifier-manager__header">
      <div>
        <h2>Grupos y productos seleccionables</h2>
        <p>El cajero elige productos simples durante el pedido. Las primeras selecciones incluidas no suman precio; las siguientes aplican su importe adicional.</p>
      </div>
      <span className="modifier-version">Versión {expectedVersion}</span>
    </div>

    {configuration.isError && configuration.data && <p role="alert">No fue posible actualizar la lectura. Se conserva tu borrador y la última versión conocida.</p>}
    {message && <p className="admin-catalog-message" role={requiresReview ? 'alert' : 'status'}>{message}</p>}
    {requiresReview && <div className="admin-catalog-message" role="alert"><p>Revisa la versión vigente antes de confirmar nuevamente. No reemplazaremos tu borrador.</p><Button variant="secondary" onClick={() => void reviewCurrentVersion()}><RotateCcw size={15} /> Revisar versión vigente</Button></div>}

    {groups.length === 0 && <div className="modifier-empty-state">Este producto todavía no tiene grupos seleccionables.</div>}

    {groups.map((group, groupIndex) => <article key={group.id || `new-${groupIndex}`} className="modifier-group-card">
      <header className="modifier-group-card__header">
        <div className="modifier-group-fields">
          <label className="premium-form-group">Nombre del grupo
            <input className="modifier-control" value={group.name} onChange={(event) => updateGroup(groupIndex, { name: event.target.value })} />
          </label>
          <label className="premium-form-group">Mínimo
            <input className="modifier-control" type="number" min="0" value={group.minimum_selections} onChange={(event) => updateGroup(groupIndex, { minimum_selections: Number(event.target.value) })} />
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
          <input type="checkbox" checked={group.is_required} onChange={(event) => updateGroup(groupIndex, { is_required: event.target.checked })} /> Grupo obligatorio
        </label>
      </header>

      <div className="modifier-group-card__body">
        {group.options.map((option, optionIndex) => {
          const advanced = !['product_component', 'instruction'].includes(option.effect_type);
          return <div key={option.id || `new-option-${optionIndex}`} className="modifier-option-row">
            <label className="premium-form-group">Tipo
              <select className="modifier-control" value={advanced ? 'advanced' : option.effect_type} disabled={advanced} onChange={(event) => updateOption(groupIndex, optionIndex, {
                effect_type: event.target.value,
                component_product_id: event.target.value === 'product_component' ? '' : null,
                component_quantity: event.target.value === 'product_component' ? '1' : null,
                inventory_effect: event.target.value !== 'instruction',
              })}>
                <option value="product_component">Producto componente</option>
                <option value="instruction">Instrucción de cocina</option>
                {advanced && <option value="advanced">Avanzado: {option.effect_type}</option>}
              </select>
            </label>
            {option.effect_type === 'product_component' ? <label className="premium-form-group">Producto
              <select className="modifier-control" value={option.component_product_id || ''} onChange={(event) => {
                const candidate = candidates.find((row) => row.id === event.target.value);
                updateOption(groupIndex, optionIndex, { component_product_id: event.target.value, name: candidate?.name.slice(0, 120) || option.name, kitchen_text: candidate?.name.slice(0, 240) || option.kitchen_text });
              }}>
                <option value="">Selecciona un producto simple</option>
                {candidates.map((candidate) => <option key={candidate.id} value={candidate.id}>{candidate.name} ({candidate.sku})</option>)}
              </select>
            </label> : <label className="premium-form-group">Nombre / instrucción
              <input className="modifier-control" value={option.name} disabled={advanced} onChange={(event) => updateOption(groupIndex, optionIndex, { name: event.target.value, kitchen_text: event.target.value })} />
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
          </div>;
        })}
        <button type="button" className="modifier-add-button modifier-add-button--option" onClick={() => updateGroup(groupIndex, { options: [...group.options, blankOption()] })}><Plus size={16} /> Agregar producto u opción</button>
      </div>
    </article>)}

    <button type="button" className="modifier-add-button modifier-add-button--group" onClick={() => change([...groups, blankGroup()])}><Plus size={16} /> Agregar grupo de selección</button>
    {validation && <p role="alert">{validation}</p>}
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
      <Button variant="primary" disabled={!dirty || save.isPending || requiresReview || Boolean(validation)} onClick={() => save.mutate()}><Save size={15} /> {save.isPending ? 'Guardando…' : 'Guardar configuración'}</Button>
    </div>
  </section>;
}
