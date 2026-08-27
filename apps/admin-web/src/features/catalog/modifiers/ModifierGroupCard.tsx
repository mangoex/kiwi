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

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
    border: '1px solid var(--color-border)',
    borderRadius: 8,
    marginBottom: 24,
    backgroundColor: 'var(--color-bg)',
    boxShadow: '0 1px 2px rgba(9, 30, 66, 0.25)'
  };

  const handleBlurTitle = () => {
    setIsEditingTitle(false);
    if (name !== group.name && name.trim()) {
      onUpdateGroup(group.id, { name: name.trim() });
    } else {
      setName(group.name);
    }
  };

  return (
    <div ref={setNodeRef} style={style}>
      <div style={{ padding: 16, borderBottom: '1px solid var(--color-border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', backgroundColor: 'var(--color-bg-secondary)', borderTopLeftRadius: 8, borderTopRightRadius: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span {...attributes} {...listeners} style={{ cursor: 'grab', color: 'var(--color-text-secondary)', touchAction: 'none' }}>☰</span>
          {isEditingTitle ? (
            <input
              autoFocus
              value={name}
              onChange={e => setName(e.target.value)}
              onBlur={handleBlurTitle}
              onKeyDown={e => e.key === 'Enter' && handleBlurTitle()}
              style={{ fontWeight: 600, fontSize: 16, border: '1px solid var(--color-border)', borderRadius: 4, padding: '2px 4px' }}
            />
          ) : (
            <span style={{ fontWeight: 600, fontSize: 16, cursor: 'pointer' }} onClick={() => setIsEditingTitle(true)}>
              {group.name}
            </span>
          )}
          <Badge variant={group.is_required ? 'error' as any : 'default' as any}>
            {group.is_required ? 'Obligatorio' : 'Opcional'}
          </Badge>
          <Badge variant="default">
            {group.maximum_selections === group.minimum_selections 
              ? `Máx ${group.maximum_selections}` 
              : `Mín ${group.minimum_selections} - Máx ${group.maximum_selections}`}
          </Badge>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={() => setIsEditingTitle(true)} style={{ background: 'none', border: 'none', cursor: 'pointer' }}>✏️</button>
          <button onClick={() => onCloneGroup(group.id)} style={{ background: 'none', border: 'none', cursor: 'pointer' }}>📋</button>
          <button onClick={() => { if(confirm('¿Seguro que deseas archivar este grupo?')) onArchiveGroup(group.id); }} style={{ background: 'none', border: 'none', cursor: 'pointer' }}>🗑️</button>
        </div>
      </div>
      
      <ul style={{ padding: 0, margin: 0, listStyle: 'none' }}>
        <SortableContext items={group.options.map(o => o.id)} strategy={verticalListSortingStrategy}>
          {group.options.map(option => (
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
      </ul>
      
      {showCreateOption && (
        <CreateOptionForm 
          groupId={group.id} 
          items={items} 
          onSave={async (payload) => { await onCreateOption(group.id, payload); setShowCreateOption(false); }}
          onCancel={() => setShowCreateOption(false)}
        />
      )}
      
      {!showCreateOption && (
        <div style={{ padding: '12px 16px' }}>
          <button onClick={() => setShowCreateOption(true)} style={{ background: 'none', border: 'none', color: 'var(--color-primary)', cursor: 'pointer', fontWeight: 500, padding: '8px 0' }}>
            + Agregar opción
          </button>
        </div>
      )}
    </div>
  );
};
