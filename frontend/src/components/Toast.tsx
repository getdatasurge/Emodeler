import { useEffect, useState } from 'react';

export type ToastKind = 'success' | 'warning' | 'error' | 'info';

export interface ToastSpec {
  id: number;
  kind: ToastKind;
  text: string;
  ttlMs?: number;
}

let _seq = 0;
const _listeners: Array<(t: ToastSpec) => void> = [];

export function pushToast(kind: ToastKind, text: string, ttlMs = 5000) {
  const spec: ToastSpec = { id: ++_seq, kind, text, ttlMs };
  for (const l of _listeners) l(spec);
}

const styles: Record<ToastKind, string> = {
  success: 'bg-green-50 text-green-900 border-green-200',
  warning: 'bg-amber-50 text-amber-900 border-amber-300',
  error: 'bg-red-50 text-red-900 border-red-300',
  info: 'bg-ink/5 text-ink border-ink/10',
};

export function ToastStack() {
  const [toasts, setToasts] = useState<ToastSpec[]>([]);

  useEffect(() => {
    function onPush(t: ToastSpec) {
      setToasts((prev) => [...prev, t]);
      if (t.ttlMs && t.ttlMs > 0) {
        setTimeout(
          () => setToasts((prev) => prev.filter((x) => x.id !== t.id)),
          t.ttlMs,
        );
      }
    }
    _listeners.push(onPush);
    return () => {
      const i = _listeners.indexOf(onPush);
      if (i >= 0) _listeners.splice(i, 1);
    };
  }, []);

  if (toasts.length === 0) return null;
  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-[100] flex w-full max-w-sm flex-col gap-2">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`pointer-events-auto rounded-md border px-3 py-2 text-sm shadow-lg ${styles[t.kind]}`}
        >
          <div className="flex items-start gap-2">
            <span className="mt-0.5 text-xs font-semibold uppercase tracking-wide">
              {t.kind}
            </span>
            <span className="flex-1">{t.text}</span>
            <button
              onClick={() =>
                setToasts((prev) => prev.filter((x) => x.id !== t.id))
              }
              className="text-ink/40 hover:text-ink"
              aria-label="Dismiss"
            >
              ×
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
