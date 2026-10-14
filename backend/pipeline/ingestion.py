"""
Data Ingestion Layer for RAIL / SIGNAL.

Provides verified, memory-efficient extraction routines for:
1. DataMeet GeoJSON Station FeatureCollections (coordinates & properties)
2. DataMeet GeoJSON Train FeatureCollections (coordinates & properties)
3. DataMeet JSON Schedules (timetable stop records)
4. Kaggle Journey Datasets (chunked / streamed CSV reader with identifier preservation)
5. Kaggle Sample Submission & Data Dictionary CSVs

All functions return structured record payloads alongside standardized ingestion metadata.
"""

from __future__ import annotations

import csv
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Generator, Iterator, List, Optional, Tuple, Union

import pandas as pd

logger = logging.getLogger("rail_signal.ingestion")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [rail_signal.ingestion] %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


@dataclass
class IngestionMetadata:
    """Metadata tracking file ingestion execution and schema verification."""
    source_path: str
    source_format: str
    status: str  # "SUCCESS" or "FAILED"
    total_records: int = 0
    columns: List[str] = field(default_factory=list)
    file_size_bytes: int = 0
    error_message: Optional[str] = None
    extra_details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_path": self.source_path,
            "source_format": self.source_format,
            "status": self.status,
            "total_records": self.total_records,
            "columns": self.columns,
            "file_size_bytes": self.file_size_bytes,
            "error_message": self.error_message,
            "extra_details": self.extra_details,
        }


