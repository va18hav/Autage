export interface AuthUser {
  id: string
  username: string
  name: string
  created_at: string
}

export interface AuthStatus {
  initialized: boolean
  authenticated: boolean
  user: AuthUser | null
}

export interface RegisterPayload {
  name: string
  username: string
  password: string
}

export interface LoginPayload {
  username: string
  password: string
}

export interface PasswordResetPayload {
  new_password: string
  confirm_password: string
}
