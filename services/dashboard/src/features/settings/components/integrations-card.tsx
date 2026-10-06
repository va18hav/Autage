import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { KeyRound, Trash2 } from 'lucide-react'
import { toast } from 'sonner'

import { credentialApi, providerApi } from '../../../shared/lib/api'
import { queryKeys } from '../../../shared/lib/query-client'
import type { Provider } from '../../../shared/types/settings'
import { Badge, Button, Card, CardContent, CardHeader, CardTitle, Input, Label } from '@/components/ui'

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
    return <Card className="animate-pulse bg-neutral-200/40" />
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Integrations</CardTitle>
        <p className="text-sm text-muted-foreground">
          API keys are encrypted at rest and never returned by the API — only a
          masked preview is shown.
        </p>
      </CardHeader>
      <CardContent className="space-y-2">
        {providers.map((provider) => {
          const credential = credentialByPurpose[provider.id]
          const configured = provider.credential_configured
          const isEditing = editing === provider.id

          if (isEditing) {
            const secretFields = provider.credential_fields.filter((f) => f.is_secret)
            const plainFields = provider.credential_fields.filter((f) => !f.is_secret)
            return (
              <div
                key={provider.id}
                className="rounded-lg border border-neutral-900/15 bg-neutral-50/60 px-3.5 py-3"
              >
                <div className="flex items-center gap-2 pb-2">
                  <KeyRound className="size-4 text-muted-foreground" />
                  <span className="text-sm font-medium">{provider.display_name}</span>
                </div>
                <div className="space-y-2">
                  {secretFields.map((field) => (
                    <div key={field.name} className="space-y-1">
                      <Label className="text-xs text-muted-foreground">
                        {field.label}
                      </Label>
                      <Input
                        type="password"
                        autoComplete="new-password"
                        value={values[field.name] ?? ''}
                        placeholder={credential ? 'Enter new key to rotate' : 'Required'}
                        onChange={(e) =>
                          setValues((prev) => ({
                            ...prev,
                            [field.name]: e.target.value,
                          }))
                        }
                        className="h-9 bg-white"
                      />
                    </div>
                  ))}
                  {plainFields.map((field) => (
                    <div key={field.name} className="space-y-1">
                      <Label className="text-xs text-muted-foreground">
                        {field.label}
                      </Label>
                      <Input
                        value={values[field.name] ?? ''}
                        placeholder={field.default ?? ''}
                        onChange={(e) =>
                          setValues((prev) => ({
                            ...prev,
                            [field.name]: e.target.value,
                          }))
                        }
                        className="h-9 bg-white"
                      />
                    </div>
                  ))}
                </div>
                <div className="flex items-center justify-end gap-2 pt-3">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setEditing(null)}
                  >
                    Cancel
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={testMutation.isPending}
                    onClick={() =>
                      testMutation.mutate({ purpose: provider.id, fields: values })
                    }
                  >
                    {testMutation.isPending ? 'Testing…' : 'Verify'}
                  </Button>
                  <Button
                    size="sm"
                    disabled={saveMutation.isPending}
                    onClick={() =>
                      saveMutation.mutate({
                        purpose: provider.id,
                        fields: values,
                      })
                    }
                  >
                    {saveMutation.isPending ? 'Saving…' : 'Save'}
                  </Button>
                </div>
              </div>
            )
          }

          return (
            <div
              key={provider.id}
              className="flex items-center gap-3 rounded-lg border px-3.5 py-2.5"
            >
              <KeyRound className="size-4 text-muted-foreground" />
              <span className="text-sm font-medium">{provider.display_name}</span>
              <div className="ml-auto flex items-center gap-2">
                {configured ? (
                  <Badge variant="outline" className="border-emerald-200 bg-emerald-50 text-emerald-700">
                    {credential?.preview ?? 'configured'}
                  </Badge>
                ) : (
                  <Badge variant="outline" className="text-muted-foreground">
                    not set
                  </Badge>
                )}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => startEditing(provider)}
                >
                  {configured ? 'Update' : 'Add key'}
                </Button>
                {credential && (
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    aria-label={`Remove ${provider.display_name} credential`}
                    onClick={() => deleteMutation.mutate(provider.id)}
                  >
                    <Trash2 className="size-3.5 text-muted-foreground" />
                  </Button>
                )}
              </div>
            </div>
          )
        })}
      </CardContent>
    </Card>
  )
}
