import { createContext, useContext, useState } from 'react';

type T = { id: number; type: 'success' | 'error' | 'info'; message: string };
const Ctx = createContext<{ push: (type: T['type'], message: string) => void }>({ push: () => {} });
export const useToast = () => useContext(Ctx);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<T[]>([]);
  const push = (type: T['type'], message: string) => {
    const id = Date.now();
    setToasts((s) => [...s, { id, type, message }]);
    setTimeout(() => setToasts((s) => s.filter((x) => x.id !== id)), 3500);
  };
  return (
    <Ctx.Provider value={{ push }}>
      {children}
      <div className="fixed bottom-4 right-4 space-y-2 z-50">
        {toasts.map((t) => (
          <div key={t.id} className={`px-4 py-2 rounded-lg text-white ${t.type === 'success' ? 'bg-emerald-600' : t.type === 'error' ? 'bg-rose-600' : 'bg-slate-700'}`}>
            {t.message}
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}
