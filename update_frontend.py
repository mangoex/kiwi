import os

users_list = """import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, Button, Badge, Modal, Input } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';
import { Plus, Users, Edit, Trash2 } from 'lucide-react';

interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  display_name?: string;
  is_active: boolean;
  role_id: string;
}

const UsersList = () => {
  const queryClient = useQueryClient();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [formData, setFormData] = useState({ email: '', display_name: '', password: '' });

  const { data: users, isLoading, error } = useQuery<User[]>({
    queryKey: ['users'],
    queryFn: () => fetchApi('/users'),
  });

  const saveMutation = useMutation({
    mutationFn: (data: typeof formData) => {
      if (editingUser) {
        return fetchApi(`/users/${editingUser.id}`, {
          method: 'PUT',
          body: JSON.stringify(data),
        });
      }
      return fetchApi('/users', {
        method: 'POST',
        body: JSON.stringify(data),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      setIsModalOpen(false);
    }
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => fetchApi(`/users/${id}`, { method: 'DELETE' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'] })
  });

  const openModal = (user?: User) => {
    if (user) {
      setEditingUser(user);
      setFormData({ email: user.email, display_name: user.display_name || user.first_name || '', password: '' });
    } else {
      setEditingUser(null);
      setFormData({ email: '', display_name: '', password: '' });
    }
    setIsModalOpen(true);
  };

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 32 }}>
        <div>
          <h1 className="admin-title" style={{ marginBottom: 4 }}>Usuarios</h1>
          <p style={{ color: 'var(--color-text-muted)' }}>Controla los accesos y permisos de tu equipo.</p>
        </div>
        <Button variant="primary" style={{ display: 'flex', alignItems: 'center', gap: 8 }} onClick={() => openModal()}>
          <Plus size={18} />
          Nuevo Usuario
        </Button>
      </div>

      <Card style={{ padding: 0, overflow: 'hidden' }}>
        {isLoading ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-text-muted)' }}>Cargando usuarios...</div>
        ) : error ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-red)' }}>Error al cargar usuarios.</div>
        ) : !users || users.length === 0 ? (
          <div style={{ padding: 60, textAlign: 'center' }}>
            <Users size={48} style={{ color: 'var(--color-border)', margin: '0 auto 16px' }} />
            <h3 style={{ marginBottom: 8 }}>No hay usuarios</h3>
            <p style={{ color: 'var(--color-text-muted)' }}>Tu organización aún no tiene usuarios registrados.</p>
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--color-border)', backgroundColor: 'var(--color-bg)' }}>
                <th style={{ padding: '16px 24px', fontWeight: 600, fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>Nombre</th>
                <th style={{ padding: '16px 24px', fontWeight: 600, fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>Correo</th>
                <th style={{ padding: '16px 24px', fontWeight: 600, fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>Estatus</th>
                <th style={{ padding: '16px 24px', fontWeight: 600, fontSize: '0.875rem', color: 'var(--color-text-muted)', textAlign: 'right' }}>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id} style={{ borderBottom: '1px solid var(--color-border)' }}>
                  <td style={{ padding: '16px 24px', fontWeight: 500 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                      <div style={{ width: 32, height: 32, borderRadius: '50%', backgroundColor: 'var(--color-blue-light)', color: 'var(--color-blue)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 600, fontSize: '0.75rem' }}>
                        {(user.display_name || user.first_name || 'U').charAt(0)}
                      </div>
                      {user.display_name || `${user.first_name} ${user.last_name || ''}`}
                    </div>
                  </td>
                  <td style={{ padding: '16px 24px', color: 'var(--color-text-muted)', fontSize: '0.875rem' }}>{user.email}</td>
                  <td style={{ padding: '16px 24px' }}>
                    <Badge variant={user.is_active || (user as any).status !== 'suspended' ? 'success' : 'default'}>
                      {user.is_active || (user as any).status !== 'suspended' ? 'Activo' : 'Inactivo'}
                    </Badge>
                  </td>
                  <td style={{ padding: '16px 24px', textAlign: 'right' }}>
                    <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                      <button onClick={() => openModal(user)} style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--color-blue)' }}><Edit size={18} /></button>
                      <button onClick={() => deleteMutation.mutate(user.id)} style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--color-red)' }}><Trash2 size={18} /></button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title={editingUser ? "Editar Usuario" : "Nuevo Usuario"}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <Input label="Correo electrónico" value={formData.email} onChange={(e: any) => setFormData({...formData, email: e.target.value})} />
          <Input label="Nombre a mostrar" value={formData.display_name} onChange={(e: any) => setFormData({...formData, display_name: e.target.value})} />
          {!editingUser && <Input label="Contraseña" type="password" value={formData.password} onChange={(e: any) => setFormData({...formData, password: e.target.value})} />}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12, marginTop: 16 }}>
            <Button variant="secondary" onClick={() => setIsModalOpen(false)}>Cancelar</Button>
            <Button variant="primary" onClick={() => saveMutation.mutate(formData)} disabled={saveMutation.isPending}>
              {saveMutation.isPending ? 'Guardando...' : 'Guardar'}
            </Button>
          </div>
        </div>
      </Modal>
    </>
  );
};
export default UsersList;
"""

