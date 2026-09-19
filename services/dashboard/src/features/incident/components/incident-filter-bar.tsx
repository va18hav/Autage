import { Search, X } from 'lucide-react'

export type IncidentStatusFilter = 'ALL' | 'ONGOING' | 'COMPLETED' | 'FAILED'

interface FilterTab {
  key: IncidentStatusFilter
  label: string
  count: number
}

interface IncidentFilterBarProps {
  tabs: FilterTab[]
  activeFilter: IncidentStatusFilter
  onFilterChange: (filter: IncidentStatusFilter) => void
  searchQuery: string
  onSearchChange: (query: string) => void
}

export function IncidentFilterBar({
  tabs,
  activeFilter,
  onFilterChange,
  searchQuery,
  onSearchChange,
}: IncidentFilterBarProps) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-4">
      <div className="flex flex-wrap items-center gap-1.5">
        {tabs.map((tab) => {
          const active = activeFilter === tab.key
          return (
            <button
              key={tab.key}
              type="button"
              onClick={() => onFilterChange(tab.key)}
              className={`inline-flex cursor-pointer items-center gap-2 rounded-full px-4 py-2 text-[14px] transition-colors duration-100 ${
                active
                  ? 'bg-neutral-900 font-medium text-white'
                  : 'bg-neutral-100/80 font-normal text-neutral-600 hover:bg-neutral-200/70 hover:text-neutral-900'
              }`}
            >
              <span>{tab.label}</span>
              <span
                className={`text-[12.5px] tabular-nums ${
                  active ? 'text-neutral-300' : 'text-neutral-400'
                }`}
              >
                {tab.count}
              </span>
            </button>
          )
        })}
      </div>

      <div className="relative w-full sm:w-80">
        <Search className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-neutral-400" />
        <input
          type="text"
          placeholder="Search incidents…"
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          className="h-10 w-full rounded-full border border-neutral-200/90 bg-white pr-9 pl-10 text-[14px] text-neutral-900 placeholder:text-neutral-400 transition-colors focus:border-neutral-400 focus:outline-none"
        />
        {searchQuery && (
          <button
            type="button"
            onClick={() => onSearchChange('')}
            className="absolute right-3 top-1/2 -translate-y-1/2 cursor-pointer text-neutral-400 hover:text-neutral-700"
            aria-label="Clear search"
          >
            <X className="size-4" />
          </button>
        )}
      </div>
    </div>
  )
}
