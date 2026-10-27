/**
 * Centralized API client for RAIL / SIGNAL.
 * Connects to the FastAPI backend with environment-driven base URL and safe fallbacks.
 */

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'

export type HealthStatus = {
  status: 'healthy' | 'degraded' | 'offline'
  version: string
  timestamp: string
  database: {
    connected: boolean
    database: string
    status: string
    error?: string
  }
  counts: {
    stations: number
    trains: number
    schedules: number
    journey_train: number
    journey_test: number
  }
}

export type OverviewData = {
  kpis: {
    stations_processed: number
    trains_processed: number
    schedules_accepted: number
    journey_records: number
    total_records: number
  }
  delay_summary: {
    total_journeys: number
    on_time_journeys: number
    delayed_journeys: number
    on_time_percentage: number
    delay_percentage: number
    avg_delay_minutes: number
    provenance_note: string
  }
  train_category_profile: Array<{
    train_type: string
    total_trains: number
    avg_distance_km: number
    avg_duration_hours: number
  }>
  passenger_utilisation_summary: {
    avg_utilisation_pct: number
    total_journeys_represented: number
    overloaded_journeys: number
    provenance_note: string
  }
  quality_summary: Record<string, any>
  data_freshness: string
}

export type TrainItem = {
  train_number: string
  train_name: string
  train_type?: string
  zone?: string
  from_station_code?: string
  from_station_name?: string
  to_station_code?: string
  to_station_name?: string
  departure_time?: string
  arrival_time?: string
  duration_hours?: number
  duration_minutes?: number
  distance_km?: number
  has_first_ac: boolean
  has_second_ac: boolean
  has_third_ac: boolean
  has_sleeper: boolean
  has_chair_car: boolean
  formatted_duration?: string
}

export type TrainListResponse = {
  items: TrainItem[]
  total: number
  page: number
  page_size: number
  total_pages: number
  available_train_types: string[]
  available_zones?: string[]
}

export type TrainDetail = {
  train: TrainItem
  stops: Array<{
    schedule_id: number
    train_number: string
    station_code: string
    station_name?: string
    arrival_time?: string
    departure_time?: string
    day_number: number
  }>
  total_stops: number
}

export type TrainPerformanceData = {
  total_trains: number
  avg_route_km: number
  avg_duration_hours: number
  formatted_avg_duration: string
  by_type: Array<{
    train_type: string
    total_trains: number
    avg_distance_km: number
    avg_duration_hours: number
  }>
  provenance_note: string
}

export type DelayAnalyticsData = {
  total_journeys: number
  delayed_journeys: number
  on_time_journeys: number
  delay_percentage: number
  avg_delay_minutes: number
  provenance_note: string
  is_synthetic_model: boolean
}

export type PassengerFlowData = {
  avg_seat_utilisation_pct: number
  total_journeys_represented: number
  overloaded_journeys: number
  bands: Array<{
    band: string
    percentage: number
    count: number
  }>
  by_train_type: Array<{
    train_type: string
    avg_seat_utilisation_pct: number
    total_journeys: number
    overloaded_journeys: number
  }>
  provenance_note: string
  is_synthetic_model: boolean
}

export type DataQualityData = {
  total_accepted: number
  total_quarantined: number
  datasets: Array<{
    name: string
    source_type: string
    input_records: number
    accepted: number
    quarantined: number
    validation_status: string
    rejection_reasons: string[]
  }>
  validation_principle: string
  rules_applied: string[]
}

export type PipelineStatusData = {
  pipeline_name: string
  last_run_timestamp?: string
  pipeline_success: boolean
  stages: Array<{
    number: string
    label: string
    description: string
    status: string
  }>
  inputs: Record<string, any>
  outputs: Record<string, any>
}

export type PipelineStageDetail = {
  stage_name: string
  status: 'SUCCESS' | 'FAILED' | 'RUNNING' | 'PENDING' | 'SKIPPED' | string
  started_at?: string | null
  ended_at?: string | null
  duration_seconds?: number | null
  records_processed: number
  details: Record<string, any>
  error?: string | null
}

