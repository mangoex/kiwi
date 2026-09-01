import React from 'react';
import { Users, Shield, Database } from 'lucide-react';
import { CategoryHubView, HubCardItem } from './CategoryHubView';

export const AdminAccessHub: React.FC = () => {
  const cards: HubCardItem[] = [
    {
      title: 'Usuarios y Cuentas',
      description: 'Directorio de colaboradores, accesos, contraseñas y asignación de sucursales.',
      icon: <Users size={26} />,
      iconBg: '#eff6ff',
      iconColor: '#1d4ed8',
      path: '/users',
    },
    {
      title: 'Roles y Permisos',
      description: 'Definición de niveles de seguridad y permisos de catálogo, inventario y caja.',
      icon: <Shield size={26} />,
      iconBg: '#fef2f2',
      iconColor: '#dc2626',
      path: '/roles',
    },
    {
      title: 'Importaciones Masivas',
      description: 'Revisión y carga masiva de insumos, productos e historial de ventas.',
      icon: <Database size={26} />,
      iconBg: '#f0fdf4',
      iconColor: '#15803d',
      path: '/imports',
    },
  ];

  return (
    <CategoryHubView
      title="Administración y Accesos"
      subtitle="Control de roles de usuario, permisos granulares e importaciones del sistema."
      cards={cards}
    />
  );
};
