import React from 'react';
import { Receipt, Briefcase, PackageCheck } from 'lucide-react';
import { CategoryHubView, HubCardItem } from './CategoryHubView';

export const PurchasingHub: React.FC = () => {
  const cards: HubCardItem[] = [
    {title:'Gastos',description:'Pagos operativos por sucursal, caja y estadísticas.',icon:<Receipt size={26}/>,iconBg:'#f5f5f5',iconColor:'#444',path:'/expenses'},
    {title:'Conceptos de gasto',description:'Luz, Renta, Agua y otros conceptos independientes de Compras.',icon:<Briefcase size={26}/>,iconBg:'#f5f5f5',iconColor:'#444',path:'/expense-concepts'},
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
      title="Compras y Gastos"
      subtitle="Abastecimiento y gastos operativos de la sucursal."
      cards={cards}
    />
  );
};