def _verify_file_exists(file_path: Union[str, Path]) -> Path:
    """Ensure file exists and is a readable file."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    if not path.is_file():
        raise ValueError(f"Path is not a regular file: {path}")
    return path


def read_stations_geojson(
    file_path: Union[str, Path] = "data/raw/datameet/stations.json",
) -> Tuple[List[Dict[str, Any]], IngestionMetadata]:
    """
    Ingests DataMeet stations GeoJSON FeatureCollection.

    Extracts:
    - properties: code, name, state, zone, address
    - coordinates: longitude (coords[0]), latitude (coords[1])

    Preserves station codes as uppercase strings.

    Returns:
        Tuple of (flattened_records_list, IngestionMetadata)
    """
    path = _verify_file_exists(file_path)
    file_size = path.stat().st_size

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        err = f"Malformed JSON in stations file {path}: {exc}"
        logger.error(err)
        return [], IngestionMetadata(
            source_path=str(path),
            source_format="GeoJSON",
            status="FAILED",
            file_size_bytes=file_size,
            error_message=err,
        )

    if not isinstance(data, dict) or data.get("type") != "FeatureCollection":
        err = (
            f"Invalid GeoJSON structure in {path}. "
            f"Expected dict with type='FeatureCollection', got {type(data)}"
        )
        logger.error(err)
        return [], IngestionMetadata(
            source_path=str(path),
            source_format="GeoJSON",
            status="FAILED",
            file_size_bytes=file_size,
            error_message=err,
        )

    features = data.get("features")
    if not isinstance(features, list):
        err = f"Missing 'features' list in FeatureCollection {path}"
        logger.error(err)
        return [], IngestionMetadata(
            source_path=str(path),
            source_format="GeoJSON",
            status="FAILED",
            file_size_bytes=file_size,
            error_message=err,
        )

    records: List[Dict[str, Any]] = []
    required_keys = {"code", "name"}

    for idx, feat in enumerate(features):
        if not isinstance(feat, dict) or "properties" not in feat:
            raise ValueError(f"Feature at index {idx} in {path} is not a valid GeoJSON Feature")

        props = dict(feat.get("properties") or {})
        missing = required_keys - set(props.keys())
        if missing:
            raise ValueError(f"Feature at index {idx} missing required properties: {missing}")

        # Preserve station code as string
        raw_code = props.get("code")
        props["code"] = str(raw_code).strip().upper() if raw_code is not None else ""

        geometry = feat.get("geometry") or {}
        coords = geometry.get("coordinates")
        if isinstance(coords, (list, tuple)) and len(coords) >= 2:
            props["longitude"] = float(coords[0]) if coords[0] is not None else None
            props["latitude"] = float(coords[1]) if coords[1] is not None else None
        else:
            props["longitude"] = None
            props["latitude"] = None

        records.append(props)

    columns = list(records[0].keys()) if records else []
    metadata = IngestionMetadata(
        source_path=str(path),
        source_format="GeoJSON FeatureCollection",
        status="SUCCESS",
        total_records=len(records),
        columns=columns,
        file_size_bytes=file_size,
        extra_details={"geojson_type": "Point"},
    )
    logger.info("Successfully ingested %d station records from %s", len(records), path)
    return records, metadata


def read_trains_geojson(
    file_path: Union[str, Path] = "data/raw/datameet/trains.json",
) -> Tuple[List[Dict[str, Any]], IngestionMetadata]:
    """
    Ingests DataMeet trains GeoJSON FeatureCollection.

    Extracts:
    - properties: number, name, type, zone, from_station_code, to_station_code,
      classes, durations, coach class counts, etc.
    - geometry: LineString coordinates sequence if present.

    Preserves train numbers as strings with leading zeros (e.g., '04601').

    Returns:
        Tuple of (records_list, IngestionMetadata)
    """
    path = _verify_file_exists(file_path)
    file_size = path.stat().st_size

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        err = f"Malformed JSON in trains file {path}: {exc}"
        logger.error(err)
        return [], IngestionMetadata(
            source_path=str(path),
            source_format="GeoJSON",
            status="FAILED",
            file_size_bytes=file_size,
            error_message=err,
        )

    if not isinstance(data, dict) or data.get("type") != "FeatureCollection":
        err = (
            f"Invalid GeoJSON structure in {path}. "
            f"Expected dict with type='FeatureCollection', got {type(data)}"
        )
        logger.error(err)
        return [], IngestionMetadata(
            source_path=str(path),
            source_format="GeoJSON",
            status="FAILED",
            file_size_bytes=file_size,
            error_message=err,
        )

    features = data.get("features")
    if not isinstance(features, list):
        err = f"Missing 'features' list in FeatureCollection {path}"
        logger.error(err)
        return [], IngestionMetadata(
            source_path=str(path),
            source_format="GeoJSON",
            status="FAILED",
            file_size_bytes=file_size,
            error_message=err,
        )

    records: List[Dict[str, Any]] = []
    required_keys = {"number", "name"}

    for idx, feat in enumerate(features):
        if not isinstance(feat, dict) or "properties" not in feat:
            raise ValueError(f"Feature at index {idx} in {path} is not a valid GeoJSON Feature")

        props = dict(feat.get("properties") or {})
        missing = required_keys - set(props.keys())
        if missing:
            raise ValueError(f"Feature at index {idx} missing required properties: {missing}")

        # Preserve train number as string, maintaining leading zeros
        raw_num = props.get("number")
        props["number"] = str(raw_num).strip() if raw_num is not None else ""

        # Station codes as strings
        if "from_station_code" in props and props["from_station_code"] is not None:
            props["from_station_code"] = str(props["from_station_code"]).strip().upper()
        if "to_station_code" in props and props["to_station_code"] is not None:
            props["to_station_code"] = str(props["to_station_code"]).strip().upper()

        records.append(props)

    columns = list(records[0].keys()) if records else []
    metadata = IngestionMetadata(
        source_path=str(path),
        source_format="GeoJSON FeatureCollection",
        status="SUCCESS",
        total_records=len(records),
        columns=columns,
        file_size_bytes=file_size,
        extra_details={"geojson_type": "LineString"},
    )
    logger.info("Successfully ingested %d train records from %s", len(records), path)
    return records, metadata


def read_schedules_json(
    file_path: Union[str, Path] = "data/raw/datameet/schedules.json",
    limit: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], IngestionMetadata]:
    """
    Ingests DataMeet timetable stop schedules from JSON Array.

    Keys:
    - id: Unique integer stop ID
    - train_number: Train identifier (preserved as string with leading zeros)
    - train_name: Train official name
    - station_code: Station identifier (preserved as uppercase string)
    - station_name: Station official name
    - arrival: Scheduled arrival time ('None' for origin stop)
    - departure: Scheduled departure time ('None' for terminus stop)
    - day: Journey day count (1, 2, 3...)

    Args:
        file_path: Path to schedules.json
        limit: Optional maximum number of records to ingest (useful for previews/tests)

    Returns:
        Tuple of (records_list, IngestionMetadata)
    """
    path = _verify_file_exists(file_path)
    file_size = path.stat().st_size

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        err = f"Malformed JSON in schedules file {path}: {exc}"
        logger.error(err)
        return [], IngestionMetadata(
            source_path=str(path),
            source_format="JSON Array",
            status="FAILED",
            file_size_bytes=file_size,
            error_message=err,
        )

    if not isinstance(data, list):
        err = f"Invalid JSON structure in {path}. Expected JSON list, got {type(data)}"
        logger.error(err)
        return [], IngestionMetadata(
            source_path=str(path),
            source_format="JSON Array",
            status="FAILED",
            file_size_bytes=file_size,
            error_message=err,
        )

    total_in_file = len(data)
    items_to_process = data[:limit] if limit is not None else data

    records: List[Dict[str, Any]] = []
    required_keys = {"id", "train_number", "station_code"}

    for idx, item in enumerate(items_to_process):
        if not isinstance(item, dict):
            raise ValueError(f"Record at index {idx} in {path} is not a JSON object")

        missing = required_keys - set(item.keys())
        if missing:
            raise ValueError(f"Schedule record at index {idx} missing required keys: {missing}")

        rec = dict(item)
        # Preserve string identifiers
        raw_num = rec.get("train_number")
        rec["train_number"] = str(raw_num).strip() if raw_num is not None else ""

        raw_code = rec.get("station_code")
        rec["station_code"] = str(raw_code).strip().upper() if raw_code is not None else ""

        records.append(rec)

    columns = list(records[0].keys()) if records else []
    metadata = IngestionMetadata(
        source_path=str(path),
        source_format="JSON Array",
        status="SUCCESS",
        total_records=len(records),
        columns=columns,
        file_size_bytes=file_size,
        extra_details={"total_file_records": total_in_file, "limit_applied": limit},
    )
    logger.info("Successfully ingested %d schedule records from %s", len(records), path)
    return records, metadata


# Verified column types for Kaggle CSVs to strictly preserve string IDs
KAGGLE_CSV_DTYPES = {
    "journey_id": "string",
    "train_number": "string",
    "train_type": "string",
    "departure_date": "string",
    "zone": "string",
    "zone_abbr": "string",
    "source_station_category": "string",
    "destination_station_category": "string",
    "traction_type": "string",
    "primary_delay_cause": "string",
}


def read_journey_csv_chunks(
    file_path: Union[str, Path],
    chunk_size: int = 50000,
    max_chunks: Optional[int] = None,
) -> Generator[pd.DataFrame, None, IngestionMetadata]:
    """
    Memory-efficient chunked reader for large journey CSV datasets.

    Yields pandas DataFrame chunks with verified string preservation for:
    - journey_id
    - train_number
    - departure_date
    - zone / categorical codes

    Returns IngestionMetadata upon generator exhaustion (via StopIteration value).
    """
    path = _verify_file_exists(file_path)
    file_size = path.stat().st_size

    total_rows = 0
    chunks_yielded = 0
    columns: List[str] = []

    try:
        reader = pd.read_csv(
            path,
            chunksize=chunk_size,
            dtype=KAGGLE_CSV_DTYPES,
            low_memory=False,
            encoding="utf-8",
        )

        for chunk in reader:
            if not columns:
                columns = list(chunk.columns)
            total_rows += len(chunk)
            chunks_yielded += 1
            yield chunk

            if max_chunks is not None and chunks_yielded >= max_chunks:
                break

    except Exception as exc:
        err = f"Failed to stream CSV chunks from {path}: {exc}"
        logger.error(err)
        return IngestionMetadata(
            source_path=str(path),
            source_format="CSV (Chunked)",
            status="FAILED",
            total_records=total_rows,
            columns=columns,
            file_size_bytes=file_size,
            error_message=err,
        )

    return IngestionMetadata(
        source_path=str(path),
        source_format="CSV (Chunked)",
        status="SUCCESS",
        total_records=total_rows,
        columns=columns,
        file_size_bytes=file_size,
        extra_details={"chunk_size": chunk_size, "chunks_read": chunks_yielded},
    )


def read_journey_train_csv(
    file_path: Union[str, Path] = "data/raw/operational_journeys/ir_train.csv",
    nrows: Optional[int] = None,
) -> Tuple[pd.DataFrame, IngestionMetadata]:
    """
    Reads the operational journey training dataset with identifier preservation.

    Notice: For memory safety on the full 1.5M row dataset, use `read_journey_csv_chunks`
    for full pipeline execution. This function supports `nrows` for controlled ingestion.
    """
    path = _verify_file_exists(file_path)
    file_size = path.stat().st_size

    try:
        df = pd.read_csv(
            path,
            nrows=nrows,
            dtype=KAGGLE_CSV_DTYPES,
            low_memory=False,
            encoding="utf-8",
        )
    except Exception as exc:
        err = f"Error reading train CSV {path}: {exc}"
        logger.error(err)
        return pd.DataFrame(), IngestionMetadata(
            source_path=str(path),
            source_format="CSV",
            status="FAILED",
            file_size_bytes=file_size,
            error_message=err,
        )

    metadata = IngestionMetadata(
        source_path=str(path),
        source_format="CSV",
        status="SUCCESS",
        total_records=len(df),
        columns=list(df.columns),
        file_size_bytes=file_size,
        extra_details={"nrows_requested": nrows},
    )
    logger.info("Ingested %d train rows from %s", len(df), path)
    return df, metadata


def read_journey_test_csv(
    file_path: Union[str, Path] = "data/raw/operational_journeys/ir_test.csv",
    nrows: Optional[int] = None,
) -> Tuple[pd.DataFrame, IngestionMetadata]:
    """Reads the journey test CSV dataset with string identifier preservation."""
    path = _verify_file_exists(file_path)
    file_size = path.stat().st_size

    try:
        df = pd.read_csv(
            path,
            nrows=nrows,
            dtype=KAGGLE_CSV_DTYPES,
            low_memory=False,
            encoding="utf-8",
        )
    except Exception as exc:
        err = f"Error reading test CSV {path}: {exc}"
        logger.error(err)
        return pd.DataFrame(), IngestionMetadata(
            source_path=str(path),
            source_format="CSV",
            status="FAILED",
            file_size_bytes=file_size,
            error_message=err,
        )

    metadata = IngestionMetadata(
        source_path=str(path),
        source_format="CSV",
        status="SUCCESS",
        total_records=len(df),
        columns=list(df.columns),
        file_size_bytes=file_size,
        extra_details={"nrows_requested": nrows},
    )
    logger.info("Ingested %d test rows from %s", len(df), path)
    return df, metadata


def read_sample_submission_csv(
    file_path: Union[str, Path] = "data/raw/operational_journeys/ir_sample_submission.csv",
    nrows: Optional[int] = None,
) -> Tuple[pd.DataFrame, IngestionMetadata]:
    """Reads the journey sample submission CSV with string identifier preservation."""
    path = _verify_file_exists(file_path)
    file_size = path.stat().st_size

    try:
        df = pd.read_csv(
            path,
            nrows=nrows,
            dtype={"journey_id": "string"},
            encoding="utf-8",
        )
    except Exception as exc:
        err = f"Error reading sample submission CSV {path}: {exc}"
        logger.error(err)
        return pd.DataFrame(), IngestionMetadata(
            source_path=str(path),
            source_format="CSV",
            status="FAILED",
            file_size_bytes=file_size,
            error_message=err,
        )

    expected_cols = ["journey_id", "is_delayed"]
    if list(df.columns) != expected_cols:
        raise ValueError(
            f"Unexpected columns in sample submission: {list(df.columns)}. Expected {expected_cols}"
        )

    metadata = IngestionMetadata(
        source_path=str(path),
        source_format="CSV",
        status="SUCCESS",
        total_records=len(df),
        columns=list(df.columns),
        file_size_bytes=file_size,
    )
    return df, metadata


def read_data_dictionary_csv(
    file_path: Union[str, Path] = "data/raw/operational_journeys/ir_data_dictionary.csv",
) -> Tuple[pd.DataFrame, IngestionMetadata]:
    """Reads the dataset column dictionary CSV."""
    path = _verify_file_exists(file_path)
    file_size = path.stat().st_size

    try:
        df = pd.read_csv(path, dtype="string", encoding="utf-8")
    except Exception as exc:
        err = f"Error reading data dictionary CSV {path}: {exc}"
        logger.error(err)
        return pd.DataFrame(), IngestionMetadata(
            source_path=str(path),
            source_format="CSV",
            status="FAILED",
            file_size_bytes=file_size,
            error_message=err,
        )

    metadata = IngestionMetadata(
        source_path=str(path),
        source_format="CSV",
        status="SUCCESS",
        total_records=len(df),
        columns=list(df.columns),
        file_size_bytes=file_size,
    )
    return df, metadata
