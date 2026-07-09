import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Overview from './features/dashboard/Overview';
import Login from './features/auth/Login';
import AdminLayout from './components/AdminLayout';

const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const token = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');
  if (!token) {
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
          <Route path="products" element={<div style={{ padding: 24 }}><h2>Products</h2><p>Building...</p></div>} />
          <Route path="branches" element={<div style={{ padding: 24 }}><h2>Branches</h2><p>Building...</p></div>} />
          <Route path="users" element={<div style={{ padding: 24 }}><h2>Users</h2><p>Building...</p></div>} />
          <Route path="analytics" element={<div style={{ padding: 24 }}><h2>Analytics</h2><p>Building...</p></div>} />
          <Route path="reports" element={<div style={{ padding: 24 }}><h2>Reports</h2><p>Building...</p></div>} />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
};

export default App;
