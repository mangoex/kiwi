import React from 'react';
import { Store, Bike, Share2, Wallet } from 'lucide-react';
import { CategoryHubView, HubCardItem } from './CategoryHubView';
import { canManageCashConcepts } from '../cash/cashConceptState';

export const BranchesHub: React.FC = () => {
  const currentUser = JSON.parse(localStorage.getItem('user') || '{}');
  const hasCashConceptManage = canManageCashConcepts(currentUser);

  const cards: HubCardItem[] = [
    {
      title: 'Sucursales',
      description: 'Configuración de sucursales, razones sociales, domicilios y coordenadas GPS.',
      icon: <Store size={26} />,
      iconBg: '#eff6ff',
      iconColor: '#1d4ed8',
      path: '/branches',
    },
    {
      title: 'Repartidores',
      description: 'Gestión de la flotilla de repartidores para entrega a domicilio propia.',
      icon: <Bike size={26} />,
      iconBg: '#fff7ed',
      iconColor: '#c2410c',
      path: '/drivers',
    },
    {
      title: 'Integraciones Omnicanal',
      description: 'Facturación CFDI 4.0 con Facturapi, pedidos de Uber Eats y tienda web.',
      icon: <Share2 size={26} />,
      iconBg: '#f5f3ff',
      iconColor: '#7c3aed',
      badge: 'Uber & Facturapi',
      path: '/integrations',
    },
    ...(hasCashConceptManage
      ? [
          {
            title: 'Conceptos de Caja',
            description: 'Motivos autorizados para ingresos y egresos de efectivo en turnos de caja.',
            icon: <Wallet size={26} />,
            iconBg: '#ecfdf5',
            iconColor: '#047857',
            path: '/cash-concepts',
          },
        ]
      : []),
  ];

  return (
    <CategoryHubView
      title="Sucursales y Canales"
      subtitle="Gestión de puntos de venta físicos, flotilla de reparto e integraciones digitales."
      cards={cards}
    />
  );
};
