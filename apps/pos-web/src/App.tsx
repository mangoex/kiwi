import React, { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { fetchApi, hasAdminCapability } from '@restaurantos/api-client';
import PosLayout from './components/PosLayout';
import PointOfSale from './features/pos/PointOfSale';
import PhysicalCountCapturePage from './features/inventory/PhysicalCountCapturePage';
import Customers from './features/customers/Customers';
import History from './features/history/History';
import { UberOrdersView, DidiOrdersView, RappiOrdersView } from './features/uber_orders/UberOrdersView';
import InvoicingView from './features/invoicing/InvoicingView';
import Settings from './features/settings/Settings';
import AdminHub from './features/admin/AdminHub';
import AttendanceReport from './features/attendance/AttendanceReport';
import CashMovements from './features/cash/CashMovements';
import SalesMonitor from './features/reports/SalesMonitor';
import PCO007Reports from './features/reports/PCO007Reports';
import { AdministrationAccess, AdminModuleRedirect } from './features/admin/AdminNavigation';
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
      window.history.replaceState(window.history.state, document.title, cleanUrl);
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

const AdministrativeReportRoute = ({permissions,children}:{permissions:string[];children:React.ReactNode}) => {
  const {session} = usePosSession();
  return permissions.some(code => hasAdminCapability(session,code)) ? <>{children}</> : <Navigate to="/pos" replace />;
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
                <Route path="inventory-counts" element={
                  <AnyPermissionRoute permissions={['inventory.count.capture', 'inventory.count']}>
                    <PhysicalCountCapturePage />
                  </AnyPermissionRoute>
                } />
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
                  <AdministrativeReportRoute permissions={['reports.sales.read']}>
                    <SalesMonitor />
                  </AdministrativeReportRoute>
                } />
                <Route path="historical-reports" element={
                  <AdministrativeReportRoute permissions={['reports.ingredient_sales.read', 'reports.expenses.read']}>
                    <PCO007Reports />
                  </AdministrativeReportRoute>
                } />
                <Route path="administration" element={<AdministrationAccess><AdminHub /></AdministrationAccess>} />
                <Route path="administration/attendance" element={<AdministrativeReportRoute permissions={['branch.staff.read']}><AttendanceReport /></AdministrativeReportRoute>} />
                <Route path="administration/products" element={<AdminModuleRedirect module="products" />} />
                <Route path="administration/inventory" element={<AdminModuleRedirect module="inventory" />} />
                <Route path="administration/variations" element={<AdminModuleRedirect module="variations" />} />
                <Route path="administration/ingredient-extras" element={<AdminModuleRedirect module="ingredient-extras" />} />
                <Route path="administration/suppliers" element={<AdminModuleRedirect module="suppliers" />} />
                <Route path="administration/purchases" element={<AdminModuleRedirect module="purchases" />} />
                <Route path="administration/production" element={<AdminModuleRedirect module="production" />} />
                <Route path="administration/waste" element={<AdminModuleRedirect module="waste" />} />
                <Route path="administration/transfers" element={<AdminModuleRedirect module="transfers" />} />
                <Route path="administration/counts" element={<AdminModuleRedirect module="counts" />} />
              </Route>
            </Routes>
          </SessionGate>
        </PosSessionProvider>
      </ProtectedRoute>
    </BrowserRouter>
  );
};

export default App;
