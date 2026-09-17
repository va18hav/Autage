import { cn } from '@/lib/utils'

interface BrandLogoProps {
  className?: string
  iconClassName?: string
  textClassName?: string
  showText?: boolean
}

export function BrandLogo({
  className,
  iconClassName,
  textClassName,
  showText = true,
}: BrandLogoProps) {
  return (
    <span className={cn('inline-flex items-center gap-2.5 select-none', className)}>
      <img
        src="/autage-logo.png"
        alt="Autage logo"
        className={cn('size-7 shrink-0 object-contain', iconClassName)}
      />
      {showText && (
        <span
          className={cn(
            'font-brand text-[18px] font-bold tracking-[-0.03em] text-neutral-950',
            textClassName,
          )}
        >
          Autage
        </span>
      )}
    </span>
  )
}
