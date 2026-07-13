import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button, Badge, Modal, Input } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';
import { Plus, Package, Edit, Trash2, ChefHat, SlidersHorizontal } from 'lucide-react';
import { RecipeManager } from './RecipeManager';
import { ModifierManager } from './ModifierManager';

import '../../premium-catalogs.css';

interface Product {
  id: string;
  name: string;
  sku: string;
  category_name: string;
  price_cents: number | null;
  station: string;
  status?: string;
  image_url?: string;
  catalog_scope?: 'organization' | 'branch';
  source_branch_id?: string | null;
}

const emptyForm = { name: '', sku: '', category_name: '', station: 'kitchen', status: 'active', price_cents: 0, image_url: '' };

const ProductsList = () => {
  const queryClient = useQueryClient();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);
  const [recipeProduct, setRecipeProduct] = useState<Product | null>(null);
  const [modifierProduct, setModifierProduct] = useState<Product | null>(null);
  const [formData, setFormData] = useState(emptyForm);

  const { data: products, isLoading, error } = useQuery<Product[]>({
    queryKey: ['products'],
    queryFn: () => fetchApi('/catalog/products'),
  });

  const saveMutation = useMutation({
    mutationFn: (data: typeof formData) => {
      if (editingProduct) {
        return fetchApi(`/catalog/products/${editingProduct.id}`, {
          method: 'PUT',
          body: JSON.stringify(data),
        });
      }
      return fetchApi('/catalog/products', {
        method: 'POST',
        body: JSON.stringify(data),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['products'] });
      setIsModalOpen(false);
    }
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => fetchApi(`/catalog/products/${id}`, { method: 'DELETE' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['products'] })
  });

  const openModal = (product?: Product) => {
    if (product) {
      setEditingProduct(product);
      setFormData({ 
        name: product.name, 
        sku: product.sku, 
        category_name: product.category_name || '', 
        station: product.station || 'kitchen', 
        status: product.status || 'active',
        price_cents: product.price_cents || 0,
        image_url: product.image_url || ''
      });
    } else {
      setEditingProduct(null);
      setFormData(emptyForm);
    }
    setIsModalOpen(true);
  };

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 32 }}>
        <div>
          <h1 className="premium-header-title">Productos y catálogo</h1>
          <p className="premium-header-subtitle">Ajusta categorías, precios, estaciones y activa los productos importados.</p>
        </div>
        <button className="premium-add-btn" onClick={() => openModal()}>
          <Plus size={18} />
          Nuevo producto
        </button>
      </div>

      <div className="premium-card">
        {isLoading ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-text-muted)' }}>Cargando catálogo...</div>
        ) : error ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-red)' }}>Error al cargar los productos.</div>
        ) : !products || products.length === 0 ? (
          <div className="premium-empty-state">
            <Package size={64} className="premium-empty-icon" />
            <h3 style={{ marginBottom: 8, fontSize: '1.25rem', fontWeight: 600 }}>No hay productos</h3>
            <p style={{ color: 'var(--color-text-muted)' }}>Comienza agregando tu primer producto al menú.</p>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="premium-table">
              <thead>
                <tr>
                  <th>Producto</th>
                  <th>SKU</th>
                  <th>Categoría</th>
                  <th>Estación</th>
                  <th style={{ textAlign: 'right' }}>Precio</th>
                  <th style={{ textAlign: 'right' }}>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {products.map((product) => (
                  <tr key={product.id}>
                    <td style={{ fontWeight: 500 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                        <div style={{ padding: 8, background: 'rgba(59, 130, 246, 0.1)', color: '#3b82f6', borderRadius: 8 }}>
                          <Package size={18} />
                        </div>
                        {product.name}
                        {product.status === 'inactive' && <Badge variant="default">Inactivo</Badge>}
                        {product.status === 'needs_review' && <Badge variant="warning">Requiere revisión</Badge>}
                        {product.catalog_scope === 'branch' && <Badge variant="info">De sucursal</Badge>}
                        {product.price_cents == null && <Badge variant="warning">Sin precio</Badge>}
                      </div>
                    </td>
                    <td style={{ color: 'var(--color-text-muted)' }}>{product.sku}</td>
                    <td><Badge variant="info">{product.category_name}</Badge></td>
                    <td>{product.station}</td>
                    <td style={{ textAlign: 'right', fontWeight: 600 }}>{product.price_cents == null ? 'No vendible' : `$${(product.price_cents / 100).toFixed(2)}`}</td>
                    <td style={{ textAlign: 'right' }}>
                      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                        <button className="premium-action-btn edit" title="Ver Receta" onClick={() => setRecipeProduct(product)}><ChefHat size={18} /></button>
                        <button className="premium-action-btn edit" title="Modificadores" onClick={() => setModifierProduct(product)}><SlidersHorizontal size={18} /></button>
                        <button className="premium-action-btn edit" onClick={() => openModal(product)}><Edit size={18} /></button>
                        <button className="premium-action-btn delete" onClick={() => deleteMutation.mutate(product.id)}><Trash2 size={18} /></button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title={editingProduct ? "Ajustar producto" : "Nuevo producto"}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div>
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 500, fontSize: '0.875rem' }}>Nombre</label>
            <Input value={formData.name} onChange={(e: any) => setFormData({...formData, name: e.target.value})} />
          </div>
          <div>
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 500, fontSize: '0.875rem' }}>SKU</label>
            <Input value={formData.sku} onChange={(e: any) => setFormData({...formData, sku: e.target.value})} />
          </div>
          <div>
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 500, fontSize: '0.875rem' }}>Categoría</label>
            <Input value={formData.category_name} onChange={(e: any) => setFormData({...formData, category_name: e.target.value})} />
          </div>
          <div>
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 500, fontSize: '0.875rem' }}>Estación operativa</label>
            <select value={formData.station} onChange={(event) => setFormData({ ...formData, station: event.target.value })} style={{ width: '100%', padding: 10, borderRadius: 8, border: '1px solid #d1d5db' }}>
              <option value="unassigned">Sin asignar</option>
              <option value="kitchen">Cocina</option>
              <option value="drinks">Bebidas</option>
              <option value="packing">Empaque</option>
            </select>
          </div>
          {editingProduct && (
            <div>
              <label style={{ display: 'block', marginBottom: 4, fontWeight: 500, fontSize: '0.875rem' }}>Estado</label>
              <select value={formData.status} onChange={(event) => setFormData({ ...formData, status: event.target.value })} style={{ width: '100%', padding: 10, borderRadius: 8, border: '1px solid #d1d5db' }}>
                <option value="needs_review">Requiere revisión</option>
                <option value="active">Activo</option>
                <option value="inactive">Inactivo</option>
              </select>
              {formData.status === 'active' && formData.station === 'unassigned' && <p style={{ color: '#b45309', fontSize: 13 }}>Asigna una estación antes de activar.</p>}
            </div>
          )}
          <div>
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 500, fontSize: '0.875rem' }}>Precio (centavos)</label>
            <Input type="number" value={formData.price_cents} onChange={(e: any) => setFormData({...formData, price_cents: parseInt(e.target.value, 10)})} />
          </div>
          <div>
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 500, fontSize: '0.875rem' }}>URL de imagen</label>
            <Input value={formData.image_url} onChange={(e: any) => setFormData({...formData, image_url: e.target.value})} placeholder="https://example.com/image.png" />
          </div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12, marginTop: 16 }}>
            <Button variant="secondary" onClick={() => setIsModalOpen(false)}>Cancelar</Button>
            <Button variant="primary" onClick={() => saveMutation.mutate(formData)} disabled={saveMutation.isPending || (formData.status === 'active' && formData.station === 'unassigned')}>
              {saveMutation.isPending ? 'Guardando...' : 'Guardar'}
            </Button>
          </div>
        </div>
      </Modal>

      {recipeProduct && (
        <RecipeManager
          isOpen={true}
          productId={recipeProduct.id}
          productName={recipeProduct.name}
          onClose={() => setRecipeProduct(null)}
        />
      )}
      {modifierProduct && <ModifierManager isOpen productId={modifierProduct.id} productName={modifierProduct.name} onClose={() => setModifierProduct(null)} />}
    </>
  );
};
export default ProductsList;
