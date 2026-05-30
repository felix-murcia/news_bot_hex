import { Radio, Music, Film } from 'lucide-react'

type PipelineType = 'NEWS' | 'AUDIO' | 'VIDEO'

interface PremiumPipelineSelectorProps {
  value: PipelineType
  onChange: (value: PipelineType) => void
  className?: string
}

const PIPELINES: Array<{ id: PipelineType; label: string; icon: typeof Radio; color: string; desc: string }> = [
  { id: 'NEWS',  label: 'News',  icon: Radio, color: '#6366F1', desc: 'RSS → Article → Publish' },
  { id: 'AUDIO', label: 'Audio', icon: Music, color: '#06B6D4', desc: 'TTS → Audio → Upload' },
  { id: 'VIDEO', label: 'Video', icon: Film,  color: '#8B5CF6', desc: 'Script → Video → Social' },
]

export function PremiumPipelineSelector({ value, onChange, className = '' }: PremiumPipelineSelectorProps) {
  return (
    <div className={`flex gap-2 ${className}`}>
      {PIPELINES.map(({ id, label, icon: Icon, color, desc }) => {
        const isActive = value === id
        return (
          <button
            key={id}
            onClick={() => onChange(id)}
            className="relative flex items-center gap-2.5 px-4 py-2.5 rounded-lg font-medium text-sm transition-all duration-200 cursor-pointer"
            style={{
              background: isActive ? `${color}18` : 'transparent',
              color: isActive ? color : '#6B7280',
              border: `1px solid ${isActive ? `${color}55` : '#1F2330'}`,
              boxShadow: isActive ? `0 0 16px ${color}22` : 'none',
              fontFamily: 'Inter, sans-serif',
            }}
            title={desc}
          >
            {isActive && (
              <span
                className="absolute inset-0 rounded-lg pointer-events-none"
                style={{
                  background: `radial-gradient(ellipse at 50% 0%, ${color}18 0%, transparent 70%)`,
                }}
              />
            )}
            <Icon size={15} style={{ flexShrink: 0 }} />
            <span className="relative">{label}</span>
            {isActive && (
              <span
                className="absolute bottom-0 left-4 right-4 h-px rounded-full"
                style={{ background: color, boxShadow: `0 0 6px ${color}` }}
              />
            )}
          </button>
        )
      })}
    </div>
  )
}
