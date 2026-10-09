export interface AuthUser {
  id: number;
  email: string;
  display_name: string;
}

export interface AuthResponse {
  user: AuthUser;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface RegistrationCredentials extends LoginCredentials {
  display_name: string;
}
