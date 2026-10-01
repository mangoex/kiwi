import { createContext, useCallback, useContext, useState, type ReactNode } from 'react';
import { QueryClientProvider } from '@tanstack/react-query';
import { createAdminQueryClient } from '../lib/sessionRecovery';

const ResetSessionQueries = createContext<() => void>(() => {});

export const useResetSessionQueries = () => useContext(ResetSessionQueries);

export function AdminQueryProvider({ children }: { children: ReactNode }) {
  const [client, setClient] = useState(createAdminQueryClient);
  const reset = useCallback(() => {
    void client.cancelQueries();
    client.clear();
    setClient(createAdminQueryClient());
  }, [client]);
  return (
    <ResetSessionQueries.Provider value={reset}>
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    </ResetSessionQueries.Provider>
  );
}
