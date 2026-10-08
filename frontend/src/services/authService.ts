import api from './api';
import { storage } from '../utils/storage';
import type { User, AuthTokens } from '../types';

interface LoginResponse {
  access: string;
  refresh: string;
  user: User;
}

export const authService = {
  login: async (email: string, password: string): Promise<LoginResponse> => {
    const { data } = await api.post<LoginResponse>('/auth/login/', { email, password });
    storage.setTokens(data.access, data.refresh);
    storage.setUser(data.user);
    return data;
  },

  logout: async (): Promise<void> => {
    try {
      await api.post('/auth/logout/');
    } finally {
      storage.clear();
    }
  },

  getCurrentUser: async (): Promise<User> => {
    const { data } = await api.get<User>('/auth/me/');
    return data;
  },

  refreshToken: async (refresh: string): Promise<AuthTokens> => {
    const { data } = await api.post<AuthTokens>('/auth/token/refresh/', { refresh });
    return data;
  },

  changePassword: async (
    currentPassword: string, newPassword: string, confirmPassword: string,
  ): Promise<{ detail: string }> => {
    const { data } = await api.post<{ detail: string }>('/auth/change-password/', {
      current_password: currentPassword,
      new_password: newPassword,
      confirm_password: confirmPassword,
    });
    return data;
  },
};
