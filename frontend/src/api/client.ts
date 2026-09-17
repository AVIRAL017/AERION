import { APIEnvelope } from '../types';

const API_BASE = '/api/v1';

// Shared singleton refresh promise to prevent duplicate concurrent refresh executions
let isRefreshingPromise: Promise<string | null> | null = null;

interface ExtendedRequestInit extends RequestInit {
  _retry?: boolean;
}

class APIClient {
  private getAuthHeader(): Record<string, string> {
    const token = typeof localStorage !== 'undefined' ? localStorage.getItem('aerion_access_token') : null;
    return token ? { Authorization: `Bearer ${token}` } : {};
  }

  async request<T>(
    endpoint: string,
    options: ExtendedRequestInit = {}
  ): Promise<APIEnvelope<T>> {
    const url = `${API_BASE}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...this.getAuthHeader(),
      ...((options.headers as Record<string, string>) || {}),
    };

    try {
      const response = await fetch(url, {
        ...options,
        headers,
      });

      // BUG-031: 401 Authentication & Session Refresh Interceptor
      if (response.status === 401) {
        const isAuthEndpoint =
          endpoint.includes('/auth/login') ||
          endpoint.includes('/auth/refresh') ||
          endpoint.includes('/auth/register') ||
          endpoint.includes('/auth/reset-password');
        const isRetry = Boolean(options._retry);
        const hasToken = typeof localStorage !== 'undefined' && Boolean(localStorage.getItem('aerion_access_token'));

        // If not already retrying, not an auth endpoint, and a token exists, attempt refresh
        if (!isRetry && !isAuthEndpoint && hasToken) {
          if (!isRefreshingPromise) {
            isRefreshingPromise = (async () => {
              try {
                const currentToken = localStorage.getItem('aerion_access_token');
                const refHeaders: Record<string, string> = {
                  'Content-Type': 'application/json',
                };
                if (currentToken) {
                  refHeaders['Authorization'] = `Bearer ${currentToken}`;
                }

                const refResponse = await fetch(`${API_BASE}/auth/refresh`, {
                  method: 'POST',
                  headers: refHeaders,
                  body: JSON.stringify({}),
                });

                if (!refResponse.ok) {
                  return null;
                }

                const refData = await refResponse.json();
                const newToken = refData?.data?.access_token || refData?.access_token;
                if (typeof newToken === 'string' && newToken.length > 0) {
                  localStorage.setItem('aerion_access_token', newToken);
                  return newToken;
                }
                return null;
              } catch {
                return null;
              } finally {
                isRefreshingPromise = null;
              }
            })();
          }

          const freshToken = await isRefreshingPromise;

          if (freshToken) {
            // Token successfully renewed; retry original request once with new token
            const retryHeaders = {
              ...headers,
              Authorization: `Bearer ${freshToken}`,
            };
            return this.request<T>(endpoint, {
              ...options,
              headers: retryHeaders,
              _retry: true,
            });
          } else {
            // Refresh failed: clear credentials, terminate session, trigger login redirection
            localStorage.removeItem('aerion_access_token');
            localStorage.removeItem('aerion_user');
            if (typeof window !== 'undefined') {
              window.dispatchEvent(new CustomEvent('aerion:unauthorized'));
            }
          }
        } else if (hasToken || endpoint.includes('/auth/me')) {
          // Token expired or invalid and cannot be refreshed; clear session
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
