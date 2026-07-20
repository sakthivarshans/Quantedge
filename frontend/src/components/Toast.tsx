import { createContext, useCallback, useContext, useRef, useState } from "react";
import type { ReactNode } from "react";

export type ToastVariant = "success" | "error" | "info";

interface Toast {
  id: number;
  variant: ToastVariant;
  title: string;
  description?: string;
}

interface ToastContextValue {
  push: (toast: Omit<Toast, "id">) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const VARIANT_STYLES: Record<ToastVariant, { border: string; icon: string; iconColor: string }> = {
  success: { border: "border-green-500/30", icon: "✓", iconColor: "text-green-400" },
  error: { border: "border-red-500/30", icon: "✕", iconColor: "text-red-400" },
  info: { border: "border-blue-500/30", icon: "ℹ", iconColor: "text-blue-400" },
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const idCounter = useRef(0);

  const push = useCallback((toast: Omit<Toast, "id">) => {
    const id = ++idCounter.current;
    setToasts((prev) => [...prev, { ...toast, id }]);
    window.setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 5000);
  }, []);

  const dismiss = (id: number) => setToasts((prev) => prev.filter((t) => t.id !== id));

  return (
    <ToastContext.Provider value={{ push }}>
      {children}
      <div className="fixed bottom-5 right-5 z-50 flex flex-col gap-2 w-80 pointer-events-none">
        {toasts.map((t) => {
          const style = VARIANT_STYLES[t.variant];
          return (
            <div
              key={t.id}
              onClick={() => dismiss(t.id)}
              className={`pointer-events-auto cursor-pointer bg-[#12151f]/95 backdrop-blur border ${style.border} rounded-lg px-4 py-3 shadow-2xl shadow-black/40 animate-toast-in`}
            >
              <div className="flex items-start gap-2.5">
                <span className={`${style.iconColor} font-bold text-sm mt-0.5`}>{style.icon}</span>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-white">{t.title}</div>
                  {t.description && <div className="text-xs text-gray-400 mt-0.5">{t.description}</div>}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
}
