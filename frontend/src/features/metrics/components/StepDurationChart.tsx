import { useState, useEffect } from 'react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'

interface StepDurationChartProps {
  pipelineType: 'NEWS' | 'AUDIO' | 'VIDEO'
  days: number
}

const steps = [
  'Download',
  'Transcribe',
  'Article',
  'Enrich',
  'TTS',
  'Video',
  'WordPress',
  'Social',
]

export function StepDurationChart({ pipelineType, days }: StepDurationChartProps) {
  const [data, setData] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    setData(generateMockData())
    setLoading(false)
  }, [pipelineType, days])

  return (
    <div
      className="rounded-lg p-6 border"
      style={{ backgroundColor: '#1A1C22', borderColor: '#2A2D35' }}
    >
      <h3 className="text-lg font-semibold mb-4" style={{ color: '#E5E7EB', fontFamily: 'Fira Code' }}>
        Step Duration (ms)
      </h3>

      {loading ? (
        <div className="h-64 flex items-center justify-center">
          <span style={{ color: '#9CA3AF' }}>Loading...</span>
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={data}>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="#2A2D35"
              opacity={0.5}
            />
            <XAxis dataKey="name" stroke="#9CA3AF" angle={-45} textAnchor="end" height={80} />
            <YAxis stroke="#9CA3AF" />
            <Tooltip
              contentStyle={{
                backgroundColor: '#0E0F14',
                borderColor: '#2A2D35',
                borderRadius: '8px',
              }}
              labelStyle={{ color: '#E5E7EB' }}
            />
            <Bar dataKey="duration" fill="#3B82F6" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}

function generateMockData() {
  return steps.map((step) => ({
    name: step,
    duration: Math.floor(Math.random() * 3000) + 500,
  }))
}
