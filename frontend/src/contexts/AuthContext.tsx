import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from 'react';
import { authService } from '../services/authService';
import { storage } from '../utils/storage';
import type { User, AuthState } from '../types';

interface AuthContextType extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: storage.getUser(),
    tokens: storage.getAccessToken()
      ? { access: storage.getAccessToken()!, refresh: storage.getRefreshToken() || '' }
      : null,
    isAuthenticated: !!storage.getAccessToken(),
    isLoading: true,
  });

  useEffect(() => {
    const token = storage.getAccessToken();
    if (token) {
      authService
        .getCurrentUser()
        .then((user: User) => {
          storage.setUser(user);
          setState(s => ({ ...s, user, isAuthenticated: true, isLoading: false }));
        })
        .catch(() => {
          storage.clear();
          setState({ user: null, tokens: null, isAuthenticated: false, isLoading: false });
        });
    } else {
      setState(s => ({ ...s, isLoading: false }));
    }
  }, []);

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
    } catch (err) {
      setState(s => ({ ...s, isLoading: false }));
      throw err;
    }
  }, []);

  const logout = useCallback(async () => {
    await authService.logout();
    setState({ user: null, tokens: null, isAuthenticated: false, isLoading: false });
  }, []);

  return (
    <AuthContext.Provider value={{ ...state, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuthContext() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuthContext must be used within AuthProvider');
  return ctx;
}
