import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Overview from './features/dashboard/Overview';
import Login from './features/auth/Login';
import AdminLayout from './components/AdminLayout';
import ProductsList from './features/catalog/ProductsList';
import CategoriesList from './features/catalog/CategoriesList';
import BranchesList from './features/branches/BranchesList';
import WarehousesList from './features/branches/WarehousesList';
import UnitsList from './features/inventory/UnitsList';
import ItemsList from './features/inventory/ItemsList';
import UsersList from './features/users/UsersList';
import RolesList from './features/users/RolesList';

const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const token = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  try {
    const user = JSON.parse(localStorage.getItem('user') || '{}');
    const userRoles = user.roles || [];
    const isCaja = userRoles.includes('Caja');
    const isAdmin = userRoles.includes('Administrador corporativo') || user.is_superadmin;

    if (isCaja && !isAdmin) {
      window.location.href = '/pos';
      return null;
    }
    if (!isAdmin) {
      return <Navigate to="/login" replace />;
    }
  } catch (e) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
};

export const App = () => {
  return (
    <BrowserRouter basename="/admin">
      <Routes>
        <Route path="/login" element={<Login />} />
        
        <Route path="/" element={
          <ProtectedRoute>
            <AdminLayout />
          </ProtectedRoute>
        }>
          <Route index element={<Overview />} />
          <Route path="products" element={<ProductsList />} />
          <Route path="categories" element={<CategoriesList />} />
          <Route path="branches" element={<BranchesList />} />
          <Route path="warehouses" element={<WarehousesList />} />
          <Route path="inventory/units" element={<UnitsList />} />
          <Route path="inventory/items" element={<ItemsList />} />
          <Route path="users" element={<UsersList />} />
          <Route path="roles" element={<RolesList />} />
          <Route path="analytics" element={<div style={{ padding: 24 }}><h2>Analytics</h2><p>Building...</p></div>} />
          <Route path="reports" element={<div style={{ padding: 24 }}><h2>Reports</h2><p>Building...</p></div>} />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
};

export default App;
