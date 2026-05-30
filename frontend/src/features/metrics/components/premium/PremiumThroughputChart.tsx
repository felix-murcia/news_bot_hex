import { useState, useEffect } from 'react'
import { smoothLinePath, smoothAreaPath, mapToCanvas } from './chartUtils'

interface ThroughputPoint {
  time: string
  throughput: number
}

interface PremiumThroughputChartProps {
  pipelineType: 'NEWS' | 'AUDIO' | 'VIDEO'
  days: number
  className?: string
}

const VW = 856, VH = 300
const CL = 56, CR = 820, CT = 20, CB = 260

const COLOR = '#06B6D4'
const GRAD_ID = 'ptc-grad'

export function PremiumThroughputChart({ pipelineType, days, className = '' }: PremiumThroughputChartProps) {
  const [data, setData] = useState<ThroughputPoint[]>([])
  const [loading, setLoading] = useState(true)
  const [animated, setAnimated] = useState(false)
  const [hoverIdx, setHoverIdx] = useState<number | null>(null)

  useEffect(() => {
    setAnimated(false)
    setLoading(true)
    const ctrl = new AbortController()
    fetch(`/api/metrics/hourly?pipeline_type=${pipelineType}&hours=${days * 24}`, { signal: ctrl.signal })
      .then(r => r.json())
      .then(json => {
        const raw = json.status === 'ok' && json.data
          ? json.data.map((d: any) => ({ time: d.timestamp, throughput: d.count || 0 }))
          : generateMock(days)
        setData(raw)
      })
      .catch(() => setData(generateMock(days)))
      .finally(() => {
        setLoading(false)
        setTimeout(() => setAnimated(true), 80)
      })
    return () => ctrl.abort()
  }, [pipelineType, days])

  const maxVal = Math.max(...data.map(d => d.throughput), 1)
  const pts = mapToCanvas(data.map(d => d.throughput), maxVal, CL, CR, CT, CB)
  const xStep = data.length > 1 ? (CR - CL) / (data.length - 1) : 0
  const gridRatios = [0, 0.25, 0.5, 0.75, 1]

  const handleMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (data.length === 0) return
    const rect = e.currentTarget.getBoundingClientRect()
    const svgX = ((e.clientX - rect.left) / rect.width) * VW
    if (svgX < CL || svgX > CR) { setHoverIdx(null); return }
    const idx = Math.max(0, Math.min(data.length - 1, Math.round((svgX - CL) / (xStep || 1))))
    setHoverIdx(idx)
  }

  return (
    <div
      className={`rounded-xl border p-6 ${className}`}
      style={{ background: '#13151B', borderColor: '#1F2330' }}
    >
      <div className="flex items-center justify-between mb-5">
        <h3 className="text-sm font-semibold tracking-wide uppercase" style={{ color: '#9CA3AF', fontFamily: 'Inter, sans-serif', letterSpacing: '0.08em' }}>
          Throughput
        </h3>
        <div className="flex items-center gap-2">
          <div className="w-2.5 h-2.5 rounded-full" style={{ background: COLOR, boxShadow: `0 0 6px ${COLOR}88` }} />
          <span className="text-xs" style={{ color: '#6B7280', fontFamily: 'JetBrains Mono, monospace' }}>exec / hora</span>
        </div>
      </div>

      {loading ? (
        <div className="animate-pulse h-48 w-full rounded-lg" style={{ background: '#1F2330' }} />
      ) : (
        <svg
          viewBox={`0 0 ${VW} ${VH}`}
          className="w-full"
          style={{ minHeight: 220, cursor: 'crosshair' }}
          onMouseMove={handleMouseMove}
          onMouseLeave={() => setHoverIdx(null)}
        >
          <defs>
            <linearGradient id={GRAD_ID} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={COLOR} stopOpacity="0.30" />
              <stop offset="100%" stopColor={COLOR} stopOpacity="0" />
            </linearGradient>
          </defs>

          {/* Grid */}
          {gridRatios.map(r => {
            const y = CB - r * (CB - CT)
            const label = Math.round(maxVal * r)
            return (
              <g key={r}>
                <line x1={CL} y1={y} x2={CR} y2={y} stroke="#1F2330" strokeWidth="1" strokeDasharray="4 4" />
                <text x={CL - 6} y={y + 4} textAnchor="end" fill="#4B5563" fontSize="10" fontFamily="JetBrains Mono, monospace">
                  {label > 1000 ? `${(label / 1000).toFixed(1)}k` : label}
                </text>
              </g>
            )
          })}

          {/* Area */}
          <path
            d={smoothAreaPath(pts, CB)}
            fill={`url(#${GRAD_ID})`}
            opacity={animated ? 1 : 0}
            style={{ transition: 'opacity 0.8s ease-out' }}
          />

          {/* Line */}
          <path
            d={smoothLinePath(pts)}
            fill="none"
            stroke={COLOR}
            strokeWidth="2"
            strokeLinecap="round"
            pathLength={1}
            strokeDasharray="1"
            strokeDashoffset={animated ? 0 : 1}
            style={{
              transition: 'stroke-dashoffset 1.4s cubic-bezier(0.4,0,0.2,1)',
              filter: `drop-shadow(0 0 5px ${COLOR}66)`,
            }}
          />

          {/* X labels */}
          {data.map((d, i) => {
            if (data.length > 12 && i % Math.ceil(data.length / 8) !== 0) return null
            return (
              <text key={i} x={CL + i * xStep} y={CB + 18} textAnchor="middle" fill="#4B5563" fontSize="9" fontFamily="Inter, sans-serif">
                {typeof d.time === 'string' ? d.time.slice(-5) : d.time}
              </text>
            )
          })}

          {/* Axes */}
          <line x1={CL} y1={CT} x2={CL} y2={CB} stroke="#1F2330" strokeWidth="1" />
          <line x1={CL} y1={CB} x2={CR} y2={CB} stroke="#1F2330" strokeWidth="1" />

          {/* Hover */}
          {hoverIdx !== null && pts[hoverIdx] && (
            <g>
              <line x1={pts[hoverIdx][0]} y1={CT} x2={pts[hoverIdx][0]} y2={CB} stroke="#374151" strokeWidth="1" strokeDasharray="3 3" />
              <circle cx={pts[hoverIdx][0]} cy={pts[hoverIdx][1]} r="5" fill={COLOR}
                style={{ filter: `drop-shadow(0 0 8px ${COLOR})` }} />
              <circle cx={pts[hoverIdx][0]} cy={pts[hoverIdx][1]} r="9" fill="none" stroke={COLOR} strokeWidth="1" strokeOpacity="0.4" />
              <rect
                x={Math.min(pts[hoverIdx][0] + 10, CR - 90)}
                y={pts[hoverIdx][1] - 28}
                width="82" height="24" rx="6"
                fill="#0D0E12" stroke="#1F2330" strokeWidth="1"
              />
              <text
                x={Math.min(pts[hoverIdx][0] + 51, CR - 49)}
                y={pts[hoverIdx][1] - 11}
                textAnchor="middle"
                fill={COLOR}
                fontSize="11"
                fontFamily="JetBrains Mono, monospace"
                fontWeight="600"
              >
                {data[hoverIdx].throughput}/hr
              </text>
            </g>
          )}
        </svg>
      )}
    </div>
  )
}

function generateMock(days: number): ThroughputPoint[] {
  return Array.from({ length: days * 24 }).map((_, i) => ({
    time: `${String(i % 24).padStart(2, '0')}:00`,
    throughput: Math.floor(Math.random() * 50) + 10,
  }))
}
