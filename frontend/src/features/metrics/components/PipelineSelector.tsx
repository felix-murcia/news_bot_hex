import { Radio, Music, Film } from 'lucide-react'

interface PipelineSelectorProps {
  value: 'NEWS' | 'AUDIO' | 'VIDEO'
  onChange: (value: 'NEWS' | 'AUDIO' | 'VIDEO') => void
}

export function PipelineSelector({ value, onChange }: PipelineSelectorProps) {
  const pipelines: Array<{
    id: 'NEWS' | 'AUDIO' | 'VIDEO'
    label: string
    icon: typeof Radio
  }> = [
    { id: 'NEWS', label: 'News', icon: Radio },
    { id: 'AUDIO', label: 'Audio', icon: Music },
    { id: 'VIDEO', label: 'Video', icon: Film },
  ]

  return (
    <div className="flex gap-2">
      {pipelines.map(({ id, label, icon: Icon }) => (
        <button
          key={id}
          onClick={() => onChange(id)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all duration-200"
          style={{
            backgroundColor: value === id ? '#3B82F6' : '#2A2D35',
            color: value === id ? '#FFFFFF' : '#9CA3AF',
            borderColor: value === id ? '#3B82F6' : '#2A2D35',
            borderWidth: '1px',
          }}
        >
          <Icon size={16} />
          {label}
        </button>
      ))}
    </div>
  )
}
