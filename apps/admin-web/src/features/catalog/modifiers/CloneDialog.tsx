import React, { useState } from 'react';
import { Button, Modal } from '@restaurantos/ui';
import { useQuery } from '@tanstack/react-query';
import { fetchApi } from '@restaurantos/api-client';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  groupId: string | null;
  productId: string;
  onClone: (targetProductId: string, mode: 'group' | 'all') => void;
}

export const CloneDialog = ({ isOpen, onClose, groupId, productId, onClone }: Props) => {
  const [targetProductId, setTargetProductId] = useState('');
  const [mode, setMode] = useState<'group' | 'all'>('group');

  const { data: products = [] } = useQuery<any[]>({
    queryKey: ['products'],
    queryFn: () => fetchApi('/products'),
    enabled: isOpen
  });

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Clonar modificadores">
      <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <label style={{ fontWeight: 500 }}>Producto destino</label>
          <select value={targetProductId} onChange={e => setTargetProductId(e.target.value)} style={{ padding: '8px 12px', border: '1px solid var(--color-border)', borderRadius: 4 }}>
            <option value="">Selecciona un producto...</option>
            {(products as any[]).filter((p: any) => p.id !== productId).map((p: any) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </div>
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <label style={{ fontWeight: 500 }}>¿Qué deseas clonar?</label>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <input type="radio" checked={mode === 'group'} onChange={() => setMode('group')} disabled={!groupId} />
            Solo el grupo seleccionado
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <input type="radio" checked={mode === 'all'} onChange={() => setMode('all')} />
            Todos los grupos de este producto
          </label>
        </div>
        
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 16 }}>
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button variant="primary" onClick={() => onClone(targetProductId, mode)} disabled={!targetProductId}>Clonar</Button>
        </div>
      </div>
    </Modal>
  );
};
