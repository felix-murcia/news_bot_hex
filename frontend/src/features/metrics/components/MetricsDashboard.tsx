import { useState, useEffect } from 'react'
import {
  PremiumKPICard,
  PremiumPercentileChart,
  PremiumStepDurationChart,
  PremiumErrorRateChart,
  PremiumThroughputChart,
  PremiumLogsTable,
  PremiumActivityHeatmap,
  PremiumPipelineSelector,
} from './premium'
import { LoadingSpinner } from './LoadingSpinner'
import { formatDurationMs } from '../utils/formatDuration'
import axios from 'axios'

interface HealthData {
  error_rate: number
  p95_latency_ms: number
  throughput_per_hour: number
  total_executions: number
  failed_executions: number
}

export function MetricsDashboard() {
  const [pipelineType, setPipelineType] = useState<'NEWS' | 'AUDIO' | 'VIDEO'>('NEWS')
  const [period, setPeriod] = useState<'24h' | '7d' | '30d'>('24h')
  const [loading, setLoading] = useState(true)
  const [health, setHealth] = useState<HealthData | null>(null)

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true)
        const res = await axios.get('/metrics/health')
        if (res.data.data && res.data.data[pipelineType]) {
          setHealth(res.data.data[pipelineType])
        }
      } catch (error) {
        console.error('Error fetching metrics:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [pipelineType])

  const days = period === '24h' ? 1 : period === '7d' ? 7 : 30

  return (
    <div className="w-full min-h-screen p-6" style={{ background: '#0D0E12' }}>
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold" style={{ color: '#F9FAFB', fontFamily: 'Inter, sans-serif' }}>
              Pipeline Metrics
            </h1>
            <p className="text-sm mt-1" style={{ color: '#6B7280', fontFamily: 'Inter, sans-serif' }}>
              Real-time monitoring — NEWS · AUDIO · VIDEO
            </p>
          </div>
        </div>

        {/* Controls */}
        <div className="flex flex-wrap gap-4 items-center">
          <PremiumPipelineSelector value={pipelineType} onChange={setPipelineType} />
          <div className="flex gap-1.5">
            {(['24h', '7d', '30d'] as const).map((p) => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className="px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200 cursor-pointer"
                style={{
                  background: period === p ? '#6366F118' : 'transparent',
                  color: period === p ? '#6366F1' : '#6B7280',
                  border: `1px solid ${period === p ? '#6366F155' : '#1F2330'}`,
                  fontFamily: 'JetBrains Mono, monospace',
                }}
              >
                {p}
              </button>
            ))}
          </div>
        </div>
      </div>

      {loading ? (
        <LoadingSpinner />
      ) : health ? (
        <div className="space-y-6">
          {/* KPI Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <PremiumKPICard
              label="Total Pipelines"
              value={health.total_executions}
              icon="Zap"
              color="indigo"
            />
            <PremiumKPICard
              label="Success Rate"
              value={`${((1 - health.error_rate) * 100).toFixed(1)}%`}
              icon="CheckCircle2"
              color="emerald"
            />
            <PremiumKPICard
              label="P95 Latency"
              value={formatDurationMs(health.p95_latency_ms)}
              icon="Clock"
              color="amber"
            />
            <PremiumKPICard
              label="Throughput"
              value={`${health.throughput_per_hour.toFixed(1)}/h`}
              icon="Activity"
              color="cyan"
            />
          </div>

          {/* Charts Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="lg:col-span-2">
              <PremiumPercentileChart pipelineType={pipelineType} days={days} />
            </div>

            <PremiumStepDurationChart pipelineType={pipelineType} days={days} />
            <PremiumErrorRateChart health={health} />

            <div className="lg:col-span-2">
              <PremiumThroughputChart pipelineType={pipelineType} days={days} />
            </div>

            <div className="lg:col-span-2">
              <PremiumActivityHeatmap pipelineType={pipelineType} />
            </div>

            <div className="lg:col-span-2">
              <PremiumLogsTable pipelineType={pipelineType} />
            </div>
          </div>
        </div>
      ) : (
        <div className="text-center py-12">
          <p style={{ color: '#6B7280', fontFamily: 'Inter, sans-serif' }}>No data available</p>
        </div>
      )}
    </div>
  )
}
