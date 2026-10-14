"""
Unit tests for data transformation and Parquet storage layer in backend.pipeline.transformation.
"""

import json
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import pyarrow.parquet as pq
import pytest

from backend.pipeline.transformation import (
    QualityReport,
    SCHEDULES_SCHEMA,
    STATIONS_SCHEMA,
    TRAINS_SCHEMA,
    save_quality_report,
    save_quarantine_records,
    stream_csv_to_parquet,
    transform_journey_dataframe,
    transform_schedules,
    transform_stations,
    transform_trains,
    write_parquet_atomic,
)


# ==============================================================================
# 1. Stations Transformation Tests
# ==============================================================================

def test_transform_stations_standardization():
    raw_records = [
        {
            "code": "ndls ",
            "name": " New Delhi ",
            "state": "Delhi",
            "zone": "nr",
            "address": "Pahar Ganj",
            "longitude": 77.2090,
            "latitude": 28.6139,
        },
        {
            "code": "csmt",
            "name": "Mumbai CST",
            "state": "Maharashtra",
            "zone": "cr",
            "address": None,
            "longitude": "72.8358",
            "latitude": "18.9398",
        },
    ]
    accepted, quarantined = transform_stations(raw_records)
    assert len(quarantined) == 0
    assert len(accepted) == 2

    # Verify standardization
    assert accepted[0]["station_code"] == "NDLS"
    assert accepted[0]["station_name"] == "New Delhi"
    assert accepted[0]["zone"] == "NR"
    assert accepted[0]["longitude"] == 77.2090

    assert accepted[1]["station_code"] == "CSMT"
    assert accepted[1]["longitude"] == 72.8358
    assert accepted[1]["latitude"] == 18.9398


def test_transform_stations_quarantine():
    raw_records = [
        {"code": "", "name": "No Code"},
        {"code": "PUNE", "name": ""},
        {"code": "PUNE", "name": "Pune Duplicate"},
        {"code": "BADLON", "name": "Bad Lon", "longitude": 200.0, "latitude": 20.0},
    ]
    accepted, quarantined = transform_stations(raw_records)
    assert len(accepted) == 0
    assert len(quarantined) == 4
    reasons = [q["rejection_reason"] for q in quarantined]
    assert any("station_code" in r for r in reasons)
    assert any("station_name" in r for r in reasons)
    assert any("Duplicate station code" in r for r in reasons)
    assert any("Longitude" in r for r in reasons)


# ==============================================================================
# 2. Trains Transformation Tests
# ==============================================================================

def test_transform_trains_leading_zeros_and_classes():
    raw_records = [
        {
            "number": "04601",
            "name": "Jammu Tawi Udhampur Special",
            "type": "demu",
            "zone": "nr",
            "from_station_code": "jat",
            "to_station_code": "uhp",
            "departure": "10:40:00",
            "arrival": "12:15:00",
            "duration_h": 1,
            "duration_m": 35,
            "distance": 53,
            "first_ac": 0,
            "second_ac": 0,
            "third_ac": 0,
            "sleeper": 1,
            "chair_car": 0,
        }
    ]
    accepted, quarantined = transform_trains(raw_records)
    assert len(quarantined) == 0
    assert len(accepted) == 1

    tr = accepted[0]
    # Leading zeros strictly preserved
    assert tr["train_number"] == "04601"
    assert isinstance(tr["train_number"], str)
    assert tr["train_type"] == "DEMU"
    assert tr["zone"] == "NR"
    assert tr["from_station_code"] == "JAT"
    assert tr["to_station_code"] == "UHP"
    assert tr["has_sleeper"] is True
    assert tr["has_first_ac"] is False


def test_transform_trains_quarantine():
    raw_records = [
        {"number": None, "name": "No Number"},
        {"number": "12301", "name": ""},
        {"number": "12301", "name": "Rajdhani Exp"},
        {"number": "12301", "name": "Duplicate Rajdhani"},
        {"number": "12302", "name": "Negative Dist", "distance": -100},
    ]
    accepted, quarantined = transform_trains(raw_records)
    assert len(accepted) == 1
    assert accepted[0]["train_number"] == "12301"
    assert len(quarantined) == 4


# ==============================================================================
# 3. Schedules Transformation Tests
# ==============================================================================

def test_transform_schedules_endpoint_nulls():
    raw_records = [
        {
            "id": 100,
            "train_number": "04601",
            "station_code": "jat",
            "station_name": "JAMMU TAWI",
            "arrival": "None",  # Origin endpoint
            "departure": "10:40:00",
            "day": 1,
        },
        {
            "id": 101,
            "train_number": "04601",
            "station_code": "uhp",
            "station_name": "UDHAMPUR",
            "arrival": "12:15:00",
            "departure": "None",  # Terminus endpoint
            "day": 1,
        },
    ]
    accepted, quarantined = transform_schedules(raw_records)
    assert len(quarantined) == 0
    assert len(accepted) == 2

    s1 = accepted[0]
    assert s1["schedule_id"] == 100
    assert s1["train_number"] == "04601"
    assert s1["station_code"] == "JAT"
    assert s1["arrival_time"] is None  # 'None' normalized to None
    assert s1["departure_time"] == "10:40:00"

    s2 = accepted[1]
    assert s2["arrival_time"] == "12:15:00"
    assert s2["departure_time"] is None  # 'None' normalized to None


