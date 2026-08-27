import React, { useState } from 'react';
import { Button, Input } from '@restaurantos/ui';

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
  const [removeQuantity, setRemoveQuantity] = useState('1');
  const [addQuantity, setAddQuantity] = useState('1');
  const [kitchenText, setKitchenText] = useState('');

  const handleSave = async () => {
    if (!name.trim()) return;
    const priceDeltaCents = Math.round(parseFloat(priceStr || '0') * 100);
    
    await onSave({
      name,
      effect_type: effectType,
      price_delta_cents: priceDeltaCents,
      affected_item_id: affectedItemId || undefined,
      replacement_item_id: replacementItemId || undefined,
      remove_quantity: removeQuantity,
      add_quantity: addQuantity,
      kitchen_text: kitchenText || name,
    });
  };

  const needsAffected = ['remove', 'quantity', 'substitute', 'variant'].includes(effectType);
  const needsReplacement = ['substitute', 'variant'].includes(effectType);

  return (
    <div style={{ padding: 16, backgroundColor: 'var(--color-bg-secondary)', borderTop: '1px solid var(--color-border)', borderBottom: '1px solid var(--color-border)' }}>
      <div style={{ display: 'flex', gap: 12, marginBottom: 12 }}>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label style={{ fontSize: 12, fontWeight: 500 }}>Nombre de la opción</label>
          <Input value={name} onChange={e => setName(e.target.value)} placeholder="Ej. Tocino extra" />
        </div>
        <div style={{ maxWidth: 150, display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label style={{ fontSize: 12, fontWeight: 500 }}>Precio</label>
          <div style={{ position: 'relative' }}>
            <span style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)' }}>$</span>
            <Input value={priceStr} onChange={e => setPriceStr(e.target.value)} style={{ paddingLeft: 24 }} placeholder="0.00" type="number" step="0.01" />
          </div>
        </div>
        <div style={{ maxWidth: 150, display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label style={{ fontSize: 12, fontWeight: 500 }}>Efecto</label>
          <select value={effectType} onChange={e => setEffectType(e.target.value)} style={{ padding: '8px 12px', borderRadius: 4, border: '1px solid var(--color-border)' }}>
            <option value="instruction">📝 Instrucción</option>
            <option value="remove">❌ Quita</option>
            <option value="add">➕ Agrega</option>
            <option value="substitute">🔄 Sustituye</option>
            <option value="variant">🔀 Variante</option>
            <option value="quantity">📊 Cantidad</option>
          </select>
        </div>
      </div>
      
      {((needsAffected || effectType === 'add') || needsReplacement) && (
        <div style={{ display: 'flex', gap: 12, marginBottom: 12 }}>
          {(needsAffected || effectType === 'add') && (
             <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 4 }}>
               <label style={{ fontSize: 12, fontWeight: 500 }}>{effectType === 'add' ? 'Artículo a agregar' : 'Artículo afectado'}</label>
               <select value={affectedItemId} onChange={e => setAffectedItemId(e.target.value)} style={{ padding: '8px 12px', borderRadius: 4, border: '1px solid var(--color-border)' }}>
                 <option value="">Selecciona</option>
                 {items.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
               </select>
             </div>
          )}
          {needsReplacement && (
             <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 4 }}>
               <label style={{ fontSize: 12, fontWeight: 500 }}>Artículo de reemplazo</label>
               <select value={replacementItemId} onChange={e => setReplacementItemId(e.target.value)} style={{ padding: '8px 12px', borderRadius: 4, border: '1px solid var(--color-border)' }}>
                 <option value="">Selecciona</option>
                 {items.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
               </select>
             </div>
          )}
        </div>
      )}
      
      <div style={{ display: 'flex', gap: 12, marginBottom: 12 }}>
         <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 4 }}>
            <label style={{ fontSize: 12, fontWeight: 500 }}>Texto para cocina</label>
            <Input value={kitchenText} onChange={e => setKitchenText(e.target.value)} placeholder="Ej. EXTRA TOCINO" />
         </div>
      </div>

      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
        <Button variant="secondary" onClick={onCancel}>Cancelar</Button>
        <Button variant="primary" onClick={handleSave} disabled={!name.trim()}>Guardar opción</Button>
      </div>
    </div>
  );
};
