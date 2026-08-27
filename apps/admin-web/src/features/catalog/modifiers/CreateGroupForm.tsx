import React, { useState } from 'react';
import { Button, Input } from '@restaurantos/ui';

interface Props {
  onSave: (payload: any) => Promise<void>;
  onCancel: () => void;
}

export const CreateGroupForm = ({ onSave, onCancel }: Props) => {
  const [name, setName] = useState('');
  const [isRequired, setIsRequired] = useState(false);
  const [min, setMin] = useState(0);
  const [max, setMax] = useState(1);

  return (
    <div style={{ padding: 16, backgroundColor: 'var(--color-bg-secondary)', borderTop: '1px solid var(--color-border)', borderBottom: '1px solid var(--color-border)' }}>
      <div style={{ display: 'flex', gap: 12, marginBottom: 12 }}>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label style={{ fontSize: 12, fontWeight: 500 }}>Nombre del grupo</label>
          <Input value={name} onChange={e => setName(e.target.value)} placeholder="Ej. Punto de cocción" />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 18 }}>
          <input type="checkbox" checked={isRequired} onChange={e => {
            const checked = e.target.checked;
            setIsRequired(checked);
            if (checked && min === 0) setMin(1);
          }} />
          <label style={{ fontSize: 12, fontWeight: 500 }}>Obligatorio</label>
        </div>
        <div style={{ width: 80, display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label style={{ fontSize: 12, fontWeight: 500 }}>Mínimo</label>
          <Input type="number" value={min} onChange={e => setMin(parseInt(e.target.value) || 0)} min={isRequired ? 1 : 0} />
        </div>
        <div style={{ width: 80, display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label style={{ fontSize: 12, fontWeight: 500 }}>Máximo</label>
          <Input type="number" value={max} onChange={e => setMax(parseInt(e.target.value) || 1)} min={Math.max(1, min)} />
        </div>
      </div>
      
      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
        <Button variant="secondary" onClick={onCancel}>Cancelar</Button>
        <Button variant="primary" onClick={() => onSave({ name, is_required: isRequired, minimum_selections: min, maximum_selections: max })} disabled={!name.trim()}>
          Crear grupo
        </Button>
      </div>
    </div>
  );
};