branches_list = """import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, Button, Badge, Modal, Input } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';
import { Plus, Store, Edit, Trash2 } from 'lucide-react';

interface Branch {
  id: string;
  name: string;
  code: string;
  status: string;
  address: string;
  organization_id: string;
}

const BranchesList = () => {
  const queryClient = useQueryClient();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingBranch, setEditingBranch] = useState<Branch | null>(null);
  const [formData, setFormData] = useState({ name: '', code: '' });

  const { data: branches, isLoading, error } = useQuery<Branch[]>({
    queryKey: ['branches'],
    queryFn: () => fetchApi('/branches'),
  });

  const saveMutation = useMutation({
    mutationFn: (data: typeof formData) => {
      if (editingBranch) {
        return fetchApi(`/branches/${editingBranch.id}`, {
          method: 'PUT',
          body: JSON.stringify(data),
        });
      }
      return fetchApi('/branches', {
        method: 'POST',
        body: JSON.stringify(data),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['branches'] });
      setIsModalOpen(false);
    }
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => fetchApi(`/branches/${id}`, { method: 'DELETE' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['branches'] })
  });

  const openModal = (branch?: Branch) => {
    if (branch) {
      setEditingBranch(branch);
      setFormData({ name: branch.name, code: branch.code || '' });
    } else {
      setEditingBranch(null);
      setFormData({ name: '', code: '' });
    }
    setIsModalOpen(true);
  };

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 32 }}>
        <div>
          <h1 className="admin-title" style={{ marginBottom: 4 }}>Branches (Sucursales)</h1>
          <p style={{ color: 'var(--color-text-muted)' }}>Administra las sucursales de la franquicia.</p>
        </div>
        <Button variant="primary" style={{ display: 'flex', alignItems: 'center', gap: 8 }} onClick={() => openModal()}>
          <Plus size={18} />
          Nueva Sucursal
        </Button>
      </div>

      <Card style={{ padding: 0, overflow: 'hidden' }}>
        {isLoading ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-text-muted)' }}>Cargando sucursales...</div>
        ) : error ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-red)' }}>Error al cargar sucursales.</div>
        ) : !branches || branches.length === 0 ? (
          <div style={{ padding: 60, textAlign: 'center' }}>
            <Store size={48} style={{ color: 'var(--color-border)', margin: '0 auto 16px' }} />
            <h3 style={{ marginBottom: 8 }}>No hay sucursales registradas</h3>
            <p style={{ color: 'var(--color-text-muted)' }}>Agrega la primera sucursal para operar.</p>
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--color-border)', backgroundColor: 'var(--color-bg)' }}>
                <th style={{ padding: '16px 24px', fontWeight: 600, fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>Nombre</th>
                <th style={{ padding: '16px 24px', fontWeight: 600, fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>Estatus</th>
                <th style={{ padding: '16px 24px', fontWeight: 600, fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>Código</th>
                <th style={{ padding: '16px 24px', fontWeight: 600, fontSize: '0.875rem', color: 'var(--color-text-muted)', textAlign: 'right' }}>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {branches.map((branch) => (
                <tr key={branch.id} style={{ borderBottom: '1px solid var(--color-border)' }}>
                  <td style={{ padding: '16px 24px', fontWeight: 500 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                      <div style={{ padding: 8, backgroundColor: 'var(--color-blue-light)', color: 'var(--color-blue)', borderRadius: 8 }}>
                        <Store size={18} />
                      </div>
                      {branch.name}
                    </div>
                  </td>
                  <td style={{ padding: '16px 24px' }}>
                    <Badge variant={branch.status === 'active' ? 'success' : 'default'}>
                      {branch.status === 'active' ? 'Activa' : 'Inactiva'}
                    </Badge>
                  </td>
                  <td style={{ padding: '16px 24px', color: 'var(--color-text-muted)', fontSize: '0.875rem' }}>{branch.code}</td>
                  <td style={{ padding: '16px 24px', textAlign: 'right' }}>
                    <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                      <button onClick={() => openModal(branch)} style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--color-blue)' }}><Edit size={18} /></button>
                      <button onClick={() => deleteMutation.mutate(branch.id)} style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--color-red)' }}><Trash2 size={18} /></button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title={editingBranch ? "Editar Sucursal" : "Nueva Sucursal"}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <Input label="Nombre de la sucursal" value={formData.name} onChange={(e: any) => setFormData({...formData, name: e.target.value})} />
          <Input label="Código (ej. SUC01)" value={formData.code} onChange={(e: any) => setFormData({...formData, code: e.target.value})} />
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12, marginTop: 16 }}>
            <Button variant="secondary" onClick={() => setIsModalOpen(false)}>Cancelar</Button>
            <Button variant="primary" onClick={() => saveMutation.mutate(formData)} disabled={saveMutation.isPending}>
              {saveMutation.isPending ? 'Guardando...' : 'Guardar'}
            </Button>
          </div>
        </div>
      </Modal>
    </>
  );
};
export default BranchesList;
"""

