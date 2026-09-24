import React from 'react';
import { Package, Utensils, Tags, MessageSquareText, Plus, ListOrdered, CopyPlus } from 'lucide-react';
import { CategoryHubView, HubCardItem } from './CategoryHubView';

export const CatalogHub: React.FC = () => {
  const currentUser = JSON.parse(localStorage.getItem('user') || '{}');
  const hasRecipesManage = Boolean((currentUser.permissions || []).includes('recipes.manage'));
  const hasCatalogManage = Boolean(
    currentUser.is_superadmin || (currentUser.permissions || []).includes('catalog.manage')
  );

  const cards: HubCardItem[] = [
    {
      title: 'Productos',
      description: 'Alta, precios, impuestos, visibilidad y estaciones de preparación de tu menú.',
      icon: <Package size={26} />,
      iconBg: '#eff6ff',
      iconColor: '#2563eb',
      path: '/products',
    },
    ...(hasRecipesManage
      ? [
          {
            title: 'Recetas',
            description: 'Fórmulas de preparación, subrecetas y explosión de insumos de cocina y barra.',
            icon: <Utensils size={26} />,
            iconBg: '#f0fdf4',
            iconColor: '#16a34a',
            path: '/recipes',
          },
          {
            title: 'Recetas en lote',
            description: 'Revisa diferencias y versiona la misma composición para varios productos.',
            icon: <CopyPlus size={26} />,
            iconBg: '#f1f5f9',
            iconColor: '#111827',
            path: '/recipes/bulk',
          },
        ]
      : []),
    {
      title: 'Grupos y subgrupos',
      description: 'Organiza las familias del menú y sus selecciones previas desde una sola pantalla.',
      icon: <Tags size={26} />,
      iconBg: '#fef3c7',
      iconColor: '#d97706',
      path: '/categories',
    },
    {
      title: 'Comentarios del pedido',
      description: 'Instrucciones especiales y especificaciones rápidas de cocina para comandas.',
      icon: <MessageSquareText size={26} />,
      iconBg: '#f3e8ff',
      iconColor: '#9333ea',
      path: '/variations',
    },
    {
      title: 'Ingredientes adicionales',
      description: 'Extras y adiciones cobrables personalizadas para enriquecer los platillos.',
      icon: <Plus size={26} />,
      iconBg: '#ecfdf5',
      iconColor: '#059669',
      path: '/ingredient-extras',
    },
    ...(hasCatalogManage
      ? [
          {
            title: 'Prioridades administrativas',
            description: 'Ordena categorías para consulta e impresión administrativa sin modificar POS.',
            icon: <ListOrdered size={26} />,
            iconBg: '#f1f5f9',
            iconColor: '#111827',
            path: '/category-priorities',
          },
        ]
      : []),
  ];

  return (
    <CategoryHubView
      title="Catálogo y Menú"
      subtitle="Administra la oferta gastronómica, recetas, precios y modificadores de tu restaurante."
      cards={cards}
    />
  );
};
