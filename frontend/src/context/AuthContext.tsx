import React, { createContext, useContext, useEffect, useState } from 'react';
import { User, LoginPayload, RegisterPayload } from '../types';
import { authApi } from '../api';

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (payload: LoginPayload) => Promise<boolean>;
  register: (payload: RegisterPayload) => Promise<boolean>;
  logout: () => void;
  error: string | null;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const restoreSession = async () => {
      const token = localStorage.getItem('aerion_access_token');
      if (token) {
        try {
          const res = await authApi.getMe();
          if (res.success && res.data) {
            setUser(res.data);
          } else {
            localStorage.removeItem('aerion_access_token');
          }
        } catch {
          localStorage.removeItem('aerion_access_token');
        }
      }
      setIsLoading(false);
    };

    restoreSession();
  }, []);

  const login = async (payload: LoginPayload): Promise<boolean> => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await authApi.login(payload);
      if (res.success && res.data) {
        localStorage.setItem('aerion_access_token', res.data.access_token);
        if ((res.data as any).user) {
          setUser((res.data as any).user);
        } else {
          const meRes = await authApi.getMe();
          if (meRes.success && meRes.data) {
            setUser(meRes.data);
          }
        }
        setIsLoading(false);
        return true;
      } else {
        setError(res.error || 'Authentication failed');
        setIsLoading(false);
        return false;
      }
    } catch (err: any) {
      setError(err.message || 'Login failed');
      setIsLoading(false);
      return false;
    }
  };

  const register = async (payload: RegisterPayload): Promise<boolean> => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await authApi.register(payload);
      if (res.success && res.data) {
        localStorage.setItem('aerion_access_token', res.data.access_token);
        if ((res.data as any).user) {
          setUser((res.data as any).user);
        } else {
          const meRes = await authApi.getMe();
          if (meRes.success && meRes.data) {
            setUser(meRes.data);
          }
        }
        setIsLoading(false);
        return true;
      } else {
        setError(res.error || 'Registration failed');
        setIsLoading(false);
        return false;
      }
    } catch (err: any) {
      setError(err.message || 'Registration error');
      setIsLoading(false);
      return false;
    }
  };

  const logout = () => {
    localStorage.removeItem('aerion_access_token');
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        login,
        register,
        logout,
        error,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
