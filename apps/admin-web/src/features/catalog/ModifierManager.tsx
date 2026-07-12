import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Badge, Button, Input, Modal } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';
import { resolveBranchId } from '../../lib/branchContext';

interface Item { id: string; name: string; unit_code: string; }
interface Option { id: string; name: string; effect_type: string; price_delta_cents: number; }
interface Group { id: string; name: string; minimum_selections: number; maximum_selections: number; options: Option[]; }
interface Props { productId: string; productName: string; isOpen: boolean; onClose: () => void; }

export const ModifierManager = ({ productId, productName, isOpen, onClose }: Props) => {
  const queryClient = useQueryClient();
  const branchId = resolveBranchId();
  const [error, setError] = useState('');
  const [groupForm, setGroupForm] = useState({ name: '', is_required: false, minimum_selections: 0, maximum_selections: 1 });
  const [optionForm, setOptionForm] = useState({ group_id: '', name: '', effect_type: 'instruction', price_delta_cents: 0, affected_item_id: '', replacement_item_id: '', remove_quantity: '0', add_quantity: '0', kitchen_text: '' });
  const query = branchId ? `?branch_id=${branchId}` : '';
  const { data: groups = [] } = useQuery<Group[]>({ queryKey: ['product-modifiers', productId, branchId], queryFn: () => fetchApi(`/products/${productId}/modifiers${query}`), enabled: isOpen });
  const { data: items = [] } = useQuery<Item[]>({ queryKey: ['inventory', 'items'], queryFn: () => fetchApi('/inventory/items'), enabled: isOpen });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['product-modifiers', productId] });
  const groupMutation = useMutation({
    mutationFn: () => fetchApi(`/products/${productId}/modifier-groups`, { method: 'POST', body: JSON.stringify(groupForm) }),
    onSuccess: async (created: unknown) => { const group = created as Group; setOptionForm({ ...optionForm, group_id: group.id }); setGroupForm({ name: '', is_required: false, minimum_selections: 0, maximum_selections: 1 }); setError(''); await refresh(); },
    onError: (reason) => setError(reason instanceof Error ? reason.message : 'No fue posible crear el grupo.'),
  });
  const optionMutation = useMutation({
    mutationFn: () => fetchApi(`/modifier-groups/${optionForm.group_id}/options`, { method: 'POST', body: JSON.stringify(optionForm) }),
    onSuccess: async () => { setOptionForm({ group_id: optionForm.group_id, name: '', effect_type: 'instruction', price_delta_cents: 0, affected_item_id: '', replacement_item_id: '', remove_quantity: '0', add_quantity: '0', kitchen_text: '' }); setError(''); await refresh(); },
    onError: (reason) => setError(reason instanceof Error ? reason.message : 'No fue posible crear la opción.'),
  });
  const needsAffected = ['remove', 'quantity', 'substitute', 'variant'].includes(optionForm.effect_type);
  const needsReplacement = ['substitute', 'variant'].includes(optionForm.effect_type);

  return <Modal isOpen={isOpen} onClose={onClose} title={`Modificadores: ${productName}`}>
    <div style={{ display: 'grid', gap: 18, maxHeight: '70vh', overflowY: 'auto' }}>
      {error && <div role="alert" style={{ color: '#b91c1c' }}>{error}</div>}
      <section><h3>Grupos activos</h3>{groups.length === 0 ? <p>Este producto aún no tiene modificadores.</p> : groups.map((group) => <div key={group.id} style={{ padding: 10, borderBottom: '1px solid var(--color-border)' }}><strong>{group.name}</strong> <Badge variant={group.minimum_selections > 0 ? 'info' : 'default'}>{group.minimum_selections}-{group.maximum_selections}</Badge><div style={{ marginTop: 6 }}>{group.options.map((option) => <span key={option.id} style={{ marginRight: 12, fontSize: 13 }}>{option.name} {option.price_delta_cents ? `+$${(option.price_delta_cents / 100).toFixed(2)}` : ''}</span>)}</div></div>)}</section>
      <section style={{ display: 'grid', gap: 8 }}><h3>Nuevo grupo</h3><Field label="Nombre" value={groupForm.name} setValue={(name) => setGroupForm({ ...groupForm, name })} /><label style={{ display: 'flex', gap: 8 }}><input type="checkbox" checked={groupForm.is_required} onChange={(event) => setGroupForm({ ...groupForm, is_required: event.target.checked, minimum_selections: event.target.checked ? Math.max(1, groupForm.minimum_selections) : groupForm.minimum_selections })} /> Obligatorio</label><div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}><NumberField label="Mínimo" value={groupForm.minimum_selections} setValue={(minimum_selections) => setGroupForm({ ...groupForm, minimum_selections })} /><NumberField label="Máximo" value={groupForm.maximum_selections} setValue={(maximum_selections) => setGroupForm({ ...groupForm, maximum_selections })} /></div><Button variant="secondary" onClick={() => groupMutation.mutate()}>Crear grupo</Button></section>
      <section style={{ display: 'grid', gap: 8 }}><h3>Nueva opción</h3><label>Grupo<select value={optionForm.group_id} onChange={(event) => setOptionForm({ ...optionForm, group_id: event.target.value })} style={{ width: '100%', padding: 9 }}><option value="">Selecciona</option>{groups.map((group) => <option key={group.id} value={group.id}>{group.name}</option>)}</select></label><Field label="Nombre" value={optionForm.name} setValue={(name) => setOptionForm({ ...optionForm, name })} /><label>Efecto<select value={optionForm.effect_type} onChange={(event) => setOptionForm({ ...optionForm, effect_type: event.target.value })} style={{ width: '100%', padding: 9 }}><option value="instruction">Instrucción libre</option><option value="remove">Quitar ingrediente</option><option value="add">Agregar ingrediente</option><option value="substitute">Sustituir</option><option value="quantity">Cambiar cantidad</option><option value="variant">Elegir variante</option></select></label>{(needsAffected || optionForm.effect_type === 'add') && <ItemSelect label={optionForm.effect_type === 'add' ? 'Artículo agregado' : 'Componente afectado'} value={optionForm.affected_item_id} items={items} setValue={(affected_item_id) => setOptionForm({ ...optionForm, affected_item_id })} />}{needsReplacement && <ItemSelect label="Artículo de reemplazo" value={optionForm.replacement_item_id} items={items} setValue={(replacement_item_id) => setOptionForm({ ...optionForm, replacement_item_id })} />}<div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}><Field label="Cantidad eliminada" value={optionForm.remove_quantity} setValue={(remove_quantity) => setOptionForm({ ...optionForm, remove_quantity })} /><Field label="Cantidad agregada" value={optionForm.add_quantity} setValue={(add_quantity) => setOptionForm({ ...optionForm, add_quantity })} /></div><NumberField label="Precio adicional (centavos)" value={optionForm.price_delta_cents} setValue={(price_delta_cents) => setOptionForm({ ...optionForm, price_delta_cents })} /><Field label="Texto para cocina" value={optionForm.kitchen_text} setValue={(kitchen_text) => setOptionForm({ ...optionForm, kitchen_text })} /><Button variant="primary" onClick={() => optionMutation.mutate()} disabled={!optionForm.group_id}>Crear opción</Button></section>
    </div>
  </Modal>;
};

const Field = ({ label, value, setValue }: { label: string; value: string; setValue: (value: string) => void }) => <label style={{ display: 'grid', gap: 4 }}>{label}<Input value={value} onChange={(event: React.ChangeEvent<HTMLInputElement>) => setValue(event.target.value)} /></label>;
const NumberField = ({ label, value, setValue }: { label: string; value: number; setValue: (value: number) => void }) => <label style={{ display: 'grid', gap: 4 }}>{label}<Input type="number" value={value} onChange={(event: React.ChangeEvent<HTMLInputElement>) => setValue(Number(event.target.value))} /></label>;
const ItemSelect = ({ label, value, items, setValue }: { label: string; value: string; items: Item[]; setValue: (value: string) => void }) => <label>{label}<select value={value} onChange={(event) => setValue(event.target.value)} style={{ width: '100%', padding: 9 }}><option value="">Selecciona</option>{items.map((item) => <option key={item.id} value={item.id}>{item.name} ({item.unit_code})</option>)}</select></label>;
