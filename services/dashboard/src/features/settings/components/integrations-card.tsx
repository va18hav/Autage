import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Trash2 } from 'lucide-react'
import { toast } from 'sonner'

import { credentialApi, providerApi } from '../../../shared/lib/api'
import { queryKeys } from '../../../shared/lib/query-client'
import type { Provider } from '../../../shared/types/settings'
import { Button, Input, Label } from '@/components/ui'
import { ProviderLogo } from './provider-logo'

interface FieldValues {
  [fieldName: string]: string
}

function initialValues(provider: Provider, currentPreview: string | null): FieldValues {
  const values: FieldValues = {}
  for (const field of provider.credential_fields) {
    values[field.name] = field.default ?? ''
  }
  if (!currentPreview) return values
  // Pre-fill non-secret fields only — secrets must be re-entered to rotate.
  for (const field of provider.credential_fields) {
    if (!field.is_secret && provider.credential_preview) {
      values[field.name] = provider.credential_preview
    }
  }
  return values
}

export function IntegrationsCard() {
  const queryClient = useQueryClient()

  const catalogQuery = useQuery({
    queryKey: queryKeys.settings.catalog(),
    queryFn: providerApi.catalog,
  })
  const credentialsQuery = useQuery({
    queryKey: queryKeys.settings.credentials(),
    queryFn: credentialApi.list,
  })

  const [editing, setEditing] = useState<string | null>(null)
  const [values, setValues] = useState<FieldValues>({})

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.settings.catalog() })
    queryClient.invalidateQueries({ queryKey: queryKeys.settings.credentials() })
    queryClient.invalidateQueries({ queryKey: queryKeys.settings.llm() })
  }

  const saveMutation = useMutation({
    mutationFn: ({ purpose, fields }: { purpose: string; fields: FieldValues }) =>
      credentialApi.save(purpose, fields),
    onSuccess: (credential) => {
      invalidate()
      setEditing(null)
      toast.success('Credential saved', {
        description: `${credential.purpose} — ${credential.preview ?? ''}`,
      })
    },
    onError: (error) => {
      toast.error('Save failed', {
        description: error instanceof Error ? error.message : 'Unknown error',
      })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (purpose: string) => credentialApi.delete(purpose),
    onSuccess: () => {
      invalidate()
      toast.success('Credential removed')
    },
    onError: (error) => {
      toast.error('Delete failed', {
        description: error instanceof Error ? error.message : 'Unknown error',
      })
    },
  })

  const testMutation = useMutation({
    mutationFn: ({ purpose, fields }: { purpose: string; fields: FieldValues }) =>
      credentialApi.test(purpose, fields),
    onSuccess: (result) => {
      if (result.ok) {
        toast.success('Connection verified', { description: result.message })
      } else {
        toast.error('Verification failed', { description: result.message })
      }
    },
    onError: (error) => {
      toast.error('Verification failed', {
        description: error instanceof Error ? error.message : 'Unknown error',
      })
    },
  })

  const providers = catalogQuery.data?.providers ?? []
  const credentialByPurpose = Object.fromEntries(
    (credentialsQuery.data ?? []).map((c) => [c.purpose, c]),
  )

  const startEditing = (provider: Provider) => {
    setEditing(provider.id)
    setValues(
      initialValues(provider, credentialByPurpose[provider.id]?.preview ?? null),
    )
  }

  if (catalogQuery.isLoading || credentialsQuery.isLoading) {
    return (
      <div className="h-48 animate-pulse rounded-lg border border-border/80 bg-white p-6" />
    )
  }

  return (
    <section className="overflow-hidden rounded-2xl border border-neutral-200/80 bg-white">
      <div className="border-b border-neutral-100 px-6 py-5">
        <h2 className="text-[16px] font-semibold text-neutral-900">Provider Credentials</h2>
        <p className="mt-1 text-[14px] text-neutral-500">
          API keys are encrypted at rest with Fernet and never returned in plaintext.
        </p>
      </div>

      <div className="divide-y divide-neutral-100">
        {providers.map((provider) => {
          const credential = credentialByPurpose[provider.id]
          const configured = provider.credential_configured
          const isEditing = editing === provider.id

          if (isEditing) {
            const secretFields = provider.credential_fields.filter((f) => f.is_secret)
            const plainFields = provider.credential_fields.filter((f) => !f.is_secret)
            return (
              <div key={provider.id} className="bg-neutral-50/50 px-6 py-5">
                <div className="flex items-center justify-between pb-4">
                  <div className="flex items-center gap-3">
                    <ProviderLogo
                      providerId={provider.id}
                      name={provider.display_name}
                      className="size-8 rounded-lg"
                    />
                    <span className="text-[15px] font-medium text-neutral-900">
                      {provider.display_name}
                    </span>
                  </div>
                </div>

                <div className="grid gap-4 sm:grid-cols-2">
                  {secretFields.map((field) => (
                    <div key={field.name} className="space-y-1.5">
                      <Label className="text-[13px] text-neutral-600">{field.label}</Label>
                      <Input
                        type="password"
                        autoComplete="new-password"
                        value={values[field.name] ?? ''}
                        placeholder={credential ? 'Enter new key to rotate' : 'sk-...'}
                        onChange={(e) =>
                          setValues((prev) => ({
                            ...prev,
                            [field.name]: e.target.value,
                          }))
                        }
                        className="h-10 rounded-xl bg-white font-mono text-[13px]"
                      />
                    </div>
                  ))}
                  {plainFields.map((field) => (
                    <div key={field.name} className="space-y-1.5">
                      <Label className="text-[13px] text-neutral-600">{field.label}</Label>
                      <Input
                        value={values[field.name] ?? ''}
                        placeholder={field.default ?? ''}
                        onChange={(e) =>
                          setValues((prev) => ({
                            ...prev,
                            [field.name]: e.target.value,
                          }))
                        }
                        className="h-10 rounded-xl bg-white font-mono text-[13px]"
                      />
                    </div>
                  ))}
                </div>

                <div className="flex items-center justify-end gap-2.5 pt-4">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="rounded-full px-4"
                    onClick={() => setEditing(null)}
                  >
                    Cancel
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="rounded-full bg-white px-4"
                    disabled={testMutation.isPending}
                    onClick={() =>
                      testMutation.mutate({ purpose: provider.id, fields: values })
                    }
                  >
                    {testMutation.isPending ? 'Verifying…' : 'Verify connection'}
                  </Button>
                  <Button
                    size="sm"
                    className="rounded-full px-4"
                    disabled={saveMutation.isPending}
                    onClick={() =>
                      saveMutation.mutate({
                        purpose: provider.id,
                        fields: values,
                      })
                    }
                  >
                    {saveMutation.isPending ? 'Saving…' : 'Save key'}
                  </Button>
                </div>
              </div>
            )
          }

          return (
            <div
              key={provider.id}
              className="flex flex-col items-start justify-between gap-3 px-4 py-4 transition-colors hover:bg-neutral-50/50 sm:flex-row sm:items-center sm:gap-4 sm:px-6"
            >
              <div className="flex items-center gap-3.5">
                <ProviderLogo
                  providerId={provider.id}
                  name={provider.display_name}
                  className="size-8 rounded-lg"
                />
                <div className="flex items-center gap-2.5">
                  <span className="text-[15px] font-medium text-neutral-900">
                    {provider.display_name}
                  </span>
                  <span
                    className={`size-2 rounded-full ${
                      configured ? 'bg-emerald-500' : 'bg-neutral-300'
                    }`}
                    title={configured ? 'Credential configured' : 'Not configured'}
                  />
                </div>
              </div>

              <div className="flex w-full flex-wrap items-center justify-between gap-2.5 sm:w-auto sm:justify-end sm:gap-3">
                {configured ? (
                  <span className="rounded-full bg-emerald-50 px-3 py-1 font-mono text-[12.5px] text-emerald-800 ring-1 ring-emerald-200/70">
                    {credential?.preview ?? 'Configured'}
                  </span>
                ) : (
                  <span className="rounded-full bg-neutral-100 px-3 py-1 text-[12.5px] text-neutral-500">
                    Not configured
                  </span>
                )}

                <Button
                  variant="outline"
                  size="sm"
                  className="rounded-full bg-white px-4"
                  onClick={() => startEditing(provider)}
                >
                  {configured ? 'Rotate' : 'Configure'}
                </Button>

                {credential && (
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    className="rounded-full text-neutral-400 hover:bg-red-50 hover:text-red-600"
                    aria-label={`Remove ${provider.display_name} credential`}
                    onClick={() => deleteMutation.mutate(provider.id)}
                  >
                    <Trash2 className="size-4" />
                  </Button>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}
