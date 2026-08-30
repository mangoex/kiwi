// SEC001-SYNTHETIC-FIXTURE provenance=restaurantos-admin-ai-visual-qa-v1
import React from 'react';
import ReactDOM from 'react-dom/client';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import AdminLayout from './components/AdminLayout';
import Overview from './features/dashboard/Overview';
import ItemsList from './features/inventory/ItemsList';
import PresentationsList from './features/purchasing/PresentationsList';
import './App.css';

const branchId = '018f6f73-2d0a-74f0-8f1c-000000000003';
const proposalId = '018f6f73-2d0a-74f0-8f1c-000000000099';
const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });

const diagnosticItems = [
  ['018f6f73-2d0a-74f0-8f1c-000000000401', 'Manzana roja', 'FRU-MAN-ROJ', 'kg'],
  ['018f6f73-2d0a-74f0-8f1c-000000000402', 'Yogurt natural GDE', 'LACT-YOG-NAT-GDE', 'pz'],
  ['018f6f73-2d0a-74f0-8f1c-000000000403', 'Medio baguette', 'PAN-BAG-MED', 'pz'],
  ['018f6f73-2d0a-74f0-8f1c-000000000404', 'Queso cabra GDE', 'LAC-QS-CAB-GDE', 'kg'],
  ['018f6f73-2d0a-74f0-8f1c-000000000405', 'Leche entera GDE', 'LAC-LEC-ENT-GDE', 'pz'],
].map(([id, name, sku, baseUnitCode]) => ({
  id,
  name,
  sku,
  base_unit_code: baseUnitCode,
  label: `${name} (${sku})`,
}));

const diagnosticProposal = {
  id: proposalId,
  status: 'DRAFT',
  payload: {
    answer: 'Se encontraron 24 insumos sin precio de compra utilizable.',
    sources: ['PRD-FR-093', 'PRD-FR-094'],
    questions: [],
    warnings: [],
    change_set: [],
    diagnostic: {
      kind: 'missing_purchase_price',
      scope: { branch_id: branchId },
      total: 24,
      items: diagnosticItems,
      truncated: true,
    },
  },
};

const inventoryItems = diagnosticItems.map((item) => ({
  ...item,
  base_unit_id: item.base_unit_code === 'kg' ? 'unit-kg' : 'unit-pz',
  unit_name: item.base_unit_code === 'kg' ? 'Kilogramo' : 'Pieza',
  unit_code: item.base_unit_code,
  item_type: 'ingredient',
  status: 'active',
  created_at: '2026-08-29T18:00:00Z',
  catalog_scope: 'organization',
  last_unit_cost: 0,
  average_unit_cost: 0,
}));

const dashboard = {
  total_revenue_cents: 35000,
  total_orders: 1,
  average_ticket_cents: 35000,
  total_products: 317,
  period_from_utc: '2026-08-01T00:00:00Z',
  period_to_utc: '2026-09-01T00:00:00Z',
  order_types: { mostrador: 1, para_llevar: 0, domicilio: 0 },
  recent_transactions: [],
  activity_chart: [{ day: '29 ago', completed: 1, pending: 0 }],
  recent_notifications: [],
  popular_categories: [
    { id: 'cat-1', name: 'Baguettes', quantity: 2, known_net_cents: 20000, share_bps: 6670 },
    { id: 'cat-2', name: 'Jugos', quantity: 1, known_net_cents: 10000, share_bps: 3330 },
  ],
};

localStorage.setItem('auth_token', 'synthetic-admin-ai-qa-token');
localStorage.setItem('admin_branch_id', branchId);
localStorage.setItem('user', JSON.stringify({
  id: 'admin-ai-qa-user',
  display_name: 'Administradora QA',
  email: 'qa@example.invalid',
  is_superadmin: true,
  assigned_branch_id: branchId,
  roles: ['Administrador'],
  permissions: ['catalog.manage', 'recipes.manage', 'reports.sales.read'],
}));

window.fetch = async (input, init) => {
  const requestUrl = typeof input === 'string'
    ? input
    : input instanceof URL
      ? input.toString()
      : input.url;
  const url = new URL(requestUrl, window.location.origin);
  const path = url.pathname.replace('/api/v1', '');
  let body: unknown = [];
  if (path === '/branches') body = [{ id: branchId, name: 'Centro', status: 'active' }];
  else if (path === '/dashboard/overview') body = dashboard;
  else if (path === '/catalog/products') body = [];
  else if (path === '/inventory/items') body = inventoryItems;
  else if (path === '/inventory/units') body = [
    { id: 'unit-kg', code: 'kg', name: 'Kilogramo' },
    { id: 'unit-pz', code: 'pz', name: 'Pieza' },
  ];
  else if (path === '/purchase-presentations') body = [];
  else if (path === '/suppliers') body = [];
  else if (path === '/admin-ai/proposals' && (init?.method || 'GET') === 'POST') body = diagnosticProposal;
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
};

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route path="/" element={<AdminLayout />}>
            <Route index element={<Overview />} />
            <Route path="purchase-presentations" element={<PresentationsList />} />
            <Route path="inventory/items" element={<ItemsList />} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  </React.StrictMode>,
);
