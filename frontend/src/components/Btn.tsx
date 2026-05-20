import { ButtonHTMLAttributes, ReactNode } from "react";

interface BtnProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  loading?: boolean;
  variant?: "primary" | "ghost" | "danger";
  children: ReactNode;
}

export function Btn({ loading, variant = "primary", children, className = "", ...rest }: BtnProps) {
  const base =
    "inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed";

  const variants = {
    primary: "bg-accent hover:bg-accent-hover text-white",
    ghost: "bg-surface-hover hover:bg-surface-border text-gray-200",
    danger: "bg-red-700 hover:bg-red-600 text-white",
  };

  return (
    <button
      {...rest}
      disabled={loading || rest.disabled}
      className={`${base} ${variants[variant]} ${className}`}
    >
      {loading && (
        <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
      )}
      {children}
    </button>
  );
}
