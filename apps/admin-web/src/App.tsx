import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Overview from './features/dashboard/Overview';
import Login from './features/auth/Login';
import AdminLayout from './components/AdminLayout';
import CategoriesList from './features/catalog/CategoriesList';
import BranchesList from './features/branches/BranchesList';
import WarehousesList from './features/branches/WarehousesList';
import UnitsList from './features/inventory/UnitsList';
import ItemsList from './features/inventory/ItemsList';
import UsersList from './features/users/UsersList';
import RolesList from './features/users/RolesList';
import CustomersList from './features/customers/CustomersList';
import SuppliersList from './features/purchasing/SuppliersList';
import PurchasesList from './features/purchasing/PurchasesList';
import PresentationsList from './features/purchasing/PresentationsList';
import ProductionList from './features/production/ProductionList';
import WasteList from './features/inventory/WasteList';
import TransferList from './features/inventory/TransferList';
import PhysicalCountList from './features/inventory/PhysicalCountList';
import LegacyImportReview from './features/imports/LegacyImportReview';
import DriversList from './features/delivery/DriversList';
import CashConceptsManager from './features/cash/CashConceptsManager';
import RecipesWorkspace from './features/recipes/RecipesWorkspace';
import CorporateReconciliationDashboard from './features/reports/CorporateReconciliationDashboard';
import IntegrationsHub from './features/integrations/IntegrationsHub';
import CategoryPriorities from './features/admin-catalog/CategoryPriorities';
import BulkRecipeWorkspace from './features/admin-catalog/BulkRecipeWorkspace';
import StockThresholds from './features/admin-catalog/StockThresholds';
import { CatalogHub } from './features/hubs/CatalogHub';
import { InventoryHub } from './features/hubs/InventoryHub';
import { PurchasingHub } from './features/hubs/PurchasingHub';
import { BranchesHub } from './features/hubs/BranchesHub';
import { ReportsHub } from './features/hubs/ReportsHub';
import { AdminAccessHub } from './features/hubs/AdminAccessHub';
import { AdminSessionProvider } from './lib/adminSession';
import { CatalogAdministration } from './features/catalog/CatalogAdministration';
import SharedModifierWorkspace from './features/catalog/SharedModifierWorkspace';
import { AdminSessionBoundary } from './components/AdminSessionBoundary';

const ProtectedRoute = ({ children }: { children: React.ReactNode }) => <AdminSessionProvider>{children}</AdminSessionProvider>;

export const App = () => {
  React.useEffect(() => {
    document.documentElement.removeAttribute('data-admin-retro');
    document.documentElement.dataset.adminModern = 'true';
    return () => document.documentElement.removeAttribute('data-admin-modern');
  }, []);

  return (
    <BrowserRouter basename="/admin">
      <AdminSessionBoundary />
      <Routes>
        <Route path="/login" element={<Login />} />
        
        <Route path="/" element={
          <ProtectedRoute>
            <AdminLayout />
          </ProtectedRoute>
        }>
          <Route index element={<Overview />} />

          {/* Category Hubs (POS Style Grid Views) */}
          <Route path="catalog" element={<CatalogHub />} />
          <Route path="inventory" element={<InventoryHub />} />
          <Route path="purchasing" element={<PurchasingHub />} />
          <Route path="branches-hub" element={<BranchesHub />} />
          <Route path="reports-hub" element={<ReportsHub />} />
          <Route path="admin-access-hub" element={<AdminAccessHub />} />

          {/* Subroutes: Catálogo y Menú */}
          <Route path="products" element={<CatalogAdministration kind="products" />} />
          <Route path="recipes" element={<RecipesWorkspace />} />
          <Route path="categories" element={<CategoriesList />} />
          <Route path="variations" element={<CatalogAdministration kind="variations" />} />
          <Route path="modifiers" element={<SharedModifierWorkspace />} />
          <Route path="ingredient-extras" element={<CatalogAdministration kind="ingredient-extras" />} />
          <Route path="category-options" element={<Navigate to="/categories" replace />} />
          <Route path="category-priorities" element={<CategoryPriorities />} />
          <Route path="recipes/bulk" element={<BulkRecipeWorkspace />} />

          {/* Subroutes: Inventario y Almacén */}
          <Route path="inventory/items" element={<ItemsList />} />
          <Route path="warehouses" element={<WarehousesList />} />
          <Route path="production" element={<ProductionList />} />
          <Route path="inventory/waste" element={<WasteList />} />
          <Route path="inventory/transfers" element={<TransferList />} />
          <Route path="inventory/counts" element={<PhysicalCountList />} />
          <Route path="inventory/units" element={<UnitsList />} />
          <Route path="inventory/thresholds" element={<StockThresholds />} />

          {/* Subroutes: Compras y Proveedores */}
          <Route path="purchases" element={<PurchasesList />} />
          <Route path="suppliers" element={<SuppliersList />} />
          <Route path="purchase-presentations" element={<PresentationsList />} />

          {/* Subroutes: Sucursales y Canales */}
          <Route path="branches" element={<BranchesList />} />
          <Route path="drivers" element={<DriversList />} />
          <Route path="integrations" element={<IntegrationsHub />} />
          <Route path="cash-concepts" element={<CashConceptsManager />} />

          {/* Subroutes: Ventas y Reportes */}
          <Route path="reports" element={<CorporateReconciliationDashboard />} />
          <Route path="analytics" element={<div style={{ padding: 24 }}><h2>Analytics</h2><p>Panel de Métricas en vivo...</p></div>} />

          {/* Subroutes: Administración y Accesos */}
          <Route path="users" element={<UsersList />} />
          <Route path="roles" element={<RolesList />} />
          <Route path="customers" element={<CustomersList />} />
          <Route path="imports" element={<LegacyImportReview />} />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
};

export default App;
