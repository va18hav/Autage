import { IntegrationsCard } from './components/integrations-card'
import { KubernetesClusterCard } from './components/kubernetes-cluster-card'
import { MonitoringSourcesCard } from './components/monitoring-sources-card'

export function IntegrationsPage() {
  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-[26px] font-semibold tracking-tight text-neutral-900">
          Integrations
        </h1>
        <p className="mt-1.5 text-[15px] text-neutral-500">
          Connect your Kubernetes cluster, monitoring platforms, and AI model providers.
        </p>
      </header>
      <KubernetesClusterCard />
      <MonitoringSourcesCard />
      <IntegrationsCard />
    </div>
  )
}
