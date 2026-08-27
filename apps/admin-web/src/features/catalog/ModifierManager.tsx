import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Modal } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';
import { resolveBranchId } from '../../lib/branchContext';
import { DndContext, closestCenter, KeyboardSensor, PointerSensor, useSensor, useSensors } from '@dnd-kit/core';
import { arrayMove, SortableContext, sortableKeyboardCoordinates, verticalListSortingStrategy } from '@dnd-kit/sortable';
import { ModifierGroupCard } from './modifiers/ModifierGroupCard';
import { CreateGroupForm } from './modifiers/CreateGroupForm';
import { RecipePreviewPanel } from './modifiers/RecipePreviewPanel';
import { CloneDialog } from './modifiers/CloneDialog';

interface Props { productId: string; productName: string; isOpen: boolean; onClose: () => void; }

export const ModifierManager = ({ productId, productName, isOpen, onClose }: Props) => {
  const queryClient = useQueryClient();
  const branchId = resolveBranchId();
  const [error, setError] = useState('');
  const [selectedOptionId, setSelectedOptionId] = useState<string | null>(null);
  const [showCreateGroup, setShowCreateGroup] = useState(false);
  const [cloneDialogState, setCloneDialogState] = useState<{isOpen: boolean, groupId: string | null}>({isOpen: false, groupId: null});

  const query = branchId ? `?branch_id=${branchId}` : '';
  const { data: groups = [] } = useQuery<any[]>({ 
    queryKey: ['product-modifiers', productId, branchId], 
    queryFn: () => fetchApi(`/products/${productId}/modifiers${query}`), 
    enabled: isOpen 
  });
  const { data: items = [] } = useQuery<any[]>({ 
    queryKey: ['inventory', 'items'], 
    queryFn: () => fetchApi('/inventory/items'), 
    enabled: isOpen 
  });

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['product-modifiers', productId] });

  const createGroup = useMutation({
    mutationFn: (payload: any) => fetchApi(`/products/${productId}/modifier-groups`, { method: 'POST', body: JSON.stringify(payload) }),
    onSuccess: async () => { setShowCreateGroup(false); await refresh(); },
  });

  const updateGroup = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: any }) => fetchApi(`/modifier-groups/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
    onSuccess: async () => { await refresh(); },
  });

  const archiveGroup = useMutation({
    mutationFn: (id: string) => fetchApi(`/modifier-groups/${id}`, { method: 'DELETE' }),
    onSuccess: async () => { await refresh(); },
  });

  const createOption = useMutation({
    mutationFn: ({ groupId, payload }: { groupId: string; payload: any }) => fetchApi(`/modifier-groups/${groupId}/options`, { method: 'POST', body: JSON.stringify(payload) }),
    onSuccess: async () => { await refresh(); },
  });

  const updateOption = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: any }) => fetchApi(`/modifier-options/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
    onSuccess: async () => { await refresh(); },
  });

  const archiveOption = useMutation({
    mutationFn: (id: string) => fetchApi(`/modifier-options/${id}`, { method: 'DELETE' }),
    onSuccess: async () => { await refresh(); },
  });

  const cloneGroupOrAll = useMutation({
    mutationFn: ({ targetProductId, mode, groupId }: { targetProductId: string, mode: 'group' | 'all', groupId?: string }) => {
      if (mode === 'group') {
        return fetchApi(`/modifier-groups/${groupId}/clone`, { method: 'POST', body: JSON.stringify({ target_product_id: targetProductId }) });
      } else {
        return fetchApi(`/products/${productId}/clone-modifiers`, { method: 'POST', body: JSON.stringify({ target_product_id: targetProductId }) });
      }
    },
    onSuccess: () => setCloneDialogState({ isOpen: false, groupId: null }),
  });

  const reorderGroups = useMutation({
    mutationFn: (orderedIds: string[]) => fetchApi(`/products/${productId}/modifier-groups/reorder`, { method: 'PUT', body: JSON.stringify({ ordered_ids: orderedIds }) }),
    onSuccess: async () => { await refresh(); },
  });

  const reorderOptions = useMutation({
    mutationFn: ({ groupId, orderedIds }: { groupId: string, orderedIds: string[] }) => fetchApi(`/modifier-groups/${groupId}/options/reorder`, { method: 'PUT', body: JSON.stringify({ ordered_ids: orderedIds }) }),
    onSuccess: async () => { await refresh(); },
  });

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  const handleDragEnd = (event: any) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;

    // Check if dragging a group
    const isGroup = groups.some((g: any) => g.id === active.id);
    if (isGroup) {
      const oldIndex = groups.findIndex((g: any) => g.id === active.id);
      const newIndex = groups.findIndex((g: any) => g.id === over.id);
      const newGroups = arrayMove(groups, oldIndex, newIndex);
      const orderedIds = newGroups.map((g: any) => g.id);
      queryClient.setQueryData(['product-modifiers', productId, branchId], newGroups);
      reorderGroups.mutate(orderedIds);
    } else {
      // It's an option. Find the group.
      const group = groups.find((g: any) => g.options.some((o: any) => o.id === active.id));
      if (!group) return;
      const oldIndex = group.options.findIndex((o: any) => o.id === active.id);
      const newIndex = group.options.findIndex((o: any) => o.id === over.id);
      const newOptions = arrayMove(group.options, oldIndex, newIndex);
      const orderedIds = newOptions.map((o: any) => o.id);
      const newGroups = groups.map((g: any) => g.id === group.id ? { ...g, options: newOptions } : g);
      queryClient.setQueryData(['product-modifiers', productId, branchId], newGroups);
      reorderOptions.mutate({ groupId: group.id, orderedIds });
    }
  };

  const selectedOption = groups.flatMap((g: any) => g.options).find((o: any) => o.id === selectedOptionId) || null;

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={`Modificadores: ${productName}`} >
      <div style={{ display: 'flex', height: '80vh', overflow: 'hidden' }}>
        <div style={{ flex: 2, padding: 24, overflowY: 'auto', borderRight: '1px solid var(--color-border)' }}>
          {error && <div role="alert" style={{ color: 'var(--color-error)', marginBottom: 16 }}>{error}</div>}
          
          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
            <SortableContext items={groups.map((g: any) => g.id)} strategy={verticalListSortingStrategy}>
              {groups.map((group: any) => (
                <ModifierGroupCard
                  key={group.id}
                  group={group}
                  items={items}
                  selectedOptionId={selectedOptionId}
                  onSelectOption={opt => setSelectedOptionId(opt.id)}
                  onUpdateGroup={(id, payload) => updateGroup.mutate({ id, payload })}
                  onArchiveGroup={(id) => archiveGroup.mutate(id)}
                  onUpdateOption={(id, payload) => updateOption.mutate({ id, payload })}
                  onArchiveOption={(id) => archiveOption.mutate(id)}
                  onCreateOption={async (groupId, payload) => { createOption.mutate({ groupId, payload }); }}
                  onCloneGroup={(id) => setCloneDialogState({ isOpen: true, groupId: id })}
                />
              ))}
            </SortableContext>
          </DndContext>
          
          {showCreateGroup ? (
            <CreateGroupForm 
              onSave={async (payload) => createGroup.mutate(payload)}
              onCancel={() => setShowCreateGroup(false)}
            />
          ) : (
            <button 
              onClick={() => setShowCreateGroup(true)}
              style={{ width: '100%', padding: 12, border: '1px dashed var(--color-border)', borderRadius: 8, background: 'transparent', cursor: 'pointer', color: 'var(--color-text-secondary)', fontWeight: 500 }}
            >
              + Crear nuevo grupo de modificadores
            </button>
          )}
        </div>
        
        <div style={{ flex: 1 }}>
          <RecipePreviewPanel productId={productId} selectedOption={selectedOption} items={items} />
        </div>
      </div>
      
      <div style={{ padding: '16px 24px', borderTop: '1px solid var(--color-border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <button 
          onClick={() => setCloneDialogState({ isOpen: true, groupId: null })}
          style={{ background: 'none', border: 'none', color: 'var(--color-primary)', cursor: 'pointer', fontWeight: 500 }}
        >
          Clonar a otro producto...
        </button>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={onClose} style={{ padding: '8px 16px', border: '1px solid var(--color-border)', borderRadius: 4, background: 'var(--color-bg)', cursor: 'pointer' }}>
            Cerrar
          </button>
        </div>
      </div>

      {cloneDialogState.isOpen && (
        <CloneDialog
          isOpen={cloneDialogState.isOpen}
          onClose={() => setCloneDialogState({ isOpen: false, groupId: null })}
          groupId={cloneDialogState.groupId}
          productId={productId}
          onClone={(targetProductId, mode) => cloneGroupOrAll.mutateAsync({ targetProductId, mode, groupId: cloneDialogState.groupId || undefined })}
        />
      )}
    </Modal>
  );
};
