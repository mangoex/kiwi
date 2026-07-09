import React from "react";
import { createRoot } from "react-dom/client";
import "./App.css";
import POSDashboard from "./features/dashboard/POSDashboard";

createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <POSDashboard />
  </React.StrictMode>
);

