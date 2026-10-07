import React from "react";
import { createRoot } from "react-dom/client";
import "./App.css";
import "./kiwi-modern-admin.css";
import App from "./App";
import { AdminQueryProvider } from './components/AdminQueryProvider';
import "@restaurantos/ui/styles/neutral.css";
import { initializeWorkspaceNavigation } from '@restaurantos/ui';

initializeWorkspaceNavigation();

createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <AdminQueryProvider>
      <App />
    </AdminQueryProvider>
  </React.StrictMode>
);
