export function LoadingSpinner() {
  return (
    <div className="flex items-center justify-center py-20">
      <div className="relative w-16 h-16">
        <div
          className="absolute inset-0 rounded-full border-4 border-transparent border-t-blue-500 border-r-blue-500 animate-spin"
          style={{
            borderTopColor: '#3B82F6',
            borderRightColor: '#3B82F6',
            animation: 'spin 1s linear infinite',
          }}
        />
        <div
          className="absolute inset-2 rounded-full border-4 border-transparent border-b-purple-500 animate-spin"
          style={{
            borderBottomColor: '#8B5CF6',
            animation: 'spin 1.5s linear infinite reverse',
          }}
        />
      </div>
      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  )
}
