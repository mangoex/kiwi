import React from 'react';
import { Link } from 'react-router-dom';
import {
  Building2, Carrot, ChefHat, ClipboardCheck, Package, Receipt,
  ShieldCheck, Store, Trash2, Truck, Users,
} from 'lucide-react';
import { usePosSession } from '../../session';

const UNIT_TYPE_LABELS: Record<string, string> = {
  restaurant: 'Restaurante',
  bakery: 'Panadería',
  production: 'Producción',
  other: 'Otro',
};

interface EnabledCard {
  to: string;
  label: string;
  description: string;
  icon: React.ComponentType<{ size?: number; color?: string }>;
}

interface DeferredCard {
  label: string;
  description: string;
  icon: React.ComponentType<{ size?: number; color?: string }>;
}

const enabledCards: EnabledCard[] = [
  {
    to: '/administration/products',
    label: 'Productos y disponibilidad',
    description: 'Consulta el catálogo central y gestiona disponibilidad de tu sucursal.',
    icon: Package,
  },
  {
    to: '/inventory',
    label: 'Insumos de la sucursal',
    description: 'Existencias y movimientos del almacén de la sucursal.',
    icon: Carrot,
  },
  {
    to: '/administration/branch',
    label: 'Sucursal activa',
    description: 'Datos de la sucursal, unidad de negocio, razón social y almacén.',
    icon: Store,
  },
  {
    to: '/administration/staff',
    label: 'Personal de sucursal',
    description: 'Consulta del personal asignado a esta sucursal.',
    icon: Users,
  },
];

const deferredCards: DeferredCard[] = [
  { label: 'Proveedores', description: 'Proveedores, contactos y presentaciones de compra.', icon: Building2 },
  { label: 'Compras', description: 'Recepciones, costos y conciliación con caja.', icon: Receipt },
  { label: 'Producción', description: 'Subrecetas, elaborados y lotes de producción.', icon: ChefHat },
  { label: 'Mermas', description: 'Registro, autorización y reversas auditables.', icon: Trash2 },
  { label: 'Traspasos', description: 'Envíos y recepciones entre sucursales.', icon: Truck },
  { label: 'Conteos físicos', description: 'Captura ciega, revisión y ajustes autorizados.', icon: ClipboardCheck },
];

const AdminHub: React.FC = () => {
  const { session } = usePosSession();
  const branch = session?.active_branch;

  return (
    <div style={{ padding: 32, maxWidth: 1280, margin: '0 auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 8 }}>
        <div style={{ padding: 12, borderRadius: 14, color: '#047857', background: '#d1fae5' }}>
          <ShieldCheck size={30} />
        </div>
        <div>
          <h1 style={{ margin: 0, color: '#0f172a' }}>Administración de sucursal</h1>
          <p style={{ margin: '5px 0 0', color: '#64748b' }}>
            Gestiona la operación de tu sucursal sin abandonar el POS.
          </p>
        </div>
      </div>

      {branch && (
        <div
          style={{
            marginTop: 16,
            padding: '12px 16px',
            borderRadius: 12,
            background: '#fff',
            border: '1px solid #e2e8f0',
            display: 'flex',
            flexWrap: 'wrap',
            gap: '0.5rem 1.5rem',
            alignItems: 'center',
            fontSize: 14,
            color: '#334155',
          }}
        >
          <strong style={{ color: '#16a34a' }}>Administración de sucursal</strong>
          <span>{branch.name} ({branch.code})</span>
          <span>{branch.business_unit.name}</span>
          <span>
            Tipo: {UNIT_TYPE_LABELS[branch.business_unit.unit_type] || branch.business_unit.unit_type}
          </span>
          <span>Razón social: {branch.legal_entity.name}</span>
          {branch.warehouse && <span>Almacén: {branch.warehouse.name}</span>}
        </div>
      )}

      <div
        role="list"
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
          gap: 16,
          marginTop: 28,
        }}
      >
        {enabledCards.map(({ to, label, description, icon: Icon }) => (
          <Link
            role="listitem"
            key={to}
            to={to}
            style={{
              display: 'block',
              padding: 20,
              borderRadius: 14,
              border: '1px solid #e2e8f0',
              background: '#fff',
              color: '#0f172a',
              textDecoration: 'none',
              boxShadow: '0 6px 18px rgba(15, 23, 42, 0.05)',
            }}
          >
            <Icon size={24} color="#10b981" />
            <h2 style={{ fontSize: 17, margin: '12px 0 6px' }}>{label}</h2>
            <p style={{ color: '#64748b', fontSize: 14, lineHeight: 1.45, margin: 0 }}>{description}</p>
          </Link>
        ))}
      </div>

      <h2 style={{ marginTop: 32, color: '#0f172a', fontSize: 18 }}>Próximos incrementos</h2>
      <div
        role="list"
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
          gap: 16,
          marginTop: 12,
        }}
      >
        {deferredCards.map(({ label, description, icon: Icon }) => (
          <div
            role="listitem"
            key={label}
            aria-disabled="true"
            style={{
              display: 'block',
              padding: 20,
              borderRadius: 14,
              border: '1px solid #f1f5f9',
              background: '#f8fafc',
              color: '#94a3b8',
              cursor: 'not-allowed',
            }}
          >
            <Icon size={24} color="#cbd5e1" />
            <h2 style={{ fontSize: 17, margin: '12px 0 6px' }}>{label}</h2>
            <p style={{ fontSize: 14, lineHeight: 1.45, margin: 0 }}>{description}</p>
            <span style={{ display: 'inline-block', marginTop: 8, fontSize: 12, fontWeight: 500, color: '#94a3b8' }}>
              Próximo incremento
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};

export default AdminHub;
