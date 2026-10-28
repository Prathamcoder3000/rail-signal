"""FastAPI Main Application for RAIL / SIGNAL.

Exposes RESTful endpoints for railway operations, passenger flow analytics,
data quality metrics, and pipeline execution status.
"""

from contextlib import asynccontextmanager
import logging
import threading
import time
from typing import Dict, Optional

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware

from backend.app import db
from backend.app.config import settings
from backend.app.logging_config import configure_logging
from backend.pipeline.monitoring import sanitize_error_message
from backend.app.schemas import (
    DataQualityResponse,
    DelayAnalyticsResponse,
    HealthResponse,
    OverviewResponse,
    PassengerFlowResponse,
    PipelineHistoryResponse,
    PipelineRunDetail,
    PipelineRunTriggerRequest,
    PipelineRunTriggerResponse,
    PipelineStatusResponse,
    TrainDetailResponse,
    TrainListResponse,
    TrainPerformanceResponse,
)
from backend.app.services import (
    get_data_quality_report,
    get_delay_analytics,
    get_health_status,
    get_overview_data,
    get_passenger_flow_analytics,
    get_pipeline_history_service,
    get_pipeline_run_detail_service,
    get_pipeline_status,
    get_train_detail,
    get_train_performance_analytics,
    get_trains,
    trigger_validation_pipeline_service,
)

