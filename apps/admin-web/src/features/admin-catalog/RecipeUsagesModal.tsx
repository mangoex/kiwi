import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchApi } from '@restaurantos/api-client';
import { Button, Modal } from '@restaurantos/ui';
import { useNavigate } from 'react-router-dom';

type Usage = {
  product_id: string; product_name: string; product_sku: string; recipe_id: string; recipe_version: number;
  item_id: string; quantity_base_units: string; unit_id: string; unit_code: string;
};

export function RecipeUsagesModal({ item, branchId, onClose }: { item: { id: string; name: string; unit_code?: string }; branchId: string; onClose: () => void }) {
  const navigate = useNavigate();
  const usages = useQuery<Usage[]>({
    queryKey: ['admin-catalog', 'recipe-usages', item.id, branchId],
    queryFn: () => fetchApi(`/admin-catalog/items/${item.id}/recipe-usages?branch_id=${encodeURIComponent(branchId)}`),
    enabled: Boolean(branchId),
  });
  const openRecipe = (usage: Usage) => {
    onClose();
    navigate(`/recipes?product_id=${encodeURIComponent(usage.product_id)}&recipe_id=${encodeURIComponent(usage.recipe_id)}`);
  };

  return <Modal isOpen onClose={onClose} title={`Recetas que usan ${item.name}`}>
    {usages.isLoading && <p role="status">Buscando usos directos en recetas efectivas…</p>}
    {usages.isError && <p role="alert">No fue posible consultar los usos de este insumo.</p>}
    {usages.data?.length === 0 && <p>No hay recetas efectivas que usen este insumo en el alcance seleccionado.</p>}
    {usages.data && usages.data.length > 0 && <div style={{ overflowX: 'auto' }}><table className="premium-table"><thead><tr><th>Producto</th><th>Versión efectiva</th><th>Cantidad</th><th><span className="sr-only">Detalle</span></th></tr></thead><tbody>{usages.data.map((usage) => <tr key={usage.recipe_id}><td><strong>{usage.product_name}</strong><br /><small>{usage.product_sku}</small></td><td>{usage.recipe_version}</td><td>{usage.quantity_base_units} {usage.unit_code}</td><td><Button variant="secondary" onClick={() => openRecipe(usage)}>Abrir receta</Button></td></tr>)}</tbody></table></div>}
  </Modal>;
}
