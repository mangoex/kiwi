export interface EditableCatalogProduct {
  id: string;
  name: string;
  sku: string;
  category: string;
  price_cents: number;
  description: string;
  station: string;
  image_url?: string;
}

export interface EditableLineSnapshot {
  product_id: string;
  product_name: string;
  unit_price_cents: number;
  station: string;
}

export function resolveEditableLineProduct(
  line: EditableLineSnapshot,
  productById: ReadonlyMap<string, EditableCatalogProduct>,
): EditableCatalogProduct {
  return productById.get(line.product_id) ?? {
    id: line.product_id,
    name: line.product_name,
    sku: '',
    category: 'Pedido actual',
    price_cents: line.unit_price_cents,
    description: '',
    station: line.station,
  };
}
