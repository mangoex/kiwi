import React from "react";
import { createRoot } from "react-dom/client";

function App() {
  return (
    <main>
      <h1>RestaurantOS KDS</h1>
      <p>Preparado para tareas por estacion.</p>
    </main>
  );
}

createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

