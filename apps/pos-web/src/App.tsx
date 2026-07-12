import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import PosLayout from './components/PosLayout';
import PointOfSale from './features/pos/PointOfSale';
import DashboardOverview from './features/dashboard/DashboardOverview';
import PosInventory from './features/inventory/PosInventory';
import Customers from './features/customers/Customers';
import History from './features/history/History';
import Settings from './features/settings/Settings';
import AdminHub from './features/admin/AdminHub';
import { isAdministrativeUser, setPosBranchId } from './session';

const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const params = new URLSearchParams(window.location.search);
  const tokenParam = params.get('token');
  const userParam = params.get('user');
  if (tokenParam && userParam) {
    localStorage.setItem('auth_token', tokenParam);
    const userData = JSON.parse(decodeURIComponent(userParam));
    localStorage.setItem('user', JSON.stringify(userData));
    // Auto-configure branch for POS users from their role assignment
    if (userData.assigned_branch_id && !localStorage.getItem('pos_branch_id')) {
      setPosBranchId(userData.assigned_branch_id);
    }
    const newUrl = window.location.pathname;
    window.history.replaceState({}, document.title, newUrl);
  }

  const isDev = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' || (window.location.port !== '' && window.location.port !== '80' && window.location.port !== '443');
  const token = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');
  if (!token) {
    const loginUrl = isDev
      ? 'http://localhost:3002/admin/login'
      : '/admin/login';
    window.location.href = loginUrl;
    return null;
  }
  try {
    const user = JSON.parse(localStorage.getItem('user') || '{}');
    const userRoles: string[] = user.roles || [];
    const permissions: string[] = user.permissions || [];
    const canOperatePos = permissions.includes('pos.operate')
      || userRoles.includes('Cajero')
      || userRoles.includes('Caja');
    const isAdmin = userRoles.includes('Administrador corporativo') || user.is_superadmin || permissions.includes('admin.manage');

    if (!canOperatePos && !isAdmin) {
      const loginUrl = isDev
        ? 'http://localhost:3002/admin/login'
        : '/admin/login';
      window.location.href = loginUrl;
      return null;
    }
  } catch (e) {
    const loginUrl = isDev
      ? 'http://localhost:3002/admin/login'
      : '/admin/login';
    window.location.href = loginUrl;
    return null;
  }
  return <>{children}</>;
};

const AdminOnlyRoute = ({ children }: { children: React.ReactNode }) => (
  isAdministrativeUser() ? <>{children}</> : <Navigate to="/pos" replace />
);

const App = () => {
  return (
    <BrowserRouter basename="/pos">
      <Routes>
        <Route path="/" element={
          <ProtectedRoute>
            <PosLayout />
          </ProtectedRoute>
        }>
          {/* Default to PointOfSale for now as it's the main feature */}
          <Route index element={<Navigate to="/pos" replace />} />
          <Route path="pos" element={<PointOfSale />} />
          <Route path="dashboard" element={<DashboardOverview />} />
          <Route path="inventory" element={<PosInventory />} />
          <Route path="customers" element={<Customers />} />
          <Route path="history" element={<History />} />
          <Route path="settings" element={<Settings />} />
          <Route path="administration" element={<AdminOnlyRoute><AdminHub /></AdminOnlyRoute>} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
};

export default App;
