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
    <div className="overflow-x-auto border-b border-[#1D2636] px-5 lg:px-8">
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
                active ? 'border-[#7C86FF] text-white' : 'border-transparent text-[#77869D] hover:text-[#C9D1DE]'
              }`}
            >
              <span
                className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold ${
                  active
                    ? 'bg-[#6671F0] text-white'
                    : completed
                    ? 'bg-[#244A43] text-[#5CE0BE]'
                    : 'bg-[#182131] text-[#8492A8]'
                }`}
              >
                {completed ? <Check className="h-3.5 w-3.5" /> : item.id}
              </span>
              {item.label}
              {index < steps.length - 1 && <ChevronRight className="ml-auto h-4 w-4 text-[#344158]" />}
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
