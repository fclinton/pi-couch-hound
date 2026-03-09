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
