import React from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "./App.css";
import App from "./App";

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    void navigator.serviceWorker.register('/pos/offline-shell-sw.js', { scope: '/pos/' }).then(async (registration) => {
      const urls = Array.from(document.querySelectorAll<HTMLScriptElement | HTMLLinkElement>('script[src], link[href]'))
        .map((element) => element instanceof HTMLScriptElement ? element.src : element.href)
        .filter((url) => new URL(url).pathname.startsWith('/pos/assets/'));
      (registration.active || (await navigator.serviceWorker.ready).active)?.postMessage({ type: 'PRECACHE_ASSETS', urls });
    });
  });
}

const queryClient = new QueryClient();

createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>
);
