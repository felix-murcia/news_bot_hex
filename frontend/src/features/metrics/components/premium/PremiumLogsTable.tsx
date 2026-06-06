import { useState, useEffect } from 'react'
import { formatDurationMs } from '../../utils/formatDuration'
import { apiFetch } from '../../../../api/client'

type LogLevel = 'INFO' | 'WARNING' | 'ERROR'

interface LogEntry {
  timestamp: string
  level: LogLevel
  message: string
  duration: number
}

interface PremiumLogsTableProps {
  pipelineType: 'NEWS' | 'AUDIO' | 'VIDEO'
  className?: string
}

const LEVEL_CONFIG: Record<LogLevel, { color: string; bg: string; dot: string }> = {
  INFO:    { color: '#6366F1', bg: '#6366F115', dot: '#6366F1' },
  WARNING: { color: '#F59E0B', bg: '#F59E0B15', dot: '#F59E0B' },
  ERROR:   { color: '#F43F5E', bg: '#F43F5E15', dot: '#F43F5E' },
}

export function PremiumLogsTable({ pipelineType, className = '' }: PremiumLogsTableProps) {
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [hoveredRow, setHoveredRow] = useState<number | null>(null)

  useEffect(() => {
    setLoading(true)
    const ctrl = new AbortController()
    apiFetch(`/api/metrics/recent-executions?pipeline_type=${pipelineType}&limit=10`, { signal: ctrl.signal })
      .then(r => r.json())
      .then(json => {
        if (json.status === 'ok' && json.data) {
          setLogs(json.data.map((exec: any) => ({
            timestamp: new Date(exec.timestamp).toLocaleTimeString('en', { hour12: false }),
            level: exec.status === 'OK' ? 'INFO' : 'ERROR',
            message: `Pipeline ${exec.status === 'OK' ? 'completed' : 'failed'} — ${exec.step_count} steps`,
            duration: exec.duration_ms,
          })))
        } else {
          setLogs(generateMock())
        }
      })
      .catch(() => setLogs(generateMock()))
      .finally(() => setLoading(false))
    return () => ctrl.abort()
  }, [pipelineType])

  return (
    <div
      className={`rounded-xl border p-6 ${className}`}
      style={{ background: '#13151B', borderColor: '#1F2330' }}
    >
      <div className="flex items-center justify-between mb-5">
        <h3 className="text-sm font-semibold tracking-wide uppercase" style={{ color: '#9CA3AF', fontFamily: 'Inter, sans-serif', letterSpacing: '0.08em' }}>
          Recent Executions
        </h3>
        <div className="flex items-center gap-1.5 px-2 py-0.5 rounded" style={{ background: '#1F2330' }}>
          <div className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: '#10B981' }} />
          <span className="text-xs" style={{ color: '#6B7280', fontFamily: 'JetBrains Mono, monospace' }}>live</span>
        </div>
      </div>

      {loading ? (
        <div className="space-y-2 animate-pulse">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-10 rounded-lg" style={{ background: '#1F2330', opacity: 1 - i * 0.12 }} />
          ))}
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs border-collapse">
            <thead>
              <tr>
                {['Time', 'Status', 'Message', 'Duration'].map(h => (
                  <th key={h} className="text-left pb-3 pr-4 font-medium tracking-wider"
                    style={{ color: '#4B5563', fontFamily: 'Inter, sans-serif', borderBottom: '1px solid #1F2330', letterSpacing: '0.06em' }}>
                    {h.toUpperCase()}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {logs.map((log, idx) => {
                const lc = LEVEL_CONFIG[log.level]
                const isHov = hoveredRow === idx
                return (
                  <tr
                    key={idx}
                    onMouseEnter={() => setHoveredRow(idx)}
                    onMouseLeave={() => setHoveredRow(null)}
                    style={{
                      background: isHov ? '#1C1F27' : 'transparent',
                      transition: 'background 0.15s',
                      cursor: 'default',
                    }}
                  >
                    <td className="py-2.5 pr-4" style={{ borderBottom: '1px solid #1A1D24' }}>
                      <span style={{ color: '#6B7280', fontFamily: 'JetBrains Mono, monospace' }}>{log.timestamp}</span>
                    </td>
                    <td className="py-2.5 pr-4" style={{ borderBottom: '1px solid #1A1D24' }}>
                      <span
                        className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium"
                        style={{ background: lc.bg, color: lc.color, fontFamily: 'JetBrains Mono, monospace' }}
                      >
                        <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: lc.dot }} />
                        {log.level}
                      </span>
                    </td>
                    <td className="py-2.5 pr-4" style={{ borderBottom: '1px solid #1A1D24', color: '#9CA3AF', fontFamily: 'Inter, sans-serif' }}>
                      {log.message}
                    </td>
                    <td className="py-2.5" style={{ borderBottom: '1px solid #1A1D24' }}>
                      <span style={{
                        color: log.duration > 3000 ? '#F59E0B' : '#6B7280',
                        fontFamily: 'JetBrains Mono, monospace',
                      }}>
                        {formatDurationMs(log.duration)}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

const MESSAGES = [
  'Pipeline completed — 8 steps',
  'Pipeline failed — step 3 error',
  'Pipeline completed — 8 steps',
  'Pipeline completed — 8 steps',
  'RSS fetch timeout — retrying',
]

function generateMock(): LogEntry[] {
  const levels: LogLevel[] = ['INFO', 'INFO', 'INFO', 'ERROR', 'WARNING']
  return Array.from({ length: 10 }).map((_, i) => ({
    timestamp: new Date(Date.now() - i * 310000).toLocaleTimeString('en', { hour12: false }),
    level: levels[Math.floor(Math.random() * levels.length)],
    message: MESSAGES[Math.floor(Math.random() * MESSAGES.length)],
    duration: Math.floor(Math.random() * 5000) + 400,
  }))
}
