import React from 'react';
import { Receipt, Briefcase, PackageCheck } from 'lucide-react';
import { CategoryHubView, HubCardItem } from './CategoryHubView';

export const PurchasingHub: React.FC = () => {
  const cards: HubCardItem[] = [
    {
      title: 'Compras directas',
      description: 'Recepción de facturas o notas de compra, asignación de proveedor y costeo promedio.',
      icon: <Receipt size={26} />,
      iconBg: '#ecfdf5',
      iconColor: '#059669',
      path: '/purchases',
    },
    {
      title: 'Proveedores',
      description: 'Directorio de proveedores autorizados, datos de contacto y condiciones comerciales.',
      icon: <Briefcase size={26} />,
      iconBg: '#eff6ff',
      iconColor: '#2563eb',
      path: '/suppliers',
    },
    {
      title: 'Presentaciones de Compra',
      description: 'Formatos comerciales en los que compras insumos (cajas de 10 kg, botellas de 1 L).',
      icon: <PackageCheck size={26} />,
      iconBg: '#fff7ed',
      iconColor: '#d97706',
      path: '/purchase-presentations',
    },
  ];

  return (
    <CategoryHubView
      title="Compras y Proveedores"
      subtitle="Abastecimiento, catálogo de proveedores y actualización de costos de adquisición."
      cards={cards}
    />
  );
};
