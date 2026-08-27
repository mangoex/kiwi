import React, { useState } from 'react';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable';
import { Badge } from '@restaurantos/ui';
import { ModifierOptionRow } from './ModifierOptionRow';
import { CreateOptionForm } from './CreateOptionForm';

interface Group {
  id: string;
  name: string;
  is_required: boolean;
  minimum_selections: number;
  maximum_selections: number;
  options: any[];
}

interface Props {
  group: Group;
  items: any[];
  selectedOptionId: string | null;
  onSelectOption: (option: any) => void;
  onUpdateGroup: (id: string, payload: any) => void;
  onArchiveGroup: (id: string) => void;
  onUpdateOption: (id: string, payload: any) => void;
  onArchiveOption: (id: string) => void;
  onCreateOption: (groupId: string, payload: any) => Promise<void>;
  onCloneGroup: (id: string) => void;
}

export const ModifierGroupCard = ({ group, items, selectedOptionId, onSelectOption, onUpdateGroup, onArchiveGroup, onUpdateOption, onArchiveOption, onCreateOption, onCloneGroup }: Props) => {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: group.id });
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [name, setName] = useState(group.name);
  const [showCreateOption, setShowCreateOption] = useState(false);
  const [hoverActions, setHoverActions] = useState(false);

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  const handleBlurTitle = () => {
    setIsEditingTitle(false);
    if (name !== group.name && name.trim()) {
      onUpdateGroup(group.id, { name: name.trim() });
    } else {
      setName(group.name);
    }
  };

  const options = group.options || [];

  return (
    <div ref={setNodeRef} style={style}>
      {/* Group Header */}
      <div
        style={{
          padding: '10px 16px',
          borderBottom: '1px solid var(--color-border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          backgroundColor: 'var(--color-bg)',
        }}
        onMouseEnter={() => setHoverActions(true)}
        onMouseLeave={() => setHoverActions(false)}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span
            {...attributes}
            {...listeners}
            style={{ cursor: 'grab', color: 'var(--color-text-muted)', touchAction: 'none', fontSize: 14, lineHeight: 1 }}
            title="Arrastra para reordenar"
          >
            ⠿
          </span>
          {isEditingTitle ? (
            <input
              autoFocus
              value={name}
              onChange={e => setName(e.target.value)}
              onBlur={handleBlurTitle}
              onKeyDown={e => { if (e.key === 'Enter') handleBlurTitle(); if (e.key === 'Escape') { setName(group.name); setIsEditingTitle(false); } }}
              style={{ fontWeight: 600, fontSize: 13, border: '1px solid var(--color-green)', borderRadius: 4, padding: '3px 6px', outline: 'none', minWidth: 120 }}
            />
          ) : (
            <span
              style={{ fontWeight: 600, fontSize: 13, cursor: 'pointer', textTransform: 'uppercase', letterSpacing: '0.3px' }}
              onClick={() => setIsEditingTitle(true)}
              title="Click para editar nombre"
            >
              {group.name}
            </span>
          )}
          <Badge variant={group.is_required ? 'danger' : 'default'}>
            {group.is_required ? 'Obligatorio' : 'Opcional'}
          </Badge>
          <Badge variant="default">
            {group.minimum_selections === group.maximum_selections
              ? `Elige ${group.maximum_selections}`
              : `${group.minimum_selections}–${group.maximum_selections}`}
          </Badge>
        </div>
        <div style={{ display: 'flex', gap: 2, opacity: hoverActions ? 1 : 0.3, transition: 'opacity 0.15s' }}>
          <button
            onClick={() => setIsEditingTitle(true)}
            title="Editar grupo"
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '4px 6px', borderRadius: 4, fontSize: 14, lineHeight: 1 }}
          >✏️</button>
          <button
            onClick={() => onCloneGroup(group.id)}
            title="Clonar grupo a otro producto"
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '4px 6px', borderRadius: 4, fontSize: 14, lineHeight: 1 }}
          >📋</button>
          <button
            onClick={() => onArchiveGroup(group.id)}
            title="Archivar grupo"
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '4px 6px', borderRadius: 4, fontSize: 14, lineHeight: 1 }}
          >🗑️</button>
        </div>
      </div>

      {/* Options list */}
      {options.length === 0 ? (
        <div style={{ padding: '16px 16px 8px', color: 'var(--color-text-muted)', fontSize: 13, fontStyle: 'italic' }}>
          Sin opciones — agrega una opción a este grupo
        </div>
      ) : (
        <SortableContext items={options.map((o: any) => o.id)} strategy={verticalListSortingStrategy}>
          {options.map((option: any) => (
            <ModifierOptionRow
              key={option.id}
              option={option}
              isSelected={selectedOptionId === option.id}
              onSelect={onSelectOption}
              onUpdate={onUpdateOption}
              onArchive={onArchiveOption}
              items={items}
            />
          ))}
        </SortableContext>
      )}

      {/* Add option button / form */}
      <div style={{ padding: '8px 16px 12px' }}>
        {showCreateOption ? (
          <CreateOptionForm
            groupId={group.id}
            items={items}
            onSave={async (payload) => { await onCreateOption(group.id, payload); setShowCreateOption(false); }}
            onCancel={() => setShowCreateOption(false)}
          />
        ) : (
          <button
            onClick={() => setShowCreateOption(true)}
            style={{ background: 'none', border: 'none', color: 'var(--color-green)', cursor: 'pointer', fontWeight: 500, fontSize: 13, padding: '4px 0' }}
          >
            + Agregar opción
          </button>
        )}
      </div>
    </div>
  );
};
