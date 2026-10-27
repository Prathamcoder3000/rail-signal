"""FastAPI Main Application for RAIL / SIGNAL.

Exposes RESTful endpoints for railway operations, passenger flow analytics,
data quality metrics, and pipeline execution status.
"""

from contextlib import asynccontextmanager
import logging
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from backend.app.config import settings
from backend.app.db import close_db_pool, get_db_pool
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

logger = logging.getLogger("rail_signal.api")
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager: initializes connection pool on startup and closes on shutdown."""
    logger.info("Starting up %s (v%s)...", settings.app_name, settings.app_version)
    try:
        get_db_pool()
    except Exception as exc:
        logger.warning("Could not pre-initialize DB pool on startup: %s", exc)
    yield
    logger.info("Shutting down %s...", settings.app_name)
    close_db_pool()


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
        raise HTTPException(status_code=500, detail=f"Failed to generate overview metrics: {str(exc)}")


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
        raise HTTPException(status_code=500, detail=f"Failed to query train records: {str(exc)}")


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
        raise HTTPException(status_code=500, detail=f"Failed to compute train performance: {str(exc)}")


@app.get("/api/analytics/delays", response_model=DelayAnalyticsResponse, tags=["Analytics"])
def delay_analytics():
    """Returns delay statistics and on-time percentages from the journey dataset."""
    try:
        return get_delay_analytics()
    except Exception as exc:
        logger.error("Error computing delay analytics: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to compute delay statistics: {str(exc)}")


@app.get("/api/analytics/passenger-flow", response_model=PassengerFlowResponse, tags=["Analytics"])
def passenger_flow_analytics():
    """Returns seat utilisation distributions, train-type averages, and overload indicators."""
    try:
        return get_passenger_flow_analytics()
    except Exception as exc:
        logger.error("Error computing passenger flow: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to compute passenger flow metrics: {str(exc)}")


@app.get("/api/data-quality", response_model=DataQualityResponse, tags=["Data Quality"])
def data_quality():
    """Returns dataset validation outcomes, accepted records, and quarantine reasons."""
    try:
        return get_data_quality_report()
    except Exception as exc:
        logger.error("Error fetching data quality report: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to load data quality report: {str(exc)}")


@app.get("/api/pipeline/status", response_model=PipelineStatusResponse, tags=["Data Pipeline"])
def pipeline_status():
    """Returns workflow stages, execution metadata, input files, and output Parquet specifications."""
    try:
        return get_pipeline_status()
    except Exception as exc:
        logger.error("Error fetching pipeline status: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to load pipeline status: {str(exc)}")


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
        raise HTTPException(status_code=500, detail=f"Failed to query pipeline execution history: {str(exc)}")


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
        raise HTTPException(status_code=500, detail=f"Failed to load execution details for run '{run_id}': {str(exc)}")


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
        raise HTTPException(status_code=400, detail=str(val_err))
    except RuntimeError as run_err:
        raise HTTPException(status_code=409, detail=str(run_err))
    except Exception as exc:
        logger.error("Error executing validation pipeline: %s", exc)
        raise HTTPException(status_code=500, detail=f"Validation pipeline execution failed: {str(exc)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host=settings.app_host, port=settings.app_port, reload=True)

