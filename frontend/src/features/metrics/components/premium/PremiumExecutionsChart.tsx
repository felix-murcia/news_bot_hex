import { useState, useEffect } from 'react'
import { apiFetch } from '../../../../api/client'

interface HourBucket {
  timestamp: string
  count: number
  error_count: number
  success_rate: number
}

interface PremiumExecutionsChartProps {
  pipelineType: 'NEWS' | 'AUDIO' | 'VIDEO'
  days: number
  className?: string
}

const COLOR_OK   = '#10B981'
const COLOR_FAIL = '#F43F5E'
const COLOR_NONE = '#1C1F27'

const VW = 856, VH = 260
const CL = 48, CR = 836, CT = 20, CB = 220

export function PremiumExecutionsChart({ pipelineType, days, className = '' }: PremiumExecutionsChartProps) {
  const [data, setData] = useState<HourBucket[]>([])
  const [loading, setLoading] = useState(true)
  const [animated, setAnimated] = useState(false)
  const [hoverIdx, setHoverIdx] = useState<number | null>(null)

  useEffect(() => {
    setAnimated(false)
    setLoading(true)
    const ctrl = new AbortController()
    apiFetch(`/api/metrics/hourly?pipeline_type=${pipelineType}&hours=${days * 24}`, { signal: ctrl.signal })
      .then(r => r.json())
      .then(json => {
        if (json.status === 'ok' && json.data?.length) {
          setData(json.data)
        } else {
          setData(generateMock(days))
        }
      })
      .catch(() => setData(generateMock(days)))
      .finally(() => {
        setLoading(false)
        setTimeout(() => setAnimated(true), 80)
      })
    return () => ctrl.abort()
  }, [pipelineType, days])

  const n = data.length
  const maxCount = Math.max(...data.map(d => d.count), 1)
  const barW = Math.max(4, Math.min(28, (CR - CL) / (n || 1) * 0.7))
  const gap   = (CR - CL) / (n || 1)

  const totalOk   = data.reduce((s, d) => s + (d.count - d.error_count), 0)
  const totalFail = data.reduce((s, d) => s + d.error_count, 0)
  const totalRun  = data.filter(d => d.count > 0).length

  const handleMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!n) return
    const rect = e.currentTarget.getBoundingClientRect()
    const svgX = ((e.clientX - rect.left) / rect.width) * VW
    const idx = Math.round((svgX - CL) / gap)
    setHoverIdx(idx >= 0 && idx < n ? idx : null)
  }

  return (
    <div
      className={`rounded-xl border p-6 ${className}`}
      style={{ background: '#13151B', borderColor: '#1F2330' }}
    >
      <div className="flex items-center justify-between mb-5">
        <h3 className="text-sm font-semibold tracking-wide uppercase"
          style={{ color: '#9CA3AF', fontFamily: 'Inter, sans-serif', letterSpacing: '0.08em' }}>
          Ejecuciones por hora
        </h3>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-sm" style={{ background: COLOR_OK }} />
            <span className="text-xs" style={{ color: '#6B7280', fontFamily: 'JetBrains Mono, monospace' }}>
              OK · {totalOk}
            </span>
          </div>
          {totalFail > 0 && (
            <div className="flex items-center gap-1.5">
              <div className="w-2 h-2 rounded-sm" style={{ background: COLOR_FAIL }} />
              <span className="text-xs" style={{ color: '#6B7280', fontFamily: 'JetBrains Mono, monospace' }}>
                FAIL · {totalFail}
              </span>
            </div>
          )}
          <span className="text-xs px-2 py-0.5 rounded"
            style={{ background: '#1F2330', color: '#6B7280', fontFamily: 'JetBrains Mono, monospace' }}>
            {totalRun} horas activas
          </span>
        </div>
      </div>

      {loading ? (
        <div className="animate-pulse h-40 w-full rounded-lg" style={{ background: '#1F2330' }} />
      ) : (
        <svg
          viewBox={`0 0 ${VW} ${VH}`}
          className="w-full"
          style={{ minHeight: 180, cursor: 'crosshair' }}
          onMouseMove={handleMouseMove}
          onMouseLeave={() => setHoverIdx(null)}
        >
          <defs>
            <linearGradient id="pec-ok" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={COLOR_OK} stopOpacity="0.9" />
              <stop offset="100%" stopColor={COLOR_OK} stopOpacity="0.5" />
            </linearGradient>
            <linearGradient id="pec-fail" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={COLOR_FAIL} stopOpacity="0.9" />
              <stop offset="100%" stopColor={COLOR_FAIL} stopOpacity="0.5" />
            </linearGradient>
          </defs>

          {/* Baseline */}
          <line x1={CL} y1={CB} x2={CR} y2={CB} stroke="#1F2330" strokeWidth="1" />

          {/* Bars */}
          {data.map((d, i) => {
            const x    = CL + i * gap
            const isHov = hoverIdx === i
            const hasRun = d.count > 0
            const isFail = d.error_count > 0
            const color  = !hasRun ? COLOR_NONE : isFail ? COLOR_FAIL : COLOR_OK
            const gradId = isFail ? 'pec-fail' : 'pec-ok'

            const barH  = hasRun
              ? Math.max(8, ((d.count / maxCount) * (CB - CT)))
              : 6
            const animH = animated ? barH : 0
            const animY = CB - (animated ? barH : 0)

            return (
              <g key={i} style={{ cursor: 'pointer' }}
                onMouseEnter={() => setHoverIdx(i)}
                onMouseLeave={() => setHoverIdx(null)}
              >
                <rect
                  x={x - barW / 2}
                  y={animY}
                  width={barW}
                  height={animH}
                  rx="3"
                  fill={hasRun ? `url(#${gradId})` : COLOR_NONE}
                  style={{
                    transition: 'y 0.6s cubic-bezier(0.4,0,0.2,1), height 0.6s cubic-bezier(0.4,0,0.2,1)',
                    transitionDelay: `${i * 12}ms`,
                    filter: isHov && hasRun ? `drop-shadow(0 0 8px ${color}99)` : 'none',
                    opacity: isHov ? 1 : hasRun ? 0.85 : 0.4,
                  }}
                />
                {/* Top glow cap */}
                {animated && hasRun && (
                  <rect
                    x={x - barW / 2}
                    y={CB - barH}
                    width={barW}
                    height="2"
                    rx="1"
                    fill={color}
                    style={{ filter: `drop-shadow(0 0 4px ${color})` }}
                  />
                )}

                {/* X label — every N ticks */}
                {n <= 24 || i % Math.ceil(n / 12) === 0 ? (
                  <text
                    x={x}
                    y={CB + 16}
                    textAnchor="middle"
                    fill={isHov ? color : '#374151'}
                    fontSize="9"
                    fontFamily="Inter, sans-serif"
                    style={{ transition: 'fill 0.15s' }}
                  >
                    {d.timestamp.slice(-5)}
                  </text>
                ) : null}

                {/* Tooltip */}
                {isHov && (
                  <g>
                    <rect
                      x={Math.min(x + 8, CR - 130)}
                      y={CB - barH - 52}
                      width="122"
                      height="46"
                      rx="6"
                      fill="#0D0E12"
                      stroke={hasRun ? color : '#1F2330'}
                      strokeWidth="1"
                      style={{ filter: hasRun ? `drop-shadow(0 0 6px ${color}44)` : 'none' }}
                    />
                    <text
                      x={Math.min(x + 69, CR - 69)}
                      y={CB - barH - 36}
                      textAnchor="middle"
                      fill="#6B7280"
                      fontSize="9"
                      fontFamily="Inter, sans-serif"
                    >
                      {d.timestamp}
                    </text>
                    <text
                      x={Math.min(x + 69, CR - 69)}
                      y={CB - barH - 22}
                      textAnchor="middle"
                      fill={hasRun ? color : '#374151'}
                      fontSize="11"
                      fontFamily="JetBrains Mono, monospace"
                      fontWeight="700"
                    >
                      {!hasRun ? 'Sin ejecución' : isFail ? `${d.error_count} fallo(s)` : `${d.count} OK`}
                    </text>
                    {hasRun && (
                      <text
                        x={Math.min(x + 69, CR - 69)}
                        y={CB - barH - 9}
                        textAnchor="middle"
                        fill="#4B5563"
                        fontSize="9"
                        fontFamily="JetBrains Mono, monospace"
                      >
                        {(d.success_rate * 100).toFixed(0)}% éxito
                      </text>
                    )}
                  </g>
                )}
              </g>
            )
          })}
        </svg>
      )}
    </div>
  )
}

function generateMock(days: number): HourBucket[] {
  return Array.from({ length: days * 24 }).map((_, i) => {
    const ran = Math.random() > 0.3
    const fail = ran && Math.random() < 0.1
    return {
      timestamp: `${String(i % 24).padStart(2, '0')}:00`,
      count: ran ? 1 : 0,
      error_count: fail ? 1 : 0,
      success_rate: fail ? 0 : 1,
    }
  })
}
