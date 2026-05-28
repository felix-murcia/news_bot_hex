import { Activity, Zap, Clock, CheckCircle2, AlertCircle, TrendingUp } from 'lucide-react'

interface KPICardProps {
  label: string
  value: string | number
  icon?: string
  color?: 'blue' | 'green' | 'yellow' | 'purple' | 'red'
  trend?: 'up' | 'down' | 'neutral'
  trendValue?: string
}

const iconMap: Record<string, typeof Activity> = {
  Zap,
  CheckCircle2,
  Clock,
  Activity,
  AlertCircle,
  TrendingUp,
}

const colorStyles: Record<string, { bg: string; icon: string; accent: string }> = {
  blue: { bg: '#1a3a52', icon: '#3B82F6', accent: '#3B82F6' },
  green: { bg: '#1a3a2a', icon: '#10B981', accent: '#10B981' },
  yellow: { bg: '#3a3a1a', icon: '#F59E0B', accent: '#F59E0B' },
  purple: { bg: '#2a1a3a', icon: '#8B5CF6', accent: '#8B5CF6' },
  red: { bg: '#3a1a1a', icon: '#EF4444', accent: '#EF4444' },
}

export function KPICard({
  label,
  value,
  icon = 'Activity',
  color = 'blue',
  trendValue,
}: KPICardProps) {
  const IconComponent = iconMap[icon] || Activity
  const colors = colorStyles[color]

  return (
    <div
      className="rounded-lg p-4 border transition-all duration-200 hover:shadow-lg hover:-translate-y-0.5 cursor-default"
      style={{
        backgroundColor: '#1A1C22',
        borderColor: '#2A2D35',
      }}
    >
      <div className="flex items-start justify-between mb-4">
        <div>
          <p style={{ color: '#9CA3AF' }} className="text-xs font-medium tracking-wider uppercase">
            {label}
          </p>
          <p
            className="text-2xl font-bold mt-2"
            style={{ color: '#E5E7EB', fontFamily: 'Fira Code' }}
          >
            {value}
          </p>
          {trendValue && (
            <div className="flex items-center gap-1 mt-2">
              <TrendingUp size={14} style={{ color: colors.accent }} />
              <span style={{ color: colors.accent }} className="text-xs font-medium">
                {trendValue}
              </span>
            </div>
          )}
        </div>
        <div
          className="p-2 rounded-lg"
          style={{ backgroundColor: colors.bg }}
        >
          <IconComponent size={24} style={{ color: colors.icon }} />
        </div>
      </div>
    </div>
  )
}
