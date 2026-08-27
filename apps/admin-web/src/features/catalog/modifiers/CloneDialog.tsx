import React, { useState } from 'react';
import { Button, Modal } from '@restaurantos/ui';
import { useQuery } from '@tanstack/react-query';
import { fetchApi } from '@restaurantos/api-client';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  groupId: string | null;
  productId: string;
  onClone: (targetProductIds: string[], mode: 'group' | 'all') => void;
}

export const CloneDialog = ({ isOpen, onClose, groupId, productId, onClone }: Props) => {
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [mode, setMode] = useState<'group' | 'all'>(groupId ? 'group' : 'all');
  const [search, setSearch] = useState('');
  const [cloning, setCloning] = useState(false);

  const { data: products = [] } = useQuery<any[]>({
    queryKey: ['catalog', 'products'],
    queryFn: () => fetchApi('/catalog/products'),
    enabled: isOpen
  });

  // Filter out the current product and apply search
  const available = (products as any[])
    .filter((p: any) => p.id !== productId && p.status === 'active')
    .filter((p: any) => !search || p.name?.toLowerCase().includes(search.toLowerCase()));

  const toggleProduct = (id: string) => {
    setSelectedIds(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    );
  };

  const selectAll = () => {
    if (selectedIds.length === available.length) {
      setSelectedIds([]);
    } else {
      setSelectedIds(available.map(p => p.id));
    }
  };

  const handleClone = async () => {
    if (selectedIds.length === 0 || cloning) return;
    setCloning(true);
    try {
      await onClone(selectedIds, mode);
    } finally {
      setCloning(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Clonar modificadores" size="md">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16, margin: '-24px', padding: '16px 20px' }}>
        {/* Mode selector */}
        <div>
          <label style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--color-text-muted)', display: 'block', marginBottom: 6 }}>
            ¿Qué clonar?
          </label>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {groupId && (
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, cursor: 'pointer', padding: '6px 10px', borderRadius: 6, backgroundColor: mode === 'group' ? 'rgba(16,185,129,0.08)' : 'transparent', border: mode === 'group' ? '1px solid var(--color-green)' : '1px solid transparent' }}>
                <input type="radio" checked={mode === 'group'} onChange={() => setMode('group')} style={{ accentColor: 'var(--color-green)' }} />
                Solo el grupo seleccionado
              </label>
            )}
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, cursor: 'pointer', padding: '6px 10px', borderRadius: 6, backgroundColor: mode === 'all' ? 'rgba(16,185,129,0.08)' : 'transparent', border: mode === 'all' ? '1px solid var(--color-green)' : '1px solid transparent' }}>
              <input type="radio" checked={mode === 'all'} onChange={() => setMode('all')} style={{ accentColor: 'var(--color-green)' }} />
              Todos los grupos de este producto
            </label>
          </div>
        </div>

        {/* Product multi-select */}
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
            <label style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--color-text-muted)' }}>
              Productos destino ({selectedIds.length} seleccionados)
            </label>
            <button
              onClick={selectAll}
              style={{ background: 'none', border: 'none', color: 'var(--color-green)', cursor: 'pointer', fontSize: 12, fontWeight: 500 }}
            >
              {selectedIds.length === available.length ? 'Deseleccionar todos' : 'Seleccionar todos'}
            </button>
          </div>

          <input
            type="text"
            placeholder="Buscar producto..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--color-border)', borderRadius: 6, fontSize: 13, marginBottom: 8, boxSizing: 'border-box' }}
          />

          <div style={{ maxHeight: 240, overflowY: 'auto', border: '1px solid var(--color-border)', borderRadius: 8 }}>
            {available.length === 0 ? (
              <div style={{ padding: 20, textAlign: 'center', color: 'var(--color-text-muted)', fontSize: 13 }}>
                {search ? 'Sin resultados para esta búsqueda' : 'No hay otros productos disponibles'}
              </div>
            ) : (
              available.map((p: any) => (
                <label
                  key={p.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                    padding: '8px 12px',
                    cursor: 'pointer',
                    fontSize: 13,
                    borderBottom: '1px solid var(--color-border)',
                    backgroundColor: selectedIds.includes(p.id) ? 'rgba(16,185,129,0.06)' : 'transparent',
                    transition: 'background-color 0.1s',
                  }}
                >
                  <input
                    type="checkbox"
                    checked={selectedIds.includes(p.id)}
                    onChange={() => toggleProduct(p.id)}
                    style={{ accentColor: 'var(--color-green)', flexShrink: 0 }}
                  />
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {p.name}
                  </span>
                  {p.category_name && (
                    <span style={{ fontSize: 11, color: 'var(--color-text-muted)', flexShrink: 0 }}>
                      {p.category_name}
                    </span>
                  )}
                </label>
              ))
            )}
          </div>
        </div>

        {/* Actions */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, paddingTop: 8, borderTop: '1px solid var(--color-border)' }}>
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button
            variant="primary"
            onClick={handleClone}
            disabled={selectedIds.length === 0 || cloning}
          >
            {cloning ? 'Clonando...' : `Clonar a ${selectedIds.length} producto${selectedIds.length !== 1 ? 's' : ''}`}
          </Button>
        </div>
      </div>
    </Modal>
  );
};
