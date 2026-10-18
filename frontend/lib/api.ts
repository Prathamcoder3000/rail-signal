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

async function apiFetch<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`
  const response = await fetch(url, {
    ...options,
    headers: {
      Accept: 'application/json',
      ...options?.headers,
    },
  })
  if (!response.ok) {
    throw new Error(`API error ${response.status}: ${response.statusText}`)
  }
  return response.json()
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
}
