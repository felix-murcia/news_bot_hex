import { useState, useEffect } from 'react'

interface ActivityHeatmapProps {
  pipelineType: 'NEWS' | 'AUDIO' | 'VIDEO'
}

export function ActivityHeatmap({ pipelineType }: ActivityHeatmapProps) {
  const [data, setData] = useState<number[][]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    setData(generateHeatmapData())
    setLoading(false)
  }, [pipelineType])

  const getHeatColor = (value: number) => {
    if (value === 0) return '#2A2D35'
    if (value < 25) return '#10B98122'
    if (value < 50) return '#10B98144'
    if (value < 75) return '#10B98166'
    return '#10B981'
  }

  const days = 7
  const hours = 24

  return (
    <div
      className="rounded-lg p-6 border"
      style={{ backgroundColor: '#1A1C22', borderColor: '#2A2D35' }}
    >
      <h3 className="text-lg font-semibold mb-4" style={{ color: '#E5E7EB', fontFamily: 'Fira Code' }}>
        Activity Heatmap (Last 7 Days)
      </h3>

      {loading ? (
        <div className="h-32 flex items-center justify-center">
          <span style={{ color: '#9CA3AF' }}>Loading...</span>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <div className="inline-block">
            {/* Day labels */}
            <div className="flex gap-1 mb-2">
              <div style={{ width: '40px' }}></div>
              {Array.from({ length: days }).map((_, i) => (
                <div key={i} className="text-xs" style={{ width: '60px', color: '#9CA3AF' }}>
                  {new Date(Date.now() - (days - i) * 86400000).toLocaleDateString('es', {
                    month: 'short',
                    day: 'numeric',
                  })}
                </div>
              ))}
            </div>

            {/* Heatmap grid */}
            {Array.from({ length: hours }).map((_, hourIdx) => (
              <div key={hourIdx} className="flex gap-1 mb-1">
                <div style={{ width: '40px', color: '#9CA3AF' }} className="text-xs text-right pr-2">
                  {hourIdx}:00
                </div>
                {data[hourIdx]?.map((value, dayIdx) => (
                  <div
                    key={`${hourIdx}-${dayIdx}`}
                    style={{
                      width: '60px',
                      height: '24px',
                      backgroundColor: getHeatColor(value),
                      borderRadius: '4px',
                      cursor: 'pointer',
                      transition: 'all 200ms',
                    }}
                    className="hover:shadow-lg hover:scale-105"
                    title={`${value} executions`}
                  />
                ))}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Legend */}
      <div className="mt-6 flex items-center gap-4 text-xs">
        <span style={{ color: '#9CA3AF' }}>Activity Level:</span>
        <div className="flex gap-2">
          {[0, 25, 50, 75, 100].map((level) => (
            <div key={level} className="flex items-center gap-1">
              <div
                style={{
                  width: '16px',
                  height: '16px',
                  backgroundColor: getHeatColor(level),
                  borderRadius: '2px',
                }}
              />
              <span style={{ color: '#9CA3AF' }}>{level}%</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function generateHeatmapData(): number[][] {
  const days = 7
  const hours = 24
  return Array.from({ length: hours }).map(() =>
    Array.from({ length: days }).map(() => Math.floor(Math.random() * 100))
  )
}
