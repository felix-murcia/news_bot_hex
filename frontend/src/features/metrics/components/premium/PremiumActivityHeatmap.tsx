import { useState, useEffect } from 'react'
import { apiFetch } from '../../../../api/client'

interface PremiumActivityHeatmapProps {
  pipelineType: 'NEWS' | 'AUDIO' | 'VIDEO'
  className?: string
}

const DAYS = 7
const HOURS = 24
const CELL_W = 36
const CELL_H = 22
const PAD_LEFT = 52
const PAD_TOP = 36

const HEAT_COLORS = [
  { min: 0, max: 0, fill: '#1C1F27' },
  { min: 1, max: 20, fill: '#1a3a4a' },
  { min: 20, max: 40, fill: '#0e5066' },
  { min: 40, max: 60, fill: '#0891b2' },
  { min: 60, max: 80, fill: '#06b6d4' },
  { min: 80, max: 101, fill: '#67e8f9' },
]

function cellColor(value: number): string {
  for (const tier of HEAT_COLORS) {
    if (value >= tier.min && value < tier.max) return tier.fill
  }
  return HEAT_COLORS[HEAT_COLORS.length - 1].fill
}

const dayLabels = Array.from({ length: DAYS }).map((_, i) => {
  const d = new Date(Date.now() - (DAYS - i - 1) * 86400000)
  return d.toLocaleDateString('en', { weekday: 'short', month: 'short', day: 'numeric' })
})

export function PremiumActivityHeatmap({ pipelineType, className = '' }: PremiumActivityHeatmapProps) {
  const [data, setData] = useState<number[][]>([])
  const [loading, setLoading] = useState(true)
  const [hovered, setHovered] = useState<{ h: number; d: number } | null>(null)

  useEffect(() => {
    setLoading(true)
    const ctrl = new AbortController()
    apiFetch(`/api/metrics/activity-heatmap?pipeline_type=${pipelineType}&days=${DAYS}`, { signal: ctrl.signal })
      .then(r => r.json())
      .then(json => {
        if (json.status === 'ok' && json.data) setData(json.data)
        else setData(generateMock())
      })
      .catch(() => setData(generateMock()))
      .finally(() => setLoading(false))
    return () => ctrl.abort()
  }, [pipelineType])

  const svgW = PAD_LEFT + DAYS * CELL_W + 20
  const svgH = PAD_TOP + HOURS * CELL_H + 32

  return (
    <div
      className={`rounded-xl border p-6 ${className}`}
      style={{ background: '#13151B', borderColor: '#1F2330' }}
    >
      <div className="flex items-center justify-between mb-5">
        <h3 className="text-sm font-semibold tracking-wide uppercase" style={{ color: '#9CA3AF', fontFamily: 'Inter, sans-serif', letterSpacing: '0.08em' }}>
          Activity Heatmap · 7 Days
        </h3>
        <div className="flex items-center gap-2">
          <span className="text-xs" style={{ color: '#4B5563', fontFamily: 'Inter' }}>Low</span>
          {HEAT_COLORS.map((t, i) => (
            <div key={i} className="w-3 h-3 rounded-sm" style={{ background: t.fill }} />
          ))}
          <span className="text-xs" style={{ color: '#4B5563', fontFamily: 'Inter' }}>High</span>
        </div>
      </div>

      {loading ? (
        <div className="animate-pulse grid gap-1" style={{ gridTemplateColumns: `repeat(${DAYS}, 1fr)` }}>
          {Array.from({ length: DAYS * 6 }).map((_, i) => (
            <div key={i} className="h-3 rounded" style={{ background: '#1F2330' }} />
          ))}
        </div>
      ) : (
        <div className="overflow-x-auto">
          <svg width={svgW} height={svgH} style={{ display: 'block' }}>
            {/* Day labels */}
            {dayLabels.map((label, d) => (
              <text
                key={d}
                x={PAD_LEFT + d * CELL_W + CELL_W / 2}
                y={20}
                textAnchor="middle"
                fill="#4B5563"
                fontSize="9"
                fontFamily="Inter, sans-serif"
              >
                {label.slice(0, 6)}
              </text>
            ))}

            {/* Hour labels (every 3h) */}
            {Array.from({ length: HOURS }).map((_, h) => {
              if (h % 3 !== 0) return null
              return (
                <text
                  key={h}
                  x={PAD_LEFT - 6}
                  y={PAD_TOP + h * CELL_H + CELL_H / 2 + 4}
                  textAnchor="end"
                  fill="#4B5563"
                  fontSize="9"
                  fontFamily="JetBrains Mono, monospace"
                >
                  {String(h).padStart(2, '0')}h
                </text>
              )
            })}

            {/* Cells */}
            {data.map((row, h) =>
              row.map((val, d) => {
                const isHov = hovered?.h === h && hovered?.d === d
                const color = cellColor(val)
                const x = PAD_LEFT + d * CELL_W
                const y = PAD_TOP + h * CELL_H
                return (
                  <g
                    key={`${h}-${d}`}
                    onMouseEnter={() => setHovered({ h, d })}
                    onMouseLeave={() => setHovered(null)}
                    style={{ cursor: 'pointer' }}
                  >
                    <rect
                      x={x + 2}
                      y={y + 2}
                      width={CELL_W - 4}
                      height={CELL_H - 4}
                      rx="3"
                      fill={color}
                      opacity={isHov ? 1 : val === 0 ? 1 : 0.75}
                      style={{
                        transition: 'opacity 0.15s, filter 0.15s',
                        filter: isHov && val > 0 ? `drop-shadow(0 0 6px ${color})` : 'none',
                      }}
                    />
                    {isHov && (
                      <g>
                        <rect
                          x={x + CELL_W / 2 - 34}
                          y={y - 28}
                          width="68"
                          height="22"
                          rx="5"
                          fill="#0D0E12"
                          stroke={color}
                          strokeWidth="1"
                        />
                        <text
                          x={x + CELL_W / 2}
                          y={y - 13}
                          textAnchor="middle"
                          fill={color}
                          fontSize="10"
                          fontFamily="JetBrains Mono, monospace"
                          fontWeight="600"
                        >
                          {val}% · {String(h).padStart(2, '0')}:00
                        </text>
                      </g>
                    )}
                  </g>
                )
              })
            )}
          </svg>
        </div>
      )}
    </div>
  )
}

function generateMock(): number[][] {
  return Array.from({ length: HOURS }).map(() =>
    Array.from({ length: DAYS }).map(() => {
      const r = Math.random()
      return r < 0.25 ? 0 : Math.floor(r * 100)
    })
  )
}