products_list = """import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, Button, Badge, Modal, Input } from '@restaurantos/ui';
import { fetchApi } from '@restaurantos/api-client';
import { Plus, Package, Edit, Trash2 } from 'lucide-react';

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
          <h1 className="admin-title" style={{ marginBottom: 4 }}>Products & Catalog</h1>
          <p style={{ color: 'var(--color-text-muted)' }}>Manage your inventory, pricing, and stations.</p>
        </div>
        <Button variant="primary" style={{ display: 'flex', alignItems: 'center', gap: 8 }} onClick={() => openModal()}>
          <Plus size={18} />
          Add Product
        </Button>
      </div>

      <Card style={{ padding: 0, overflow: 'hidden' }}>
        {isLoading ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-text-muted)' }}>Cargando catálogo...</div>
        ) : error ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-red)' }}>Error al cargar los productos.</div>
        ) : !products || products.length === 0 ? (
          <div style={{ padding: 60, textAlign: 'center' }}>
            <Package size={48} style={{ color: 'var(--color-border)', margin: '0 auto 16px' }} />
            <h3 style={{ marginBottom: 8 }}>No hay productos</h3>
            <p style={{ color: 'var(--color-text-muted)' }}>Comienza agregando tu primer producto al menú.</p>
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--color-border)', backgroundColor: 'var(--color-bg)' }}>
                <th style={{ padding: '16px 24px', fontWeight: 600, fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>Product</th>
                <th style={{ padding: '16px 24px', fontWeight: 600, fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>SKU</th>
                <th style={{ padding: '16px 24px', fontWeight: 600, fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>Category</th>
                <th style={{ padding: '16px 24px', fontWeight: 600, fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>Station</th>
                <th style={{ padding: '16px 24px', fontWeight: 600, fontSize: '0.875rem', color: 'var(--color-text-muted)', textAlign: 'right' }}>Price</th>
                <th style={{ padding: '16px 24px', fontWeight: 600, fontSize: '0.875rem', color: 'var(--color-text-muted)', textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {products.map((product) => (
                <tr key={product.id} style={{ borderBottom: '1px solid var(--color-border)' }}>
                  <td style={{ padding: '16px 24px', fontWeight: 500 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      {product.name}
                      {product.status === 'inactive' && <Badge variant="default">Inactivo</Badge>}
                    </div>
                  </td>
                  <td style={{ padding: '16px 24px', color: 'var(--color-text-muted)', fontSize: '0.875rem' }}>{product.sku}</td>
                  <td style={{ padding: '16px 24px' }}><Badge variant="info">{product.category_name}</Badge></td>
                  <td style={{ padding: '16px 24px', fontSize: '0.875rem' }}>{product.station}</td>
                  <td style={{ padding: '16px 24px', textAlign: 'right', fontWeight: 600 }}>${(product.price_cents / 100).toFixed(2)}</td>
                  <td style={{ padding: '16px 24px', textAlign: 'right' }}>
                    <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                      <button onClick={() => openModal(product)} style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--color-blue)' }}><Edit size={18} /></button>
                      <button onClick={() => deleteMutation.mutate(product.id)} style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--color-red)' }}><Trash2 size={18} /></button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title={editingProduct ? "Edit Product" : "New Product"}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <Input label="Name" value={formData.name} onChange={(e: any) => setFormData({...formData, name: e.target.value})} />
          <Input label="SKU" value={formData.sku} onChange={(e: any) => setFormData({...formData, sku: e.target.value})} />
          {!editingProduct && (
             <Input label="Category" value={formData.category_name} onChange={(e: any) => setFormData({...formData, category_name: e.target.value})} />
          )}
          {!editingProduct && (
             <Input label="Station (kitchen/drinks/packing)" value={formData.station} onChange={(e: any) => setFormData({...formData, station: e.target.value})} />
          )}
          <Input label="Price (cents)" type="number" value={formData.price_cents} onChange={(e: any) => setFormData({...formData, price_cents: parseInt(e.target.value, 10)})} />
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
"""

import os
base = r"c:\Users\Miguel Gonzalez\Downloads\Kiwi\apps\admin-web\src\features"
with open(os.path.join(base, "users", "UsersList.tsx"), "w", encoding="utf-8") as f:
    f.write(users_list)
with open(os.path.join(base, "branches", "BranchesList.tsx"), "w", encoding="utf-8") as f:
    f.write(branches_list)
with open(os.path.join(base, "catalog", "ProductsList.tsx"), "w", encoding="utf-8") as f:
    f.write(products_list)
