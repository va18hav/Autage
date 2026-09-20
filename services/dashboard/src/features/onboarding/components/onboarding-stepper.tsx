import { Check } from 'lucide-react'

export interface OnboardingStepMeta {
  key: string
  shortLabel: string
  title: string
  subtitle: string
  configured?: boolean
}

interface OnboardingStepperProps {
  steps: OnboardingStepMeta[]
  currentIndex: number
  onSelectStep: (index: number) => void
}

export function OnboardingStepper({
  steps,
  currentIndex,
  onSelectStep,
}: OnboardingStepperProps) {
  const progressPct =
    steps.length > 1 ? (currentIndex / (steps.length - 1)) * 100 : 0

  return (
    <nav aria-label="Onboarding progress" className="mx-auto w-full max-w-xl select-none">
      <div className="relative flex items-center justify-between">
        {/* Background Track Line */}
        <div
          aria-hidden="true"
          className="absolute right-4 left-4 top-4 h-[2px] -translate-y-1/2 rounded-full bg-neutral-200/90"
        />

        {/* Animated Fill Line */}
        <div
          aria-hidden="true"
          className="absolute left-4 top-4 h-[2px] -translate-y-1/2 rounded-full bg-neutral-900 transition-[width] duration-400 ease-[cubic-bezier(0.22,1,0.36,1)]"
          style={{
            width: `calc((100% - 32px) * ${progressPct / 100})`,
          }}
        />

        {steps.map((step, idx) => {
          const isActive = idx === currentIndex
          const isPast = idx < currentIndex
          const isDone = isPast || Boolean(step.configured)

          return (
            <button
              key={step.key}
              type="button"
              onClick={() => onSelectStep(idx)}
              className="group relative z-10 flex cursor-pointer flex-col items-center gap-2 focus-visible:outline-none"
            >
              <span
                className={`flex size-8 items-center justify-center rounded-full text-xs font-semibold transition-all duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] ${
                  isActive
                    ? 'scale-110 bg-neutral-900 text-white shadow-sm ring-4 ring-neutral-900/10'
                    : isDone
                      ? 'bg-neutral-900 text-white group-hover:scale-105'
                      : 'border border-neutral-200 bg-white text-neutral-400 group-hover:border-neutral-300 group-hover:text-neutral-700'
                }`}
              >
                {isPast ? (
                  <Check className="size-3.5 animate-in zoom-in-75 duration-200" strokeWidth={2.5} />
                ) : (
                  <span className="tabular-nums">{idx + 1}</span>
                )}
              </span>

              <span
                className={`text-[12px] transition-colors duration-200 ${
                  isActive
                    ? 'font-semibold text-neutral-950'
                    : isPast
                      ? 'font-medium text-neutral-600 group-hover:text-neutral-900'
                      : 'font-normal text-neutral-400 group-hover:text-neutral-600'
                }`}
              >
                {step.shortLabel}
              </span>
            </button>
          )
        })}
      </div>
    </nav>
  )
}
