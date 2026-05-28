import { useState, useEffect } from 'react'

interface LogEntry {
  timestamp: string
  level: 'INFO' | 'WARNING' | 'ERROR'
  message: string
  duration: number
}

interface LogsTableProps {
  pipelineType: 'NEWS' | 'AUDIO' | 'VIDEO'
}

export function LogsTable({ pipelineType }: LogsTableProps) {
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true)
        const response = await fetch(`/api/metrics/recent-executions?pipeline_type=${pipelineType}&limit=10`)
        const json = await response.json()

        if (json.status === 'ok' && json.data) {
          const logEntries: LogEntry[] = json.data.map((exec: any) => ({
            timestamp: new Date(exec.timestamp).toLocaleTimeString(),
            level: exec.status === 'OK' ? 'INFO' : 'ERROR',
            message: `Pipeline ${exec.status === 'OK' ? 'completed' : 'failed'} (${exec.step_count} steps)`,
            duration: exec.duration_ms,
          }))
          setLogs(logEntries)
        } else {
          setLogs(generateMockLogs())
        }
      } catch (error) {
        console.error('Error fetching recent executions:', error)
        setLogs(generateMockLogs())
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [pipelineType])

  const getLevelColor = (level: string) => {
    switch (level) {
      case 'INFO':
        return '#3B82F6'
      case 'WARNING':
        return '#F59E0B'
      case 'ERROR':
        return '#EF4444'
      default:
        return '#9CA3AF'
    }
  }

  return (
    <div
      className="rounded-lg p-6 border"
      style={{ backgroundColor: '#1A1C22', borderColor: '#2A2D35' }}
    >
      <h3 className="text-lg font-semibold mb-4" style={{ color: '#E5E7EB', fontFamily: 'Fira Code' }}>
        Recent Logs
      </h3>

      {loading ? (
        <div className="h-64 flex items-center justify-center">
          <span style={{ color: '#9CA3AF' }}>Loading...</span>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottomColor: '#2A2D35', borderBottomWidth: '1px' }}>
                <th
                  className="text-left py-2 px-3 font-semibold"
                  style={{ color: '#9CA3AF' }}
                >
                  Time
                </th>
                <th
                  className="text-left py-2 px-3 font-semibold"
                  style={{ color: '#9CA3AF' }}
                >
                  Level
                </th>
                <th
                  className="text-left py-2 px-3 font-semibold"
                  style={{ color: '#9CA3AF' }}
                >
                  Message
                </th>
                <th
                  className="text-left py-2 px-3 font-semibold"
                  style={{ color: '#9CA3AF' }}
                >
                  Duration
                </th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log, idx) => (
                <tr
                  key={idx}
                  style={{ borderBottomColor: '#2A2D35', borderBottomWidth: '1px' }}
                  className="hover:bg-opacity-50 transition-colors"
                >
                  <td className="py-2 px-3" style={{ color: '#E5E7EB', fontFamily: 'Fira Code' }}>
                    {log.timestamp}
                  </td>
                  <td className="py-2 px-3">
                    <span
                      className="px-2 py-0.5 rounded text-xs font-medium"
                      style={{
                        backgroundColor: getLevelColor(log.level) + '22',
                        color: getLevelColor(log.level),
                      }}
                    >
                      {log.level}
                    </span>
                  </td>
                  <td className="py-2 px-3" style={{ color: '#9CA3AF' }}>
                    {log.message}
                  </td>
                  <td className="py-2 px-3" style={{ color: '#9CA3AF', fontFamily: 'Fira Code' }}>
                    {log.duration}ms
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function generateMockLogs(): LogEntry[] {
  const messages = [
    'Pipeline started',
    'Downloaded content',
    'Processing transcription',
    'Generated article',
    'Enriching images',
    'Publishing to WordPress',
    'Pipeline completed',
  ]

  const levels: ('INFO' | 'WARNING' | 'ERROR')[] = ['INFO', 'INFO', 'INFO', 'WARNING', 'INFO', 'INFO']

  return Array.from({ length: 10 }).map((_, i) => ({
    timestamp: new Date(Date.now() - i * 300000).toLocaleTimeString(),
    level: levels[Math.floor(Math.random() * levels.length)],
    message: messages[Math.floor(Math.random() * messages.length)],
    duration: Math.floor(Math.random() * 5000) + 500,
  }))
}
