"""
Unit tests for data ingestion layer in backend.pipeline.ingestion.
"""

import json
from pathlib import Path

import pandas as pd
import pytest

from backend.pipeline.ingestion import (
    IngestionMetadata,
    read_data_dictionary_csv,
    read_journey_csv_chunks,
    read_journey_test_csv,
    read_journey_train_csv,
    read_sample_submission_csv,
    read_schedules_json,
    read_stations_geojson,
    read_trains_geojson,
)


@pytest.fixture
def temp_stations_file(tmp_path: Path) -> Path:
    geojson_data = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [77.2090, 28.6139]},
                "properties": {
                    "code": "ndls",
                    "name": "New Delhi",
                    "zone": "NR",
                    "state": "Delhi",
                    "address": "Bhavbhuti Marg, Ratan Lal Market",
                },
            },
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [72.8358, 18.9398]},
                "properties": {
                    "code": "CSMT",
                    "name": "Chhatrapati Shivaji Maharaj Terminus",
                    "zone": "CR",
                    "state": "Maharashtra",
                    "address": "Fort, Mumbai",
                },
            },
        ],
    }
    file_path = tmp_path / "sample_stations.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(geojson_data, f)
    return file_path


@pytest.fixture
def temp_trains_file(tmp_path: Path) -> Path:
    geojson_data = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[77.2, 28.6], [72.8, 18.9]],
                },
                "properties": {
                    "number": "01234",
                    "name": "Special Express",
                    "type": "EXP",
                    "zone": "NR",
                    "from_station_code": "ndls",
                    "to_station_code": "csmt",
                    "duration_h": 16,
                    "duration_m": 30,
                    "distance": 1400,
                },
            }
        ],
    }
    file_path = tmp_path / "sample_trains.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(geojson_data, f)
    return file_path


@pytest.fixture
def temp_schedules_file(tmp_path: Path) -> Path:
    schedules_data = [
        {
            "id": 1001,
            "train_number": "01234",
            "train_name": "Special Express",
            "station_code": "ndls",
            "station_name": "New Delhi",
            "arrival": "None",
            "departure": "06:00:00",
            "day": 1,
        },
        {
            "id": 1002,
            "train_number": "01234",
            "train_name": "Special Express",
            "station_code": "csmt",
            "station_name": "Chhatrapati Shivaji Maharaj Terminus",
            "arrival": "22:30:00",
            "departure": "None",
            "day": 1,
        },
    ]
    file_path = tmp_path / "sample_schedules.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(schedules_data, f)
    return file_path


@pytest.fixture
def temp_journey_csv(tmp_path: Path) -> Path:
    csv_content = (
        "journey_id,train_number,train_type,departure_date,zone,distance_km,seat_utilisation_pct,is_delayed,primary_delay_cause,delay_minutes\n"
        "J_001,01234,EXP,2024-01-01,NR,1400,85.5,0,On Time,0\n"
        "J_002,05678,SF,2024-01-02,WR,800,92.0,1,Signal Failure,45\n"
        "J_003,09999,PASS,2024-01-03,CR,120,60.0,0,On Time,0\n"
    )
    file_path = tmp_path / "sample_journey.csv"
    file_path.write_text(csv_content, encoding="utf-8")
    return file_path


def test_read_stations_geojson_preserves_identifiers(temp_stations_file: Path):
    records, meta = read_stations_geojson(temp_stations_file)
    assert meta.status == "SUCCESS"
    assert meta.total_records == 2
    assert "longitude" in meta.columns
    assert "latitude" in meta.columns
    # Check string uppercase standardization
    assert records[0]["code"] == "NDLS"
    assert records[0]["name"] == "New Delhi"
    assert records[0]["longitude"] == 77.2090
    assert records[0]["latitude"] == 28.6139
    assert records[1]["code"] == "CSMT"


def test_read_trains_geojson_preserves_leading_zeros(temp_trains_file: Path):
    records, meta = read_trains_geojson(temp_trains_file)
    assert meta.status == "SUCCESS"
    assert meta.total_records == 1
    # Check string leading zero preservation
    assert records[0]["number"] == "01234"
    assert isinstance(records[0]["number"], str)
    assert records[0]["from_station_code"] == "NDLS"
    assert records[0]["to_station_code"] == "CSMT"


def test_read_schedules_json(temp_schedules_file: Path):
    records, meta = read_schedules_json(temp_schedules_file)
    assert meta.status == "SUCCESS"
    assert meta.total_records == 2
    assert records[0]["train_number"] == "01234"
    assert records[0]["station_code"] == "NDLS"
    assert records[0]["arrival"] == "None"


def test_read_schedules_json_limit(temp_schedules_file: Path):
    records, meta = read_schedules_json(temp_schedules_file, limit=1)
    assert meta.status == "SUCCESS"
    assert meta.total_records == 1
    assert meta.extra_details["total_file_records"] == 2
    assert meta.extra_details["limit_applied"] == 1


def test_read_journey_csv_chunks_preserves_identifiers(temp_journey_csv: Path):
    chunks = []
    gen = read_journey_csv_chunks(temp_journey_csv, chunk_size=2)
    try:
        while True:
            chunks.append(next(gen))
    except StopIteration as stop_val:
        meta = stop_val.value

    assert len(chunks) == 2  # 3 rows chunked by 2 = 2 chunks
    assert meta.status == "SUCCESS"
    assert meta.total_records == 3
    # Check string preservation in chunk dataframes
    df_first = chunks[0]
    assert df_first.iloc[0]["train_number"] == "01234"
    assert isinstance(df_first.iloc[0]["train_number"], str)
    assert df_first.iloc[0]["journey_id"] == "J_001"


def test_read_journey_train_csv_nrows(temp_journey_csv: Path):
    df, meta = read_journey_train_csv(temp_journey_csv, nrows=2)
    assert meta.status == "SUCCESS"
    assert len(df) == 2
    assert df.iloc[0]["train_number"] == "01234"
    assert isinstance(df.iloc[0]["train_number"], str)


def test_missing_file_raises_filenotfound(tmp_path: Path):
    missing_path = tmp_path / "non_existent.json"
    with pytest.raises(FileNotFoundError):
        read_stations_geojson(missing_path)

    with pytest.raises(FileNotFoundError):
        read_schedules_json(missing_path)


def test_invalid_geojson_structure(tmp_path: Path):
    invalid_file = tmp_path / "invalid_structure.json"
    invalid_file.write_text(json.dumps({"type": "InvalidType"}), encoding="utf-8")

    records, meta = read_stations_geojson(invalid_file)
    assert meta.status == "FAILED"
    assert len(records) == 0
    assert "Invalid GeoJSON structure" in meta.error_message
