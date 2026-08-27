import React from 'react';

interface Props {
  productId: string;
  selectedOption: any | null;
  items: any[];
}

export const RecipePreviewPanel = ({ productId, selectedOption, items }: Props) => {

  const getItemName = (id: string | null | undefined) => {
    if (!id) return '—';
    return items.find(i => i.id === id)?.name || id;
  };

  const priceMXN = (cents: number) => {
    const abs = Math.abs(cents / 100).toFixed(2);
    return cents >= 0 ? `+$${abs}` : `-$${abs}`;
  };

  if (!selectedOption) {
    return (
      <div style={{ padding: 32, height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: 'var(--color-text-muted)', textAlign: 'center' }}>
        <div style={{ fontSize: 40, marginBottom: 12, opacity: 0.4 }}>👁️</div>
        <p style={{ margin: '0 0 4px', fontWeight: 500, fontSize: 14 }}>Vista previa</p>
        <p style={{ margin: 0, fontSize: 12, lineHeight: 1.5, maxWidth: 200 }}>
          Selecciona una opción del panel izquierdo para ver cómo afecta la receta y el costo
        </p>
      </div>
    );
  }

  return (
    <div style={{ padding: 20, height: '100%', overflowY: 'auto' }}>
      {/* Header */}
      <div style={{ marginBottom: 16 }}>
        <h3 style={{ margin: '0 0 2px', fontSize: 15, fontWeight: 600, color: 'var(--color-text)' }}>
          {selectedOption.name}
        </h3>
        <span style={{ fontSize: 12, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
          {selectedOption.effect_type}
        </span>
      </div>

      {/* Effect Details */}
      <div style={{ backgroundColor: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 8, padding: 14, marginBottom: 12 }}>
        <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 10 }}>
          Efecto en receta
        </div>

        {selectedOption.effect_type === 'instruction' && (
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, fontSize: 13 }}>
            <span style={{ fontSize: 16 }}>📝</span>
            <div>
              <div style={{ fontWeight: 500 }}>Instrucción para cocina</div>
              <div style={{ color: 'var(--color-text-muted)', marginTop: 2 }}>
                "{selectedOption.kitchen_text || selectedOption.name}"
              </div>
            </div>
          </div>
        )}

        {selectedOption.effect_type === 'remove' && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
            <span style={{ color: 'var(--color-red)', fontSize: 16 }}>✕</span>
            <div>
              <span style={{ textDecoration: 'line-through', color: 'var(--color-red)' }}>
                {getItemName(selectedOption.affected_item_id)}
              </span>
              {selectedOption.remove_quantity > 0 && (
                <span style={{ color: 'var(--color-text-muted)', marginLeft: 4 }}>
                  ×{selectedOption.remove_quantity}
                </span>
              )}
            </div>
          </div>
        )}

        {selectedOption.effect_type === 'add' && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
            <span style={{ color: 'var(--color-green)', fontSize: 16 }}>+</span>
            <div>
              <span style={{ color: 'var(--color-green)', fontWeight: 500 }}>
                {getItemName(selectedOption.affected_item_id || selectedOption.replacement_item_id)}
              </span>
              {selectedOption.add_quantity > 0 && (
                <span style={{ color: 'var(--color-text-muted)', marginLeft: 4 }}>
                  ×{selectedOption.add_quantity}
                </span>
              )}
            </div>
          </div>
        )}

        {['substitute', 'variant'].includes(selectedOption.effect_type) && (
          <div style={{ fontSize: 13 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
              <span style={{ color: 'var(--color-red)', fontSize: 14 }}>✕</span>
              <span style={{ textDecoration: 'line-through', color: 'var(--color-red)' }}>
                {getItemName(selectedOption.affected_item_id)}
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, paddingLeft: 22 }}>
              <span style={{ color: 'var(--color-green)', fontSize: 14 }}>↳</span>
              <span style={{ color: 'var(--color-green)', fontWeight: 500 }}>
                {getItemName(selectedOption.replacement_item_id)}
              </span>
            </div>
          </div>
        )}

        {selectedOption.effect_type === 'quantity' && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
            <span style={{ fontSize: 14 }}>#</span>
            <div>
              <span style={{ fontWeight: 500 }}>{getItemName(selectedOption.affected_item_id)}</span>
              <span style={{ color: 'var(--color-text-muted)', marginLeft: 4 }}>
                {selectedOption.remove_quantity > 0 && `−${selectedOption.remove_quantity} `}
                {selectedOption.add_quantity > 0 && `+${selectedOption.add_quantity}`}
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Price Impact */}
      <div style={{ backgroundColor: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 8, padding: 14, marginBottom: 12 }}>
        <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>
          Impacto en precio
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: 13 }}>Precio adicional</span>
          <span style={{
            fontSize: 18,
            fontWeight: 700,
            fontVariantNumeric: 'tabular-nums',
            color: selectedOption.price_delta_cents > 0 ? 'var(--color-green)' : selectedOption.price_delta_cents < 0 ? 'var(--color-red)' : 'var(--color-text-muted)',
          }}>
            {priceMXN(selectedOption.price_delta_cents)}
          </span>
        </div>
      </div>

      {/* Inventory Effect */}
      <div style={{ backgroundColor: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 8, padding: 14 }}>
        <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>
          Inventario
        </div>
        <div style={{ fontSize: 13, color: selectedOption.inventory_effect ? 'var(--color-green)' : 'var(--color-text-muted)' }}>
          {selectedOption.inventory_effect
            ? '✓ Afecta inventario — se descontará al producir'
            : '○ Sin efecto en inventario'}
        </div>
      </div>
    </div>
  );
};
