import { useState, useEffect } from 'react'
import { smoothLinePath, smoothAreaPath, mapToCanvas } from './chartUtils'
import { formatDurationMs } from '../../utils/formatDuration'

interface PercentilePoint {
  timestamp: string
  p50: number
  p95: number
  p99: number
}

interface PremiumPercentileChartProps {
  pipelineType: 'NEWS' | 'AUDIO' | 'VIDEO'
  days: number
  className?: string
}

const SERIES = [
  { key: 'p50' as const, label: 'P50', color: '#10B981', gradId: 'ppc-g50' },
  { key: 'p95' as const, label: 'P95', color: '#F59E0B', gradId: 'ppc-g95' },
  { key: 'p99' as const, label: 'P99', color: '#8B5CF6', gradId: 'ppc-g99' },
]

const CL = 64, CR = 792, CT = 24, CB = 272
const VW = 856, VH = 320

function SkeletonChart() {
  return (
    <div className="animate-pulse space-y-3 pt-2">
      <div className="h-3 w-32 rounded" style={{ background: '#1F2330' }} />
      <div className="h-48 w-full rounded-lg" style={{ background: '#1F2330' }} />
    </div>
  )
}

export function PremiumPercentileChart({ pipelineType, days, className = '' }: PremiumPercentileChartProps) {
  const [data, setData] = useState<PercentilePoint[]>([])
  const [loading, setLoading] = useState(true)
  const [animated, setAnimated] = useState(false)
  const [hoverX, setHoverX] = useState<number | null>(null)
  const [hoverIdx, setHoverIdx] = useState<number | null>(null)

  useEffect(() => {
    setAnimated(false)
    setLoading(true)
    const ctrl = new AbortController()
    fetch(`/api/metrics/daily-average?pipeline_type=${pipelineType}&days=${days}`, { signal: ctrl.signal })
      .then(r => r.json())
      .then(json => {
        const raw = json.status === 'ok' && json.data ? json.data : generateMock(days)
        setData(raw.map((d: any) => ({
          timestamp: (d.timestamp || '').split('T')[0],
          p50: d.p50 || 0,
          p95: d.p95 || 0,
          p99: d.p99 || 0,
        })))
      })
      .catch(() => setData(generateMock(days)))
      .finally(() => {
        setLoading(false)
        setTimeout(() => setAnimated(true), 80)
      })
    return () => ctrl.abort()
  }, [pipelineType, days])

  const maxVal = Math.max(...data.flatMap(d => [d.p50, d.p95, d.p99]), 1)
  const gridVals = [0, 0.25, 0.5, 0.75, 1].map(r => maxVal * r)

  const pts = (key: 'p50' | 'p95' | 'p99') =>
    mapToCanvas(data.map(d => d[key]), maxVal, CL, CR, CT, CB)

  const xStep = data.length > 1 ? (CR - CL) / (data.length - 1) : 0

  const handleMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect()
    const svgX = ((e.clientX - rect.left) / rect.width) * VW
    if (svgX < CL || svgX > CR) { setHoverIdx(null); setHoverX(null); return }
    const rawIdx = Math.round((svgX - CL) / (xStep || 1))
    const idx = Math.max(0, Math.min(data.length - 1, rawIdx))
    setHoverIdx(idx)
    setHoverX(CL + idx * xStep)
  }

  return (
    <div
      className={`rounded-xl border p-6 ${className}`}
      style={{ background: '#13151B', borderColor: '#1F2330' }}
    >
      <div className="flex items-center justify-between mb-5">
        <h3 className="text-sm font-semibold tracking-wide uppercase" style={{ color: '#9CA3AF', fontFamily: 'Inter, sans-serif', letterSpacing: '0.08em' }}>
          Latency Percentiles
        </h3>
        <div className="flex items-center gap-4">
          {SERIES.map(s => (
            <div key={s.key} className="flex items-center gap-1.5">
              <div className="w-2.5 h-2.5 rounded-full" style={{ background: s.color, boxShadow: `0 0 6px ${s.color}88` }} />
              <span className="text-xs" style={{ color: '#6B7280', fontFamily: 'JetBrains Mono, monospace' }}>{s.label}</span>
            </div>
          ))}
        </div>
      </div>

      {loading ? <SkeletonChart /> : (
        <svg
          viewBox={`0 0 ${VW} ${VH}`}
          className="w-full"
          style={{ minHeight: 240, cursor: 'crosshair' }}
          onMouseMove={handleMouseMove}
          onMouseLeave={() => { setHoverIdx(null); setHoverX(null) }}
        >
          <defs>
            {SERIES.map(s => (
              <linearGradient key={s.gradId} id={s.gradId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={s.color} stopOpacity="0.28" />
                <stop offset="100%" stopColor={s.color} stopOpacity="0" />
              </linearGradient>
            ))}
          </defs>

          {/* Horizontal grid */}
          {gridVals.map((v, i) => {
            const y = CB - (v / maxVal) * (CB - CT)
            return (
              <g key={i}>
                <line x1={CL} y1={y} x2={CR} y2={y} stroke="#1F2330" strokeWidth="1" strokeDasharray="4 4" />
                <text x={CL - 8} y={y + 4} textAnchor="end" fill="#4B5563" fontSize="10" fontFamily="JetBrains Mono, monospace">
                  {formatDurationMs(v)}
                </text>
              </g>
            )
          })}

          {/* Area fills */}
          {SERIES.map(s => {
            const p = pts(s.key)
            return (
              <path
                key={`area-${s.key}`}
                d={smoothAreaPath(p, CB)}
                fill={`url(#${s.gradId})`}
                opacity={animated ? 1 : 0}
                style={{ transition: 'opacity 0.8s ease-out' }}
              />
            )
          })}

          {/* Lines */}
          {SERIES.map(s => {
            const p = pts(s.key)
            return (
              <path
                key={`line-${s.key}`}
                d={smoothLinePath(p)}
                fill="none"
                stroke={s.color}
                strokeWidth="2"
                strokeLinecap="round"
                pathLength={1}
                strokeDasharray="1"
                strokeDashoffset={animated ? 0 : 1}
                style={{
                  transition: 'stroke-dashoffset 1.2s cubic-bezier(0.4,0,0.2,1)',
                  filter: `drop-shadow(0 0 4px ${s.color}66)`,
                }}
              />
            )
          })}

          {/* X-axis labels */}
          {data.map((d, i) => {
            if (data.length > 10 && i % Math.ceil(data.length / 7) !== 0) return null
            const x = CL + i * xStep
            return (
              <text key={i} x={x} y={CB + 18} textAnchor="middle" fill="#4B5563" fontSize="10" fontFamily="Inter, sans-serif">
                {d.timestamp.slice(5)}
              </text>
            )
          })}

          {/* Hover crosshair + tooltip */}
          {hoverX !== null && hoverIdx !== null && data[hoverIdx] && (
            <g>
              <line x1={hoverX} y1={CT} x2={hoverX} y2={CB} stroke="#374151" strokeWidth="1" strokeDasharray="3 3" />
              {SERIES.map(s => {
                const p = pts(s.key)
                const [px, py] = p[hoverIdx] || [0, 0]
                return (
                  <circle key={s.key} cx={px} cy={py} r="4" fill={s.color}
                    style={{ filter: `drop-shadow(0 0 6px ${s.color})` }} />
                )
              })}
              <rect
                x={Math.min(hoverX + 10, CR - 130)}
                y={CT + 4}
                width="124"
                height={SERIES.length * 22 + 16}
                rx="6"
                fill="#0D0E12"
                stroke="#1F2330"
                strokeWidth="1"
              />
              <text x={Math.min(hoverX + 20, CR - 120)} y={CT + 18} fill="#6B7280" fontSize="9" fontFamily="Inter">
                {data[hoverIdx].timestamp}
              </text>
              {SERIES.map((s, si) => (
                <g key={s.key}>
                  <circle cx={Math.min(hoverX + 20, CR - 120)} cy={CT + 30 + si * 22} r="3" fill={s.color} />
                  <text x={Math.min(hoverX + 27, CR - 113)} y={CT + 34 + si * 22} fill={s.color} fontSize="10" fontFamily="JetBrains Mono, monospace">
                    {s.label}: {formatDurationMs(data[hoverIdx][s.key])}
                  </text>
                </g>
              ))}
            </g>
          )}
        </svg>
      )}
    </div>
  )
}

function generateMock(days: number): PercentilePoint[] {
  return Array.from({ length: days }).map((_, i) => ({
    timestamp: new Date(Date.now() - (days - i) * 86400000).toISOString(),
    p50: Math.floor(Math.random() * 400) + 100,
    p95: Math.floor(Math.random() * 800) + 500,
    p99: Math.floor(Math.random() * 1500) + 1000,
  }))
}
