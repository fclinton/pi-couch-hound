export interface SystemStatus {
  status: string;
  uptime_seconds: number;
  version: string;
  monitoring_enabled: boolean;
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

export interface TwoStageConfig {
  enabled: boolean;
  anchor_label: string;
  anchor_confidence: number;
  anchor_padding: number;
  second_stage_confidence: number;
  min_contour_area: number;
  contour_padding: number;
  debug_overlay: boolean;
}

export interface DetectionConfig {
  model: string;
  labels: string;
  target_label: string;
  confidence_threshold: number;
  use_coral: boolean;
  roi: RoiConfig;
  two_stage: TwoStageConfig;
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

export interface EscalationLevelConfig {
  delay: number;
  actions: string[];
}

export interface EscalationConfig {
  enabled: boolean;
  reset_cooldown: number;
  levels: EscalationLevelConfig[];
}

export interface AuthConfig {
  enabled: boolean;
  username: string;
  password_hash: string;
}

export interface SslConfig {
  enabled: boolean;
  certfile: string | null;
  keyfile: string | null;
  self_signed: boolean;
}

export interface WebConfig {
  host: string;
  port: number;
  auth: AuthConfig;
  ssl: SslConfig;
}

export interface LoggingConfig {
  level: "DEBUG" | "INFO" | "WARNING" | "ERROR";
  file: string;
  max_size_mb: number;
  backup_count: number;
}

export interface UpdateConfig {
  enabled: boolean;
  check_interval_minutes: number;
  auto_apply: boolean;
  maintenance_window_start: string | null;
  maintenance_window_end: string | null;
}

export interface UpdateStatus {
  state: "up_to_date" | "checking" | "available" | "applying" | "error";
  current_commit: string;
  remote_commit: string | null;
  current_version: string;
  available_version: string | null;
  last_check_time: string | null;
  last_error: string | null;
  commits_behind: number;
  commit_messages: string[];
}

export interface AutoDisableConfig {
  person_detection: boolean;
}

export interface MonitoringConfig {
  enabled: boolean;
  auto_disable: AutoDisableConfig;
}

export interface AppConfig {
  camera: CameraConfig;
  detection: DetectionConfig;
  cooldown: CooldownConfig;
  actions: ActionConfig[];
  escalation: EscalationConfig;
  monitoring: MonitoringConfig;
  web: WebConfig;
  logging: LoggingConfig;
  update: UpdateConfig;
  _restart?: boolean;
}

export interface EventStatsResponse {
  total_events: number;
  avg_confidence: number;
  detections_per_hour: Record<string, number>;
  detections_per_day: Record<string, number>;
  peak_hour: number | null;
  confidence_distribution: Record<string, number>;
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
  setup_required: boolean;
}

export interface SetupRequest {
  username: string;
  password: string;
}

export interface SetupResponse {
  access_token: string;
  token_type: string;
}
