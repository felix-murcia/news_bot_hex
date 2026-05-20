import { ReactNode } from "react";

interface StepCardProps {
  step: number;
  title: string;
  description?: string;
  children: ReactNode;
}

export function StepCard({ step, title, description, children }: StepCardProps) {
  return (
    <div className="bg-surface-card border border-surface-border rounded-xl p-5 mb-4">
      <div className="flex items-start gap-3 mb-4">
        <span className="flex-shrink-0 w-7 h-7 rounded-full bg-accent/20 text-accent text-xs font-bold flex items-center justify-center">
          {step}
        </span>
        <div>
          <h3 className="font-semibold text-sm text-white">{title}</h3>
          {description && (
            <p className="text-xs text-gray-400 mt-0.5">{description}</p>
          )}
        </div>
      </div>
      <div>{children}</div>
    </div>
  );
}
