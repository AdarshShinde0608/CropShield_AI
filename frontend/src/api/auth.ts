import api from "./client";
import type {
  LoginRequest,
  ProfileUpdateRequest,
  RegisterRequest,
  TokenResponse,
  User
} from "../types/api";

export async function login(request: LoginRequest): Promise<TokenResponse> {
  const response = await api.post<TokenResponse>("/auth/login", request);
  return response.data;
}

export async function register(request: RegisterRequest): Promise<TokenResponse> {
  const response = await api.post<TokenResponse>("/auth/register", request);
  return response.data;
}

export async function getCurrentUser(): Promise<User> {
  const response = await api.get<User>("/auth/me");
  return response.data;
}

export async function updateProfile(request: ProfileUpdateRequest): Promise<User> {
  const response = await api.patch<User>("/auth/me", request);
  return response.data;
}