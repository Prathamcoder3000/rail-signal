"""Pydantic schemas and response models for RAIL / SIGNAL API."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ==============================================================================
# Health & Status
# ==============================================================================

class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: datetime
    database: Dict[str, Any]
    counts: Dict[str, int]


# ==============================================================================
# Overview
# ==============================================================================

class OverviewKpis(BaseModel):
    stations_processed: int
    trains_processed: int
    schedules_accepted: int
    journey_records: int
    total_records: int


class DelaySummary(BaseModel):
    total_journeys: int
    on_time_journeys: int
    delayed_journeys: int
    on_time_percentage: float
    delay_percentage: float
    avg_delay_minutes: float
    provenance_note: str


class TrainTypeSummary(BaseModel):
    train_type: str
    total_trains: int
    avg_distance_km: float
    avg_duration_hours: float


class PassengerUtilisationSummary(BaseModel):
    avg_utilisation_pct: float
    total_journeys_represented: int
    overloaded_journeys: int
    provenance_note: str


class OverviewResponse(BaseModel):
    kpis: OverviewKpis
    delay_summary: DelaySummary
    train_category_profile: List[TrainTypeSummary]
    passenger_utilisation_summary: PassengerUtilisationSummary
    quality_summary: Dict[str, Any]
    data_freshness: str


# ==============================================================================
# Trains
# ==============================================================================

class TrainItem(BaseModel):
    train_number: str
    train_name: str
    train_type: Optional[str] = None
    zone: Optional[str] = None
    from_station_code: Optional[str] = None
    from_station_name: Optional[str] = None
    to_station_code: Optional[str] = None
    to_station_name: Optional[str] = None
    departure_time: Optional[str] = None
    arrival_time: Optional[str] = None
    duration_hours: Optional[int] = None
    duration_minutes: Optional[int] = None
    distance_km: Optional[int] = None
    has_first_ac: bool = False
    has_second_ac: bool = False
    has_third_ac: bool = False
    has_sleeper: bool = False
    has_chair_car: bool = False
    formatted_duration: Optional[str] = None


class TrainListResponse(BaseModel):
    items: List[TrainItem]
    total: int
    page: int
    page_size: int
    total_pages: int
    available_train_types: List[str]
    available_zones: List[str] = []


class ScheduleStop(BaseModel):
    schedule_id: int
    train_number: str
    station_code: str
    station_name: Optional[str] = None
    arrival_time: Optional[str] = None
    departure_time: Optional[str] = None
    day_number: int


class TrainDetailResponse(BaseModel):
    train: TrainItem
    stops: List[ScheduleStop]
    total_stops: int


# ==============================================================================
# Analytics: Performance & Delays
# ==============================================================================

class TrainPerformanceResponse(BaseModel):
    total_trains: int
    avg_route_km: float
    avg_duration_hours: float
    formatted_avg_duration: str
    by_type: List[TrainTypeSummary]
    provenance_note: str


class DelayAnalyticsResponse(BaseModel):
    total_journeys: int
    delayed_journeys: int
    on_time_journeys: int
    delay_percentage: float
    avg_delay_minutes: float
    provenance_note: str
    is_synthetic_model: bool = True


# ==============================================================================
# Analytics: Passenger Flow & Utilisation
# ==============================================================================

class UtilisationBand(BaseModel):
    band: str
    percentage: float
    count: int


class PassengerTypeUtilisation(BaseModel):
    train_type: str
    avg_seat_utilisation_pct: float
    total_journeys: int
    overloaded_journeys: int


class PassengerFlowResponse(BaseModel):
    avg_seat_utilisation_pct: float
    total_journeys_represented: int
    overloaded_journeys: int
    bands: List[UtilisationBand]
    by_train_type: List[PassengerTypeUtilisation]
    provenance_note: str
    is_synthetic_model: bool = True


# ==============================================================================
# Data Quality & Quarantine
# ==============================================================================

class DatasetQualityItem(BaseModel):
    name: str
    source_type: str
    input_records: int
    accepted: int
    quarantined: int
    validation_status: str
    rejection_reasons: List[str] = []


class DataQualityResponse(BaseModel):
    total_accepted: int
    total_quarantined: int
    datasets: List[DatasetQualityItem]
    validation_principle: str
    rules_applied: List[str]


# ==============================================================================
# Pipeline Status
# ==============================================================================

class PipelineStage(BaseModel):
    number: str
    label: str
    description: str
    status: str


class PipelineStatusResponse(BaseModel):
    pipeline_name: str
    last_run_timestamp: Optional[str] = None
    pipeline_success: bool
    stages: List[PipelineStage]
    inputs: Dict[str, Any]
    outputs: Dict[str, Any]
