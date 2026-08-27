import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Badge, Button, Input, Modal } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';

interface Item { id: string; name: string; unit_code: string; }
interface Option {
  id: string;
  name: string;
  effect_type: string;
  price_delta_cents: number;
  catalog_price_delta_cents?: number;
  affected_item_id?: string | null;
  replacement_item_id?: string | null;
  remove_quantity?: string | number;
  add_quantity?: string | number;
  kitchen_text?: string;
  variation_kind?: 'ingredient_extra' | 'order_comment';
}
interface Group {
  id: string;
  name: string;
  is_required: boolean;
  minimum_selections: number;
  maximum_selections: number;
  options: Option[];
}
interface Props { productId: string; productName: string; isOpen: boolean; onClose: () => void; }

const emptyGroupForm = { name: '', is_required: false, minimum_selections: 0, maximum_selections: 1 };
const emptyOptionForm = (group_id = '') => ({
  group_id,
  name: '',
  effect_type: 'instruction',
  price_delta_cents: 0,
  affected_item_id: '',
  replacement_item_id: '',
  remove_quantity: '0',
  add_quantity: '0',
  kitchen_text: '',
});

export const ModifierManager = ({ productId, productName, isOpen, onClose }: Props) => {
  const queryClient = useQueryClient();
  const [error, setError] = useState('');
  const [editingGroupId, setEditingGroupId] = useState<string | null>(null);
  const [editingOptionId, setEditingOptionId] = useState<string | null>(null);
  const [groupForm, setGroupForm] = useState(emptyGroupForm);
  const [optionForm, setOptionForm] = useState(emptyOptionForm());
  const { data: groups = [] } = useQuery<Group[]>({
    queryKey: ['product-modifiers', productId],
    queryFn: () => fetchApi(`/products/${productId}/modifier-groups`),
    enabled: isOpen,
  });
  const { data: items = [] } = useQuery<Item[]>({
    queryKey: ['inventory', 'items'],
    queryFn: () => fetchApi('/inventory/items'),
    enabled: isOpen,
  });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['product-modifiers', productId] });
  const resetGroupEditor = () => {
    setEditingGroupId(null);
    setGroupForm(emptyGroupForm);
  };
  const resetOptionEditor = (groupId = optionForm.group_id) => {
    setEditingOptionId(null);
    setOptionForm(emptyOptionForm(groupId));
  };

  const groupMutation = useMutation({
    mutationFn: () => fetchApi(
      editingGroupId ? `/modifier-groups/${editingGroupId}` : `/products/${productId}/modifier-groups`,
      { method: editingGroupId ? 'PATCH' : 'POST', body: JSON.stringify(groupForm) },
    ),
    onSuccess: async (result: unknown) => {
      const saved = result as Group;
      if (!editingGroupId) setOptionForm(emptyOptionForm(saved.id));
      resetGroupEditor();
      setError('');
      await refresh();
    },
    onError: (reason) => setError(reason instanceof Error ? reason.message : 'No fue posible guardar el grupo.'),
  });
  const optionMutation = useMutation({
    mutationFn: () => fetchApi(
      editingOptionId
        ? `/modifier-options/${editingOptionId}`
        : `/modifier-groups/${optionForm.group_id}/options`,
      { method: editingOptionId ? 'PATCH' : 'POST', body: JSON.stringify(optionForm) },
    ),
    onSuccess: async () => {
      resetOptionEditor();
      setError('');
      await refresh();
    },
    onError: (reason) => setError(reason instanceof Error ? reason.message : 'No fue posible guardar la opción.'),
  });
  const archiveGroupMutation = useMutation({
    mutationFn: (groupId: string) => fetchApi(`/modifier-groups/${groupId}`, { method: 'DELETE' }),
    onSuccess: async (_result, groupId) => {
      if (editingGroupId === groupId) resetGroupEditor();
      if (optionForm.group_id === groupId) resetOptionEditor('');
      setError('');
      await refresh();
    },
    onError: (reason) => setError(reason instanceof Error ? reason.message : 'No fue posible eliminar el grupo.'),
  });
  const archiveOptionMutation = useMutation({
    mutationFn: (optionId: string) => fetchApi(`/modifier-options/${optionId}`, { method: 'DELETE' }),
    onSuccess: async (_result, optionId) => {
      if (editingOptionId === optionId) resetOptionEditor();
      setError('');
      await refresh();
    },
    onError: (reason) => setError(reason instanceof Error ? reason.message : 'No fue posible eliminar la opción.'),
  });

  const beginGroupEdit = (group: Group) => {
    setEditingGroupId(group.id);
    setGroupForm({
      name: group.name,
      is_required: group.is_required,
      minimum_selections: group.minimum_selections,
      maximum_selections: group.maximum_selections,
    });
    setError('');
  };
  const beginOptionEdit = (group: Group, option: Option) => {
    setEditingOptionId(option.id);
    setOptionForm({
      group_id: group.id,
      name: option.name,
      effect_type: option.effect_type,
      price_delta_cents: option.catalog_price_delta_cents ?? option.price_delta_cents,
      affected_item_id: option.affected_item_id || '',
      replacement_item_id: option.replacement_item_id || '',
      remove_quantity: String(option.remove_quantity ?? 0),
      add_quantity: String(option.add_quantity ?? 0),
      kitchen_text: option.kitchen_text || '',
    });
    setError('');
  };
  const confirmArchiveGroup = (group: Group) => {
    if (window.confirm(`¿Eliminar el grupo “${group.name}”? Dejará de aparecer en ventas futuras; los pedidos históricos se conservarán.`)) {
      archiveGroupMutation.mutate(group.id);
    }
  };
  const confirmArchiveOption = (option: Option) => {
    if (window.confirm(`¿Eliminar la opción “${option.name}”? Dejará de aparecer en ventas futuras; los pedidos históricos se conservarán.`)) {
      archiveOptionMutation.mutate(option.id);
    }
  };

  const needsAffected = ['remove', 'quantity', 'substitute', 'variant'].includes(optionForm.effect_type);
  const needsReplacement = ['substitute', 'variant'].includes(optionForm.effect_type);

  return <Modal isOpen={isOpen} onClose={onClose} title={`Modificadores: ${productName}`}>
    <div style={{ display: 'grid', gap: 18, maxHeight: '70vh', overflowY: 'auto' }}>
      {error && <div role="alert" style={{ color: '#b91c1c' }}>{error}</div>}
      <section>
        <h3>Grupos activos</h3>
        {groups.length === 0 ? <p>Este producto aún no tiene modificadores.</p> : groups.map((group) => {
          const canManageGroup = group.options.every(
            (option) => !option.variation_kind && option.effect_type !== 'preset_instruction',
          );
          return <div key={group.id} style={{ padding: 10, borderBottom: '1px solid var(--color-border)', display: 'grid', gap: 8 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'center' }}>
              <span><strong>{group.name}</strong> <Badge variant={group.minimum_selections > 0 ? 'info' : 'default'}>{group.minimum_selections}-{group.maximum_selections}</Badge></span>
              {canManageGroup && <span style={{ display: 'flex', gap: 6 }}>
                <Button variant="secondary" onClick={() => beginGroupEdit(group)}>Editar grupo</Button>
                <Button variant="secondary" onClick={() => confirmArchiveGroup(group)} disabled={archiveGroupMutation.isPending}>Eliminar grupo</Button>
              </span>}
            </div>
            {group.options.map((option) => {
              const canManageOption = !option.variation_kind && option.effect_type !== 'preset_instruction';
              return <div key={option.id} style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'center', fontSize: 13 }}>
                <span>{option.name} {option.price_delta_cents ? `+$${(option.price_delta_cents / 100).toFixed(2)}` : ''}</span>
                {canManageOption && <span style={{ display: 'flex', gap: 6 }}>
                  <Button variant="secondary" onClick={() => beginOptionEdit(group, option)}>Editar</Button>
                  <Button variant="secondary" onClick={() => confirmArchiveOption(option)} disabled={archiveOptionMutation.isPending}>Eliminar</Button>
                </span>}
              </div>;
            })}
          </div>;
        })}
      </section>
      <section style={{ display: 'grid', gap: 8 }}>
        <h3>{editingGroupId ? 'Editar grupo' : 'Nuevo grupo'}</h3>
        <Field label="Nombre" value={groupForm.name} setValue={(name) => setGroupForm({ ...groupForm, name })} />
        <label style={{ display: 'flex', gap: 8 }}><input type="checkbox" checked={groupForm.is_required} onChange={(event) => setGroupForm({ ...groupForm, is_required: event.target.checked, minimum_selections: event.target.checked ? Math.max(1, groupForm.minimum_selections) : 0 })} /> Obligatorio</label>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}><NumberField label="Mínimo" value={groupForm.minimum_selections} setValue={(minimum_selections) => setGroupForm({ ...groupForm, minimum_selections })} /><NumberField label="Máximo" value={groupForm.maximum_selections} setValue={(maximum_selections) => setGroupForm({ ...groupForm, maximum_selections })} /></div>
        <div style={{ display: 'flex', gap: 8 }}>
          <Button variant="secondary" onClick={() => groupMutation.mutate()} disabled={!groupForm.name.trim() || groupMutation.isPending}>{editingGroupId ? 'Guardar cambios' : 'Crear grupo'}</Button>
          {editingGroupId && <Button variant="secondary" onClick={resetGroupEditor}>Cancelar</Button>}
        </div>
      </section>
      <section style={{ display: 'grid', gap: 8 }}>
        <h3>{editingOptionId ? 'Editar opción' : 'Nueva opción'}</h3>
        <label>Grupo<select value={optionForm.group_id} disabled={Boolean(editingOptionId)} onChange={(event) => setOptionForm({ ...optionForm, group_id: event.target.value })} style={{ width: '100%', padding: 9 }}><option value="">Selecciona</option>{groups.filter((group) => group.options.every((option) => !option.variation_kind && option.effect_type !== 'preset_instruction')).map((group) => <option key={group.id} value={group.id}>{group.name}</option>)}</select></label>
        <Field label="Nombre" value={optionForm.name} setValue={(name) => setOptionForm({ ...optionForm, name })} />
        <label>Efecto<select value={optionForm.effect_type} onChange={(event) => setOptionForm({ ...optionForm, effect_type: event.target.value })} style={{ width: '100%', padding: 9 }}><option value="instruction">Instrucción libre</option><option value="remove">Quitar ingrediente</option><option value="add">Agregar ingrediente</option><option value="substitute">Sustituir</option><option value="quantity">Cambiar cantidad</option><option value="variant">Elegir variante</option></select></label>
        {(needsAffected || optionForm.effect_type === 'add') && <ItemSelect label={optionForm.effect_type === 'add' ? 'Artículo agregado' : 'Componente afectado'} value={optionForm.affected_item_id} items={items} setValue={(affected_item_id) => setOptionForm({ ...optionForm, affected_item_id })} />}
        {needsReplacement && <ItemSelect label="Artículo de reemplazo" value={optionForm.replacement_item_id} items={items} setValue={(replacement_item_id) => setOptionForm({ ...optionForm, replacement_item_id })} />}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}><Field label="Cantidad eliminada" value={optionForm.remove_quantity} setValue={(remove_quantity) => setOptionForm({ ...optionForm, remove_quantity })} /><Field label="Cantidad agregada" value={optionForm.add_quantity} setValue={(add_quantity) => setOptionForm({ ...optionForm, add_quantity })} /></div>
        <NumberField label="Precio adicional (centavos)" value={optionForm.price_delta_cents} setValue={(price_delta_cents) => setOptionForm({ ...optionForm, price_delta_cents })} />
        <Field label="Texto para cocina" value={optionForm.kitchen_text} setValue={(kitchen_text) => setOptionForm({ ...optionForm, kitchen_text })} />
        <div style={{ display: 'flex', gap: 8 }}>
          <Button variant="primary" onClick={() => optionMutation.mutate()} disabled={!optionForm.group_id || !optionForm.name.trim() || optionMutation.isPending}>{editingOptionId ? 'Guardar cambios' : 'Crear opción'}</Button>
          {editingOptionId && <Button variant="secondary" onClick={() => resetOptionEditor()}>Cancelar</Button>}
        </div>
      </section>
    </div>
  </Modal>;
};

const Field = ({ label, value, setValue }: { label: string; value: string; setValue: (value: string) => void }) => <label style={{ display: 'grid', gap: 4 }}>{label}<Input value={value} onChange={(event: React.ChangeEvent<HTMLInputElement>) => setValue(event.target.value)} /></label>;
const NumberField = ({ label, value, setValue }: { label: string; value: number; setValue: (value: number) => void }) => <label style={{ display: 'grid', gap: 4 }}>{label}<Input type="number" value={value} onChange={(event: React.ChangeEvent<HTMLInputElement>) => setValue(Number(event.target.value))} /></label>;
const ItemSelect = ({ label, value, items, setValue }: { label: string; value: string; items: Item[]; setValue: (value: string) => void }) => <label>{label}<select value={value} onChange={(event) => setValue(event.target.value)} style={{ width: '100%', padding: 9 }}><option value="">Selecciona</option>{items.map((item) => <option key={item.id} value={item.id}>{item.name} ({item.unit_code})</option>)}</select></label>;
