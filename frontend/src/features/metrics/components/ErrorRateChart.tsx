import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from 'recharts'

interface ErrorRateChartProps {
  health: {
    error_rate: number
    total_executions: number
    failed_executions: number
  }
}

export function ErrorRateChart({ health }: ErrorRateChartProps) {
  const successRate = (1 - health.error_rate) * 100
  const errorRate = health.error_rate * 100

  const data = [
    { name: 'Successful', value: Math.round(successRate), color: '#10B981' },
    { name: 'Failed', value: Math.round(errorRate), color: '#EF4444' },
  ]

  return (
    <div
      className="rounded-lg p-6 border"
      style={{ backgroundColor: '#1A1C22', borderColor: '#2A2D35' }}
    >
      <h3 className="text-lg font-semibold mb-4" style={{ color: '#E5E7EB', fontFamily: 'Fira Code' }}>
        Execution Status
      </h3>

      <ResponsiveContainer width="100%" height={280}>
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            labelLine={false}
            label={({ name, value }) => `${name} ${value}%`}
            outerRadius={80}
            fill="#8884d8"
            dataKey="value"
          >
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.color} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              backgroundColor: '#0E0F14',
              borderColor: '#2A2D35',
              borderRadius: '8px',
              color: '#E5E7EB',
            }}
          />
          <Legend />
        </PieChart>
      </ResponsiveContainer>

      <div className="mt-4 space-y-2">
        <div className="flex justify-between text-sm">
          <span style={{ color: '#9CA3AF' }}>Total Executions:</span>
          <span style={{ color: '#E5E7EB', fontFamily: 'Fira Code' }}>
            {health.total_executions}
          </span>
        </div>
        <div className="flex justify-between text-sm">
          <span style={{ color: '#9CA3AF' }}>Failed:</span>
          <span style={{ color: '#EF4444', fontFamily: 'Fira Code' }}>
            {health.failed_executions}
          </span>
        </div>
      </div>
    </div>
  )
}
