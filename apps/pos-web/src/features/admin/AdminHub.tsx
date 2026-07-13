import React from 'react';
import { Link } from 'react-router-dom';
import {
  Building2, Carrot, ChefHat, ClipboardCheck, Package, Receipt,
  ShieldCheck, Trash2, Truck,
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

const enabledCards: EnabledCard[] = [
  {
    to: '/administration/products',
    label: 'Productos y recetas',
    description: 'Disponibilidad local sobre productos vinculados al catálogo y recetas centrales.',
    icon: Package,
  },
  {
    to: '/inventory',
    label: 'Insumos de la sucursal',
    description: 'Existencias y movimientos del almacén de la sucursal.',
    icon: Carrot,
  },
  {
    to: '/administration/suppliers',
    label: 'Proveedores',
    description: 'Consulta de proveedores, contactos y presentaciones disponibles para comprar.',
    icon: Building2,
  },
  {
    to: '/administration/purchases',
    label: 'Compras',
    description: 'Consulta de recepciones, costos y conciliación con caja de la sucursal.',
    icon: Receipt,
  },
  {
    to: '/administration/production',
    label: 'Producción',
    description: 'Consulta de elaborados y lotes producidos localmente.',
    icon: ChefHat,
  },
  {
    to: '/administration/waste',
    label: 'Mermas',
    description: 'Consulta de registros, autorizaciones y reversas auditables de la sucursal.',
    icon: Trash2,
  },
  {
    to: '/administration/transfers',
    label: 'Traspasos',
    description: 'Seguimiento de envíos, tránsito y recepciones relacionadas con la sucursal.',
    icon: Truck,
  },
  {
    to: '/administration/counts',
    label: 'Conteos físicos',
    description: 'Consulta de capturas, revisiones y ajustes autorizados.',
    icon: ClipboardCheck,
  },
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

    </div>
  );
};

export default AdminHub;
