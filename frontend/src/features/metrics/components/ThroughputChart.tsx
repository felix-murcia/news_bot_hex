import { useState, useEffect } from 'react'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'

interface ThroughputChartProps {
  pipelineType: 'NEWS' | 'AUDIO' | 'VIDEO'
  days: number
}

export function ThroughputChart({ pipelineType, days }: ThroughputChartProps) {
  const [data, setData] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    setData(generateMockData(days))
    setLoading(false)
  }, [pipelineType, days])

  return (
    <div
      className="rounded-lg p-6 border"
      style={{ backgroundColor: '#1A1C22', borderColor: '#2A2D35' }}
    >
      <h3 className="text-lg font-semibold mb-4" style={{ color: '#E5E7EB', fontFamily: 'Fira Code' }}>
        Throughput (Executions/Hour)
      </h3>

      {loading ? (
        <div className="h-64 flex items-center justify-center">
          <span style={{ color: '#9CA3AF' }}>Loading...</span>
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={300}>
          <AreaChart data={data}>
            <defs>
              <linearGradient id="colorThroughput" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#3B82F6" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#3B82F6" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="#2A2D35"
              opacity={0.5}
            />
            <XAxis dataKey="time" stroke="#9CA3AF" />
            <YAxis stroke="#9CA3AF" />
            <Tooltip
              contentStyle={{
                backgroundColor: '#0E0F14',
                borderColor: '#2A2D35',
                borderRadius: '8px',
              }}
              labelStyle={{ color: '#E5E7EB' }}
            />
            <Area
              type="monotone"
              dataKey="throughput"
              stroke="#3B82F6"
              strokeWidth={2}
              fillOpacity={1}
              fill="url(#colorThroughput)"
            />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}

function generateMockData(days: number) {
  const hours = days * 24
  return Array.from({ length: hours }).map((_, i) => ({
    time: `${i % 24}:00`,
    throughput: Math.floor(Math.random() * 50) + 20,
  }))
}
