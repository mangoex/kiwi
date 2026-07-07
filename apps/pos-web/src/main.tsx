import React from "react";
import { createRoot } from "react-dom/client";

function App() {
  return (
    <main>
      <h1>RestaurantOS POS</h1>
      <p>Preparado para el primer vertical slice offline.</p>
    </main>
  );
}

createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

