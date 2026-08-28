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
    mutationFn: async ({ targetProductIds, mode, groupId }: { targetProductIds: string[], mode: 'group' | 'all', groupId?: string }) => {
      const results = [];
      for (const targetId of targetProductIds) {
        if (mode === 'group' && groupId) {
          results.push(await fetchApi(`/modifier-groups/${groupId}/clone`, { method: 'POST', body: JSON.stringify({ target_product_id: targetId }) }));
        } else {
          results.push(await fetchApi(`/products/${productId}/clone-modifiers`, { method: 'POST', body: JSON.stringify({ target_product_id: targetId }) }));
        }
      }
      return results;
    },
    onSuccess: () => {
      setCloneDialogState({ isOpen: false, groupId: null });
      alert(`Modificadores clonados exitosamente`);
    },
    onError: () => {
      alert('Error al clonar modificadores. Verifica que los productos destino sean válidos.');
    },
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

    const isGroup = groups.some((g: any) => g.id === active.id);
    if (isGroup) {
      const oldIndex = groups.findIndex((g: any) => g.id === active.id);
      const newIndex = groups.findIndex((g: any) => g.id === over.id);
      const newGroups = arrayMove(groups, oldIndex, newIndex);
      const orderedIds = newGroups.map((g: any) => g.id);
      queryClient.setQueryData(['product-modifiers', productId, branchId], newGroups);
      reorderGroups.mutate(orderedIds);
    } else {
      const group = groups.find((g: any) => g.options?.some((o: any) => o.id === active.id));
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

  const selectedOption = groups.flatMap((g: any) => g.options || []).find((o: any) => o.id === selectedOptionId) || null;

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={`Modificadores — ${productName}`} size="xl">
      <div style={{ display: 'flex', minHeight: '60vh', margin: '-24px', borderTop: '1px solid var(--color-border)' }}>
        {/* Left panel: Groups & Options */}
        <div style={{ flex: 3, overflowY: 'auto', maxHeight: '75vh' }}>
          {groups.length === 0 && !showCreateGroup ? (
            <div style={{ padding: 48, textAlign: 'center', color: 'var(--color-text-muted)' }}>
              <div style={{ fontSize: 32, marginBottom: 12 }}>📋</div>
              <p style={{ margin: '0 0 4px', fontWeight: 500 }}>Este producto aún no tiene modificadores</p>
              <p style={{ margin: '0 0 16px', fontSize: 13 }}>Los modificadores permiten al cliente personalizar su pedido</p>
              <button
                onClick={() => setShowCreateGroup(true)}
                style={{ padding: '8px 20px', backgroundColor: 'var(--color-green)', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer', fontWeight: 600, fontSize: 13 }}
              >
                + Crear primer grupo
              </button>
            </div>
          ) : (
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
                    onArchiveGroup={(id) => { if (confirm('¿Archivar este grupo y todas sus opciones?')) archiveGroup.mutate(id); }}
                    onUpdateOption={(id, payload) => updateOption.mutate({ id, payload })}
                    onArchiveOption={(id) => { if (confirm('¿Archivar esta opción?')) archiveOption.mutate(id); }}
                    onCreateOption={async (groupId, payload) => { await createOption.mutateAsync({ groupId, payload }); }}
                    onCloneGroup={(id) => setCloneDialogState({ isOpen: true, groupId: id })}
                  />
                ))}
              </SortableContext>
            </DndContext>
          )}

          {groups.length > 0 && (
            <div style={{ padding: '12px 16px', borderTop: '1px solid var(--color-border)' }}>
              {showCreateGroup ? (
                <CreateGroupForm
                  onSave={async (payload) => createGroup.mutate(payload)}
                  onCancel={() => setShowCreateGroup(false)}
                />
              ) : (
                <button
                  onClick={() => setShowCreateGroup(true)}
                  style={{ width: '100%', padding: '10px 16px', border: '2px dashed var(--color-border)', borderRadius: 8, background: 'transparent', cursor: 'pointer', color: 'var(--color-text-muted)', fontWeight: 500, fontSize: 13, transition: 'all 0.15s' }}
                  onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--color-green)'; e.currentTarget.style.color = 'var(--color-green)'; }}
                  onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--color-border)'; e.currentTarget.style.color = 'var(--color-text-muted)'; }}
                >
                  + Agregar grupo de modificadores
                </button>
              )}
            </div>
          )}
        </div>

        {/* Right panel: Preview */}
        <div style={{ flex: 2, borderLeft: '1px solid var(--color-border)', backgroundColor: 'var(--color-bg)' }}>
          <RecipePreviewPanel productId={productId} selectedOption={selectedOption} items={items} />
        </div>
      </div>

      {/* Footer */}
      <div style={{ margin: '-24px', marginTop: 0, padding: '12px 20px', borderTop: '1px solid var(--color-border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', backgroundColor: 'var(--color-bg)' }}>
        <button
          onClick={() => setCloneDialogState({ isOpen: true, groupId: null })}
          style={{ background: 'none', border: 'none', color: 'var(--color-green)', cursor: 'pointer', fontWeight: 600, fontSize: 13, padding: '6px 0' }}
          disabled={groups.length === 0}
        >
          📋 Clonar modificadores a otro producto
        </button>
        <button
          onClick={onClose}
          style={{ padding: '8px 20px', border: '1px solid var(--color-border)', borderRadius: 6, background: 'var(--color-surface)', cursor: 'pointer', fontWeight: 500, fontSize: 13 }}
        >
          Cerrar
        </button>
      </div>

      {cloneDialogState.isOpen && (
        <CloneDialog
          isOpen={cloneDialogState.isOpen}
          onClose={() => setCloneDialogState({ isOpen: false, groupId: null })}
          groupId={cloneDialogState.groupId}
          productId={productId}
          onClone={(targetProductIds, mode) => cloneGroupOrAll.mutateAsync({ targetProductIds, mode, groupId: cloneDialogState.groupId || undefined })}
        />
      )}
    </Modal>
  );
};
