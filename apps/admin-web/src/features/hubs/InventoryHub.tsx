import React from 'react';
import { Carrot, Box, Flame, Trash2, Truck, ClipboardCheck, Scale } from 'lucide-react';
import { CategoryHubView, HubCardItem } from './CategoryHubView';

export const InventoryHub: React.FC = () => {
  const currentUser = JSON.parse(localStorage.getItem('user') || '{}');
  const hasCatalogManage = Boolean(
    currentUser.is_superadmin || (currentUser.permissions || []).includes('catalog.manage')
  );

  const cards: HubCardItem[] = [
    {
      title: 'Insumos',
      description: 'Ingredientes base, empaques, costos unitarios y existencias de almacén.',
      icon: <Carrot size={26} />,
      iconBg: '#fff7ed',
      iconColor: '#ea580c',
      path: '/inventory/items',
    },
    ...(hasCatalogManage
      ? [
          {
            title: 'Almacenes',
            description: 'Gestión y asignación de almacenes y bodegas por cada sucursal.',
            icon: <Box size={26} />,
            iconBg: '#f1f5f9',
            iconColor: '#475569',
            path: '/warehouses',
          },
        ]
      : []),
    {
      title: 'Producción de Lotes',
      description: 'Transformación y elaboración de subrecetas por batch (salsas, aderezos, bases).',
      icon: <Flame size={26} />,
      iconBg: '#fef2f2',
      iconColor: '#dc2626',
      path: '/production',
    },
    {
      title: 'Mermas',
      description: 'Registro de bajas de stock, caducidades y mermas operativas con trazabilidad.',
      icon: <Trash2 size={26} />,
      iconBg: '#fef2f2',
      iconColor: '#e11d48',
      path: '/inventory/waste',
    },
    {
      title: 'Traspasos',
      description: 'Envíos, tránsito y recepción conciliada de mercancía entre sucursales.',
      icon: <Truck size={26} />,
      iconBg: '#eff6ff',
      iconColor: '#0284c7',
      path: '/inventory/transfers',
    },
    {
      title: 'Conteos Físicos',
      description: 'Auditorías periódicas de inventario, capturas ciegas y ajustes al kardex.',
      icon: <ClipboardCheck size={26} />,
      iconBg: '#f0fdf4',
      iconColor: '#16a34a',
      path: '/inventory/counts',
    },
    {
      title: 'Unidades de Medida',
      description: 'Catálogo de unidades base (kg, litros, piezas) y factores de conversión.',
      icon: <Scale size={26} />,
      iconBg: '#faf5ff',
      iconColor: '#7c3aed',
      path: '/inventory/units',
    },
  ];

  return (
    <CategoryHubView
      title="Inventario y Almacén"
      subtitle="Control de stock perpetuo, costeo promedio, mermas, traspasos y auditorías físicas."
      cards={cards}
    />
  );
};
