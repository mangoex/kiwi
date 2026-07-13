import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { fetchApi, ApiError } from '@restaurantos/api-client';
import { ArrowLeft, Users, AlertCircle } from 'lucide-react';
import { usePosSession } from '../../session';

interface StaffMember {
  id: string;
  email: string;
  display_name: string;
  status: string;
  roles: { name: string; scope: string; branch_id: string | null }[];
}

const BranchAdminStaff: React.FC = () => {
  const { session } = usePosSession();
  const [staff, setStaff] = useState<StaffMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    void (async () => {
      setLoading(true);
      setError('');
      try {
        const data = await fetchApi<StaffMember[]>('/branch-administration/staff');
        setStaff(data);
      } catch (err) {
        if (err instanceof ApiError) {
          setError(err.message);
        } else {
          setError('No se pudo cargar el personal.');
        }
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const branch = session?.active_branch;

  return (
    <div style={{ padding: '32px', maxWidth: '1280px', margin: '0 auto' }}>
      <div style={{ marginBottom: '1rem' }}>
        <Link to="/administration" style={{ color: '#16a34a', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
          <ArrowLeft size={16} /> Administración
        </Link>
      </div>

      <div style={{ background: '#fff', borderRadius: '0.75rem', padding: '1rem 1.5rem', marginBottom: '1rem', border: '1px solid #e5e7eb' }}>
        <strong>Administración de sucursal</strong>
        {branch && (
          <span style={{ marginLeft: '0.75rem', color: '#6b7280' }}>
            {branch.name} ({branch.code})
          </span>
        )}
      </div>

      <h2 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <Users size={20} /> Personal de sucursal
      </h2>

      <p style={{ color: '#6b7280', fontSize: '0.875rem', marginBottom: '1rem' }}>
        La administración de cuentas y permisos corresponde al administrador corporativo.
      </p>

      {error && (
        <div style={{ color: '#dc2626', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
          <AlertCircle size={16} /> {error}
        </div>
      )}

      {loading ? (
        <p>Cargando personal…</p>
      ) : staff.length === 0 ? (
        <p style={{ color: '#6b7280' }}>No hay personal asignado a esta sucursal.</p>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', background: '#fff', borderRadius: '0.75rem', overflow: 'hidden' }}>
            <thead>
              <tr style={{ background: '#f9fafb', textAlign: 'left' }}>
                <th style={{ padding: '0.6rem 1rem', fontSize: '0.875rem' }}>Nombre</th>
                <th style={{ padding: '0.6rem 1rem', fontSize: '0.875rem' }}>Correo</th>
                <th style={{ padding: '0.6rem 1rem', fontSize: '0.875rem' }}>Estado</th>
                <th style={{ padding: '0.6rem 1rem', fontSize: '0.875rem' }}>Roles</th>
              </tr>
            </thead>
            <tbody>
              {staff.map((s) => (
                <tr key={s.id} style={{ borderTop: '1px solid #f3f4f6' }}>
                  <td style={{ padding: '0.6rem 1rem' }}>{s.display_name}</td>
                  <td style={{ padding: '0.6rem 1rem', color: '#6b7280' }}>{s.email}</td>
                  <td style={{ padding: '0.6rem 1rem' }}>{s.status}</td>
                  <td style={{ padding: '0.6rem 1rem' }}>
                    {s.roles.map((r) => r.name).join(', ') || '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default BranchAdminStaff;
