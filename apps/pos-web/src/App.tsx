import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import PosLayout from './components/PosLayout';
import PointOfSale from './features/pos/PointOfSale';
import DashboardOverview from './features/dashboard/DashboardOverview';
import PosInventory from './features/inventory/PosInventory';
import Customers from './features/customers/Customers';
import History from './features/history/History';
import Settings from './features/settings/Settings';

const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const token = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');
  if (!token) {
    window.location.href = '/admin/login';
    return null;
  }
  try {
    const user = JSON.parse(localStorage.getItem('user') || '{}');
    const userRoles = user.roles || [];
    const isCaja = userRoles.includes('Caja');
    const isAdmin = userRoles.includes('Administrador corporativo') || user.is_superadmin;

    if (!isCaja && !isAdmin) {
      window.location.href = '/admin/login';
      return null;
    }
  } catch (e) {
    window.location.href = '/admin/login';
    return null;
  }
  return <>{children}</>;
};

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
        </Route>
      </Routes>
    </BrowserRouter>
  );
};

export default App;
