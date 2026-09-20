import { useState } from 'react'
import { Cpu } from 'lucide-react'
import { cn } from '@/lib/utils'

const PROVIDER_LOGO_URLS: Record<string, string> = {
  google: 'https://www.gstatic.com/lamda/images/gemini_sparkle_v002_d4735304ff6292a690345.svg',
  openai: 'https://unpkg.com/@lobehub/icons-static-svg@1.95.1/icons/openai.svg',
  anthropic: 'https://unpkg.com/@lobehub/icons-static-svg@1.95.1/icons/anthropic.svg',
  openrouter: 'https://unpkg.com/@lobehub/icons-static-svg@1.95.1/icons/openrouter.svg',
  ollama: 'https://ollama.com/public/ollama.png',
}

interface ProviderLogoProps {
  providerId: string
  name?: string
  className?: string
  imgClassName?: string
}

export function ProviderLogo({
  providerId,
  name,
  className,
  imgClassName,
}: ProviderLogoProps) {
  const [failed, setFailed] = useState(false)
  const src = PROVIDER_LOGO_URLS[providerId.toLowerCase()]

  return (
    <span
      className={cn(
        'inline-flex size-7 shrink-0 items-center justify-center rounded-md border border-neutral-200/80 bg-white shadow-2xs',
        className,
      )}
    >
      {src && !failed ? (
        <img
          src={src}
          alt={name ? `${name} logo` : `${providerId} logo`}
          className={cn('size-4 object-contain', imgClassName)}
          loading="lazy"
          onError={() => setFailed(true)}
        />
      ) : (
        <Cpu className="size-3.5 text-neutral-500" />
      )}
    </span>
  )
}
