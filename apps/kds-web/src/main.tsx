import React from "react";
import { createRoot } from "react-dom/client";
import KitchenBoard from "./features/orders/KitchenBoard";

createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <KitchenBoard />
  </React.StrictMode>
);
