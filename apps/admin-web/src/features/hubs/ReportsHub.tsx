import React from 'react';
import { BarChart3, History, LineChart } from 'lucide-react';
import { CategoryHubView, HubCardItem } from './CategoryHubView';

export const ReportsHub: React.FC = () => {
  const cards: HubCardItem[] = [
    {
      title: 'Cierre y Reconciliación',
      description: 'Dashboard corporativo de reconciliación de turnos, ingresos y reembolsos.',
      icon: <BarChart3 size={26} />,
      iconBg: '#eff6ff',
      iconColor: '#2563eb',
      path: '/reports',
    },
    {
      title: 'Reportes históricos',
      description: 'Consulta cortes, venta por insumos y gastos por sucursal o de toda la organización.',
      icon: <History size={26} />,
      iconBg: '#fff7ed',
      iconColor: '#ea580c',
      path: '/historical-reports',
    },
    {
      title: 'Métricas y Rendimiento',
      description: 'Visualización de tendencias, ventas por categoría e indicadores clave.',
      icon: <LineChart size={26} />,
      iconBg: '#f0fdf4',
      iconColor: '#16a34a',
      path: '/analytics',
    },
  ];

  return (
    <CategoryHubView
      title="Ventas y Reportes"
      subtitle="Monitoreo financiero, consolidación de ingresos y métricas operativas de la cadena."
      cards={cards}
    />
  );
};
