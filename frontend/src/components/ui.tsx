import type { ReactNode } from 'react';

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 text-ink/70">
      <span className="inline-block h-5 w-5 animate-spin rounded-full border-2 border-amber border-t-transparent" />
      {label && <span>{label}</span>}
    </div>
  );
}

export function ErrorBox({ message }: { message: string }) {
  return (
    <div className="rounded-md border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800">
      {message}
    </div>
  );
}

export function Button({
  children,
  onClick,
  type = 'button',
  variant = 'primary',
  disabled,
  className = '',
}: {
  children: ReactNode;
  onClick?: () => void;
  type?: 'button' | 'submit';
  variant?: 'primary' | 'secondary' | 'ghost';
  disabled?: boolean;
  className?: string;
}) {
  const base =
    'inline-flex items-center justify-center rounded-md px-4 py-2 text-sm font-semibold transition disabled:opacity-50 disabled:cursor-not-allowed';
  const variants: Record<string, string> = {
    primary: 'bg-amber text-white hover:bg-amber-dark',
    secondary: 'border border-ink/20 bg-white text-ink hover:bg-neutralbg',
    ghost: 'text-ink/70 hover:text-ink',
  };
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`${base} ${variants[variant]} ${className}`}
    >
      {children}
    </button>
  );
}

export function Card({
  children,
  className = '',
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-lg border border-ink/10 bg-white p-5 shadow-sm ${className}`}
    >
      {children}
    </div>
  );
}

export function SectionTitle({
  children,
  step,
}: {
  children: ReactNode;
  step?: number;
}) {
  return (
    <div className="mb-3 flex items-center gap-2">
      {step != null && (
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-ink text-xs font-bold text-white">
          {step}
        </span>
      )}
      <h2 className="text-lg font-semibold text-ink">{children}</h2>
    </div>
  );
}

export function Label({ children }: { children: ReactNode }) {
  return (
    <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-ink/60">
      {children}
    </label>
  );
}

export function TextInput(
  props: React.InputHTMLAttributes<HTMLInputElement>,
) {
  return (
    <input
      {...props}
      className={`w-full rounded-md border border-ink/20 px-3 py-2 text-sm text-ink focus:border-amber focus:outline-none focus:ring-1 focus:ring-amber ${props.className ?? ''}`}
    />
  );
}

export function Select(
  props: React.SelectHTMLAttributes<HTMLSelectElement>,
) {
  return (
    <select
      {...props}
      className={`w-full rounded-md border border-ink/20 bg-white px-3 py-2 text-sm text-ink focus:border-amber focus:outline-none focus:ring-1 focus:ring-amber ${props.className ?? ''}`}
    />
  );
}
