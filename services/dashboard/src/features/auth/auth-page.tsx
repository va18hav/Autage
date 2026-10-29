import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { BrandLogo } from '../../shared/components/brand-logo'
import { authApi } from '../../shared/lib/api'
import { queryKeys } from '../../shared/lib/query-client'
import { Button, Input, Label } from '@/components/ui'

interface AuthPageProps {
  mode: 'setup' | 'login'
}

export function AuthPage({ mode }: AuthPageProps) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const isSetup = mode === 'setup'
  const [forgot, setForgot] = useState(false)
  const isForgot = mode === 'login' && forgot

  const [name, setName] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [setupToken, setSetupToken] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [info, setInfo] = useState<string | null>(null)

  const authMutation = useMutation({
    mutationFn: async () => {
      if (isSetup) {
        return authApi.register(
          {
            name: name.trim(),
            username: username.trim().toLowerCase(),
            password,
          },
          setupToken.trim(),
        )
      }
      return authApi.login({
        username: username.trim().toLowerCase(),
        password,
      })
    },
    onSuccess: (user) => {
      queryClient.setQueryData(queryKeys.auth.status(), {
        initialized: true,
        authenticated: true,
        user,
      })
      if (isSetup) {
        navigate('/onboarding', { replace: true })
      }
    },
    onError: (err) => {
      setError(err instanceof Error ? err.message : 'Authentication failed')
    },
  })

  const resetMutation = useMutation({
    mutationFn: () =>
      authApi.resetPassword(
        {
          new_password: password,
          confirm_password: confirmPassword,
        },
        setupToken.trim(),
      ),
    onSuccess: () => {
      setForgot(false)
      setPassword('')
      setConfirmPassword('')
      setSetupToken('')
      setError(null)
      setInfo('Password updated. Sign in with your new password.')
    },
    onError: (err) => {
      setError(err instanceof Error ? err.message : 'Password reset failed')
    },
  })

  const showForgot = () => {
    setForgot(true)
    setPassword('')
    setConfirmPassword('')
    setSetupToken('')
    setError(null)
    setInfo(null)
  }

  const showLogin = () => {
    setForgot(false)
    setPassword('')
    setConfirmPassword('')
    setSetupToken('')
    setError(null)
    setInfo(null)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setInfo(null)

    if (isForgot) {
      if (password.length < 12) {
        setError('Password must be at least 12 characters.')
        return
      }
      if (password !== confirmPassword) {
        setError('Passwords do not match.')
        return
      }
      if (setupToken.trim().length < 32) {
        setError('Enter the setup token from AUTAGE_SETUP_TOKEN.')
        return
      }
      resetMutation.mutate()
      return
    }

    if (isSetup && name.trim().length < 1) {
      setError('Please enter your name.')
      return
    }
    if (username.trim().length < 2) {
      setError('Username must be at least 2 characters.')
      return
    }
    if (isSetup && password.length < 12) {
      setError('Password must be at least 12 characters.')
      return
    }
    if (isSetup && setupToken.trim().length < 32) {
      setError('Enter the setup token from AUTAGE_SETUP_TOKEN.')
      return
    }
    authMutation.mutate()
  }

  const isPending = authMutation.isPending || resetMutation.isPending

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-[#FAFAFA] px-4 antialiased selection:bg-neutral-900 selection:text-white">
      <div className="w-full max-w-[360px]">
        <div className="mb-6 flex flex-col items-start">
          <BrandLogo iconClassName="size-8" textClassName="text-[20px]" />

          <h1 className="mt-4 text-lg font-semibold tracking-tight text-neutral-950">
            {isSetup
              ? 'Initialize workspace'
              : isForgot
                ? 'Reset password'
                : 'Sign in to your workspace'}
          </h1>
          <p className="mt-1 text-xs leading-relaxed text-neutral-500">
            {isSetup
              ? 'No user account found. Create the owner account for this instance.'
              : isForgot
                ? 'Enter the setup token from AUTAGE_SETUP_TOKEN and choose a new password.'
                : 'Enter your credentials to access the workspace.'}
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="space-y-4 rounded-lg border border-neutral-200/80 bg-white p-5 shadow-[0_1px_2px_rgba(0,0,0,0.03)]"
        >
          {isSetup && (
            <div className="space-y-1.5">
              <Label htmlFor="auth-name" className="text-xs text-neutral-700">
                Name
              </Label>
              <Input
                id="auth-name"
                type="text"
                autoComplete="name"
                autoFocus
                required
                placeholder="Alex Rivera"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="h-8 bg-white text-xs"
              />
            </div>
          )}

          {!isForgot && (
            <div className="space-y-1.5">
              <Label htmlFor="auth-username" className="text-xs text-neutral-700">
                Username
              </Label>
              <Input
                id="auth-username"
                type="text"
                autoComplete="username"
                autoFocus={!isSetup}
                required
                placeholder="alex"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="h-8 bg-white font-mono text-xs"
              />
            </div>
          )}

          <div className="space-y-1.5">
            <Label htmlFor="auth-password" className="text-xs text-neutral-700">
              {isSetup || isForgot ? 'New password' : 'Password'}
            </Label>
            <Input
              id="auth-password"
              type="password"
              autoComplete={isSetup || isForgot ? 'new-password' : 'current-password'}
              required
              placeholder={isSetup || isForgot ? 'At least 12 characters' : '••••••••'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="h-8 bg-white text-xs"
            />
          </div>

          {isForgot && (
            <div className="space-y-1.5">
              <Label htmlFor="auth-confirm-password" className="text-xs text-neutral-700">
                Confirm new password
              </Label>
              <Input
                id="auth-confirm-password"
                type="password"
                autoComplete="new-password"
                required
                placeholder="Repeat the new password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="h-8 bg-white text-xs"
              />
            </div>
          )}

          {(isSetup || isForgot) && (
            <div className="space-y-1.5">
              <Label htmlFor="auth-setup-token" className="text-xs text-neutral-700">
                Setup token
              </Label>
              <Input
                id="auth-setup-token"
                type="password"
                autoComplete="off"
                autoFocus={isForgot}
                required
                placeholder="From AUTAGE_SETUP_TOKEN in .env"
                value={setupToken}
                onChange={(e) => setSetupToken(e.target.value)}
                className="h-8 bg-white font-mono text-xs"
              />
            </div>
          )}

          {info && (
            <p className="rounded-md border border-emerald-200/80 bg-emerald-50/60 px-3 py-2 text-xs text-emerald-700">
              {info}
            </p>
          )}

          {error && (
            <p className="rounded-md border border-red-200/80 bg-red-50/60 px-3 py-2 text-xs text-red-700">
              {error}
            </p>
          )}

          <Button type="submit" disabled={isPending} className="h-8 w-full text-xs">
            {isPending
              ? isForgot
                ? 'Updating password…'
                : isSetup
                  ? 'Creating account…'
                  : 'Signing in…'
              : isForgot
                ? 'Update password'
                : isSetup
                  ? 'Create account'
                  : 'Sign in'}
          </Button>

          {mode === 'login' && (
            <div className="text-center">
              <Button
                type="button"
                variant="link"
                size="sm"
                onClick={isForgot ? showLogin : showForgot}
                className="h-auto p-0 text-xs text-neutral-500 hover:text-neutral-900"
              >
                {isForgot ? 'Back to sign in' : 'Forgot password?'}
              </Button>
            </div>
          )}
        </form>
      </div>
    </div>
  )
}
