import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, ChevronDown, Copy, Trash2 } from 'lucide-react'
import { toast } from 'sonner'

import { kubernetesSettingsApi } from '../../../shared/lib/api'
import { queryKeys } from '../../../shared/lib/query-client'
import { Button, Input, Label } from '@/components/ui'

const SETUP_COMMANDS = `# 1. Create a read-only ServiceAccount for Autage
kubectl create serviceaccount autage-reader -n default
kubectl create clusterrolebinding autage-reader-binding \\
  --clusterrole=view \\
  --serviceaccount=default:autage-reader

# 2. Print your Cluster API URL
kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}{"\\n"}'

# 3. Generate a read-only ServiceAccount Bearer Token (valid 1 year)
kubectl create token autage-reader -n default --duration=8760h`

export function KubernetesClusterCard() {
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [showGuide, setShowGuide] = useState(false)
  const [copiedCommands, setCopiedCommands] = useState(false)

  const [serverUrl, setServerUrl] = useState('')
  const [token, setToken] = useState('')

  const k8sQuery = useQuery({
    queryKey: queryKeys.settings.kubernetes(),
    queryFn: kubernetesSettingsApi.get,
  })

  const saveMutation = useMutation({
    mutationFn: () =>
      kubernetesSettingsApi.save({
        server_url: serverUrl.trim(),
        token: token.trim(),
      }),
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.settings.kubernetes(), data)
      setEditing(false)
      setToken('')
      toast.success('Kubernetes cluster connected', {
        description: `Connected to ${data.server_url}`,
      })
    },
    onError: (err) => {
      toast.error('Failed to save cluster configuration', {
        description: err instanceof Error ? err.message : 'Unknown error',
      })
    },
  })

  const testMutation = useMutation({
    mutationFn: () =>
      kubernetesSettingsApi.test({
        server_url: serverUrl.trim(),
        token: token.trim(),
      }),
    onSuccess: (res) => {
      if (res.ok) {
        toast.success('Cluster connection verified', {
          description: res.message,
        })
      } else {
        toast.error('Cluster verification failed', {
          description: res.message,
        })
      }
    },
    onError: (err) => {
      toast.error('Cluster verification failed', {
        description: err instanceof Error ? err.message : 'Unknown error',
      })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: kubernetesSettingsApi.delete,
    onSuccess: () => {
      queryClient.setQueryData(queryKeys.settings.kubernetes(), {
        configured: false,
        server_url: null,
        token_preview: null,
        updated_at: null,
      })
      toast.success('Kubernetes cluster disconnected', {
        description: 'Reverted to mock cluster mode.',
      })
    },
    onError: (err) => {
      toast.error('Failed to disconnect cluster', {
        description: err instanceof Error ? err.message : 'Unknown error',
      })
    },
  })

  const copyCommands = () => {
    navigator.clipboard.writeText(SETUP_COMMANDS)
    setCopiedCommands(true)
    setTimeout(() => setCopiedCommands(false), 1500)
  }

  if (k8sQuery.isLoading) {
    return (
      <div className="h-44 animate-pulse rounded-2xl border border-neutral-200/80 bg-white p-6" />
    )
  }

  const config = k8sQuery.data
  const configured = Boolean(config?.configured)

  const handleStartEdit = () => {
    setServerUrl(config?.server_url ?? '')
    setToken('')
    setEditing(true)
  }

  return (
    <section className="overflow-hidden rounded-2xl border border-neutral-200/80 bg-white">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-neutral-100 px-4 py-4 sm:px-6 sm:py-5">
        <div className="flex items-center gap-3.5">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-xl border border-neutral-200/80 bg-white shadow-2xs">
            <img
              src="https://cdn.simpleicons.org/kubernetes"
              alt="Kubernetes logo"
              className="size-5 object-contain"
              loading="lazy"
            />
          </span>
          <div>
            <h2 className="text-[16px] font-semibold text-neutral-900">
              Kubernetes Cluster
            </h2>
            <p className="mt-0.5 text-[14px] text-neutral-500">
              Connect your production cluster via Cluster API URL and a read-only ServiceAccount token.
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={() => setShowGuide((prev) => !prev)}
          className="inline-flex cursor-pointer items-center gap-1.5 rounded-full bg-neutral-100/90 px-3.5 py-1.5 text-[13px] font-medium text-neutral-700 transition-colors hover:bg-neutral-200/70"
        >
          <span>Setup commands</span>
          <ChevronDown
            className={`size-3.5 text-neutral-500 transition-transform duration-150 ${showGuide ? 'rotate-180' : ''
              }`}
          />
        </button>
      </div>

      {/* Collapsible 1-Step Terminal Setup Guide */}
      <div
        className={`grid transition-[grid-template-rows,opacity] duration-200 ease-[cubic-bezier(0.22,1,0.36,1)] ${showGuide ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0'
          }`}
      >
        <div className="overflow-hidden">
          <div className="border-b border-neutral-100 bg-neutral-50/50 px-4 py-4 sm:px-6 sm:py-5">
            <p className="mb-3 text-[13.5px] text-neutral-600">
              Run these commands in your terminal where <code className="font-mono text-xs text-neutral-800">kubectl</code> is connected to your cluster:
            </p>

            <div className="overflow-hidden rounded-2xl bg-[#141414] text-neutral-100">
              <div className="flex items-center justify-between px-5 pt-3.5 pb-2 text-[12.5px]">
                <span className="font-medium text-neutral-400">Bash</span>
                <button
                  type="button"
                  onClick={copyCommands}
                  className="inline-flex cursor-pointer items-center gap-1.5 text-[12px] font-medium text-neutral-400 transition-colors hover:text-white"
                >
                  {copiedCommands ? (
                    <>
                      <Check className="size-3.5 text-emerald-400" />
                      <span>Copied</span>
                    </>
                  ) : (
                    <>
                      <Copy className="size-3.5" />
                      <span>Copy</span>
                    </>
                  )}
                </button>
              </div>
              <pre className="overflow-x-auto px-5 pt-1 pb-4 font-mono text-[12.5px] leading-relaxed text-neutral-200">
                {SETUP_COMMANDS}
              </pre>
            </div>
          </div>
        </div>
      </div>

      {/* Body: Status Row or Edit Form */}
      {editing ? (
        <div className="bg-neutral-50/40 px-4 py-5 sm:px-6">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="k8s-server-url" className="text-[13px] text-neutral-600">
                Cluster API Server URL
              </Label>
              <Input
                id="k8s-server-url"
                type="url"
                value={serverUrl}
                onChange={(e) => setServerUrl(e.target.value)}
                placeholder="https://F48D92A1B.gr7.us-east-1.eks.amazonaws.com"
                className="h-10 rounded-xl bg-white font-mono text-[13px]"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="k8s-sa-token" className="text-[13px] text-neutral-600">
                ServiceAccount Bearer Token
              </Label>
              <Input
                id="k8s-sa-token"
                type="password"
                autoComplete="new-password"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder={
                  configured ? 'Enter new token to rotate' : 'eyJhbGciOiJSUzI1NiIs...'
                }
                className="h-10 rounded-xl bg-white font-mono text-[13px]"
              />
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-end gap-2.5 pt-4">
            <Button
              variant="ghost"
              size="sm"
              className="rounded-full px-4"
              onClick={() => setEditing(false)}
            >
              Cancel
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="rounded-full bg-white px-4"
              disabled={!serverUrl.trim() || !token.trim() || testMutation.isPending}
              onClick={() => testMutation.mutate()}
            >
              {testMutation.isPending ? 'Verifying…' : 'Verify connection'}
            </Button>
            <Button
              size="sm"
              className="rounded-full px-4"
              disabled={!serverUrl.trim() || !token.trim() || saveMutation.isPending}
              onClick={() => saveMutation.mutate()}
            >
              {saveMutation.isPending ? 'Saving…' : 'Save cluster'}
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex flex-col items-start justify-between gap-3 px-4 py-4 sm:flex-row sm:items-center sm:gap-4 sm:px-6">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <p className="text-[14.5px] font-medium text-neutral-900">
                {configured ? 'Production Cluster Connected' : 'Mock Cluster Mode Active'}
              </p>
            </div>
            <p className="mt-0.5 truncate font-mono text-[12.5px] text-neutral-400">
              {configured
                ? `${config?.server_url} · token ${config?.token_preview ?? '••••'}`
                : 'Using simulated kubectl responses until a cluster is connected'}
            </p>
          </div>

          <div className="flex w-full flex-wrap items-center justify-end gap-2.5 sm:w-auto">
            <Button
              variant={configured ? 'outline' : 'default'}
              size="sm"
              className={`rounded-full px-4 ${configured ? 'bg-white' : ''}`}
              onClick={handleStartEdit}
            >
              {configured ? 'Update cluster' : 'Connect cluster'}
            </Button>

            {configured && (
              <Button
                variant="ghost"
                size="icon-sm"
                className="rounded-full text-neutral-400 hover:bg-red-50 hover:text-red-600"
                title="Disconnect cluster"
                aria-label="Disconnect cluster"
                onClick={() => deleteMutation.mutate()}
              >
                <Trash2 className="size-4" />
              </Button>
            )}
          </div>
        </div>
      )}
    </section>
  )
}
