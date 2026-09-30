import axios from 'axios';
import { storage } from '../utils/storage';

// In dev, Vite proxies '/api' to the backend. In production (e.g. Railway) set
// VITE_API_URL to the backend's public URL, e.g.
//   https://<backend>.up.railway.app/api
const API_BASE = import.meta.env.VITE_API_URL || '/api';

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use((config) => {
  const token = storage.getAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      const refreshToken = storage.getRefreshToken();
      if (refreshToken) {
        try {
          const { data } = await axios.post('/api/auth/token/refresh/', {
            refresh: refreshToken,
          });
          storage.setTokens(data.access, storage.getRefreshToken() || '');
          originalRequest.headers.Authorization = `Bearer ${data.access}`;
          return api(originalRequest);
        } catch {
          storage.clear();
          window.location.href = '/login';
        }
      } else {
        storage.clear();
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

// Base URL for raw fetch() calls (file downloads/exports) that bypass axios.
export const apiBaseUrl = API_BASE;

export default api;
