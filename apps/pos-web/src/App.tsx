import React, { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { fetchApi } from '@restaurantos/api-client';
import PosLayout from './components/PosLayout';
import PointOfSale from './features/pos/PointOfSale';
import PosInventory from './features/inventory/PosInventory';
import Customers from './features/customers/Customers';
import History from './features/history/History';
import { UberOrdersView, DidiOrdersView, RappiOrdersView } from './features/uber_orders/UberOrdersView';
import InvoicingView from './features/invoicing/InvoicingView';
import Settings from './features/settings/Settings';
import AdminHub from './features/admin/AdminHub';
import BranchAdminProducts from './features/admin/BranchAdminProducts';
import BranchAdminVariations from './features/admin/BranchAdminVariations';
import BranchAdminIngredientExtras from './features/admin/BranchAdminIngredientExtras';
import AttendanceReport from './features/attendance/AttendanceReport';
import CashMovements from './features/cash/CashMovements';
import SalesMonitor from './features/reports/SalesMonitor';
import PCO007Reports from './features/reports/PCO007Reports';
import {
  BranchAdminCounts,
  BranchAdminProduction,
  BranchAdminPurchases,
  BranchAdminSuppliers,
  BranchAdminTransfers,
  BranchAdminWaste,
} from './features/admin/BranchAdminOperations';
import { PosSessionProvider, usePosSession } from './session';

const adminLoginUrl = () => {
  const isDev = window.location.hostname === 'localhost'
    || window.location.hostname === '127.0.0.1'
    || (window.location.port !== '' && window.location.port !== '80' && window.location.port !== '443');
  return isDev ? 'http://localhost:3002/admin/login' : '/admin/login';
};

const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const [state, setState] = useState<'checking' | 'ready' | 'error'>('checking');

  useEffect(() => {
    const fragment = new URLSearchParams(window.location.hash.replace(/^#/, ''));
    const handoffCode = fragment.get('handoff');
    const cleanSearch = new URLSearchParams(window.location.search);
    const hadLegacyCredentials = cleanSearch.has('token') || cleanSearch.has('user');
    cleanSearch.delete('token');
    cleanSearch.delete('user');
    const remainingSearch = cleanSearch.toString();
    const cleanUrl = `${window.location.pathname}${remainingSearch ? `?${remainingSearch}` : ''}`;

    if (handoffCode || hadLegacyCredentials || window.location.hash) {
      window.history.replaceState({}, document.title, cleanUrl);
    }

    if (handoffCode) {
      localStorage.removeItem('auth_token');
      sessionStorage.removeItem('auth_token');
      void fetchApi<{ token: string }>('/auth/pos-handoffs/exchange', {
        method: 'POST',
        body: JSON.stringify({ handoff_code: handoffCode }),
      }).then(({ token }) => {
        localStorage.setItem('auth_token', token);
        setState('ready');
      }).catch(() => {
        setState('error');
      });
      return;
    }

    const token = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');
    if (token) {
      setState('ready');
      return;
    }
    window.location.href = adminLoginUrl();
  }, []);

  if (state === 'checking') return null;
  if (state === 'error') {
    return (
      <main style={{ display: 'grid', placeItems: 'center', minHeight: '100vh', padding: 24 }}>
        <div style={{ textAlign: 'center' }}>
          <p>No fue posible transferir la sesión al POS.</p>
          <button type="button" onClick={() => { window.location.href = adminLoginUrl(); }}>
            Volver a iniciar sesión
          </button>
        </div>
      </main>
    );
  }
  return <>{children}</>;
};

const SessionGate: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { state } = usePosSession();

  if (state.status === 'loading') {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <p style={{ color: '#64748b' }}>Cargando sesión…</p>
      </div>
    );
  }

  if (state.status === 'error') {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', height: '100vh', gap: '1rem' }}>
        <p style={{ color: '#dc2626', fontSize: 18 }}>{state.message}</p>
        <button
          onClick={() => window.location.reload()}
          style={{
            padding: '0.5rem 1.5rem',
            borderRadius: '0.5rem',
            border: '1px solid #16a34a',
            background: '#16a34a',
            color: '#fff',
            cursor: 'pointer',
          }}
        >
          Reintentar
        </button>
      </div>
    );
  }

  if (state.status === 'ok') {
    if (!state.session.permissions.includes('pos.operate')) {
      return (
        <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', height: '100vh', gap: '1rem' }}>
          <p style={{ color: '#dc2626', fontSize: 18 }}>Tu cuenta no tiene acceso al POS.</p>
        </div>
      );
    }
  }

  return <>{children}</>;
};

const PermissionRoute: React.FC<{
  permission: string;
  children: React.ReactNode;
}> = ({ permission, children }) => {
  const { hasPermission } = usePosSession();
  if (!hasPermission(permission)) {
    return <Navigate to="/pos" replace />;
  }
  return <>{children}</>;
};

