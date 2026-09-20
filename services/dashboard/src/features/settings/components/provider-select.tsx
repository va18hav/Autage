import { useEffect, useRef, useState } from 'react'
import { Check, ChevronDown } from 'lucide-react'
import type { Provider } from '../../../shared/types/settings'
import { ProviderLogo } from './provider-logo'

interface ProviderSelectProps {
  providers: Provider[]
  value: string
  onChange: (providerId: string) => void
  ariaLabel?: string
}

export function ProviderSelect({
  providers,
  value,
  onChange,
  ariaLabel,
}: ProviderSelectProps) {
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  const selected = providers.find((p) => p.id === value) ?? providers[0]

  useEffect(() => {
    if (!open) return
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [open])

  if (!selected) return null

  return (
    <div ref={containerRef} className="relative w-full sm:w-auto">
      <button
        type="button"
        aria-label={ariaLabel}
        aria-expanded={open}
        onClick={() => setOpen((prev) => !prev)}
        className="flex h-10 w-full cursor-pointer items-center justify-between gap-2.5 rounded-xl border border-neutral-200/90 bg-white px-3 text-[13.5px] font-medium text-neutral-800 transition-colors duration-100 hover:border-neutral-300 focus-visible:border-neutral-400 focus-visible:outline-none sm:min-w-48"
      >
        <span className="flex items-center gap-2.5 truncate">
          <ProviderLogo
            providerId={selected.id}
            name={selected.display_name}
            className="size-5 border-0 bg-transparent shadow-none"
            imgClassName="size-4"
          />
          <span className="truncate">{selected.display_name}</span>
        </span>
        <ChevronDown
          className={`size-4 shrink-0 text-neutral-400 transition-transform duration-150 ${
            open ? 'rotate-180' : ''
          }`}
        />
      </button>

      {open && (
        <div className="absolute right-0 z-30 mt-1.5 min-w-52 overflow-hidden rounded-xl border border-neutral-200/90 bg-white p-1 shadow-lg">
          {providers.map((provider) => {
            const isSelected = provider.id === selected.id
            return (
              <button
                key={provider.id}
                type="button"
                onClick={() => {
                  onChange(provider.id)
                  setOpen(false)
                }}
                className={`flex w-full cursor-pointer items-center justify-between gap-2.5 rounded-lg px-2.5 py-2 text-left text-[13.5px] transition-colors duration-100 ${
                  isSelected
                    ? 'bg-neutral-100 font-medium text-neutral-950'
                    : 'text-neutral-700 hover:bg-neutral-50 hover:text-neutral-950'
                }`}
              >
                <span className="flex items-center gap-2.5 truncate">
                  <ProviderLogo
                    providerId={provider.id}
                    name={provider.display_name}
                    className="size-5 border-0 bg-transparent shadow-none"
                    imgClassName="size-4"
                  />
                  <span className="truncate">{provider.display_name}</span>
                </span>
                {isSelected && <Check className="size-4 shrink-0 text-neutral-900" />}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
