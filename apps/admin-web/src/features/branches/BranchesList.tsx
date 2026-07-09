import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, Button, Badge } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';
import { Plus, Store, Edit, Trash2 } from 'lucide-react';

interface Branch {
  id: string;
  name: string;
  status: string;
  address: string;
  organization_id: string;
}

const BranchesList = () => {
  const { data: branches, isLoading, error } = useQuery<Branch[]>({
    queryKey: ['branches'],
    queryFn: () => fetchApi('/branches'),
  });

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 32 }}>
        <div>
          <h1 className="admin-title" style={{ marginBottom: 4 }}>Branches (Sucursales)</h1>
          <p style={{ color: 'var(--color-text-muted)' }}>Administra las sucursales de la franquicia.</p>
        </div>
        <Button variant="primary" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Plus size={18} />
          Nueva Sucursal
        </Button>
      </div>

      <Card style={{ padding: 0, overflow: 'hidden' }}>
        {isLoading ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-text-muted)' }}>
            Cargando sucursales...
          </div>
        ) : error ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-red)' }}>
            Error al cargar sucursales. Revisa tu conexión.
          </div>
        ) : !branches || branches.length === 0 ? (
          <div style={{ padding: 60, textAlign: 'center' }}>
            <Store size={48} style={{ color: 'var(--color-border)', margin: '0 auto 16px' }} />
            <h3 style={{ marginBottom: 8 }}>No hay sucursales registradas</h3>
            <p style={{ color: 'var(--color-text-muted)' }}>Agrega la primera sucursal para operar.</p>
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--color-border)', backgroundColor: 'var(--color-bg)' }}>
                <th style={{ padding: '16px 24px', fontWeight: 600, fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>Nombre</th>
                <th style={{ padding: '16px 24px', fontWeight: 600, fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>Estatus</th>
                <th style={{ padding: '16px 24px', fontWeight: 600, fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>Dirección</th>
                <th style={{ padding: '16px 24px', fontWeight: 600, fontSize: '0.875rem', color: 'var(--color-text-muted)', textAlign: 'right' }}>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {branches.map((branch) => (
                <tr key={branch.id} style={{ borderBottom: '1px solid var(--color-border)' }}>
                  <td style={{ padding: '16px 24px', fontWeight: 500 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                      <div style={{ padding: 8, backgroundColor: 'var(--color-blue-light)', color: 'var(--color-blue)', borderRadius: 8 }}>
                        <Store size={18} />
                      </div>
                      {branch.name}
                    </div>
                  </td>
                  <td style={{ padding: '16px 24px' }}>
                    <Badge variant={branch.status === 'active' ? 'success' : 'default'}>
                      {branch.status || 'Activa'}
                    </Badge>
                  </td>
                  <td style={{ padding: '16px 24px', color: 'var(--color-text-muted)', fontSize: '0.875rem' }}>
                    {branch.address || 'Sin dirección'}
                  </td>
                  <td style={{ padding: '16px 24px', textAlign: 'right' }}>
                    <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                      <button style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--color-blue)' }}><Edit size={18} /></button>
                      <button style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--color-red)' }}><Trash2 size={18} /></button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </>
  );
};

export default BranchesList;
