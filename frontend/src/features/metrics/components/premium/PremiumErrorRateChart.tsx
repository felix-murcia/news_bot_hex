import { useState } from 'react'

interface HealthData {
  error_rate: number
  total_executions: number
  failed_executions: number
}

interface PremiumErrorRateChartProps {
  health: HealthData
  className?: string
}

const CX = 120, CY = 120, R_OUTER = 88, R_INNER = 62

function donutSegment(startDeg: number, endDeg: number): string {
  const toRad = (d: number) => ((d - 90) * Math.PI) / 180
  const ox1 = CX + R_OUTER * Math.cos(toRad(startDeg))
  const oy1 = CY + R_OUTER * Math.sin(toRad(startDeg))
  const ox2 = CX + R_OUTER * Math.cos(toRad(endDeg))
  const oy2 = CY + R_OUTER * Math.sin(toRad(endDeg))
  const ix1 = CX + R_INNER * Math.cos(toRad(endDeg))
  const iy1 = CY + R_INNER * Math.sin(toRad(endDeg))
  const ix2 = CX + R_INNER * Math.cos(toRad(startDeg))
  const iy2 = CY + R_INNER * Math.sin(toRad(startDeg))
  const large = endDeg - startDeg > 180 ? 1 : 0
  return `M ${ox1} ${oy1} A ${R_OUTER} ${R_OUTER} 0 ${large} 1 ${ox2} ${oy2} L ${ix1} ${iy1} A ${R_INNER} ${R_INNER} 0 ${large} 0 ${ix2} ${iy2} Z`
}

export function PremiumErrorRateChart({ health, className = '' }: PremiumErrorRateChartProps) {
  const [hovered, setHovered] = useState<'success' | 'error' | null>(null)

  const successRate = (1 - health.error_rate) * 100
  const errorRate = health.error_rate * 100
  const successDeg = (successRate / 100) * 360
  const successCount = health.total_executions - health.failed_executions

  const segments = [
    {
      id: 'success' as const,
      label: 'Successful',
      value: successRate,
      count: successCount,
      color: '#10B981',
      start: 0,
      end: successDeg,
    },
    {
      id: 'error' as const,
      label: 'Failed',
      value: errorRate,
      count: health.failed_executions,
      color: '#F43F5E',
      start: successDeg,
      end: 360,
    },
  ]

  return (
    <div
      className={`rounded-xl border p-6 ${className}`}
      style={{ background: '#13151B', borderColor: '#1F2330' }}
    >
      <h3 className="text-sm font-semibold tracking-wide uppercase mb-5" style={{ color: '#9CA3AF', fontFamily: 'Inter, sans-serif', letterSpacing: '0.08em' }}>
        Execution Status
      </h3>

      <div className="flex flex-col md:flex-row items-center gap-8">
        {/* Donut */}
        <svg width="240" height="240" viewBox="0 0 240 240" style={{ flexShrink: 0 }}>
          <defs>
            <filter id="perc-glow-green">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
            <filter id="perc-glow-red">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
          </defs>

          {/* Track ring */}
          <circle cx={CX} cy={CY} r={(R_OUTER + R_INNER) / 2} fill="none"
            stroke="#1F2330" strokeWidth={R_OUTER - R_INNER} />

          {segments.map(seg => {
            const isHov = hovered === seg.id
            const gap = 2
            return (
              <path
                key={seg.id}
                d={donutSegment(seg.start + gap, seg.end - gap)}
                fill={seg.color}
                opacity={hovered && !isHov ? 0.35 : isHov ? 1 : 0.85}
                style={{
                  cursor: 'pointer',
                  transition: 'opacity 0.25s ease',
                  filter: isHov ? `drop-shadow(0 0 10px ${seg.color}88)` : 'none',
                }}
                onMouseEnter={() => setHovered(seg.id)}
                onMouseLeave={() => setHovered(null)}
              />
            )
          })}

          {/* Center */}
          <text x={CX} y={CY - 10} textAnchor="middle" fill="#E5E7EB" fontSize="26" fontFamily="JetBrains Mono, monospace" fontWeight="700">
            {successRate.toFixed(1)}%
          </text>
          <text x={CX} y={CY + 10} textAnchor="middle" fill="#4B5563" fontSize="11" fontFamily="Inter, sans-serif">
            success rate
          </text>
          <text x={CX} y={CY + 28} textAnchor="middle" fill="#374151" fontSize="10" fontFamily="JetBrains Mono, monospace">
            {health.total_executions} total
          </text>
        </svg>

        {/* Legend */}
        <div className="flex-1 space-y-3 w-full">
          {segments.map(seg => {
            const isHov = hovered === seg.id
            return (
              <div
                key={seg.id}
                className="rounded-lg p-4 border cursor-pointer"
                style={{
                  background: isHov ? `${seg.color}0D` : 'transparent',
                  borderColor: isHov ? `${seg.color}66` : '#1F2330',
                  transition: 'all 0.25s ease',
                  boxShadow: isHov ? `0 0 16px ${seg.color}22` : 'none',
                }}
                onMouseEnter={() => setHovered(seg.id)}
                onMouseLeave={() => setHovered(null)}
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2.5">
                    <div className="w-2.5 h-2.5 rounded-full" style={{ background: seg.color, boxShadow: `0 0 6px ${seg.color}` }} />
                    <span className="text-sm font-medium" style={{ color: '#D1D5DB', fontFamily: 'Inter, sans-serif' }}>{seg.label}</span>
                  </div>
                  <span className="text-sm font-bold" style={{ color: seg.color, fontFamily: 'JetBrains Mono, monospace' }}>
                    {seg.value.toFixed(1)}%
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <div className="flex-1 h-1.5 rounded-full mr-3" style={{ background: '#1F2330' }}>
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${seg.value}%`,
                        background: seg.color,
                        boxShadow: `0 0 6px ${seg.color}66`,
                        transition: 'width 0.8s cubic-bezier(0.4,0,0.2,1)',
                      }}
                    />
                  </div>
                  <span className="text-xs" style={{ color: '#6B7280', fontFamily: 'JetBrains Mono, monospace', whiteSpace: 'nowrap' }}>
                    {seg.count} exec
                  </span>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
