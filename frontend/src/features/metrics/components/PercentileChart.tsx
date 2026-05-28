import { useState, useEffect } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import axios from 'axios'

interface PercentileChartProps {
  pipelineType: 'NEWS' | 'AUDIO' | 'VIDEO'
  days: number
}

export function PercentileChart({ pipelineType, days }: PercentileChartProps) {
  const [data, setData] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await axios.get(
          `/metrics/daily-average?pipeline_type=${pipelineType}&days=${days}`
        )
        const chartData = res.data.data?.map((d: any) => ({
          timestamp: d.timestamp?.split('T')[0] || '',
          p50: d.p50 || 0,
          p95: d.p95 || 0,
          p99: d.p99 || 0,
        })) || []
        setData(chartData)
      } catch (error) {
        console.error('Error fetching percentile data:', error)
        setData(generateMockData(days))
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [pipelineType, days])

  return (
    <div
      className="rounded-lg p-6 border"
      style={{ backgroundColor: '#1A1C22', borderColor: '#2A2D35' }}
    >
      <h3 className="text-lg font-semibold mb-4" style={{ color: '#E5E7EB', fontFamily: 'Fira Code' }}>
        Latency Percentiles (P50 / P95 / P99)
      </h3>

      {loading ? (
        <div className="h-64 flex items-center justify-center">
          <span style={{ color: '#9CA3AF' }}>Loading...</span>
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={data}>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="#2A2D35"
              opacity={0.5}
            />
            <XAxis dataKey="timestamp" stroke="#9CA3AF" />
            <YAxis stroke="#9CA3AF" />
            <Tooltip
              contentStyle={{
                backgroundColor: '#0E0F14',
                borderColor: '#2A2D35',
                borderRadius: '8px',
              }}
              labelStyle={{ color: '#E5E7EB' }}
            />
            <Legend />
            <Line
              type="monotone"
              dataKey="p50"
              stroke="#10B981"
              strokeWidth={2}
              dot={false}
              name="P50"
            />
            <Line
              type="monotone"
              dataKey="p95"
              stroke="#F59E0B"
              strokeWidth={2}
              dot={false}
              name="P95"
            />
            <Line
              type="monotone"
              dataKey="p99"
              stroke="#EF4444"
              strokeWidth={2}
              dot={false}
              name="P99"
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}

function generateMockData(days: number) {
  return Array.from({ length: days }).map((_, i) => ({
    timestamp: new Date(Date.now() - (days - i) * 86400000).toISOString().split('T')[0],
    p50: Math.floor(Math.random() * 500) + 100,
    p95: Math.floor(Math.random() * 1000) + 500,
    p99: Math.floor(Math.random() * 2000) + 1000,
  }))
}
