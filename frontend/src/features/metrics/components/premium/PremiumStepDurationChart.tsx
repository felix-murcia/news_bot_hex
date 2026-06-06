import { useState, useEffect } from 'react'
import { formatDurationMs } from '../../utils/formatDuration'
import { apiFetch } from '../../../../api/client'

interface StepData {
  name: string
  duration: number
}

interface PremiumStepDurationChartProps {
  pipelineType: 'NEWS' | 'AUDIO' | 'VIDEO'
  days: number
  className?: string
}

const STEP_COLORS = [
  '#6366F1', '#06B6D4', '#10B981', '#F59E0B',
  '#8B5CF6', '#F43F5E', '#3B82F6', '#14B8A6',
]

const MOCK_STEPS = ['Download', 'Transcribe', 'Article', 'Enrich', 'TTS', 'Video', 'WordPress', 'Social']

const VW = 820, VH = 300
const CL = 72, CR = 800, CT = 20, CB = 250

function SkeletonBars() {
  return (
    <div className="flex items-end gap-3 h-48 px-4 animate-pulse">
      {MOCK_STEPS.map((_, i) => (
        <div key={i} className="flex-1 rounded-t-md" style={{
          background: '#1F2330',
          height: `${30 + Math.random() * 70}%`,
        }} />
      ))}
    </div>
  )
}

export function PremiumStepDurationChart({ pipelineType, days, className = '' }: PremiumStepDurationChartProps) {
  const [data, setData] = useState<StepData[]>([])
  const [loading, setLoading] = useState(true)
  const [animated, setAnimated] = useState(false)
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null)

  useEffect(() => {
    setAnimated(false)
    setLoading(true)
    const ctrl = new AbortController()
    apiFetch(`/api/metrics/step-breakdown?pipeline_type=${pipelineType}&days=${days}`, { signal: ctrl.signal })
      .then(r => r.json())
      .then(json => {
        const raw = json.status === 'ok' && json.data
          ? json.data.map((s: any) => ({ name: s.name, duration: s.avg_duration_ms || 0 }))
          : generateMock()
        setData(raw)
      })
      .catch(() => setData(generateMock()))
      .finally(() => {
        setLoading(false)
        setTimeout(() => setAnimated(true), 80)
      })
    return () => ctrl.abort()
  }, [pipelineType, days])

  const maxDur = Math.max(...data.map(d => d.duration), 1)
  const n = data.length
  const barW = n > 0 ? Math.min(48, (CR - CL) / n * 0.55) : 48
  const xStep = n > 1 ? (CR - CL) / (n - 1) : 0
  const barX = (i: number) => (n === 1 ? (CL + CR) / 2 : CL + i * xStep) - barW / 2

  const gridRatios = [0.25, 0.5, 0.75, 1]

  return (
    <div
      className={`rounded-xl border p-6 ${className}`}
      style={{ background: '#13151B', borderColor: '#1F2330' }}
    >
      <div className="flex items-center justify-between mb-5">
        <h3 className="text-sm font-semibold tracking-wide uppercase" style={{ color: '#9CA3AF', fontFamily: 'Inter, sans-serif', letterSpacing: '0.08em' }}>
          Step Duration
        </h3>
        <span className="text-xs px-2 py-0.5 rounded" style={{ background: '#1F2330', color: '#6B7280', fontFamily: 'JetBrains Mono, monospace' }}>
          avg · {days}d
        </span>
      </div>

      {loading ? <SkeletonBars /> : (
        <svg viewBox={`0 0 ${VW} ${VH}`} className="w-full" style={{ minHeight: 220 }}>
          <defs>
            {data.map((_, i) => {
              const c = STEP_COLORS[i % STEP_COLORS.length]
              return (
                <linearGradient key={`g-${i}`} id={`psdc-g${i}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={c} stopOpacity="0.9" />
                  <stop offset="100%" stopColor={c} stopOpacity="0.35" />
                </linearGradient>
              )
            })}
          </defs>

          {/* Grid */}
          {gridRatios.map(r => {
            const y = CB - r * (CB - CT)
            return (
              <g key={r}>
                <line x1={CL} y1={y} x2={CR} y2={y} stroke="#1F2330" strokeWidth="1" strokeDasharray="4 4" />
                <text x={CL - 6} y={y + 4} textAnchor="end" fill="#4B5563" fontSize="10" fontFamily="JetBrains Mono, monospace">
                  {(maxDur * r / 1000).toFixed(1)}s
                </text>
              </g>
            )
          })}

          {/* Bars */}
          {data.map((item, i) => {
            const color = STEP_COLORS[i % STEP_COLORS.length]
            const barH = ((item.duration / maxDur) * (CB - CT))
            const animH = animated ? barH : 0
            const animY = animated ? CB - barH : CB
            const x = barX(i)
            const isHov = hoveredIdx === i

            return (
              <g
                key={i}
                style={{ cursor: 'pointer' }}
                onMouseEnter={() => setHoveredIdx(i)}
                onMouseLeave={() => setHoveredIdx(null)}
              >
                {/* Bar */}
                <rect
                  x={x}
                  y={animY}
                  width={barW}
                  height={animH}
                  rx="4"
                  fill={`url(#psdc-g${i})`}
                  style={{
                    transition: 'y 0.7s cubic-bezier(0.4,0,0.2,1), height 0.7s cubic-bezier(0.4,0,0.2,1)',
                    filter: isHov ? `drop-shadow(0 0 8px ${color}99)` : 'none',
                    opacity: isHov ? 1 : 0.85,
                  }}
                />
                {/* Top cap glow line */}
                {animated && (
                  <rect
                    x={x}
                    y={CB - barH}
                    width={barW}
                    height="2"
                    rx="1"
                    fill={color}
                    style={{ filter: `drop-shadow(0 0 4px ${color})`, opacity: isHov ? 1 : 0.7 }}
                  />
                )}
                {/* Label */}
                <text
                  x={x + barW / 2}
                  y={CB + 16}
                  textAnchor="middle"
                  fill={isHov ? color : '#4B5563'}
                  fontSize="10"
                  fontFamily="Inter, sans-serif"
                  style={{ transition: 'fill 0.2s' }}
                >
                  {item.name.slice(0, 4)}
                </text>

                {/* Tooltip */}
                {isHov && (
                  <g>
                    <rect
                      x={x + barW / 2 - 52}
                      y={CB - barH - 38}
                      width="104"
                      height="32"
                      rx="6"
                      fill="#0D0E12"
                      stroke={color}
                      strokeWidth="1"
                      style={{ filter: `drop-shadow(0 0 6px ${color}44)` }}
                    />
                    <text x={x + barW / 2} y={CB - barH - 22} textAnchor="middle" fill={color} fontSize="10" fontFamily="JetBrains Mono, monospace" fontWeight="600">
                      {item.name}
                    </text>
                    <text x={x + barW / 2} y={CB - barH - 10} textAnchor="middle" fill="#E5E7EB" fontSize="11" fontFamily="JetBrains Mono, monospace" fontWeight="700">
                      {formatDurationMs(item.duration)}
                    </text>
                  </g>
                )}
              </g>
            )
          })}

          {/* Axes */}
          <line x1={CL} y1={CT} x2={CL} y2={CB} stroke="#1F2330" strokeWidth="1" />
          <line x1={CL} y1={CB} x2={CR} y2={CB} stroke="#1F2330" strokeWidth="1" />
        </svg>
      )}
    </div>
  )
}

function generateMock(): StepData[] {
  return MOCK_STEPS.map(name => ({ name, duration: Math.floor(Math.random() * 3000) + 400 }))
}