def test_transform_schedules_quarantine():
    raw_records = [
        {"id": None, "train_number": "12345", "station_code": "NDLS", "day": 1},
        {"id": 200, "train_number": "", "station_code": "NDLS", "day": 1},
        {"id": 201, "train_number": "12345", "station_code": "", "day": 1},
        {"id": 202, "train_number": "12345", "station_code": "NDLS", "day": 0},  # Day <= 0
        {"id": 202, "train_number": "12345", "station_code": "NDLS", "day": 1},  # Dup ID
    ]
    accepted, quarantined = transform_schedules(raw_records)
    assert len(accepted) == 0
    assert len(quarantined) == 5


# ==============================================================================
# 4. Journey DataFrame Transformation & Leakage Safeguards
# ==============================================================================

def test_transform_journey_dataframe_training():
    df = pd.DataFrame(
        {
            "journey_id": ["J_01", "J_02", "J_01", "J_BAD_TARGET", "J_NEG_DIST"],
            "train_number": ["01234", "05678", "01234", "09999", "08888"],
            "distance_km": [500, 1000, 500, 200, -50],
            "seat_utilisation_pct": [80.0, 95.5, 80.0, 50.0, 60.0],
            "is_delayed": [0, 1, 0, 99, 1],  # 99 is invalid target
            "primary_delay_cause": ["On Time", "Signal", "On Time", "On Time", "On Time"],
            "delay_minutes": [0, 45, 0, 0, 10],
        }
    )
    clean_df, quarantined = transform_journey_dataframe(df, is_training=True)

    # J_01 duplicate, J_BAD_TARGET (non-binary target), and J_NEG_DIST (distance < 0) quarantined
    assert len(clean_df) == 2
    assert set(clean_df["journey_id"]) == {"J_01", "J_02"}
    assert clean_df.iloc[0]["train_number"] == "01234"
    assert isinstance(clean_df.iloc[0]["train_number"], str)
    assert len(quarantined) == 3


def test_transform_journey_dataframe_test_leakage_removal():
    df = pd.DataFrame(
        {
            "journey_id": ["TEST_01", "TEST_02"],
            "train_number": ["01234", "05678"],
            "distance_km": [500, 1000],
            # Unauthorized training outcome fields present in test input:
            "is_delayed": [0, 1],
            "primary_delay_cause": ["Equipment", "Weather"],
            "delay_minutes": [15, 30],
        }
    )
    clean_df, quarantined = transform_journey_dataframe(df, is_training=False)
    assert len(clean_df) == 2
    # Leakage columns must be strictly excluded from test output
    assert "is_delayed" not in clean_df.columns
    assert "primary_delay_cause" not in clean_df.columns
    assert "delay_minutes" not in clean_df.columns


# ==============================================================================
# 5. Atomic Parquet Write and Readback
# ==============================================================================

def test_write_parquet_atomic(tmp_path: Path):
    target = tmp_path / "test_stations.parquet"
    data = [
        {"station_code": "NDLS", "station_name": "New Delhi", "state": "Delhi", "zone": "NR", "address": "Pahar Ganj", "latitude": 28.6139, "longitude": 77.2090}
    ]
    df = pd.DataFrame(data)
    bytes_written = write_parquet_atomic(df, target, schema=STATIONS_SCHEMA)

    assert target.exists()
    assert bytes_written > 0

    # Read back and verify
    read_table = pq.read_table(target)
    assert read_table.num_rows == 1
    assert read_table.column("station_code")[0].as_py() == "NDLS"


def test_write_parquet_atomic_empty_fails(tmp_path: Path):
    target = tmp_path / "empty.parquet"
    empty_df = pd.DataFrame(columns=["station_code", "station_name"])
    with pytest.raises(ValueError):
        write_parquet_atomic(empty_df, target)
    assert not target.exists()


# ==============================================================================
# 6. Stream CSV to Parquet Chunked
# ==============================================================================

def test_stream_csv_to_parquet_fixture(tmp_path: Path):
    csv_file = tmp_path / "sample_journey.csv"
    csv_file.write_text(
        "journey_id,train_number,distance_km,seat_utilisation_pct,is_delayed,primary_delay_cause,delay_minutes\n"
        "J1,01234,100,50.0,0,On Time,0\n"
        "J2,05678,200,80.0,1,Signal,20\n"
        "J3,09999,-5,60.0,0,On Time,0\n"  # bad dist
        "J4,01111,150,150.0,0,On Time,0\n" # bad util > 100
    )
    parquet_target = tmp_path / "output.parquet"
    accepted_count, file_size, quarantined = stream_csv_to_parquet(
        csv_file, parquet_target, is_training=True, chunk_size=2
    )

    assert accepted_count == 2
    assert len(quarantined) == 2
    assert parquet_target.exists()
    assert file_size > 0

    # Verify readback
    table = pq.read_table(parquet_target)
    assert table.num_rows == 2
    assert set(table.column("journey_id").to_pylist()) == {"J1", "J2"}


# ==============================================================================
# 7. Quality Report and Quarantine File Persistence
# ==============================================================================

def test_quality_report_persistence(tmp_path: Path):
    quarantine_items = [{"record": {"id": 1}, "rejection_reason": "Test Reason"}]
    q_path = save_quarantine_records(quarantine_items, "test_dataset", tmp_path / "quarantine")
    assert q_path.exists()

    report = QualityReport()
    report.accepted_counts["test_dataset"] = 10
    report.quarantined_counts["test_dataset"] = 1
    report_file = tmp_path / "quality_report.json"
    saved = save_quality_report(report, report_file)

    assert saved.exists()
    with open(saved, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["accepted_counts"]["test_dataset"] == 10
    assert data["quarantined_counts"]["test_dataset"] == 1
