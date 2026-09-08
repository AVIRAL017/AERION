import { APIEnvelope } from '../types';

const API_BASE = '/api/v1';

class APIClient {
  private getAuthHeader(): Record<string, string> {
    const token = localStorage.getItem('aerion_access_token');
    return token ? { Authorization: `Bearer ${token}` } : {};
  }

  async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<APIEnvelope<T>> {
    const url = `${API_BASE}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...this.getAuthHeader(),
      ...(options.headers as Record<string, string> || {}),
    };

    try {
      const response = await fetch(url, {
        ...options,
        headers,
      });

      if (response.status === 401) {
        // Clear invalid token
        localStorage.removeItem('aerion_access_token');
        localStorage.removeItem('aerion_user');
      }

      const json = await response.json();

      if (!response.ok) {
        throw new Error(json.detail || json.message || `HTTP ${response.status}: ${response.statusText}`);
      }

      // Backend envelope wraps response as { success, data, meta }
      if (json && typeof json === 'object' && 'data' in json) {
        return json as APIEnvelope<T>;
      }

      // Direct response fallback
      return {
        success: true,
        data: json as T,
        meta: {},
      };
    } catch (err: any) {
      return {
        success: false,
        data: null as any,
        meta: {},
        error: err.message || 'Network request failed',
      };
    }
  }

  get<T>(endpoint: string, options?: RequestInit) {
    return this.request<T>(endpoint, { ...options, method: 'GET' });
  }

  post<T>(endpoint: string, body?: any, options?: RequestInit) {
    return this.request<T>(endpoint, {
      ...options,
      method: 'POST',
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  put<T>(endpoint: string, body?: any, options?: RequestInit) {
    return this.request<T>(endpoint, {
      ...options,
      method: 'PUT',
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  delete<T>(endpoint: string, options?: RequestInit) {
    return this.request<T>(endpoint, { ...options, method: 'DELETE' });
  }
}

export const apiClient = new APIClient();