const AnyPermissionRoute: React.FC<{
  permissions: string[];
  children: React.ReactNode;
}> = ({ permissions, children }) => {
  const { hasPermission } = usePosSession();
  if (!permissions.some(hasPermission)) return <Navigate to="/pos" replace />;
  return <>{children}</>;
};

const App = () => {
  return (
    <BrowserRouter basename="/pos">
      <ProtectedRoute>
        <PosSessionProvider>
          <SessionGate>
            <Routes>
              <Route path="/" element={<PosLayout />}>
                <Route index element={<PointOfSale />} />
                <Route path="pos" element={<PointOfSale />} />
                <Route path="pos/orders/:editOrderId/edit" element={<PointOfSale />} />
                <Route path="orders/:editOrderId/edit" element={<PointOfSale />} />
                <Route path="dashboard" element={<Navigate to="/" replace />} />
                <Route path="inventory" element={<Navigate to="/administration/inventory" replace />} />
                <Route path="customers" element={<Customers />} />
                <Route path="history" element={<History />} />
                <Route path="uber-orders" element={<UberOrdersView />} />
                <Route path="didi-orders" element={<DidiOrdersView />} />
                <Route path="rappi-orders" element={<RappiOrdersView />} />
                <Route path="invoicing" element={<InvoicingView />} />
                <Route path="cash-movements" element={
                  <AnyPermissionRoute permissions={[
                    'cash.movement.read', 'cash.movement.withdraw', 'cash.movement.deposit',
                  ]}>
                    <CashMovements />
                  </AnyPermissionRoute>
                } />
                <Route path="settings" element={<Settings />} />
                <Route path="sales-monitor" element={
                  <PermissionRoute permission="reports.sales.read">
                    <SalesMonitor />
                  </PermissionRoute>
                } />
                <Route path="historical-reports" element={
                  <AnyPermissionRoute permissions={['reports.ingredient_sales.read', 'reports.expenses.read']}>
                    <PCO007Reports />
                  </AnyPermissionRoute>
                } />
                <Route path="administration" element={
                  <AnyPermissionRoute permissions={[
                    'branch.admin.access', 'admin.manage', 'purchases.read', 'inventory.read',
                    'inventory.waste', 'recipes.manage', 'reports.sales.read',
                    'reports.ingredient_sales.read', 'cash.user_cut.read',
                  ]}>
                    <AdminHub />
                  </AnyPermissionRoute>
                } />
                <Route path="administration/attendance" element={
                  <AnyPermissionRoute permissions={['branch.staff.read', 'admin.manage']}>
                    <AttendanceReport />
                  </AnyPermissionRoute>
                } />
                <Route path="administration/products" element={
                  <AnyPermissionRoute permissions={['recipes.manage', 'branch.admin.access', 'admin.manage']}>
                    <BranchAdminProducts />
                  </AnyPermissionRoute>
                } />
                <Route path="administration/inventory" element={
                  <AnyPermissionRoute permissions={['inventory.read', 'branch.admin.access', 'admin.manage']}>
                    <PosInventory />
                  </AnyPermissionRoute>
                } />
                <Route path="administration/variations" element={
                  <PermissionRoute permission="catalog.branch.manage">
                    <PermissionRoute permission="branch.admin.access">
                      <BranchAdminVariations />
                    </PermissionRoute>
                  </PermissionRoute>
                } />
                <Route path="administration/ingredient-extras" element={
                  <PermissionRoute permission="catalog.branch.manage">
                    <PermissionRoute permission="branch.admin.access">
                      <BranchAdminIngredientExtras />
                    </PermissionRoute>
                  </PermissionRoute>
                } />
                <Route path="administration/suppliers" element={
                  <PermissionRoute permission="purchases.read">
                    <BranchAdminSuppliers />
                  </PermissionRoute>
                } />
                <Route path="administration/purchases" element={
                  <PermissionRoute permission="purchases.read">
                    <BranchAdminPurchases />
                  </PermissionRoute>
                } />
                <Route path="administration/production" element={
                  <PermissionRoute permission="production.manage">
                    <BranchAdminProduction />
                  </PermissionRoute>
                } />
                <Route path="administration/waste" element={
                  <PermissionRoute permission="inventory.waste">
                    <BranchAdminWaste />
                  </PermissionRoute>
                } />
                <Route path="administration/transfers" element={
                  <PermissionRoute permission="inventory.transfer.send">
                    <BranchAdminTransfers />
                  </PermissionRoute>
                } />
                <Route path="administration/counts" element={
                  <PermissionRoute permission="inventory.count">
                    <BranchAdminCounts />
                  </PermissionRoute>
                } />
              </Route>
            </Routes>
          </SessionGate>
        </PosSessionProvider>
      </ProtectedRoute>
    </BrowserRouter>
  );
};

export default App;
