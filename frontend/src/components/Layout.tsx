import { ReactNode } from "react";

export function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-surface text-gray-100 font-sans">
      <header className="border-b border-surface-border px-6 py-4 flex items-center gap-3">
        <span className="text-accent text-xl font-bold">⬡</span>
        <h1 className="text-lg font-semibold tracking-wide">News Bot Hex</h1>
        <span className="ml-auto text-xs text-gray-500">dashboard</span>
      </header>
      <main className="max-w-5xl mx-auto px-4 py-8">{children}</main>
    </div>
  );
}
