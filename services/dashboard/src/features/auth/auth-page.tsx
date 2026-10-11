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

  const [name, setName] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: async () => {
      if (isSetup) {
        return authApi.register({
          name: name.trim(),
          username: username.trim().toLowerCase(),
          password,
        })
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

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    if (isSetup && name.trim().length < 1) {
      setError('Please enter your name.')
      return
    }
    if (username.trim().length < 2) {
      setError('Username must be at least 2 characters.')
      return
    }
    if (isSetup && password.length < 6) {
      setError('Password must be at least 6 characters.')
      return
    }
    mutation.mutate()
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-[#FAFAFA] px-4 antialiased selection:bg-neutral-900 selection:text-white">
      <div className="w-full max-w-[360px]">
        <div className="mb-6 flex flex-col items-start">
          <BrandLogo iconClassName="size-8" textClassName="text-[20px]" />

          <h1 className="mt-4 text-lg font-semibold tracking-tight text-neutral-950">
            {isSetup ? 'Initialize workspace' : 'Sign in to your workspace'}
          </h1>
          <p className="mt-1 text-xs leading-relaxed text-neutral-500">
            {isSetup
              ? 'No user account found. Create the owner account for this instance.'
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

          <div className="space-y-1.5">
            <Label htmlFor="auth-password" className="text-xs text-neutral-700">
              Password
            </Label>
            <Input
              id="auth-password"
              type="password"
              autoComplete={isSetup ? 'new-password' : 'current-password'}
              required
              placeholder={isSetup ? 'At least 6 characters' : '••••••••'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="h-8 bg-white text-xs"
            />
          </div>

          {error && (
            <p className="rounded-md border border-red-200/80 bg-red-50/60 px-3 py-2 text-xs text-red-700">
              {error}
            </p>
          )}

          <Button
            type="submit"
            disabled={mutation.isPending}
            className="h-8 w-full text-xs"
          >
            {mutation.isPending
              ? isSetup
                ? 'Creating account…'
                : 'Signing in…'
              : isSetup
                ? 'Create account'
                : 'Sign in'}
          </Button>
        </form>
      </div>
    </div>
  )
}
