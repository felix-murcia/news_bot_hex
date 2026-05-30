import { Activity, Zap, Clock, CheckCircle2, AlertCircle, TrendingUp, TrendingDown, Minus } from 'lucide-react'

type AccentColor = 'indigo' | 'cyan' | 'emerald' | 'amber' | 'violet' | 'rose'

interface PremiumKPICardProps {
  label: string
  value: string | number
  subValue?: string
  icon?: string
  color?: AccentColor
  trend?: 'up' | 'down' | 'neutral'
  trendValue?: string
  className?: string
}

const COLORS: Record<AccentColor, { accent: string; bg: string; glow: string }> = {
  indigo:  { accent: '#6366F1', bg: '#6366F10D', glow: '#6366F133' },
  cyan:    { accent: '#06B6D4', bg: '#06B6D40D', glow: '#06B6D433' },
  emerald: { accent: '#10B981', bg: '#10B9810D', glow: '#10B98133' },
  amber:   { accent: '#F59E0B', bg: '#F59E0B0D', glow: '#F59E0B33' },
  violet:  { accent: '#8B5CF6', bg: '#8B5CF60D', glow: '#8B5CF633' },
  rose:    { accent: '#F43F5E', bg: '#F43F5E0D', glow: '#F43F5E33' },
}

const ICON_MAP: Record<string, typeof Activity> = {
  Activity, Zap, Clock, CheckCircle2, AlertCircle, TrendingUp,
}

export function PremiumKPICard({
  label,
  value,
  subValue,
  icon = 'Activity',
  color = 'indigo',
  trend,
  trendValue,
  className = '',
}: PremiumKPICardProps) {
  const c = COLORS[color]
  const Icon = ICON_MAP[icon] || Activity
  const TrendIcon = trend === 'up' ? TrendingUp : trend === 'down' ? TrendingDown : Minus
  const trendColor = trend === 'up' ? '#10B981' : trend === 'down' ? '#F43F5E' : '#6B7280'

  return (
    <div
      className={`rounded-xl border p-5 cursor-default transition-all duration-300 group ${className}`}
      style={{
        background: '#13151B',
        borderColor: '#1F2330',
      }}
      onMouseEnter={e => {
        const el = e.currentTarget
        el.style.borderColor = `${c.accent}66`
        el.style.boxShadow = `0 0 20px ${c.glow}`
        el.style.background = '#1C1F27'
      }}
      onMouseLeave={e => {
        const el = e.currentTarget
        el.style.borderColor = '#1F2330'
        el.style.boxShadow = 'none'
        el.style.background = '#13151B'
      }}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <p className="text-xs font-medium tracking-wider uppercase mb-3"
            style={{ color: '#6B7280', fontFamily: 'Inter, sans-serif', letterSpacing: '0.08em' }}>
            {label}
          </p>
          <p className="text-3xl font-bold leading-none mb-1"
            style={{ color: '#F9FAFB', fontFamily: 'JetBrains Mono, monospace' }}>
            {value}
          </p>
          {subValue && (
            <p className="text-xs mt-1.5" style={{ color: '#4B5563', fontFamily: 'Inter, sans-serif' }}>
              {subValue}
            </p>
          )}
          {trendValue && (
            <div className="flex items-center gap-1.5 mt-3">
              <TrendIcon size={13} style={{ color: trendColor }} />
              <span className="text-xs font-medium" style={{ color: trendColor, fontFamily: 'JetBrains Mono, monospace' }}>
                {trendValue}
              </span>
            </div>
          )}
        </div>

        <div
          className="p-2.5 rounded-lg ml-3 flex-shrink-0"
          style={{ background: c.bg }}
        >
          <Icon size={20} style={{ color: c.accent }} />
        </div>
      </div>

      {/* Bottom accent bar */}
      <div className="mt-4 h-0.5 rounded-full overflow-hidden" style={{ background: '#1F2330' }}>
        <div
          className="h-full rounded-full"
          style={{
            background: `linear-gradient(90deg, ${c.accent}, ${c.accent}44)`,
            width: '60%',
            boxShadow: `0 0 8px ${c.accent}66`,
          }}
        />
      </div>
    </div>
  )
}
