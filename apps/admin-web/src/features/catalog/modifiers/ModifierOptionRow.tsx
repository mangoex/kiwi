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
  kitchen_text?: string;
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

const EFFECT_CONFIG: Record<string, { emoji: string; label: string; variant: 'default' | 'success' | 'warning' | 'danger' | 'info' }> = {
  instruction: { emoji: '📝', label: 'Instrucción', variant: 'info' },
  remove:      { emoji: '✕',  label: 'Quita', variant: 'danger' },
  add:         { emoji: '+',  label: 'Agrega', variant: 'success' },
  substitute:  { emoji: '⇄',  label: 'Sustituye', variant: 'warning' },
  variant:     { emoji: '◇',  label: 'Variante', variant: 'warning' },
  quantity:    { emoji: '#',  label: 'Cantidad', variant: 'default' },
};

export const ModifierOptionRow = ({ option, isSelected, onSelect, onUpdate, onArchive, items }: Props) => {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: option.id });
  const [isEditing, setIsEditing] = useState(false);
  const [name, setName] = useState(option.name);
  const [hover, setHover] = useState(false);

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  const effect = EFFECT_CONFIG[option.effect_type] || EFFECT_CONFIG.instruction;
  const itemName = option.affected_item_id ? items.find(i => i.id === option.affected_item_id)?.name : null;

  const handleBlur = () => {
    setIsEditing(false);
    if (name !== option.name && name.trim()) {
      onUpdate(option.id, { name: name.trim() });
    } else {
      setName(option.name);
    }
  };

  const priceMXN = (option.price_delta_cents / 100).toFixed(2);

  return (
    <div
      ref={setNodeRef}
      style={{
        ...style,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '8px 16px',
        borderBottom: '1px solid var(--color-border)',
        backgroundColor: isSelected ? 'rgba(16, 185, 129, 0.06)' : hover ? 'rgba(0,0,0,0.015)' : 'transparent',
        cursor: 'pointer',
        transition: 'background-color 0.1s',
      }}
      onClick={() => onSelect(option)}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      {/* Left: drag + name + badge */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1, minWidth: 0 }}>
        <span
          {...attributes}
          {...listeners}
          style={{ cursor: 'grab', color: 'var(--color-text-muted)', touchAction: 'none', fontSize: 12, lineHeight: 1, opacity: hover ? 1 : 0.3, transition: 'opacity 0.15s' }}
          title="Arrastra para reordenar"
        >
          ⋮⋮
        </span>
        {isEditing ? (
          <input
            autoFocus
            value={name}
            onChange={e => setName(e.target.value)}
            onBlur={handleBlur}
            onKeyDown={e => { if (e.key === 'Enter') handleBlur(); if (e.key === 'Escape') { setName(option.name); setIsEditing(false); } }}
            style={{ fontWeight: 500, fontSize: 13, border: '1px solid var(--color-green)', borderRadius: 4, padding: '2px 6px', outline: 'none', minWidth: 100 }}
            onClick={e => e.stopPropagation()}
          />
        ) : (
          <span
            style={{ fontWeight: 500, fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
            onDoubleClick={(e) => { e.stopPropagation(); setIsEditing(true); }}
            title="Doble click para editar"
          >
            {option.name}
          </span>
        )}
        <Badge variant={effect.variant}>
          {effect.emoji} {effect.label}
        </Badge>
        {itemName && (
          <span style={{ fontSize: 11, color: 'var(--color-text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 120 }} title={itemName}>
            {itemName}
          </span>
        )}
      </div>

      {/* Right: price + actions */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
        <span style={{
          fontVariantNumeric: 'tabular-nums',
          fontWeight: 600,
          fontSize: 13,
          color: option.price_delta_cents > 0 ? 'var(--color-green)' : 'var(--color-text-muted)',
          minWidth: 52,
          textAlign: 'right',
        }}>
          {option.price_delta_cents > 0 ? `+$${priceMXN}` : option.price_delta_cents < 0 ? `-$${Math.abs(option.price_delta_cents / 100).toFixed(2)}` : '$0.00'}
        </span>
        <div style={{ display: 'flex', gap: 0, opacity: hover ? 1 : 0, transition: 'opacity 0.15s' }}>
          <button
            onClick={(e) => { e.stopPropagation(); setIsEditing(true); }}
            title="Editar opción"
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '2px 4px', fontSize: 13, lineHeight: 1 }}
          >✏️</button>
          <button
            onClick={(e) => { e.stopPropagation(); onArchive(option.id); }}
            title="Archivar opción"
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '2px 4px', fontSize: 13, lineHeight: 1 }}
          >🗑️</button>
        </div>
      </div>
    </div>
  );
};
