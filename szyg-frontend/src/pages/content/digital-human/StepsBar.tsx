import { Check, ChevronRight } from 'lucide-react'

export interface StepDescriptor {
  id: number
  label: string
}

interface StepsBarProps {
  steps: StepDescriptor[]
  current: number
  onChange: (step: number) => void
}

export default function StepsBar({ steps, current, onChange }: StepsBarProps) {
  return (
    <div className="overflow-x-auto border-b border-border px-5 lg:px-8">
      <div className="flex min-w-[720px] items-center">
        {steps.map((item, index) => {
          const active = step_isActive(current, item.id)
          const completed = current > item.id
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onChange(item.id)}
              className={`group flex h-16 flex-1 items-center justify-center gap-3 border-b-2 text-sm transition ${
                active ? 'border-primary text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
            >
              <span
                className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold ${
                  active
                    ? 'bg-primary text-primary-foreground'
                    : completed
                    ? 'bg-success-soft text-success-ink'
                    : 'bg-muted text-muted-foreground'
                }`}
              >
                {completed ? <Check className="h-3.5 w-3.5" /> : item.id}
              </span>
              {item.label}
              {index < steps.length - 1 && <ChevronRight className="ml-auto h-4 w-4 text-muted-foreground" />}
            </button>
          )
        })}
      </div>
    </div>
  )
}

function step_isActive(current: number, id: number): boolean {
  return current === id
}
