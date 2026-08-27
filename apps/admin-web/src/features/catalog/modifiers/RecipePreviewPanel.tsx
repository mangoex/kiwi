import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchApi } from '@restaurantos/api-client';

interface Props {
  productId: string;
  selectedOption: any | null;
  items: any[];
}

export const RecipePreviewPanel = ({ productId, selectedOption, items }: Props) => {
  const { data: productInfo } = useQuery({
    queryKey: ['product', productId],
    queryFn: () => fetchApi(`/products/${productId}`),
    enabled: !!productId
  });
  
  // Here we would typically fetch the recipe, but since there's no endpoint guaranteed in the mockup other than /products/{productId}/modifiers, we use a placeholder or simulate it if productInfo has components
  
  return (
    <div style={{ padding: 24, backgroundColor: 'var(--color-bg-secondary)', height: '100%', overflowY: 'auto' }}>
      {selectedOption ? (
        <>
          <h2 style={{ fontSize: 16, fontWeight: 600, margin: '0 0 16px 0' }}>Vista Previa: {selectedOption.name}</h2>
          
          <div style={{ background: 'var(--color-bg)', border: '1px solid var(--color-border)', borderRadius: 8, padding: 16, marginBottom: 16 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--color-text-secondary)', textTransform: 'uppercase', marginBottom: 8 }}>Efecto del modificador</div>
            <ul style={{ margin: 0, paddingLeft: 20, fontSize: 14 }}>
              {selectedOption.effect_type === 'add' && selectedOption.affected_item_id && (
                <li style={{ color: 'var(--color-success)', fontWeight: 500 }}>➕ Agrega {selectedOption.add_quantity}x {items.find(i => i.id === selectedOption.affected_item_id)?.name}</li>
              )}
              {selectedOption.effect_type === 'remove' && selectedOption.affected_item_id && (
                <li style={{ color: 'var(--color-error)', textDecoration: 'line-through' }}>❌ Quita {selectedOption.remove_quantity}x {items.find(i => i.id === selectedOption.affected_item_id)?.name}</li>
              )}
              {['substitute', 'variant'].includes(selectedOption.effect_type) && (
                <>
                  <li style={{ color: 'var(--color-error)', textDecoration: 'line-through' }}>❌ Quita {selectedOption.remove_quantity}x {items.find(i => i.id === selectedOption.affected_item_id)?.name}</li>
                  <li style={{ color: 'var(--color-success)', fontWeight: 500 }}>➕ Agrega {selectedOption.add_quantity}x {items.find(i => i.id === selectedOption.replacement_item_id)?.name}</li>
                </>
              )}
              {selectedOption.effect_type === 'instruction' && (
                <li>📝 {selectedOption.kitchen_text}</li>
              )}
            </ul>
          </div>
          
          <div style={{ background: 'var(--color-bg)', border: '1px solid var(--color-border)', borderRadius: 8, padding: 16 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--color-text-secondary)', textTransform: 'uppercase', marginBottom: 8 }}>Impacto en Precio</div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 14, fontWeight: 600 }}>
              <span>Adicional:</span>
              <span style={{ color: selectedOption.price_delta_cents > 0 ? 'var(--color-success)' : 'inherit' }}>
                ${(selectedOption.price_delta_cents / 100).toFixed(2)}
              </span>
            </div>
          </div>
        </>
      ) : (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--color-text-secondary)' }}>
          Selecciona una opción para ver su efecto
        </div>
      )}
    </div>
  );
};
