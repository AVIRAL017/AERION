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
  AnalysisHistoryItem,
  AERIONAnalysisResultData,
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

  refreshToken: async (): Promise<APIEnvelope<TokenResponse>> => {
    return apiClient.post<TokenResponse>('/auth/refresh', {});
  },

  forgotPassword: async (email: string): Promise<APIEnvelope<{ message: string; delivery_status: string; reset_token?: string }>> => {
    return apiClient.post('/auth/forgot-password', { email });
  },

  resetPassword: async (payload: { token: string; new_password: string }): Promise<APIEnvelope<{ message: string }>> => {
    return apiClient.post('/auth/reset-password', payload);
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

  getWeather: async (id: string, latitude?: number, longitude?: number): Promise<APIEnvelope<WeatherData>> => {
    let url = `/situations/${id}/weather`;
    if (latitude !== undefined && longitude !== undefined) {
      url += `?latitude=${latitude}&longitude=${longitude}`;
    }
    return apiClient.get<WeatherData>(url);
  },

  getRoutes: async (id: string): Promise<APIEnvelope<RouteOption[]>> => {
    return apiClient.get<RouteOption[]>(`/situations/${id}/routes`);
  },

  getReport: async (id: string, analysisId?: string): Promise<APIEnvelope<SituationReport>> => {
    const qs = analysisId ? `?analysis_id=${encodeURIComponent(analysisId)}` : '';
    return apiClient.get<SituationReport>(`/situations/${id}/report${qs}`);
  },

  downloadReportUrl: (id: string, format: 'pdf' | 'json' = 'pdf', loc?: any, analysisId?: string): string => {
    const params = new URLSearchParams({ format });
    if (analysisId) params.append('analysis_id', analysisId);
    if (loc?.location_source) params.append('location_source', loc.location_source);
    if (loc?.location_precision) params.append('location_precision', loc.location_precision);
    if (loc?.location_method) params.append('location_method', loc.location_method);
    if (loc?.label) params.append('label', loc.label);
    return `/api/v1/situations/${id}/report/download?${params.toString()}`;
  },
};

export const geospatialApi = {
  resolveAdmin: async (latitude: number, longitude: number): Promise<any> => {
    return apiClient.get(`/geospatial/admin/resolve?latitude=${latitude}&longitude=${longitude}`);
  },

  resolveBorder: async (latitude: number, longitude: number): Promise<any> => {
    return apiClient.get(`/geospatial/border/resolve?latitude=${latitude}&longitude=${longitude}`);
  },
};

export const sheltersApi = {
  list: async (params?: { latitude?: number; longitude?: number; radius_km?: number }): Promise<any> => {
    const query = new URLSearchParams();
    if (params?.latitude !== undefined) query.append('latitude', params.latitude.toString());
    if (params?.longitude !== undefined) query.append('longitude', params.longitude.toString());
    if (params?.radius_km !== undefined) query.append('radius_km', params.radius_km.toString());
    const qs = query.toString();
    return apiClient.get(`/shelters${qs ? `?${qs}` : ''}`);
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

  getHistory: async (params?: {
    mode?: string;
    status?: string;
    limit?: number;
    offset?: number;
  }): Promise<APIEnvelope<AnalysisHistoryItem[]>> => {
    const query = new URLSearchParams();
    if (params?.mode) query.append('mode', params.mode);
    if (params?.status) query.append('status', params.status);
    if (params?.limit) query.append('limit', params.limit.toString());
    if (params?.offset) query.append('offset', params.offset.toString());
    const qs = query.toString();
    return apiClient.get<AnalysisHistoryItem[]>(`/analysis/history${qs ? `?${qs}` : ''}`);
  },

  getById: async (analysisId: string): Promise<APIEnvelope<AERIONAnalysisResultData>> => {
    return apiClient.get<AERIONAnalysisResultData>(`/analysis/${analysisId}`);
  },

  submitBorderJob: async (payload: {
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
    idempotency_key?: string;
  }): Promise<APIEnvelope<any>> => {
    return apiClient.post('/analysis/jobs/border', payload);
  },

  submitDisasterJob: async (payload: {
    before_image_path?: string;
    after_image_path?: string;
    before_base64?: string;
    after_base64?: string;
    threshold?: number;
    latitude?: number;
    longitude?: number;
    idempotency_key?: string;
  }): Promise<APIEnvelope<any>> => {
    return apiClient.post('/analysis/jobs/disaster', payload);
  },

  getJobStatus: async (jobId: string): Promise<APIEnvelope<any>> => {
    return apiClient.get(`/analysis/jobs/${jobId}`);
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

export const boundariesApi = {
  list: async (): Promise<APIEnvelope<any[]>> => {
    return apiClient.get<any[]>('/boundaries');
  },

  getById: async (boundaryId: string): Promise<APIEnvelope<any>> => {
    return apiClient.get<any>(`/boundaries/${boundaryId}`);
  },

  evaluate: async (boundaryId: string, payload: {
    evidence_points?: Array<{ latitude: number; longitude: number; point_id?: string; weight?: number }>;
    sensor_coverage_ratio?: number;
    terrain_type?: string;
  }): Promise<APIEnvelope<any>> => {
    return apiClient.post(`/boundaries/${boundaryId}/evaluate`, payload);
  },
};


