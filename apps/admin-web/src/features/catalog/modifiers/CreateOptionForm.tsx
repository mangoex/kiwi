import React, { useState } from 'react';
import { Button, Input } from '@restaurantos/ui';
import { mxnToCentsExact } from '../ingredientVariationMoney';

interface Props {
  groupId: string;
  items: { id: string; name: string; }[];
  onSave: (payload: any) => Promise<void>;
  onCancel: () => void;
}

export const CreateOptionForm = ({ groupId, items, onSave, onCancel }: Props) => {
  const [name, setName] = useState('');
  const [priceStr, setPriceStr] = useState('0.00');
  const [effectType, setEffectType] = useState('instruction');
  const [affectedItemId, setAffectedItemId] = useState('');
  const [replacementItemId, setReplacementItemId] = useState('');
  const [kitchenText, setKitchenText] = useState('');
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState('');

  const handleSave = async () => {
    if (!name.trim() || saving) return;
    setSaveError('');
    let priceDeltaCents: number;
    try {
      priceDeltaCents = mxnToCentsExact(priceStr || '0');
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : 'El precio no es válido.');
      return;
    }
    setSaving(true);
    try {
      await onSave({
        name: name.trim(),
        effect_type: effectType,
        price_delta_cents: priceDeltaCents,
        affected_item_id: affectedItemId || undefined,
        replacement_item_id: replacementItemId || undefined,
        kitchen_text: kitchenText || name.trim(),
      });
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : 'No fue posible guardar la opción.');
    } finally {
      setSaving(false);
    }
  };

  const needsAffected = ['remove', 'quantity', 'substitute', 'variant'].includes(effectType);
  const needsReplacement = ['substitute', 'variant'].includes(effectType);

  const labelStyle = { fontSize: 11, fontWeight: 600 as const, color: 'var(--color-text-muted)', textTransform: 'uppercase' as const, letterSpacing: '0.3px', marginBottom: 3 };
  const selectStyle = { padding: '6px 10px', borderRadius: 4, border: '1px solid var(--color-border)', fontSize: 13, width: '100%', backgroundColor: 'var(--color-surface)' };

  return (
    <div style={{ padding: 14, backgroundColor: 'var(--color-bg)', border: '1px solid var(--color-border)', borderRadius: 8 }}>
      <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 10, color: 'var(--color-text)' }}>
        Nueva opción
      </div>

      {/* Row 1: Name + Effect + Price */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 140px 100px', gap: 10, marginBottom: 10 }}>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <label style={labelStyle}>Nombre</label>
          <Input value={name} onChange={e => setName(e.target.value)} placeholder="Ej. Tocino extra" />
        </div>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <label style={labelStyle}>Efecto</label>
          <select value={effectType} onChange={e => setEffectType(e.target.value)} style={selectStyle}>
            <option value="instruction">📝 Instrucción</option>
            <option value="remove">✕ Quita</option>
            <option value="add">+ Agrega</option>
            <option value="substitute">⇄ Sustituye</option>
            <option value="variant">◇ Variante</option>
            <option value="quantity"># Cantidad</option>
          </select>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <label style={labelStyle}>Precio</label>
          <div style={{ position: 'relative' }}>
            <span style={{ position: 'absolute', left: 8, top: '50%', transform: 'translateY(-50%)', color: 'var(--color-text-muted)', fontSize: 13 }}>$</span>
            <Input value={priceStr} onChange={e => setPriceStr(e.target.value)} style={{ paddingLeft: 20 }} placeholder="0.00" type="number" step="0.01" />
          </div>
        </div>
      </div>

      {/* Row 2: Item selectors (conditional) */}
      {(needsAffected || effectType === 'add' || needsReplacement) && (
        <div style={{ display: 'grid', gridTemplateColumns: needsReplacement ? '1fr 1fr' : '1fr', gap: 10, marginBottom: 10 }}>
          {(needsAffected || effectType === 'add') && (
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              <label style={labelStyle}>{effectType === 'add' ? 'Artículo a agregar' : 'Artículo afectado'}</label>
              <select value={affectedItemId} onChange={e => setAffectedItemId(e.target.value)} style={selectStyle}>
                <option value="">— Selecciona —</option>
                {items.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
            </div>
          )}
          {needsReplacement && (
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              <label style={labelStyle}>Reemplazo</label>
              <select value={replacementItemId} onChange={e => setReplacementItemId(e.target.value)} style={selectStyle}>
                <option value="">— Selecciona —</option>
                {items.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
            </div>
          )}
        </div>
      )}

      {/* Row 3: Kitchen text */}
      <div style={{ display: 'flex', flexDirection: 'column', marginBottom: 12 }}>
        <label style={labelStyle}>Texto para cocina</label>
        <Input value={kitchenText} onChange={e => setKitchenText(e.target.value)} placeholder={name ? name.toUpperCase() : 'Ej. EXTRA TOCINO'} />
      </div>

      {saveError && (
        <div role="alert" style={{ marginBottom: 10, color: 'var(--color-error)', fontSize: 12 }}>
          {saveError}
        </div>
      )}

      {/* Buttons */}
      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
        <Button variant="secondary" onClick={onCancel}>Cancelar</Button>
        <Button variant="primary" onClick={handleSave} disabled={!name.trim() || saving}>
          {saving ? 'Guardando...' : 'Guardar opción'}
        </Button>
      </div>
    </div>
  );
};
