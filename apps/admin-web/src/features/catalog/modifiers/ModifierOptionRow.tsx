import React, { useState } from 'react';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { Badge } from '@restaurantos/ui';

interface Option {
  id: string;
  name: string;
  effect_type: string;
  price_delta_cents: number;
  affected_item_id?: string | null;
  replacement_item_id?: string | null;
}

interface Item { id: string; name: string; }

interface Props {
  option: Option;
  isSelected: boolean;
  onSelect: (option: Option) => void;
  onUpdate: (id: string, payload: any) => void;
  onArchive: (id: string) => void;
  items: Item[];
}

export const ModifierOptionRow = ({ option, isSelected, onSelect, onUpdate, onArchive, items }: Props) => {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: option.id });
  const [isEditing, setIsEditing] = useState(false);
  const [name, setName] = useState(option.name);

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  const getBadgeInfo = () => {
    const itemName = option.affected_item_id ? items.find(i => i.id === option.affected_item_id)?.name || '' : '';
    switch (option.effect_type) {
      case 'instruction': return { text: '📝 Instrucción', variant: 'info' as const };
      case 'remove': return { text: `❌ Quita: ${itemName}`, variant: 'error' as const };
      case 'add': return { text: `➕ Agrega: ${itemName}`, variant: 'success' as const };
      case 'substitute': return { text: '🔄 Sustituye', variant: 'warning' as const };
      case 'variant': return { text: '🔀 Variante', variant: 'warning' as const };
      case 'quantity': return { text: '📊 Cantidad', variant: 'default' as const };
      default: return { text: option.effect_type, variant: 'default' as const };
    }
  };
  const badgeInfo = getBadgeInfo();

  const handleBlur = () => {
    setIsEditing(false);
    if (name !== option.name && name.trim()) {
      onUpdate(option.id, { name: name.trim() });
    } else {
      setName(option.name);
    }
  };

  return (
    <li
      ref={setNodeRef}
      style={{ ...style, display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px', borderBottom: '1px solid var(--color-border)', backgroundColor: isSelected ? 'var(--color-bg-secondary)' : 'transparent', cursor: 'pointer' }}
      onClick={() => onSelect(option)}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <span {...attributes} {...listeners} style={{ cursor: 'grab', color: 'var(--color-text-secondary)', touchAction: 'none' }}>⋮⋮</span>
        {isEditing ? (
          <input
            autoFocus
            value={name}
            onChange={e => setName(e.target.value)}
            onBlur={handleBlur}
            onKeyDown={e => e.key === 'Enter' && handleBlur()}
            style={{ fontWeight: 600, fontSize: 16, border: '1px solid var(--color-border)', borderRadius: 4, padding: '2px 4px' }}
            onClick={e => e.stopPropagation()}
          />
        ) : (
          <span style={{ fontWeight: 600, fontSize: 16 }} onClick={(e) => { e.stopPropagation(); setIsEditing(true); }}>
            {option.name}
          </span>
        )}
        <Badge variant={badgeInfo.variant as any}>{badgeInfo.text}</Badge>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <span style={{ fontVariantNumeric: 'tabular-nums', fontWeight: 500 }}>
          ${(option.price_delta_cents / 100).toFixed(2)}
        </span>
        <button onClick={(e) => { e.stopPropagation(); setIsEditing(true); }} style={{ background: 'none', border: 'none', cursor: 'pointer' }}>✏️</button>
        <button onClick={(e) => { e.stopPropagation(); onArchive(option.id); }} style={{ background: 'none', border: 'none', cursor: 'pointer' }}>🗑️</button>
      </div>
    </li>
  );
};