logger = configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager: initializes connection pool on startup and closes on shutdown."""
    logger.info("Starting up %s (v%s)...", settings.app_name, settings.app_version)
    try:
        db.get_db_pool()
    except Exception as exc:
        logger.warning("Could not pre-initialize DB pool on startup: %s", exc)
    yield
    logger.info("Shutting down %s...", settings.app_name)
    db.close_db_pool()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "RAIL / SIGNAL — Railway Operations & Passenger Flow Data Engineering Platform. "
        "Provides verified metrics on infrastructure, journey delay modeling, passenger utilisation, "
        "and data engineering quality reports."
    ),
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================================================================
# Prometheus Metrics Cache Configuration
# ==============================================================================
METRICS_CACHE_TTL_SECONDS: float = 60.0
_METRICS_CACHE_LOCK = threading.Lock()
_METRICS_TABLE_COUNTS_CACHE: Dict[str, int] = {}
_METRICS_CACHE_TIMESTAMP: float = 0.0


def get_cached_table_counts(ttl: float = METRICS_CACHE_TTL_SECONDS) -> Dict[str, int]:
    """
    Returns verified core table counts cached in-memory with a thread-safe TTL.
    Prevents stampeding / duplicate full-table scans on high-frequency scrapes.
    """
    global _METRICS_CACHE_TIMESTAMP, _METRICS_TABLE_COUNTS_CACHE
    now = time.time()

    if _METRICS_TABLE_COUNTS_CACHE and (now - _METRICS_CACHE_TIMESTAMP) < ttl:
        return _METRICS_TABLE_COUNTS_CACHE

    with _METRICS_CACHE_LOCK:
        now = time.time()
        if _METRICS_TABLE_COUNTS_CACHE and (now - _METRICS_CACHE_TIMESTAMP) < ttl:
            return _METRICS_TABLE_COUNTS_CACHE

        query = (
            "SELECT "
            "(SELECT COUNT(*) FROM stations) AS stations, "
            "(SELECT COUNT(*) FROM trains) AS trains, "
            "(SELECT COUNT(*) FROM schedules) AS schedules, "
            "(SELECT COUNT(*) FROM journey_train) AS journey_train, "
            "(SELECT COUNT(*) FROM journey_test) AS journey_test;"
        )
        new_counts: Dict[str, int] = {}
        with db.get_db_cursor() as cur:
            cur.execute(query)
            row = cur.fetchone()
            if row:
                if isinstance(row, dict):
                    for k in ("stations", "trains", "schedules", "journey_train", "journey_test"):
                        new_counts[k] = int(row.get(k, 0))
                else:
                    new_counts = {
                        "stations": int(row[0]),
                        "trains": int(row[1]),
                        "schedules": int(row[2]),
                        "journey_train": int(row[3]),
                        "journey_test": int(row[4]),
                    }

        _METRICS_TABLE_COUNTS_CACHE = new_counts
        _METRICS_CACHE_TIMESTAMP = now
        return _METRICS_TABLE_COUNTS_CACHE


# ==============================================================================
# API Endpoints
# ==============================================================================

@app.get("/api/health", response_model=HealthResponse, tags=["System"])
def health_check():
    """Returns application health, version, database connectivity, and record counts."""
    return get_health_status()


@app.get("/api/overview", response_model=OverviewResponse, tags=["Dashboard"])
def get_overview():
    """Returns consolidated operational metrics, delay distributions, category profiles, and freshness."""
    try:
        return get_overview_data()
    except Exception as exc:
        logger.error("Error generating overview: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to generate overview metrics.")


@app.get("/api/trains", response_model=TrainListResponse, tags=["Trains"])
def list_trains(
    query: Optional[str] = Query(None, description="Search term for train number or name"),
    train_type: Optional[str] = Query(None, description="Filter by train type (e.g. SF, EXP, PASS, RAJ)"),
    zone: Optional[str] = Query(None, description="Filter by administrative zone (e.g. NR, WR, CR)"),
    sort_by: Optional[str] = Query("train_number", description="Sort field: train_number, train_name, distance_km, duration_hours, zone"),
    sort_order: Optional[str] = Query("asc", description="Sort order: asc or desc"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
):
    """Searches, filters, sorts, and paginates train reference records with duration formatting."""
    try:
        return get_trains(
            query=query,
            train_type=train_type,
            zone=zone,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
        )
    except Exception as exc:
        logger.error("Error listing trains: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to query train records.")


@app.get("/api/trains/{train_number}", response_model=TrainDetailResponse, tags=["Trains"])
def get_train(train_number: str):
    """Returns detailed information for a specific train including its complete stop schedule."""
    detail = get_train_detail(train_number)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Train with number '{train_number}' not found.")
    return detail


@app.get("/api/analytics/train-performance", response_model=TrainPerformanceResponse, tags=["Analytics"])
def train_performance():
    """Returns average distance, duration, and volume breakdowns by train type."""
    try:
        return get_train_performance_analytics()
    except Exception as exc:
        logger.error("Error computing train performance: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to compute train performance analytics.")


@app.get("/api/analytics/delays", response_model=DelayAnalyticsResponse, tags=["Analytics"])
def delay_analytics():
    """Returns delay statistics and on-time percentages from the journey dataset."""
    try:
        return get_delay_analytics()
    except Exception as exc:
        logger.error("Error computing delay analytics: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to compute delay statistics.")


@app.get("/api/analytics/passenger-flow", response_model=PassengerFlowResponse, tags=["Analytics"])
def passenger_flow_analytics():
    """Returns seat utilisation distributions, train-type averages, and overload indicators."""
    try:
        return get_passenger_flow_analytics()
    except Exception as exc:
        logger.error("Error computing passenger flow: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to compute passenger flow metrics.")


@app.get("/api/data-quality", response_model=DataQualityResponse, tags=["Data Quality"])
def data_quality():
    """Returns dataset validation outcomes, accepted records, and quarantine reasons."""
    try:
        return get_data_quality_report()
    except Exception as exc:
        logger.error("Error fetching data quality report: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to load data quality report.")


@app.get("/api/pipeline/status", response_model=PipelineStatusResponse, tags=["Data Pipeline"])
def pipeline_status():
    """Returns workflow stages, execution metadata, input files, and output Parquet specifications."""
    try:
        return get_pipeline_status()
    except Exception as exc:
        logger.error("Error fetching pipeline status: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to load pipeline status.")


@app.get("/api/pipeline/history", response_model=PipelineHistoryResponse, tags=["Data Pipeline"])
def pipeline_history(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by status: RUNNING, SUCCESS, FAILED"),
    run_type: Optional[str] = Query(None, description="Filter by run_type: VALIDATION, FULL_ETL"),
):
    """Returns paginated pipeline execution runs with duration, record counts, and status."""
    try:
        return get_pipeline_history_service(
            page=page,
            page_size=page_size,
            status=status,
            run_type=run_type,
        )
    except Exception as exc:
        logger.error("Error querying pipeline history: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to query pipeline execution history.")


@app.get("/api/pipeline/history/{run_id}", response_model=PipelineRunDetail, tags=["Data Pipeline"])
def pipeline_run_detail(run_id: str):
    """Returns granular stage-level execution telemetry and timing for a specific run ID."""
    try:
        detail = get_pipeline_run_detail_service(run_id)
        if not detail:
            raise HTTPException(status_code=404, detail=f"Pipeline run '{run_id}' not found.")
        return detail
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error fetching run detail '%s': %s", run_id, exc)
        raise HTTPException(status_code=500, detail=f"Failed to load execution details for run '{run_id}'.")


@app.post("/api/pipeline/run", response_model=PipelineRunTriggerResponse, tags=["Data Pipeline"])
def trigger_pipeline_run(payload: Optional[PipelineRunTriggerRequest] = None):
    """
    Executes a safe, non-destructive pipeline validation run.
    Guarantees no modifications or duplicate insertions into existing database tables.
    """
    mode = payload.mode if payload else "validation"
    try:
        return trigger_validation_pipeline_service(mode=mode)
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=sanitize_error_message(val_err))
    except RuntimeError as run_err:
        raise HTTPException(status_code=409, detail=sanitize_error_message(run_err))
    except Exception as exc:
        logger.error("Error executing validation pipeline: %s", exc)
        raise HTTPException(status_code=500, detail="Validation pipeline execution failed.")


@app.get("/metrics", tags=["Observability"])
def prometheus_metrics():
    """
    Exposes Prometheus-compatible pipeline execution telemetry, stage durations,
    and verified record counts in standard text exposition format (version 0.0.4).
    Bounded cardinality: only statuses and stages are labeled; zero sensitive data.
    """
    from backend.pipeline.monitoring import get_pipeline_history_stats

    lines = [
        "# HELP rail_signal_pipeline_runs_total Total number of pipeline execution runs by terminal status",
        "# TYPE rail_signal_pipeline_runs_total counter",
    ]
    try:
        stats = get_pipeline_history_stats()
        lines.append(f'rail_signal_pipeline_runs_total{{status="SUCCESS"}} {stats.get("successful_runs", 0)}')
        lines.append(f'rail_signal_pipeline_runs_total{{status="FAILED"}} {stats.get("failed_runs", 0)}')
        lines.append(f'rail_signal_pipeline_runs_total{{status="RUNNING"}} {stats.get("running_runs", 0)}')
        lines.append(f'rail_signal_pipeline_runs_total{{status="ALL"}} {stats.get("total_runs", 0)}')

        latest_dur = stats.get("latest_run_duration_seconds")
        if latest_dur is not None:
            lines.append("# HELP rail_signal_pipeline_latest_duration_seconds Duration of latest pipeline run in seconds")
            lines.append("# TYPE rail_signal_pipeline_latest_duration_seconds gauge")
            lines.append(f"rail_signal_pipeline_latest_duration_seconds {latest_dur}")
    except Exception as stats_err:
        logger.warning("Error collecting pipeline run stats for metrics: %s", stats_err)

    # Independent database connectivity probe and cached table counts
    db_is_up = False
    table_counts: Optional[Dict[str, int]] = None

    try:
        # Lightweight liveness query
        with db.get_db_cursor() as cur:
            cur.execute("SELECT 1;")
            cur.fetchone()

        # Cache retrieval (refreshes from DB on cache miss)
        table_counts = get_cached_table_counts()
        db_is_up = True
    except Exception as db_err:
        sanitized = sanitize_error_message(db_err)
        logger.warning("Database unavailable during metrics generation: %s", sanitized)
        db_is_up = False

    # Emit rail_signal_database_up sample exactly once per response
    lines.append("# HELP rail_signal_database_up Database connectivity health probe (1 = connected, 0 = unreachable)")
    lines.append("# TYPE rail_signal_database_up gauge")
    lines.append(f"rail_signal_database_up {1 if db_is_up else 0}")

    # Emit table counts only if database and counts are successfully available
    if db_is_up and table_counts is not None:
        lines.append("# HELP rail_signal_records_verified_total Total verified relational records in database")
        lines.append("# TYPE rail_signal_records_verified_total gauge")
        for t in ("stations", "trains", "schedules", "journey_train", "journey_test"):
            cnt = table_counts.get(t, 0)
            lines.append(f'rail_signal_records_verified_total{{table="{t}"}} {cnt}')

    content = "\n".join(lines) + "\n"
    return Response(content=content, media_type="text/plain; version=0.0.4; charset=utf-8")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host=settings.app_host, port=settings.app_port, reload=True)

