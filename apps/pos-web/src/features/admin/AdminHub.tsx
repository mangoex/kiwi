import React from 'react';
import {
  Building2, Carrot, ChefHat, ClipboardCheck, Package, Receipt,
  ShieldCheck, Store, Trash2, Truck, Users,
} from 'lucide-react';

const adminUrl = (path: string) => {
  const isDev = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
  return isDev ? `http://localhost:3002/admin${path}` : `/admin${path}`;
};

const modules = [
  { path: '/products', label: 'Productos y recetas', description: 'Menú, precios, recetas de venta y modificadores.', icon: Package },
  { path: '/inventory/items', label: 'Insumos', description: 'Catálogo central de materias primas y elaborados.', icon: Carrot },
  { path: '/suppliers', label: 'Proveedores', description: 'Proveedores, contactos y presentaciones de compra.', icon: Building2 },
  { path: '/purchases', label: 'Compras', description: 'Recepciones, costos y conciliación con caja.', icon: Receipt },
  { path: '/production', label: 'Producción', description: 'Subrecetas, elaborados y lotes de producción.', icon: ChefHat },
  { path: '/inventory/waste', label: 'Mermas', description: 'Registro, autorización y reversas auditables.', icon: Trash2 },
  { path: '/inventory/transfers', label: 'Traspasos', description: 'Envíos y recepciones entre sucursales.', icon: Truck },
  { path: '/inventory/counts', label: 'Conteos físicos', description: 'Captura ciega, revisión y ajustes autorizados.', icon: ClipboardCheck },
  { path: '/branches', label: 'Sucursales', description: 'Sucursales, unidades de negocio y almacenes.', icon: Store },
  { path: '/users', label: 'Usuarios y roles', description: 'Cuentas, permisos y alcance por sucursal.', icon: Users },
];

const AdminHub = () => (
  <div style={{ padding: 32, maxWidth: 1280, margin: '0 auto' }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 8 }}>
      <div style={{ padding: 12, borderRadius: 14, color: '#047857', background: '#d1fae5' }}><ShieldCheck size={30} /></div>
      <div>
        <h1 style={{ margin: 0, color: '#0f172a' }}>Administración</h1>
        <p style={{ margin: '5px 0 0', color: '#64748b' }}>Gestiona los catálogos centrales y la operación de la sucursal activa.</p>
      </div>
    </div>
    <div role="list" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 16, marginTop: 28 }}>
      {modules.map(({ path, label, description, icon: Icon }) => (
        <a
          role="listitem"
          key={path}
          href={adminUrl(path)}
          style={{ display: 'block', padding: 20, borderRadius: 14, border: '1px solid #e2e8f0', background: '#fff', color: '#0f172a', textDecoration: 'none', boxShadow: '0 6px 18px rgba(15, 23, 42, 0.05)' }}
        >
          <Icon size={24} color="#10b981" />
          <h2 style={{ fontSize: 17, margin: '12px 0 6px' }}>{label}</h2>
          <p style={{ color: '#64748b', fontSize: 14, lineHeight: 1.45, margin: 0 }}>{description}</p>
        </a>
      ))}
    </div>
  </div>
);

export default AdminHub;
