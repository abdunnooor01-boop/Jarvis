export interface User {
  email: string
  displayName: string
}

export interface AuthResponse {
  token: string
  user: User
}
