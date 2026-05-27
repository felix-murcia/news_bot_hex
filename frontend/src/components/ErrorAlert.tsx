import { AlertCircle, X } from "lucide-react";

interface ErrorAlertProps {
  message: string;
  details?: string;
  errorCode?: string;
  onDismiss?: () => void;
  variant?: "error" | "warning";
}

export function ErrorAlert({
  message,
  details,
  errorCode,
  onDismiss,
  variant = "error",
}: ErrorAlertProps) {
  const bgColor = variant === "error" ? "bg-red-950/40" : "bg-amber-950/40";
  const borderColor = variant === "error" ? "border-red-800" : "border-amber-800";
  const textColor = variant === "error" ? "text-red-300" : "text-amber-300";
  const iconColor = variant === "error" ? "text-red-500" : "text-amber-500";

  return (
    <div className={`${bgColor} border ${borderColor} rounded-lg p-4 space-y-2`}>
      <div className="flex items-start gap-3">
        <AlertCircle className={`w-5 h-5 ${iconColor} flex-shrink-0 mt-0.5`} />
        <div className="flex-1 min-w-0">
          <p className={`font-semibold text-sm ${textColor}`}>{message}</p>
          {details && (
            <p className={`text-xs ${textColor} opacity-80 mt-1`}>{details}</p>
          )}
          {errorCode && (
            <p className={`text-xs ${textColor} opacity-60 mt-2 font-mono`}>
              Código: {errorCode}
            </p>
          )}
        </div>
        {onDismiss && (
          <button
            onClick={onDismiss}
            className={`${textColor} hover:opacity-70 transition-opacity flex-shrink-0 mt-0.5`}
            aria-label="Cerrar error"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>
    </div>
  );
}
