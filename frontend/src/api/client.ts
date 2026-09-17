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
        // Only invalidate the session if the request actually sent an Authorization header
        // and failed with 401, or if it was an explicit profile verification endpoint (/auth/me).
        const hasAuthHeader = Boolean(headers['Authorization']);
        const isAuthMe = endpoint.includes('/auth/me');
        if (hasAuthHeader || isAuthMe) {
          localStorage.removeItem('aerion_access_token');
          localStorage.removeItem('aerion_user');
          if (typeof window !== 'undefined') {
            window.dispatchEvent(new CustomEvent('aerion:unauthorized'));
          }
        }
      }

      const contentType = response.headers.get('content-type') || '';
      const requestId = response.headers.get('x-request-id') || undefined;
      const text = await response.text();

      let json: any = null;
      if (text && text.trim().length > 0) {
        if (contentType.includes('application/json') || text.trim().startsWith('{') || text.trim().startsWith('[')) {
          try {
            json = JSON.parse(text);
          } catch {
            json = null;
          }
        }
      }

      if (!response.ok) {
        let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
        if (json && typeof json === 'object') {
          if (typeof json.error === 'object' && json.error?.message) {
            errorMessage = json.error.message;
          } else if (json.error && typeof json.error === 'string') {
            errorMessage = json.error;
          } else if (json.detail) {
            errorMessage = typeof json.detail === 'string' ? json.detail : JSON.stringify(json.detail);
          } else if (json.message) {
            errorMessage = json.message;
          }
        } else if (text && text.trim().length > 0 && text.length < 300) {
          errorMessage = text.trim();
        }

        return {
          success: false,
          data: null as any,
          meta: requestId ? { request_id: requestId } : {},
          error: errorMessage,
        };
      }

      // Backend envelope wraps response as { success, data, meta }
      if (json && typeof json === 'object' && 'data' in json) {
        return json as APIEnvelope<T>;
      }

      // Direct response fallback
      return {
        success: true,
        data: (json !== null ? json : text) as T,
        meta: requestId ? { request_id: requestId } : {},
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
