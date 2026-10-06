export type ModelTier = 'fast' | 'balanced' | 'frontier'

export interface ProviderModel {
  id: string
  label: string
  tier: ModelTier
}

export interface CredentialField {
  name: string
  label: string
  is_secret: boolean
  required: boolean
  default: string | null
}

export interface Provider {
  id: string
  display_name: string
  models: ProviderModel[]
  credential_fields: CredentialField[]
  credential_configured: boolean
  credential_preview: string | null
}

export interface StepKeyInfo {
  key: string
  label: string
}

export interface ProviderCatalog {
  providers: Provider[]
  steps: StepKeyInfo[]
}

export interface StepConfig {
  step_key: string
  provider_id: string
  model_id: string
  temperature: number | null
  max_output_tokens: number | null
  is_default: boolean
  credential_configured: boolean
}

export interface StepConfigUpdate {
  step_key: string
  provider_id: string
  model_id: string
  temperature: number | null
  max_output_tokens: number | null
}

export interface Credential {
  purpose: string
  preview: string | null
  created_at: string
  updated_at: string
}

export interface TestCredentialResult {
  ok: boolean
  provider: string | null
  model: string | null
  message: string
}
