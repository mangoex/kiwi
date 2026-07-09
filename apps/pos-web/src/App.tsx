import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import PosLayout from './components/PosLayout';
import PointOfSale from './features/pos/PointOfSale';
import DashboardOverview from './features/dashboard/DashboardOverview';
import PosInventory from './features/inventory/PosInventory';
import Customers from './features/customers/Customers';
import History from './features/history/History';
import Settings from './features/settings/Settings';

const App = () => {
  return (
    <BrowserRouter basename="/pos">
      <Routes>
        <Route path="/" element={<PosLayout />}>
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
