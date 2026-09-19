import React, { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, fetchApi } from '@restaurantos/api-client';
import { ArrowDown, ArrowUp, Printer, Save } from 'lucide-react';
import '../../premium-catalogs.css';

type Category = { id: string; name: string; position: number };
type PriorityResponse = { version: number; view_order: Category[]; print_order: Category[] };
type Product = { id: string; name: string; sku: string; category_name?: string; price_cents?: number; status: string };

const failure = (reason: unknown, fallback: string) => (
  reason instanceof ApiError ? reason.message : fallback
);

const move = (items: Category[], id: string, direction: -1 | 1) => {
  const index = items.findIndex((item) => item.id === id);
  const next = index + direction;
  if (index < 0 || next < 0 || next >= items.length) return items;
  const copy = [...items];
  [copy[index], copy[next]] = [copy[next], copy[index]];
  return copy;
};

const OrderEditor = ({
  title, items, onMove, printOnly = false, products = [], canSeePrice = false,
}: {
  title: string;
  items: Category[];
  onMove: (id: string, direction: -1 | 1) => void;
  printOnly?: boolean;
  products?: Product[];
  canSeePrice?: boolean;
}) => (
  <section className={`premium-card admin-catalog-order${printOnly ? ' admin-catalog-print-order' : ''}`} style={{ padding: 20 }}>
    <h2 style={{ fontSize: '1rem', marginBottom: 8 }}>{title}</h2>
    <p className="premium-form-hint" style={{ marginBottom: 16 }}>
      {printOnly ? 'Esta secuencia se usa al imprimir el catálogo administrativo.' : 'Esta secuencia sólo organiza la consulta administrativa.'}
    </p>
    <ol className="admin-catalog-order-list">
      {items.map((category, index) => (
        <li key={category.id}>
          <span><strong>{index + 1}.</strong> {category.name}</span>
          <span className="admin-catalog-order-actions">
            <button type="button" aria-label={`Subir ${category.name}`} disabled={index === 0} onClick={() => onMove(category.id, -1)}><ArrowUp size={16} /></button>
            <button type="button" aria-label={`Bajar ${category.name}`} disabled={index === items.length - 1} onClick={() => onMove(category.id, 1)}><ArrowDown size={16} /></button>
          </span>
        </li>
      ))}
    </ol>
    {printOnly && <div className="admin-catalog-print-catalog" aria-label="Catálogo para impresión administrativa">
      {items.map((category) => {
        const categoryProducts = products.filter((product) => product.status === 'active' && product.category_name === category.name);
        return <section key={category.id} className="admin-catalog-print-group"><h3>{category.name}</h3>{categoryProducts.length === 0 ? <p>Sin productos activos.</p> : <ul>{categoryProducts.map((product) => <li key={product.id}><span>{product.name} <small>{product.sku}</small></span>{canSeePrice && typeof product.price_cents === 'number' && <span>${(product.price_cents / 100).toFixed(2)}</span>}</li>)}</ul>}</section>;
      })}
    </div>}
  </section>
);

export default function CategoryPriorities() {
  const client = useQueryClient();
  const [viewOrder, setViewOrder] = useState<Category[]>([]);
  const [printOrder, setPrintOrder] = useState<Category[]>([]);
  const [version, setVersion] = useState<number | null>(null);
  const [message, setMessage] = useState('');
  const priorities = useQuery<PriorityResponse>({
    queryKey: ['admin-catalog', 'category-priorities'],
    queryFn: () => fetchApi('/admin-catalog/category-priorities'),
  });
  const products = useQuery<Product[]>({ queryKey: ['catalog', 'products', 'admin-priority-preview'], queryFn: () => fetchApi('/catalog/products') });
  const currentUser = JSON.parse(localStorage.getItem('user') || '{}');
  const canSeePrice = Boolean(currentUser.is_superadmin || (currentUser.permissions || []).includes('catalog.manage'));

  useEffect(() => {
    if (!priorities.data) return;
    setViewOrder(priorities.data.view_order);
    setPrintOrder(priorities.data.print_order);
    setVersion(priorities.data.version);
  }, [priorities.data]);

  const save = useMutation({
    mutationFn: () => fetchApi<PriorityResponse>('/admin-catalog/category-priorities', {
      method: 'PUT',
      body: JSON.stringify({
        expected_version: version,
        view_category_ids: viewOrder.map((category) => category.id),
        print_category_ids: printOrder.map((category) => category.id),
      }),
    }),
    onSuccess: (response) => {
      setMessage('Prioridades administrativas guardadas.');
      setViewOrder(response.view_order);
      setPrintOrder(response.print_order);
      setVersion(response.version);
      void client.invalidateQueries({ queryKey: ['admin-catalog', 'category-priorities'] });
    },
    onError: (reason) => setMessage(failure(reason, 'No fue posible guardar las prioridades.')),
  });

  if (priorities.isLoading) return <p role="status">Cargando prioridades administrativas…</p>;
  if (priorities.isError) return <p role="alert">No fue posible cargar las prioridades. Recarga para reintentar.</p>;

  return (
    <main className="admin-catalog-tool">
      <header className="admin-catalog-tool__header">
        <div>
          <h1 className="premium-header-title">Prioridades administrativas</h1>
          <p className="premium-header-subtitle">Consulta e impresión tienen órdenes separados. El POS y las comandas no cambian.</p>
        </div>
        <div className="admin-catalog-tool__actions">
          <button className="premium-add-btn" type="button" onClick={() => window.print()}><Printer size={17} /> Imprimir catálogo</button>
          <button className="premium-add-btn" type="button" disabled={save.isPending || version === null} onClick={() => save.mutate()}><Save size={17} /> {save.isPending ? 'Guardando…' : 'Guardar prioridades'}</button>
        </div>
      </header>
      {message && <p role="status" className="admin-catalog-message">{message}</p>}
      <div className="admin-catalog-two-columns">
        <OrderEditor title="Orden de consulta" items={viewOrder} onMove={(id, direction) => setViewOrder((items) => move(items, id, direction))} />
        <OrderEditor title="Orden de impresión" printOnly items={printOrder} products={products.data || []} canSeePrice={canSeePrice} onMove={(id, direction) => setPrintOrder((items) => move(items, id, direction))} />
      </div>
      <section className="premium-card admin-catalog-catalog-view" style={{ padding: 20, marginTop: 20 }} aria-label="Vista administrativa del catálogo">
        <h2 style={{ fontSize: '1rem', marginBottom: 12 }}>Consulta administrativa del catálogo</h2>
        {viewOrder.map((category) => {
          const categoryProducts = (products.data || []).filter((product) => product.status === 'active' && product.category_name === category.name);
          return <section key={category.id} className="admin-catalog-print-group"><h3>{category.name}</h3>{categoryProducts.length === 0 ? <p>Sin productos activos.</p> : <ul>{categoryProducts.map((product) => <li key={product.id}><span>{product.name} <small>{product.sku}</small></span>{canSeePrice && typeof product.price_cents === 'number' && <span>${(product.price_cents / 100).toFixed(2)}</span>}</li>)}</ul>}</section>;
        })}
      </section>
    </main>
  );
}
