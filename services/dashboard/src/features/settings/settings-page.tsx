import { ModelStepsCard } from './components/model-steps-card'
import { PasswordCard } from './components/password-card'

export function SettingsPage() {
  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-[26px] font-semibold tracking-tight text-neutral-900">
          Settings
        </h1>
        <p className="mt-1.5 text-[15px] text-neutral-500">
          Manage account security and assign AI providers and models to the incident response pipeline.
        </p>
      </header>
      <ModelStepsCard />
      <PasswordCard />
    </div>
  )
}
