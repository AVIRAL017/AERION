export interface APIEnvelope<T> {
  success: boolean;
  data: T;
  meta: Record<string, any>;
  error?: string | null;
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: 'admin' | 'analyst' | 'operator' | 'viewer';
  tier: 'free' | 'pro' | 'enterprise';
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface LoginPayload {
  username: string; // OAuth2 standard form field or JSON email
  password: string;
}

export interface RegisterPayload {
  email: string;
  password: string;
  full_name: string;
  role?: string;
}

export interface DetectionTarget {
  id: string;
  track_id?: string;
  class_name: string;
  confidence: number;
  bbox: [number, number, number, number]; // [ymin, xmin, ymax, xmax] or [x1, y1, x2, y2]
  velocity?: number | null;
  heading?: number | null;
  threat_level?: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' | null;
}

export interface SituationEvent {
  id: string;
  situation_id: string;
  event_type: string;
  title: string;
  description?: string;
  severity: 'INFO' | 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  created_at: string;
  metadata?: Record<string, any>;
}

export interface WeatherData {
  temperature_c?: number;
  wind_speed_ms?: number;
  wind_direction_deg?: number;
  visibility_km?: number;
  precipitation_mm?: number;
  conditions?: string;
  status: 'AVAILABLE' | 'UNAVAILABLE';
}

export interface RouteOption {
  id: string;
  name: string;
  type: 'SAFEST_FEASIBLE' | 'FASTEST_FEASIBLE' | 'STANDARD';
  distance_km: number;
  duration_min: number;
  hazard_clearance_score?: number;
  is_viable: boolean;
  waypoints?: [number, number][];
}

export interface ShelterData {
  id: string;
  name: string;
  location: [number, number];
  capacity: number;
  current_occupancy: number;
  status: 'OPEN' | 'FULL' | 'CLOSED';
  services: string[];
}

export interface DamageSummary {
  damage_percentage: number;
  damaged_pixels: number;
  total_pixels: number;
  mean_damage_probability: number;
  classification: 'NO_DAMAGE' | 'MINOR' | 'MODERATE' | 'SEVERE' | 'CATASTROPHIC';
  pre_image_url?: string;
  post_image_url?: string;
  mask_url?: string;
}

export interface Situation {
  id: string;
  title: string;
  situation_type: 'BORDER_SECURITY' | 'DISASTER_RESPONSE';
  status: 'ACTIVE' | 'ARCHIVED' | 'MONITORING';
  location_name?: string;
  latitude?: number;
  longitude?: number;
  vulnerability_score?: number;
  threat_level?: string;
  created_at: string;
  updated_at: string;
  detections?: DetectionTarget[];
  events?: SituationEvent[];
  weather?: WeatherData;
  routes?: RouteOption[];
  shelters?: ShelterData[];
  damage?: DamageSummary;
}

export interface SituationReport {
  situation_id: string;
  generated_at: string;
  executive_summary: string;
  verified_facts: string[];
  derived_metrics: Record<string, any>;
  ai_advisory?: {
    advisory_text: string;
    model: string;
    generated_at: string;
    disclaimer: string;
  };
  evidence_lineage?: {
    evidence_id: string;
    source: string;
    hash: string;
  }[];
}

export interface UsageSummary {
  tier: string;
  api_requests_used: number;
  api_requests_limit: number;
  drone_processing_minutes_used: number;
  drone_processing_minutes_limit: number;
  satellite_scenes_used: number;
  satellite_scenes_limit: number;
  storage_bytes_used: number;
  storage_bytes_limit: number;
}

export interface HealthStatus {
  status: string;
  version: string;
  environment: string;
  timestamp: string;
}

export interface BoundingBox2D {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

export interface Point2DCoord {
  x: number;
  y: number;
}

export interface RuntimeDetection {
  source: string;
  class_id: number;
  class_name: string;
  confidence: number;
  bbox?: BoundingBox2D | null;
  obb_points?: Point2DCoord[] | null;
  track_id?: number | null;
  frame_number?: number | null;
}

export interface RuntimeDamageAnalysis {
  before_width: number;
  before_height: number;
  after_width: number;
  after_height: number;
  probability_min: number;
  probability_max: number;
  probability_mean: number;
  threshold: number;
  damage_pixels: number;
  total_pixels: number;
  damage_ratio: number;
  damage_percentage: number;
  probability_map_available: boolean;
  damage_mask_available: boolean;
}

export interface RuntimeSceneSummary {
  critical: number;
  high: number;
  medium: number;
  low: number;
}

export interface RuntimeIntelligenceItem {
  object_class: string;
  confidence: number;
  class_weight: number;
  change_score: number;
  priority_score: number;
  priority: string;
  mode: string;
  protocol: string;
}

export interface AnnotatedVideoArtifact {
  artifact_key: string;
  sha256: string;
  file_size_bytes: number;
  mime_type: string;
  width: number;
  height: number;
  fps: number;
  frame_count: number;
  source_frame_count: number;
  codec: string;
  duration_seconds: number;
  unique_tracks_count: number;
  total_detections_count: number;
}

export interface AERIONAnalysisResultData {
  project: string;
  version: string;
  analysis_id: string;
  mode: string;
  source_type: string;
  image_width?: number | null;
  image_height?: number | null;
  frame_number?: number | null;
  detections: RuntimeDetection[];
  tracks: any[];
  border_analysis: any[];
  damage_analysis?: RuntimeDamageAnalysis | null;
  intelligence: RuntimeIntelligenceItem[];
  summary: RuntimeSceneSummary;
  overall_status: string;
  metadata: Record<string, any>;
  annotated_image_base64?: string | null;
  annotated_video_artifact?: AnnotatedVideoArtifact | null;
}
