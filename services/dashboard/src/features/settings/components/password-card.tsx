import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { toast } from 'sonner'

import { authApi } from '../../../shared/lib/api'
import { Button, Input, Label } from '@/components/ui'

export function PasswordCard() {
  const [setupToken, setSetupToken] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: () =>
      authApi.resetPassword(
        {
          new_password: newPassword,
          confirm_password: confirmPassword,
        },
        setupToken.trim(),
      ),
    onSuccess: () => {
      setSetupToken('')
      setNewPassword('')
      setConfirmPassword('')
      setError(null)
      toast.success('Password updated')
    },
    onError: (err) => {
      setError(err instanceof Error ? err.message : 'Password update failed')
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    if (newPassword.length < 12) {
      setError('Password must be at least 12 characters.')
      return
    }
    if (newPassword !== confirmPassword) {
      setError('Passwords do not match.')
      return
    }
    if (setupToken.trim().length < 32) {
      setError('Enter the setup token from AUTAGE_SETUP_TOKEN.')
      return
    }

    mutation.mutate()
  }

  return (
    <section className="overflow-hidden rounded-2xl border border-neutral-200/80 bg-white">
      <div className="border-b border-neutral-100 px-4 py-4 sm:px-6 sm:py-5">
        <h2 className="text-[16px] font-semibold text-neutral-900">Password</h2>
        <p className="mt-1 text-[14px] text-neutral-500">
          Change the administrator password using the setup token from your deployment.
        </p>
      </div>

      <form
        onSubmit={handleSubmit}
        className="max-w-xl space-y-3 px-4 py-4 sm:px-6 sm:py-5"
      >
        <div className="space-y-1.5">
          <Label htmlFor="settings-setup-token" className="text-xs text-neutral-700">
            Setup token
          </Label>
          <Input
            id="settings-setup-token"
            type="password"
            autoComplete="off"
            required
            placeholder="From AUTAGE_SETUP_TOKEN in .env"
            value={setupToken}
            onChange={(e) => setSetupToken(e.target.value)}
            className="h-8 bg-white font-mono text-xs"
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="settings-new-password" className="text-xs text-neutral-700">
            New password
          </Label>
          <Input
            id="settings-new-password"
            type="password"
            autoComplete="new-password"
            required
            placeholder="At least 12 characters"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            className="h-8 bg-white text-xs"
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="settings-confirm-password" className="text-xs text-neutral-700">
            Confirm new password
          </Label>
          <Input
            id="settings-confirm-password"
            type="password"
            autoComplete="new-password"
            required
            placeholder="Repeat the new password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            className="h-8 bg-white text-xs"
          />
        </div>

        {error && (
          <p className="rounded-md border border-red-200/80 bg-red-50/60 px-3 py-2 text-xs text-red-700">
            {error}
          </p>
        )}

        <Button type="submit" disabled={mutation.isPending} className="h-8 text-xs">
          {mutation.isPending ? 'Updating password…' : 'Update password'}
        </Button>
      </form>
    </section>
  )
}
