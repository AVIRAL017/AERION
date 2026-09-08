import { apiClient } from './client';
import {
  APIEnvelope,
  User,
  TokenResponse,
  LoginPayload,
  RegisterPayload,
  Situation,
  SituationEvent,
  WeatherData,
  RouteOption,
  SituationReport,
  UsageSummary,
  HealthStatus,
} from '../types';

export const authApi = {
  login: async (payload: LoginPayload): Promise<APIEnvelope<TokenResponse>> => {
    // Backend expects { email, password }
    return apiClient.post<TokenResponse>('/auth/login', {
      email: payload.username,
      password: payload.password,
    });
  },

  register: async (payload: RegisterPayload): Promise<APIEnvelope<TokenResponse>> => {
    return apiClient.post<TokenResponse>('/auth/register', {
      email: payload.email,
      password: payload.password,
      organization_name: payload.full_name || 'AERION Operations',
      role: payload.role || 'operator',
    });
  },

  getMe: async (): Promise<APIEnvelope<User>> => {
    return apiClient.get<User>('/auth/me');
  },
};

export const situationsApi = {
  list: async (): Promise<APIEnvelope<Situation[]>> => {
    return apiClient.get<Situation[]>('/situations');
  },

  get: async (id: string): Promise<APIEnvelope<Situation>> => {
    return apiClient.get<Situation>(`/situations/${id}`);
  },

  getEvents: async (id: string): Promise<APIEnvelope<SituationEvent[]>> => {
    return apiClient.get<SituationEvent[]>(`/situations/${id}/events`);
  },

  getWeather: async (id: string): Promise<APIEnvelope<WeatherData>> => {
    return apiClient.get<WeatherData>(`/situations/${id}/weather`);
  },

  getRoutes: async (id: string): Promise<APIEnvelope<RouteOption[]>> => {
    return apiClient.get<RouteOption[]>(`/situations/${id}/routes`);
  },

  getReport: async (id: string): Promise<APIEnvelope<SituationReport>> => {
    return apiClient.get<SituationReport>(`/situations/${id}/report`);
  },
};

export const usageApi = {
  getSummary: async (): Promise<APIEnvelope<UsageSummary>> => {
    return apiClient.get<UsageSummary>('/usage/summary');
  },

  upgradeSubscription: async (tier: string): Promise<APIEnvelope<any>> => {
    return apiClient.post('/subscriptions/upgrade', { tier });
  },
};

export const systemApi = {
  getHealth: async (): Promise<APIEnvelope<HealthStatus>> => {
    return apiClient.get<HealthStatus>('/health');
  },

  getReady: async (): Promise<APIEnvelope<any>> => {
    return apiClient.get<any>('/ready');
  },
};
