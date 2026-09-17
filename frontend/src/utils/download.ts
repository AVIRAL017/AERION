/**
 * AERION — Authenticated Artifact & Report Downloader Utility (BUG-020)
 * Uses browser fetch() with Bearer token authentication to download binary blobs
 * without triggering HTTP 401s from raw unauthenticated <a> tags.
 */

import { API_BASE } from '../api/client';

export async function downloadAuthenticatedArtifact(
  url: string,
  filename: string
): Promise<void> {
  const token = localStorage.getItem('aerion_access_token');
  const headers: Record<string, string> = {};

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(url, {
    method: 'GET',
    headers,
  });

  if (!response.ok) {
    if (response.status === 401) {
      // Invalidate if authentication failed
      localStorage.removeItem('aerion_access_token');
      localStorage.removeItem('aerion_user');
      window.dispatchEvent(new CustomEvent('aerion:unauthorized'));
      throw new Error('Authentication expired. Please log in again.');
    }
    throw new Error(`Download failed: HTTP ${response.status} ${response.statusText}`);
  }

  const blob = await response.blob();
  const blobUrl = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = blobUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(blobUrl);
}

export async function downloadAuthenticatedReport(
  situationId: string,
  format: 'pdf' | 'json',
  locationContext?: {
    source?: string;
    precision?: string;
    method?: string;
    label?: string;
    state?: string;
    country?: string;
    relevant_border?: string;
    geofence_status?: string;
  },
  analysisId?: string
): Promise<void> {
  const params = new URLSearchParams({ format });
  if (analysisId) params.set('analysis_id', analysisId);
  if (locationContext) {
    if (locationContext.source) params.set('location_source', locationContext.source);
    if (locationContext.precision) params.set('location_precision', locationContext.precision);
    if (locationContext.method) params.set('location_method', locationContext.method);
    if (locationContext.label) params.set('label', locationContext.label);
    if (locationContext.state) params.set('state', locationContext.state);
    if (locationContext.country) params.set('country', locationContext.country);
    if (locationContext.relevant_border) params.set('relevant_border', locationContext.relevant_border);
    if (locationContext.geofence_status) params.set('geofence_status', locationContext.geofence_status);
  }

  const url = `${API_BASE}/situations/${situationId}/report/download?${params.toString()}`;
  const ident = analysisId ? analysisId.substring(0, 8) : situationId.substring(0, 8);
  const filename = `AERION_SITREP_${ident}.${format}`;
  await downloadAuthenticatedArtifact(url, filename);
}
