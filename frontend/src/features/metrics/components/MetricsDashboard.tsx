import { useState, useEffect } from 'react'
import { KPICard } from './KPICard'
import { PercentileChart } from './PercentileChart'
import { StepDurationChart } from './StepDurationChart'
import { ErrorRateChart } from './ErrorRateChart'
import { ThroughputChart } from './ThroughputChart'
import { LogsTable } from './LogsTable'
import { ActivityHeatmap } from './ActivityHeatmap'
import { PipelineSelector } from './PipelineSelector'
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
    <div className="w-full min-h-screen p-6" style={{ backgroundColor: '#0E0F14' }}>
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-3xl font-bold" style={{ color: '#E5E7EB', fontFamily: 'system-ui' }}>
              Pipeline Metrics
            </h1>
            <p style={{ color: '#9CA3AF' }} className="text-sm mt-1">
              Real-time monitoring dashboard for NEWS, AUDIO, and VIDEO pipelines
            </p>
          </div>
        </div>

        {/* Controls */}
        <div className="flex gap-4 items-center">
          <PipelineSelector value={pipelineType} onChange={setPipelineType} />
          <div className="flex gap-2">
            {(['24h', '7d', '30d'] as const).map((p) => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className="px-3 py-1 rounded text-sm font-medium transition-all duration-200"
                style={{
                  backgroundColor: period === p ? '#3B82F6' : '#2A2D35',
                  color: period === p ? '#FFFFFF' : '#9CA3AF',
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
          {/* KPI Cards - 4 columns */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <KPICard
              label="Total Pipelines"
              value={health.total_executions}
              icon="Zap"
              color="blue"
            />
            <KPICard
              label="Success Rate"
              value={`${((1 - health.error_rate) * 100).toFixed(1)}%`}
              icon="CheckCircle2"
              color="green"
            />
            <KPICard
              label="Avg Latency"
              value={formatDurationMs(health.p95_latency_ms)}
              icon="Clock"
              color="yellow"
            />
            <KPICard
              label="Throughput"
              value={`${health.throughput_per_hour.toFixed(1)}/h`}
              icon="Activity"
              color="purple"
            />
          </div>

          {/* Charts Grid - 2x2 layout */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Percentiles - Full width on top */}
            <div className="lg:col-span-2">
              <PercentileChart pipelineType={pipelineType} days={days} />
            </div>

            {/* Step Duration */}
            <StepDurationChart pipelineType={pipelineType} days={days} />

            {/* Error Rate */}
            <ErrorRateChart health={health} />

            {/* Throughput */}
            <div className="lg:col-span-2">
              <ThroughputChart pipelineType={pipelineType} days={days} />
            </div>

            {/* Activity Heatmap */}
            <div className="lg:col-span-2">
              <ActivityHeatmap pipelineType={pipelineType} />
            </div>

            {/* Logs Table */}
            <div className="lg:col-span-2">
              <LogsTable pipelineType={pipelineType} />
            </div>
          </div>
        </div>
      ) : (
        <div className="text-center py-12">
          <p style={{ color: '#9CA3AF' }}>No data available</p>
        </div>
      )}
    </div>
  )
}
