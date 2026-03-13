export interface SystemStatus {
  status: string;
  uptime_seconds: number;
  version: string;
}

export interface DetectionEvent {
  id: number;
  timestamp: string;
  confidence: number;
  label: string;
  bbox: number[];
  snapshot_path: string | null;
  actions_fired: string[];
}

export interface EventListResponse {
  events: DetectionEvent[];
  total: number;
  limit: number;
  offset: number;
}

// --- Config types ---

export interface CameraConfig {
  source: number | string;
  resolution: [number, number];
  capture_interval: number;
}

export interface RoiConfig {
  enabled: boolean;
  polygon: number[][];
  min_overlap: number;
}

export interface DetectionConfig {
  model: string;
  labels: string;
  target_label: string;
  confidence_threshold: number;
  use_coral: boolean;
  roi: RoiConfig;
}

export interface CooldownConfig {
  seconds: number;
}

export type ActionType =
  | "sound"
  | "snapshot"
  | "http"
  | "mqtt"
  | "script"
  | "gpio";

export interface ActionConfig {
  name: string;
  type: ActionType;
  enabled: boolean;
  sound_file?: string | null;
  volume?: number | null;
  save_dir?: string | null;
  max_kept?: number | null;
  url?: string | null;
  method?: string | null;
  headers?: Record<string, string> | null;
  body?: string | null;
  broker?: string | null;
  port?: number | null;
  topic?: string | null;
  payload?: string | null;
  command?: string | null;
  timeout?: number | null;
  pin?: number | null;
  mode?: "pulse" | "toggle" | "momentary" | null;
  duration?: number | null;
}

export interface AuthConfig {
  enabled: boolean;
  username: string;
  password_hash: string;
}

export interface WebConfig {
  host: string;
  port: number;
  auth: AuthConfig;
}

export interface LoggingConfig {
  level: "DEBUG" | "INFO" | "WARNING" | "ERROR";
  file: string;
  max_size_mb: number;
  backup_count: number;
}

export interface AppConfig {
  camera: CameraConfig;
  detection: DetectionConfig;
  cooldown: CooldownConfig;
  actions: ActionConfig[];
  web: WebConfig;
  logging: LoggingConfig;
}

export interface EventStatsResponse {
  total_events: number;
  avg_confidence: number;
  detections_per_hour: Record<string, number>;
  detections_per_day: Record<string, number>;
  peak_hour: number | null;
}

// --- Auth types ---

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export interface AuthStatusResponse {
  auth_enabled: boolean;
  authenticated: boolean;
  username: string | null;
}
