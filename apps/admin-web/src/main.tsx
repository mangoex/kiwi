import React from "react";
import { createRoot } from "react-dom/client";

function App() {
  return (
    <main>
      <h1>RestaurantOS Admin</h1>
      <p>Fase 0: plataforma y salud del sistema.</p>
    </main>
  );
}

createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

