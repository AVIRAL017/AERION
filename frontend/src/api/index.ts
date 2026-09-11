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

  googleLogin: async (idToken: string): Promise<APIEnvelope<TokenResponse>> => {
    return apiClient.post<TokenResponse>('/auth/google', {
      id_token: idToken,
    });
  },

  logout: async (): Promise<APIEnvelope<{ message: string }>> => {
    return apiClient.post<{ message: string }>('/auth/logout', {});
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

export const analysisApi = {
  analyzeImage: async (payload: {
    image_base64?: string;
    image_path?: string;
    source_type?: string;
    mode?: string;
    drone_model?: string;
    confidence_threshold?: number;
    iou_threshold?: number;
    terrain_context?: string;
    run_intelligence?: boolean;
  }): Promise<APIEnvelope<any>> => {
    return apiClient.post('/analysis/image', payload);
  },

  analyzeDamage: async (payload: {
    before_base64?: string;
    after_base64?: string;
    before_image_path?: string;
    after_image_path?: string;
    threshold?: number;
    run_intelligence?: boolean;
  }): Promise<APIEnvelope<any>> => {
    return apiClient.post('/analysis/damage', payload);
  },

  analyzeBorderVideo: async (payload: {
    video_path?: string;
    video_base64?: string;
    project_id?: string;
    max_frames?: number;
    frame_stride?: number;
    terrain_context?: string;
  }): Promise<APIEnvelope<any>> => {
    return apiClient.post('/analysis/border/video', payload);
  },

  analyzeDisasterE2E: async (payload: {
    before_image_path?: string;
    after_image_path?: string;
    before_base64?: string;
    after_base64?: string;
    threshold?: number;
    latitude?: number;
    longitude?: number;
    evacuation_dest_lat?: number;
    evacuation_dest_lon?: number;
    radius_km?: number;
    run_intelligence?: boolean;
  }): Promise<APIEnvelope<any>> => {
    return apiClient.post('/analysis/disaster/e2e', payload);
  },

  analyzeBorderE2E: async (payload: {
    video_path?: string;
    video_base64?: string;
    image_path?: string;
    image_base64?: string;
    max_frames?: number;
    frame_stride?: number;
    terrain_context?: string;
    latitude?: number;
    longitude?: number;
    generate_annotated_video?: boolean;
    run_intelligence?: boolean;
  }): Promise<APIEnvelope<any>> => {
    return apiClient.post('/analysis/border/e2e', payload);
  },
};

export const externalApi = {
  getWeather: async (latitude: number, longitude: number, timestampUtc?: string): Promise<APIEnvelope<any>> => {
    const query = new URLSearchParams({
      latitude: latitude.toString(),
      longitude: longitude.toString(),
    });
    if (timestampUtc) query.append('timestamp_utc', timestampUtc);
    return apiClient.get(`/external/weather?${query.toString()}`);
  },

  getRoute: async (
    originLat: number,
    originLon: number,
    destLat: number,
    destLon: number,
    profile: string = 'driving-car'
  ): Promise<APIEnvelope<any>> => {
    const query = new URLSearchParams({
      origin_lat: originLat.toString(),
      origin_lon: originLon.toString(),
      dest_lat: destLat.toString(),
      dest_lon: destLon.toString(),
      profile,
    });
    return apiClient.get(`/external/route?${query.toString()}`);
  },

  forwardGeocode: async (queryText: string, limit: number = 1): Promise<APIEnvelope<any>> => {
    const query = new URLSearchParams({
      query: queryText,
      limit: limit.toString(),
    });
    return apiClient.get(`/external/geocode?${query.toString()}`);
  },

  reverseGeocode: async (latitude: number, longitude: number): Promise<APIEnvelope<any>> => {
    const query = new URLSearchParams({
      latitude: latitude.toString(),
      longitude: longitude.toString(),
    });
    return apiClient.get(`/external/reverse-geocode?${query.toString()}`);
  },
};