export type PipelineRunSummary = {
  run_id: string
  pipeline_name: string
  run_type: 'VALIDATION' | 'FULL_ETL' | 'CUSTOM' | string
  trigger_type: 'MANUAL_API' | 'CLI' | 'SCHEDULED' | 'SYSTEM' | string
  status: 'SUCCESS' | 'FAILED' | 'RUNNING' | 'PENDING' | string
  start_time: string
  finish_time?: string | null
  duration_seconds?: number | null
  records_processed: number
  records_accepted: number
  records_quarantined: number
  current_stage?: string | null
  failed_stage?: string | null
  error_summary?: string | null
  stage_count: number
  created_at?: string | null
}

export type PipelineRunDetail = PipelineRunSummary & {
  stage_details: PipelineStageDetail[]
  metadata: Record<string, any>
}

export type PipelineHistoryStats = {
  total_runs: number
  successful_runs: number
  failed_runs: number
  running_runs: number
  latest_run_status?: string | null
  latest_run_timestamp?: string | null
  latest_run_duration_seconds?: number | null
}

export type PipelineHistoryResponse = {
  items: PipelineRunSummary[]
  total: number
  page: number
  page_size: number
  total_pages: number
  stats?: PipelineHistoryStats | null
}

export type PipelineRunTriggerRequest = {
  mode: 'validation' | 'full_etl'
}

export type PipelineRunTriggerResponse = {
  run_id: string
  run_type: string
  status: string
  message: string
  duration_seconds?: number | null
  summary: Record<string, any>
}

