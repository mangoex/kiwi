import React from "react";
import { createRoot } from "react-dom/client";
import Overview from "./features/dashboard/Overview";

createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <Overview />
  </React.StrictMode>
);
