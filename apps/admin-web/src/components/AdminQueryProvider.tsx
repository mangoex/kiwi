import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from 'react';
import { QueryClientProvider } from '@tanstack/react-query';
import { createAdminQueryClient } from '../lib/sessionRecovery';

const ResetSessionQueries = createContext<() => void>(() => {});

export const useResetSessionQueries = () => useContext(ResetSessionQueries);

export function AdminQueryProvider({ children }: { children: ReactNode }) {
  const [client, setClient] = useState(createAdminQueryClient);
  const currentClient = useRef(client);
  const reset = useCallback(() => {
    void currentClient.current.cancelQueries();
    currentClient.current.clear();
    const nextClient = createAdminQueryClient();
    currentClient.current = nextClient;
    setClient(nextClient);
  }, []);
  return (
    <ResetSessionQueries.Provider value={reset}>
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    </ResetSessionQueries.Provider>
  );
}