async function apiFetch<T>(endpoint: string, options?: RequestInit & { timeoutMs?: number }): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`
  const timeout = options?.timeoutMs || 8000
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeout)

  try {
    const response = await fetch(url, {
      ...options,
      signal: options?.signal || controller.signal,
      headers: {
        Accept: 'application/json',
        ...options?.headers,
      },
    })
    clearTimeout(timeoutId)
    if (!response.ok) {
      let detail = response.statusText
      try {
        const errJson = await response.json()
        if (errJson && errJson.detail) {
          detail = errJson.detail
        }
      } catch {
        // use default statusText
      }
      throw new Error(`API error ${response.status}: ${detail}`)
    }
    return response.json()
  } catch (err: any) {
    clearTimeout(timeoutId)
    if (err.name === 'AbortError') {
      throw new Error(`Request timed out after ${timeout}ms connecting to ${url}`)
    }
    throw err
  }
}

export type SystemHealthState =
  | 'checking'
  | 'healthy'
  | 'db_disconnected'
  | 'backend_offline'
  | 'check_failed'

export type SystemHealthInfo = {
  state: SystemHealthState
  status: SystemHealthState
  label: string
  tone: 'good' | 'warn' | 'error' | 'neutral'
  headline: string
  detail: string
  details: string
  latencyMs: number | null
  database: 'connected' | 'disconnected' | 'unknown'
  checkedAt: string
  health?: HealthStatus
  error?: string
}

export const api = {
  getHealth: () => apiFetch<HealthStatus>('/api/health'),
  getOverview: () => apiFetch<OverviewData>('/api/overview'),
  getTrains: (params?: {
    query?: string
    train_type?: string
    zone?: string
    sort_by?: string
    sort_order?: string
    page?: number
    page_size?: number
  }) => {
    const searchParams = new URLSearchParams()
    if (params?.query) searchParams.set('query', params.query)
    if (params?.train_type && params.train_type !== 'All types') searchParams.set('train_type', params.train_type)
    if (params?.zone && params.zone !== 'All zones') searchParams.set('zone', params.zone)
    if (params?.sort_by) searchParams.set('sort_by', params.sort_by)
    if (params?.sort_order) searchParams.set('sort_order', params.sort_order)
    if (params?.page) searchParams.set('page', params.page.toString())
    if (params?.page_size) searchParams.set('page_size', params.page_size.toString())
    const qs = searchParams.toString()
    return apiFetch<TrainListResponse>(`/api/trains${qs ? `?${qs}` : ''}`)
  },
  getTrainDetail: (trainNumber: string) => apiFetch<TrainDetail>(`/api/trains/${encodeURIComponent(trainNumber)}`),
  getTrainPerformance: () => apiFetch<TrainPerformanceData>('/api/analytics/train-performance'),
  getDelays: () => apiFetch<DelayAnalyticsData>('/api/analytics/delays'),
  getPassengerFlow: () => apiFetch<PassengerFlowData>('/api/analytics/passenger-flow'),
  getDataQuality: () => apiFetch<DataQualityData>('/api/data-quality'),
  getPipelineStatus: () => apiFetch<PipelineStatusData>('/api/pipeline/status'),
  getPipelineHistory: (params?: {
    page?: number
    page_size?: number
    status?: string
    run_type?: string
  }) => {
    const searchParams = new URLSearchParams()
    if (params?.page) searchParams.set('page', params.page.toString())
    if (params?.page_size) searchParams.set('page_size', params.page_size.toString())
    if (params?.status && params.status !== 'ALL') searchParams.set('status', params.status)
    if (params?.run_type && params.run_type !== 'ALL') searchParams.set('run_type', params.run_type)
    const qs = searchParams.toString()
    return apiFetch<PipelineHistoryResponse>(`/api/pipeline/history${qs ? `?${qs}` : ''}`)
  },
  getPipelineRunDetail: (runId: string) =>
    apiFetch<PipelineRunDetail>(`/api/pipeline/history/${encodeURIComponent(runId)}`),
  triggerPipelineRun: (payload?: PipelineRunTriggerRequest) =>
    apiFetch<PipelineRunTriggerResponse>('/api/pipeline/run', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload || { mode: 'validation' }),
      timeoutMs: 15000,
    }),

  checkSystemHealth: async (): Promise<SystemHealthInfo> => {
    const start = Date.now()
    const checkedAt = new Date().toLocaleTimeString()
    try {
      const health = await api.getHealth()
      const latencyMs = Date.now() - start
      if (health.database && health.database.connected === false) {
        const errorDetail = health.database.error || 'FastAPI online, but PostgreSQL connection pool failed.'
        return {
          state: 'db_disconnected',
          status: 'db_disconnected',
          label: 'DATABASE OFFLINE',
          tone: 'warn',
          headline: 'PostgreSQL Disconnected',
          detail: errorDetail,
          details: errorDetail,
          latencyMs,
          database: 'disconnected',
          checkedAt,
          health,
        }
      }
      const connDetail = `Connected to rail_signal (${health.counts.trains.toLocaleString()} trains, ${health.counts.stations.toLocaleString()} stations).`
      return {
        state: 'healthy',
        status: 'healthy',
        label: 'SYSTEM HEALTHY',
        tone: 'good',
        headline: 'FastAPI & PostgreSQL Online',
        detail: connDetail,
        details: connDetail,
        latencyMs,
        database: 'connected',
        checkedAt,
        health,
      }
    } catch (err: any) {
      const latencyMs = Date.now() - start
      const errMsg = err?.message || String(err)
      if (errMsg.includes('API error')) {
        const failDetail = `FastAPI responded with an error: ${errMsg}`
        return {
          state: 'check_failed',
          status: 'check_failed',
          label: 'CHECK FAILED',
          tone: 'error',
          headline: 'Health Check Failed',
          detail: failDetail,
          details: failDetail,
          latencyMs,
          database: 'unknown',
          checkedAt,
          error: errMsg,
        }
      }
      const offlineDetail = `Cannot reach ${API_BASE_URL}/api/health. Start backend with: uvicorn backend.app.main:app --port 8000`
      return {
        state: 'backend_offline',
        status: 'backend_offline',
        label: 'BACKEND OFFLINE',
        tone: 'warn',
        headline: 'FastAPI Server Unreachable',
        detail: offlineDetail,
        details: offlineDetail,
        latencyMs: null,
        database: 'unknown',
        checkedAt,
        error: errMsg,
      }
    }
  },
}

export const checkSystemHealth = api.checkSystemHealth

