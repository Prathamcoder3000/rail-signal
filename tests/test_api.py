"""Automated unit and integration tests for FastAPI backend in backend.app.main."""

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("healthy", "degraded")
    assert data["version"] == "0.3.0"
    assert "database" in data
    assert "counts" in data
    assert data["counts"]["trains"] > 0
    assert data["counts"]["stations"] > 0


def test_overview_endpoint():
    response = client.get("/api/overview")
    assert response.status_code == 200
    data = response.json()

    # Verify KPI counts
    kpis = data["kpis"]
    assert kpis["stations_processed"] == 8988
    assert kpis["trains_processed"] == 5207
    assert kpis["schedules_accepted"] == 394469
    assert kpis["journey_records"] == 1875000
    assert kpis["total_records"] == 2283664

    # Verify delay metrics
    delay = data["delay_summary"]
    assert delay["total_journeys"] == 1500000
    assert delay["on_time_percentage"] > 0
    assert delay["delay_percentage"] > 0
    assert "educational simulation" in delay["provenance_note"].lower()

    # Verify category profile
    assert len(data["train_category_profile"]) > 0


def test_trains_list_pagination_and_search():
    # 1. Default page
    resp = client.get("/api/trains?page=1&page_size=5")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 5
    assert data["total"] == 5207
    assert data["page"] == 1
    assert data["page_size"] == 5
    assert len(data["available_train_types"]) > 0

    # 2. Search query for Rajdhani
    search_resp = client.get("/api/trains?query=Rajdhani")
    assert search_resp.status_code == 200
    search_data = search_resp.json()
    assert search_data["total"] > 0
    for item in search_data["items"]:
        assert "rajdhani" in item["train_name"].lower() or "rajdhani" in item["train_number"].lower()

    # 3. Filter by type
    filter_resp = client.get("/api/trains?train_type=EXP&page_size=10")
    assert filter_resp.status_code == 200
    filter_data = filter_resp.json()
    for item in filter_data["items"]:
        assert item["train_type"] == "EXP"


def test_train_detail_and_stops():
    # Known train '04601'
    resp = client.get("/api/trains/04601")
    assert resp.status_code == 200
    data = resp.json()
    assert data["train"]["train_number"] == "04601"
    assert data["train"]["from_station_code"] == "JAT"
    assert data["train"]["to_station_code"] == "UHP"
    assert data["total_stops"] >= 2
    assert len(data["stops"]) == data["total_stops"]


def test_train_detail_not_found():
    resp = client.get("/api/trains/NON_EXISTENT_TRAIN_99999")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_analytics_train_performance():
    resp = client.get("/api/analytics/train-performance")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_trains"] == 5207
    assert data["avg_route_km"] > 0
    assert len(data["by_type"]) > 0


def test_analytics_delays():
    resp = client.get("/api/analytics/delays")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_journeys"] == 1500000
    assert data["is_synthetic_model"] is True
    assert data["delay_percentage"] > 0
    assert data["avg_delay_minutes"] > 0


def test_analytics_passenger_flow():
    resp = client.get("/api/analytics/passenger-flow")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_synthetic_model"] is True
    assert data["total_journeys_represented"] == 1875000
    assert data["avg_seat_utilisation_pct"] > 0
    assert len(data["bands"]) == 4

    # Verify bands percentages sum to ~100%
    total_pct = sum(b["percentage"] for b in data["bands"])
    assert 99.0 <= total_pct <= 101.0


def test_data_quality_endpoint():
    resp = client.get("/api/data-quality")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_accepted"] == 2283664
    assert data["total_quarantined"] == 22614
    assert len(data["datasets"]) == 5
    assert len(data["rules_applied"]) >= 3


def test_pipeline_status_endpoint():
    resp = client.get("/api/pipeline/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["pipeline_success"] is True
    assert len(data["stages"]) >= 7
    assert "outputs" in data
    assert "stations" in data["outputs"]
