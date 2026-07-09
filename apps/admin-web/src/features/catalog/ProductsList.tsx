import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button, Badge, Modal, Input } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';
import { Plus, Package, Edit, Trash2 } from 'lucide-react';

import '../../premium-catalogs.css';

interface Product {
  id: string;
  name: string;
  sku: string;
  category_name: string;
  price_cents: number;
  station: string;
  status?: string;
}

const ProductsList = () => {
  const queryClient = useQueryClient();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);
  const [formData, setFormData] = useState({ name: '', sku: '', category_name: '', station: 'kitchen', price_cents: 0 });

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
        price_cents: product.price_cents 
      });
    } else {
      setEditingProduct(null);
      setFormData({ name: '', sku: '', category_name: '', station: 'kitchen', price_cents: 0 });
    }
    setIsModalOpen(true);
  };

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 32 }}>
        <div>
          <h1 className="premium-header-title">Products & Catalog</h1>
          <p className="premium-header-subtitle">Manage your inventory, pricing, and stations with style.</p>
        </div>
        <button className="premium-add-btn" onClick={() => openModal()}>
          <Plus size={18} />
          Add Product
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
                  <th>Product</th>
                  <th>SKU</th>
                  <th>Category</th>
                  <th>Station</th>
                  <th style={{ textAlign: 'right' }}>Price</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
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
                      </div>
                    </td>
                    <td style={{ color: 'var(--color-text-muted)' }}>{product.sku}</td>
                    <td><Badge variant="info">{product.category_name}</Badge></td>
                    <td>{product.station}</td>
                    <td style={{ textAlign: 'right', fontWeight: 600 }}>${(product.price_cents / 100).toFixed(2)}</td>
                    <td style={{ textAlign: 'right' }}>
                      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
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

      <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title={editingProduct ? "Edit Product" : "New Product"}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div>
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 500, fontSize: '0.875rem' }}>Name</label>
            <Input value={formData.name} onChange={(e: any) => setFormData({...formData, name: e.target.value})} />
          </div>
          <div>
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 500, fontSize: '0.875rem' }}>SKU</label>
            <Input value={formData.sku} onChange={(e: any) => setFormData({...formData, sku: e.target.value})} />
          </div>
          {!editingProduct && (
             <div>
               <label style={{ display: 'block', marginBottom: 4, fontWeight: 500, fontSize: '0.875rem' }}>Category</label>
               <Input value={formData.category_name} onChange={(e: any) => setFormData({...formData, category_name: e.target.value})} />
             </div>
          )}
          {!editingProduct && (
             <div>
               <label style={{ display: 'block', marginBottom: 4, fontWeight: 500, fontSize: '0.875rem' }}>Station (kitchen/drinks/packing)</label>
               <Input value={formData.station} onChange={(e: any) => setFormData({...formData, station: e.target.value})} />
             </div>
          )}
          <div>
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 500, fontSize: '0.875rem' }}>Price (cents)</label>
            <Input type="number" value={formData.price_cents} onChange={(e: any) => setFormData({...formData, price_cents: parseInt(e.target.value, 10)})} />
          </div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12, marginTop: 16 }}>
            <Button variant="secondary" onClick={() => setIsModalOpen(false)}>Cancel</Button>
            <Button variant="primary" onClick={() => saveMutation.mutate(formData)} disabled={saveMutation.isPending}>
              {saveMutation.isPending ? 'Saving...' : 'Save'}
            </Button>
          </div>
        </div>
      </Modal>
    </>
  );
};
export default ProductsList;
