import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { fetchApi, ApiError } from '@restaurantos/api-client';
import { ArrowLeft, Building2, AlertCircle } from 'lucide-react';
import { usePosSession, type SessionActiveBranch } from '../../session';

const UNIT_TYPE_LABELS: Record<string, string> = {
  restaurant: 'Restaurante',
  bakery: 'Panadería',
  production: 'Producción',
  other: 'Otro',
};

function InfoCard({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div style={{ background: '#fff', borderRadius: '0.75rem', padding: '1rem 1.5rem', border: '1px solid #e5e7eb' }}>
      <div style={{ fontSize: '0.75rem', color: '#6b7280', marginBottom: '0.25rem' }}>{label}</div>
      <div style={{ fontWeight: 500 }}>{value || '—'}</div>
    </div>
  );
}

const BranchAdminContext: React.FC = () => {
  const { session } = usePosSession();
  const [branch, setBranch] = useState<SessionActiveBranch | null>(session?.active_branch ?? null);
  const [loading, setLoading] = useState(!session?.active_branch);
  const [error, setError] = useState('');

  useEffect(() => {
    if (session?.active_branch) {
      setBranch(session.active_branch);
      setLoading(false);
      return;
    }
    void (async () => {
      setLoading(true);
      setError('');
      try {
        const data = await fetchApi<SessionActiveBranch>('/branch-administration/context');
        setBranch(data);
      } catch (err) {
        if (err instanceof ApiError) {
          setError(err.message);
        } else {
          setError('No se pudo cargar el contexto de la sucursal.');
        }
      } finally {
        setLoading(false);
      }
    })();
  }, [session?.active_branch]);

  return (
    <div style={{ padding: '32px', maxWidth: '1280px', margin: '0 auto' }}>
      <div style={{ marginBottom: '1rem' }}>
        <Link to="/administration" style={{ color: '#16a34a', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
          <ArrowLeft size={16} /> Administración
        </Link>
      </div>

      <div style={{ background: '#fff', borderRadius: '0.75rem', padding: '1rem 1.5rem', marginBottom: '1rem', border: '1px solid #e5e7eb' }}>
        <strong>Administración de sucursal</strong>
      </div>

      <h2 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <Building2 size={20} /> Sucursal activa
      </h2>

      {error && (
        <div style={{ color: '#dc2626', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
          <AlertCircle size={16} /> {error}
        </div>
      )}

      {loading ? (
        <p>Cargando sucursal…</p>
      ) : branch ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(15rem, 1fr))', gap: '0.75rem', marginTop: '1rem' }}>
          <InfoCard label="Sucursal" value={branch.name} />
          <InfoCard label="Código" value={branch.code} />
          <InfoCard label="Zona horaria" value={branch.timezone} />
          <InfoCard label="Estado" value={branch.status} />
          <InfoCard label="Unidad de negocio" value={branch.business_unit.name} />
          <InfoCard label="Código de unidad" value={branch.business_unit.code} />
          <InfoCard label="Tipo" value={UNIT_TYPE_LABELS[branch.business_unit.unit_type] || branch.business_unit.unit_type} />
          <InfoCard label="Razón social" value={branch.legal_entity.name} />
          <InfoCard label="Almacén" value={branch.warehouse?.name} />
        </div>
      ) : (
        <p style={{ color: '#6b7280' }}>No hay sucursal activa.</p>
      )}
    </div>
  );
};

export default BranchAdminContext;
