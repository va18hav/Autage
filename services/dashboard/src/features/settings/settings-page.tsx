import { IntegrationsCard } from './components/integrations-card'
import { ModelStepsCard } from './components/model-steps-card'

export function SettingsPage() {
  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Connect providers and choose which models each pipeline step runs on.
        </p>
      </header>
      <ModelStepsCard />
      <IntegrationsCard />
    </div>
  )
}
