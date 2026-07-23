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
import SuppliersList from './features/purchasing/SuppliersList';
import PurchasesList from './features/purchasing/PurchasesList';
import ProductionList from './features/production/ProductionList';
import WasteList from './features/inventory/WasteList';
import TransferList from './features/inventory/TransferList';
import PhysicalCountList from './features/inventory/PhysicalCountList';
import LegacyImportReview from './features/imports/LegacyImportReview';
import VariationNotes from './features/catalog/VariationNotes';
import IngredientExtras from './features/catalog/IngredientExtras';
import DriversList from './features/delivery/DriversList';

const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const token = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  try {
    const user = JSON.parse(localStorage.getItem('user') || '{}');
    const userRoles: string[] = user.roles || [];
    const permissions: string[] = user.permissions || [];
    const isPosOperator = permissions.includes('pos.operate')
      || userRoles.includes('Cajero')
      || userRoles.includes('Caja');
    const isAdmin = user.is_superadmin
      || userRoles.includes('Administrador corporativo')
      || permissions.includes('admin.manage')
      || permissions.includes('dashboard.read')
      || permissions.includes('inventory.transfer.receive');

    if (isPosOperator && !isAdmin) {
      const token = localStorage.getItem('auth_token');
      const isDev = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' || (window.location.port !== '' && window.location.port !== '80' && window.location.port !== '443');
      const targetUrl = isDev 
        ? `http://localhost:3001/pos/pos?token=${token}&user=${encodeURIComponent(JSON.stringify(user))}`
        : '/pos/pos';
      window.location.href = targetUrl;
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
          <Route path="variations" element={<VariationNotes />} />
          <Route path="ingredient-extras" element={<IngredientExtras />} />
          <Route path="categories" element={<CategoriesList />} />
          <Route path="branches" element={<BranchesList />} />
          <Route path="drivers" element={<DriversList />} />
          <Route path="warehouses" element={<WarehousesList />} />
          <Route path="inventory/units" element={<UnitsList />} />
          <Route path="inventory/items" element={<ItemsList />} />
          <Route path="suppliers" element={<SuppliersList />} />
          <Route path="purchases" element={<PurchasesList />} />
          <Route path="production" element={<ProductionList />} />
          <Route path="inventory/waste" element={<WasteList />} />
          <Route path="inventory/transfers" element={<TransferList />} />
          <Route path="inventory/counts" element={<PhysicalCountList />} />
          <Route path="imports" element={<LegacyImportReview />} />
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
