import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import PosLayout from './components/PosLayout';
import PointOfSale from './features/pos/PointOfSale';
import PosInventory from './features/inventory/PosInventory';
import Customers from './features/customers/Customers';
import History from './features/history/History';
import Settings from './features/settings/Settings';
import AdminHub from './features/admin/AdminHub';
import BranchAdminProducts from './features/admin/BranchAdminProducts';
import BranchAdminVariations from './features/admin/BranchAdminVariations';
import BranchAdminIngredientExtras from './features/admin/BranchAdminIngredientExtras';
import {
  BranchAdminCounts,
  BranchAdminProduction,
  BranchAdminPurchases,
  BranchAdminSuppliers,
  BranchAdminTransfers,
  BranchAdminWaste,
} from './features/admin/BranchAdminOperations';
import { PosSessionProvider, usePosSession } from './session';

const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const params = new URLSearchParams(window.location.search);
  const tokenParam = params.get('token');
  // The legacy `user` query param is no longer used as authority; only the
  // token is kept as a credential and the session is validated via /auth/session.
  if (tokenParam) {
    localStorage.setItem('auth_token', tokenParam);
    const newUrl = window.location.pathname;
    window.history.replaceState({}, document.title, newUrl);
  }

  const isDev =
    window.location.hostname === 'localhost' ||
    window.location.hostname === '127.0.0.1' ||
    (window.location.port !== '' &&
      window.location.port !== '80' &&
      window.location.port !== '443');
  const token = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');
  if (!token) {
    const loginUrl = isDev ? 'http://localhost:3002/admin/login' : '/admin/login';
    window.location.href = loginUrl;
    return null;
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

const App = () => {
  return (
    <BrowserRouter basename="/pos">
      <ProtectedRoute>
        <PosSessionProvider>
          <SessionGate>
            <Routes>
              <Route path="/" element={<PosLayout />}>
                <Route index element={<Navigate to="/pos" replace />} />
                <Route path="pos" element={<PointOfSale />} />
                <Route path="dashboard" element={<Navigate to="/pos" replace />} />
                <Route path="inventory" element={<Navigate to="/administration/inventory" replace />} />
                <Route path="customers" element={<Customers />} />
                <Route path="history" element={<History />} />
                <Route path="settings" element={<Settings />} />
                <Route path="administration" element={
                  <PermissionRoute permission="branch.admin.access">
                    <AdminHub />
                  </PermissionRoute>
                } />
                <Route path="administration/products" element={
                  <PermissionRoute permission="branch.admin.access">
                    <BranchAdminProducts />
                  </PermissionRoute>
                } />
                <Route path="administration/inventory" element={
                  <PermissionRoute permission="branch.admin.access">
                    <PosInventory />
                  </PermissionRoute>
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
