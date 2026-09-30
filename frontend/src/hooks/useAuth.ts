import { useState, useCallback } from 'react';
import { authService } from '../services/authService';
import { storage } from '../utils/storage';
import type { AuthState } from '../types';

export function useAuth() {
  const [state, setState] = useState<AuthState>({
    user: storage.getUser(),
    tokens: storage.getAccessToken()
      ? { access: storage.getAccessToken()!, refresh: storage.getRefreshToken() || '' }
      : null,
    isAuthenticated: !!storage.getAccessToken(),
    isLoading: false,
  });

  const login = useCallback(async (email: string, password: string) => {
    setState(s => ({ ...s, isLoading: true }));
    try {
      const data = await authService.login(email, password);
      setState({
        user: data.user,
        tokens: { access: data.access, refresh: data.refresh },
        isAuthenticated: true,
        isLoading: false,
      });
      return data;
    } catch (err) {
      setState(s => ({ ...s, isLoading: false }));
      throw err;
    }
  }, []);

  const logout = useCallback(async () => {
    setState(s => ({ ...s, isLoading: true }));
    await authService.logout();
    setState({ user: null, tokens: null, isAuthenticated: false, isLoading: false });
  }, []);

  return { ...state, login, logout };
}
