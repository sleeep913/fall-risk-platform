export type UserRole = 'admin' | 'caregiver' | 'family'

export interface User {
  id: number
  username: string
  display_name: string
  role: UserRole
  is_active: boolean
  created_at: string
}

export interface LoginPayload {
  username: string
  password: string
}

export interface TokenResponse {
  access_token: string
  token_type: 'bearer'
  expires_in: number
  user: User
}

