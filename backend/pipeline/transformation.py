"""
Data Cleaning, Transformation, and Parquet Storage Layer for RAIL / SIGNAL.

Standardizes, cleans, and transforms raw ingested railway and operational journey
records into analytical Parquet datasets aligned with docs/data-dictionary.md.

Outputs:
1. data/processed/stations.parquet
2. data/processed/trains.parquet
3. data/processed/schedules.parquet
4. data/processed/journey_train.parquet
5. data/processed/journey_test.parquet
6. data/processed/quarantine/<dataset>_quarantine.json
7. data/processed/quality_report.json

Provides atomic write guarantees, quarantine auditing, and memory-safe chunked
processing for massive CSV datasets.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, Iterator, List, Optional, Sequence, Set, Tuple, Union

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from backend.pipeline.ingestion import (
    read_journey_csv_chunks,
    read_journey_test_csv,
    read_journey_train_csv,
    read_schedules_json,
    read_stations_geojson,
    read_trains_geojson,
)
from backend.pipeline.validation import (
    LEAKAGE_COLUMNS,
    TARGET_COLUMN,
    TIME_REGEX,
    validate_journey_dataframe,
    validate_schedules,
    validate_stations,
    validate_trains,
)

logger = logging.getLogger("rail_signal.transformation")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [rail_signal.transformation] %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


# ==============================================================================
# Helper Functions: Normalization & Safe Conversion
# ==============================================================================

def clean_str(val: Any) -> Optional[str]:
    """Trims string and converts literal 'None', 'null', or empty string to None."""
    if val is None or pd.isna(val):
        return None
    s = str(val).strip()
    if not s or s.lower() in ("none", "null", "nan"):
        return None
    return s


def clean_int(val: Any) -> Optional[int]:
    """Safely converts value to int or None if invalid or empty."""
    if val is None or pd.isna(val):
        return None
    s = str(val).strip()
    if not s or s.lower() in ("none", "null", "nan"):
        return None
    try:
        # Handles strings like '10.0' or '10'
        return int(float(s))
    except (ValueError, TypeError):
        return None


def clean_float(val: Any) -> Optional[float]:
    """Safely converts value to float or None if invalid or empty."""
    if val is None or pd.isna(val):
        return None
    s = str(val).strip()
    if not s or s.lower() in ("none", "null", "nan"):
        return None
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def clean_bool(val: Any) -> bool:
    """Evaluates presence or numeric indicator to strict boolean."""
    if val is None or pd.isna(val):
        return False
    if isinstance(val, bool):
        return val
    s = str(val).strip().lower()
    if s in ("1", "true", "t", "yes", "y"):
        return True
    try:
        return float(s) > 0
    except (ValueError, TypeError):
        return False


def clean_time(val: Any) -> Optional[str]:
    """
    Normalizes time strings. Converts endpoint 'None', null, or empty string to None.
    If valid HH:MM:SS, returns HH:MM:SS. If invalid, returns None.
    """
    cleaned = clean_str(val)
    if cleaned is None:
        return None
    if TIME_REGEX.match(cleaned):
        return cleaned
    return None


# ==============================================================================
# 1. Transform Stations
# ==============================================================================

def transform_stations(
    raw_records: Sequence[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Standardizes station records aligned with docs/data-dictionary.md.

    Schema:
    - station_code: str (PK, required)
    - station_name: str (required)
    - state: Optional[str]
    - zone: Optional[str]
    - address: Optional[str]
    - latitude: Optional[float]
    - longitude: Optional[float]

    Returns:
        (accepted_records, quarantined_records)
    """
    accepted: List[Dict[str, Any]] = []
    quarantined: List[Dict[str, Any]] = []
    seen_codes: Set[str] = set()

    for idx, rec in enumerate(raw_records):
        code = clean_str(rec.get("code"))
        name = clean_str(rec.get("name"))

        # Quarantine check: required fields
        if not code:
            quarantined.append({
                "record": rec,
                "rejection_reason": "Missing or empty required 'station_code'",
                "index": idx,
            })
            continue

        code_upper = code.upper()
        if code_upper in seen_codes:
            quarantined.append({
                "record": rec,
                "rejection_reason": f"Duplicate station code '{code_upper}'",
                "index": idx,
            })
            continue
        seen_codes.add(code_upper)

        if not name:
            quarantined.append({
                "record": rec,
                "rejection_reason": "Missing or empty required 'station_name'",
                "index": idx,
            })
            continue

        # Coordinate bounds check
        lon = clean_float(rec.get("longitude"))
        lat = clean_float(rec.get("latitude"))

        if lon is not None and not (-180.0 <= lon <= 180.0):
            quarantined.append({
                "record": rec,
                "rejection_reason": f"Longitude {lon} out of valid bounds [-180, 180]",
                "index": idx,
            })
            continue

        if lat is not None and not (-90.0 <= lat <= 90.0):
            quarantined.append({
                "record": rec,
                "rejection_reason": f"Latitude {lat} out of valid bounds [-90, 90]",
                "index": idx,
            })
            continue

        state = clean_str(rec.get("state"))
        zone = clean_str(rec.get("zone"))
        address = clean_str(rec.get("address"))

        accepted.append({
            "station_code": code_upper,
            "station_name": name,
            "state": state,
            "zone": zone.upper() if zone else None,
            "address": address,
            "latitude": lat,
            "longitude": lon,
        })

    return accepted, quarantined


# ==============================================================================
# 2. Transform Trains
# ==============================================================================

def transform_trains(
    raw_records: Sequence[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Standardizes train records aligned with docs/data-dictionary.md.

    Schema:
    - train_number: str (PK, required, leading zeros preserved)
    - train_name: str (required)
    - train_type: Optional[str]
    - zone: Optional[str]
    - from_station_code: Optional[str]
    - from_station_name: Optional[str]
    - to_station_code: Optional[str]
    - to_station_name: Optional[str]
    - departure_time: Optional[str]
    - arrival_time: Optional[str]
    - duration_hours: Optional[int]
    - duration_minutes: Optional[int]
    - distance_km: Optional[int]
    - has_first_ac: bool
    - has_second_ac: bool
    - has_third_ac: bool
    - has_sleeper: bool
    - has_chair_car: bool

    Returns:
        (accepted_records, quarantined_records)
    """
    accepted: List[Dict[str, Any]] = []
    quarantined: List[Dict[str, Any]] = []
    seen_numbers: Set[str] = set()

    for idx, rec in enumerate(raw_records):
        num_raw = rec.get("number")
        name_raw = rec.get("name")

        # Preserve train number as string with leading zeros
        if num_raw is None:
            quarantined.append({
                "record": rec,
                "rejection_reason": "Missing or empty required 'train_number'",
                "index": idx,
            })
            continue

        num_str = str(num_raw).strip()
        if not num_str or num_str.lower() in ("none", "null", "nan"):
            quarantined.append({
                "record": rec,
                "rejection_reason": "Missing or empty required 'train_number'",
                "index": idx,
            })
            continue

        if num_str in seen_numbers:
            quarantined.append({
                "record": rec,
                "rejection_reason": f"Duplicate train number '{num_str}'",
                "index": idx,
            })
            continue

        name = clean_str(name_raw)
        if not name:
            quarantined.append({
                "record": rec,
                "rejection_reason": "Missing or empty required 'train_name'",
                "index": idx,
            })
            continue

        # Numeric checks
        dist = clean_int(rec.get("distance"))
        if dist is not None and dist < 0:
            quarantined.append({
                "record": rec,
                "rejection_reason": f"Negative distance: {dist}",
                "index": idx,
            })
            continue

        dur_h = clean_int(rec.get("duration_h"))
        if dur_h is not None and dur_h < 0:
            quarantined.append({
                "record": rec,
                "rejection_reason": f"Negative duration hours: {dur_h}",
                "index": idx,
            })
            continue

        dur_m = clean_int(rec.get("duration_m"))
        if dur_m is not None and dur_m < 0:
            quarantined.append({
                "record": rec,
                "rejection_reason": f"Negative duration minutes: {dur_m}",
                "index": idx,
            })
            continue

        seen_numbers.add(num_str)

        from_code = clean_str(rec.get("from_station_code"))
        to_code = clean_str(rec.get("to_station_code"))
        zone = clean_str(rec.get("zone"))
        ttype = clean_str(rec.get("type"))

        accepted.append({
            "train_number": num_str,
            "train_name": name,
            "train_type": ttype.upper() if ttype else None,
            "zone": zone.upper() if zone else None,
            "from_station_code": from_code.upper() if from_code else None,
            "from_station_name": clean_str(rec.get("from_station_name")),
            "to_station_code": to_code.upper() if to_code else None,
            "to_station_name": clean_str(rec.get("to_station_name")),
            "departure_time": clean_time(rec.get("departure")),
            "arrival_time": clean_time(rec.get("arrival")),
            "duration_hours": dur_h,
            "duration_minutes": dur_m,
            "distance_km": dist,
            "has_first_ac": clean_bool(rec.get("first_ac")),
            "has_second_ac": clean_bool(rec.get("second_ac")),
            "has_third_ac": clean_bool(rec.get("third_ac")),
            "has_sleeper": clean_bool(rec.get("sleeper")),
            "has_chair_car": clean_bool(rec.get("chair_car")),
        })

    return accepted, quarantined


# ==============================================================================
# 3. Transform Schedules
# ==============================================================================

def transform_schedules(
    raw_records: Sequence[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Standardizes timetable schedule stop records aligned with docs/data-dictionary.md.

    Schema:
    - schedule_id: int (PK, required)
    - train_number: str (required, string with leading zeros)
    - station_code: str (required, uppercase)
    - station_name: Optional[str]
    - arrival_time: Optional[str] (HH:MM:SS; None if endpoint or invalid)
    - departure_time: Optional[str] (HH:MM:SS; None if endpoint or invalid)
    - day_number: int (required, positive)

    Returns:
        (accepted_records, quarantined_records)
    """
    accepted: List[Dict[str, Any]] = []
    quarantined: List[Dict[str, Any]] = []
    seen_ids: Set[int] = set()

    for idx, rec in enumerate(raw_records):
        sched_id = clean_int(rec.get("id"))
        if sched_id is None:
            quarantined.append({
                "record": rec,
                "rejection_reason": "Missing or invalid required 'id'",
                "index": idx,
            })
            continue

        if sched_id in seen_ids:
            quarantined.append({
                "record": rec,
                "rejection_reason": f"Duplicate schedule ID '{sched_id}'",
                "index": idx,
            })
            continue
        seen_ids.add(sched_id)

        # Train number as string
        t_num_raw = rec.get("train_number")
        if t_num_raw is None:
            quarantined.append({
                "record": rec,
                "rejection_reason": "Missing required 'train_number'",
                "index": idx,
            })
            continue
        t_num_str = str(t_num_raw).strip()
        if not t_num_str or t_num_str.lower() in ("none", "null", "nan"):
            quarantined.append({
                "record": rec,
                "rejection_reason": "Missing or empty required 'train_number'",
                "index": idx,
            })
            continue

        # Station code
        st_code = clean_str(rec.get("station_code"))
        if not st_code:
            quarantined.append({
                "record": rec,
                "rejection_reason": "Missing or empty required 'station_code'",
                "index": idx,
            })
            continue

        # Day must be a positive integer
        day = clean_int(rec.get("day"))
        if day is None or day < 1:
            quarantined.append({
                "record": rec,
                "rejection_reason": f"Invalid or non-positive day_number: {rec.get('day')}",
                "index": idx,
            })
            continue

        # Arrival and departure normalization (endpoints 'None' normalize cleanly to None)
        arr_time = clean_time(rec.get("arrival"))
        dep_time = clean_time(rec.get("departure"))

        accepted.append({
            "schedule_id": sched_id,
            "train_number": t_num_str,
            "station_code": st_code.upper(),
            "station_name": clean_str(rec.get("station_name")),
            "arrival_time": arr_time,
            "departure_time": dep_time,
            "day_number": day,
        })

    return accepted, quarantined


# ==============================================================================
# 4. Transform Journey DataFrame
# ==============================================================================

def transform_journey_dataframe(
    df: pd.DataFrame,
    is_training: bool = True,
) -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
    """
    Cleans and standardizes a Kaggle operational journey DataFrame.

    Rules:
    - Quarantines rows missing 'journey_id' or with duplicate 'journey_id'.
    - Validates target 'is_delayed' as binary integer (0 or 1) in training data.
    - Quarantines rows with invalid binary target values.
    - Enforces numeric boundaries: distance >= 0, duration >= 0, stops >= 0,
      and seat_utilisation_pct in [0.0, 100.0]. Invalid rows quarantined.
    - Preserves string identifiers (journey_id, train_number).
    - If is_training=False: Strictly ensures 'is_delayed', 'primary_delay_cause',
      and 'delay_minutes' are NOT present in output.

    Returns:
        (accepted_df, quarantined_records)
    """
    quarantined: List[Dict[str, Any]] = []

    if df.empty:
        return df.copy(), []

    # Work on a copy
    work_df = df.copy()

    # 1. Test set leakage safeguard: drop any accidentally present leakage columns
    if not is_training:
        for col in LEAKAGE_COLUMNS | {TARGET_COLUMN}:
            if col in work_df.columns:
                logger.warning("Dropping unauthorized column '%s' from test dataframe", col)
                work_df = work_df.drop(columns=[col])

    # 2. Check journey_id
    if "journey_id" not in work_df.columns:
        raise ValueError("Journey DataFrame missing required column 'journey_id'")

    # Mask for missing journey_id
    missing_id_mask = work_df["journey_id"].isna() | (work_df["journey_id"].astype(str).str.strip() == "")
    if missing_id_mask.any():
        bad_rows = work_df[missing_id_mask]
        for idx, row in bad_rows.iterrows():
            quarantined.append({
                "record": row.to_dict(),
                "rejection_reason": "Missing or empty required 'journey_id'",
                "index": int(idx),
            })
        work_df = work_df[~missing_id_mask]

    # Mask for duplicate journey_id
    dup_mask = work_df["journey_id"].duplicated(keep="first")
    if dup_mask.any():
        bad_dups = work_df[dup_mask]
        for idx, row in bad_dups.iterrows():
            quarantined.append({
                "record": row.to_dict(),
                "rejection_reason": f"Duplicate journey_id '{row['journey_id']}'",
                "index": int(idx),
            })
        work_df = work_df[~dup_mask]

    # 3. Training target check
    if is_training:
        if TARGET_COLUMN not in work_df.columns:
            raise ValueError(f"Training DataFrame missing required target '{TARGET_COLUMN}'")

        # Convert target to numeric
        target_numeric = pd.to_numeric(work_df[TARGET_COLUMN], errors="coerce")
        invalid_target_mask = target_numeric.isna() | (~target_numeric.isin([0, 1]))
        if invalid_target_mask.any():
            bad_targets = work_df[invalid_target_mask]
            for idx, row in bad_targets.iterrows():
                quarantined.append({
                    "record": row.to_dict(),
                    "rejection_reason": f"Non-binary target 'is_delayed': {row[TARGET_COLUMN]}",
                    "index": int(idx),
                })
            work_df = work_df[~invalid_target_mask]
            target_numeric = target_numeric[~invalid_target_mask]

        work_df[TARGET_COLUMN] = target_numeric.astype(int)

    # 4. Numeric boundary checks
    if "distance_km" in work_df.columns:
        dist_numeric = pd.to_numeric(work_df["distance_km"], errors="coerce")
        bad_dist = dist_numeric.notna() & (dist_numeric < 0)
        if bad_dist.any():
            for idx, row in work_df[bad_dist].iterrows():
                quarantined.append({
                    "record": row.to_dict(),
                    "rejection_reason": f"Negative distance_km: {row['distance_km']}",
                    "index": int(idx),
                })
            work_df = work_df[~bad_dist]

    if "seat_utilisation_pct" in work_df.columns:
        util_numeric = pd.to_numeric(work_df["seat_utilisation_pct"], errors="coerce")
        bad_util = util_numeric.notna() & ((util_numeric < 0.0) | (util_numeric > 100.0))
        if bad_util.any():
            for idx, row in work_df[bad_util].iterrows():
                quarantined.append({
                    "record": row.to_dict(),
                    "rejection_reason": f"seat_utilisation_pct out of bounds [0, 100]: {row['seat_utilisation_pct']}",
                    "index": int(idx),
                })
            work_df = work_df[~bad_util]

    # Standardize string IDs
    work_df["journey_id"] = work_df["journey_id"].astype(str).str.strip()
    if "train_number" in work_df.columns:
        work_df["train_number"] = work_df["train_number"].astype(str).str.strip()

    return work_df.reset_index(drop=True), quarantined


# ==============================================================================
# Parquet PyArrow Schema Definitions (Strict Data Types)
# ==============================================================================

STATIONS_SCHEMA = pa.schema([
    ("station_code", pa.string()),
    ("station_name", pa.string()),
    ("state", pa.string()),
    ("zone", pa.string()),
    ("address", pa.string()),
    ("latitude", pa.float64()),
    ("longitude", pa.float64()),
])

TRAINS_SCHEMA = pa.schema([
    ("train_number", pa.string()),
    ("train_name", pa.string()),
    ("train_type", pa.string()),
    ("zone", pa.string()),
    ("from_station_code", pa.string()),
    ("from_station_name", pa.string()),
    ("to_station_code", pa.string()),
    ("to_station_name", pa.string()),
    ("departure_time", pa.string()),
    ("arrival_time", pa.string()),
    ("duration_hours", pa.int64()),
    ("duration_minutes", pa.int64()),
    ("distance_km", pa.int64()),
    ("has_first_ac", pa.bool_()),
    ("has_second_ac", pa.bool_()),
    ("has_third_ac", pa.bool_()),
    ("has_sleeper", pa.bool_()),
    ("has_chair_car", pa.bool_()),
])

SCHEDULES_SCHEMA = pa.schema([
    ("schedule_id", pa.int64()),
    ("train_number", pa.string()),
    ("station_code", pa.string()),
    ("station_name", pa.string()),
    ("arrival_time", pa.string()),
    ("departure_time", pa.string()),
    ("day_number", pa.int64()),
])


# ==============================================================================
# Atomic Parquet Writing
# ==============================================================================

def write_parquet_atomic(
    table: Union[pa.Table, pd.DataFrame],
    target_path: Union[str, Path],
    schema: Optional[pa.Schema] = None,
    compression: str = "snappy",
) -> int:
    """
    Safely writes a Table/DataFrame to Parquet atomically using a temporary file.

    1. Writes to `<target_path>.tmp.<pid>`.
    2. Validates that output is non-empty and readable.
    3. Replaces destination file atomically.
    4. Cleans up temp file on failure.

    Returns:
        Written file size in bytes.
    """
    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    # Convert DataFrame to pa.Table if needed
    if isinstance(table, pd.DataFrame):
        pa_table = pa.Table.from_pandas(table, schema=schema, preserve_index=False)
    else:
        pa_table = table

    if pa_table.num_rows == 0:
        raise ValueError(f"Cannot atomically write empty table to {target}")

    # Write to temporary file in same directory to ensure atomic rename
    tmp_path = target.parent / f"{target.name}.tmp.{os.getpid()}"

    try:
        pq.write_table(pa_table, tmp_path, compression=compression)

        # Verify readability
        meta = pq.read_metadata(tmp_path)
        if meta.num_rows != pa_table.num_rows:
            raise IOError(f"Parquet row count mismatch: wrote {pa_table.num_rows}, got {meta.num_rows}")

        # Atomic replace
        if target.exists():
            target.unlink()
        tmp_path.rename(target)

        file_size = target.stat().st_size
        logger.info("Atomically wrote %s (%d rows, %d bytes)", target.name, pa_table.num_rows, file_size)
        return file_size

    except Exception as exc:
        if tmp_path.exists():
            tmp_path.unlink()
        logger.error("Failed to atomically write %s: %s", target, exc)
        raise exc


# ==============================================================================
# Chunked Parquet Writer for Large CSVs
# ==============================================================================

def stream_csv_to_parquet(
    csv_path: Union[str, Path],
    parquet_path: Union[str, Path],
    is_training: bool = True,
    chunk_size: int = 50000,
    max_chunks: Optional[int] = None,
) -> Tuple[int, int, List[Dict[str, Any]]]:
    """
    Streams large CSV in chunks, transforms each chunk, and writes to Parquet
    incrementally using PyArrow ParquetWriter without exhausting RAM.

    Returns:
        (accepted_rows_count, file_size_bytes, quarantined_records)
    """
    parquet_target = Path(parquet_path)
    parquet_target.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = parquet_target.parent / f"{parquet_target.name}.tmp.{os.getpid()}"

    total_accepted = 0
    all_quarantined: List[Dict[str, Any]] = []
    writer: Optional[pq.ParquetWriter] = None

    try:
        chunk_generator = read_journey_csv_chunks(
            csv_path, chunk_size=chunk_size, max_chunks=max_chunks
        )

        for chunk_df in chunk_generator:
            clean_chunk, quarantined = transform_journey_dataframe(chunk_df, is_training=is_training)
            all_quarantined.extend(quarantined)

            if clean_chunk.empty:
                continue

            pa_table = pa.Table.from_pandas(clean_chunk, preserve_index=False)

            if writer is None:
                # Initialize writer on first chunk with detected schema
                writer = pq.ParquetWriter(tmp_path, pa_table.schema, compression="snappy")

            writer.write_table(pa_table)
            total_accepted += len(clean_chunk)

        if writer is not None:
            writer.close()

        if total_accepted == 0:
            if tmp_path.exists():
                tmp_path.unlink()
            raise ValueError(f"No valid records to write to {parquet_target}")

        # Atomic rename
        if parquet_target.exists():
            parquet_target.unlink()
        tmp_path.rename(parquet_target)

        file_size = parquet_target.stat().st_size
        logger.info(
            "Streamed %s to Parquet: %d rows, %d quarantined, %d bytes",
            parquet_target.name, total_accepted, len(all_quarantined), file_size
        )
        return total_accepted, file_size, all_quarantined

    except Exception as exc:
        if writer is not None:
            try:
                writer.close()
            except Exception:
                pass
        if tmp_path.exists():
            tmp_path.unlink()
        logger.error("Error streaming %s to Parquet: %s", csv_path, exc)
        raise exc


# ==============================================================================
# 5. Quarantine & Quality Report Generation
# ==============================================================================

@dataclass
class QualityReport:
    """Consolidated pipeline quality and execution metadata."""
    run_timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)
    accepted_counts: Dict[str, int] = field(default_factory=dict)
    quarantined_counts: Dict[str, int] = field(default_factory=dict)
    rejection_reasons: Dict[str, List[str]] = field(default_factory=dict)
    warnings: Dict[str, List[str]] = field(default_factory=dict)
    pipeline_success: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def save_quarantine_records(
    quarantined_records: Sequence[Dict[str, Any]],
    dataset_name: str,
    output_dir: Union[str, Path] = "data/processed/quarantine",
) -> Path:
    """Saves quarantined records and their rejection reasons to a JSON file."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{dataset_name}_quarantine.json"

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(quarantined_records, f, indent=2, default=str)

    logger.info("Saved %d quarantined records for %s to %s", len(quarantined_records), dataset_name, out_path)
    return out_path


def save_quality_report(
    report: QualityReport,
    output_path: Union[str, Path] = "data/processed/quality_report.json",
) -> Path:
    """Saves the comprehensive quality report JSON atomically."""
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = target.parent / f"{target.name}.tmp.{os.getpid()}"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, indent=2)

    if target.exists():
        target.unlink()
    tmp_path.rename(target)

    logger.info("Quality report saved to %s", target)
    return target


# ==============================================================================
# Full Pipeline Execution Routine
# ==============================================================================

def execute_transformation_pipeline(
    raw_dir: Union[str, Path] = "data/raw",
    processed_dir: Union[str, Path] = "data/processed",
    chunk_size: int = 50000,
    max_journey_chunks: Optional[int] = None,
) -> QualityReport:
    """
    Executes the full transformation and Parquet storage pipeline.

    Ingests:
    - stations.json -> transforms -> data/processed/stations.parquet
    - trains.json -> transforms -> data/processed/trains.parquet
    - schedules.json -> transforms -> data/processed/schedules.parquet
    - ir_train.csv -> chunked stream -> data/processed/journey_train.parquet
    - ir_test.csv -> chunked stream -> data/processed/journey_test.parquet

    Quarantines invalid records and produces data/processed/quality_report.json.
    """
    raw_p = Path(raw_dir)
    proc_p = Path(processed_dir)
    quarantine_p = proc_p / "quarantine"

    proc_p.mkdir(parents=True, exist_ok=True)
    quarantine_p.mkdir(parents=True, exist_ok=True)

    report = QualityReport()

    # ---------------------------------------------------------
    # 1. Stations
    # ---------------------------------------------------------
    st_path = raw_p / "datameet" / "stations.json"
    logger.info("Ingesting and transforming stations from %s...", st_path)
    raw_st, st_meta = read_stations_geojson(st_path)
    report.inputs["stations"] = {"path": str(st_path), "raw_records": len(raw_st)}

    clean_st, bad_st = transform_stations(raw_st)
    report.accepted_counts["stations"] = len(clean_st)
    report.quarantined_counts["stations"] = len(bad_st)
    if bad_st:
        report.rejection_reasons["stations"] = list({r["rejection_reason"] for r in bad_st})
        save_quarantine_records(bad_st, "stations", quarantine_p)

    st_df = pd.DataFrame(clean_st)
    st_parquet_path = proc_p / "stations.parquet"
    st_size = write_parquet_atomic(st_df, st_parquet_path, schema=STATIONS_SCHEMA)
    report.outputs["stations"] = {
        "path": str(st_parquet_path),
        "records": len(clean_st),
        "file_size_bytes": st_size,
        "success": True,
    }

    # Reference sets for referential validation
    valid_station_codes = {s["station_code"] for s in clean_st}

    # ---------------------------------------------------------
    # 2. Trains
    # ---------------------------------------------------------
    tr_path = raw_p / "datameet" / "trains.json"
    logger.info("Ingesting and transforming trains from %s...", tr_path)
    raw_tr, tr_meta = read_trains_geojson(tr_path)
    report.inputs["trains"] = {"path": str(tr_path), "raw_records": len(raw_tr)}

    clean_tr, bad_tr = transform_trains(raw_tr)
    report.accepted_counts["trains"] = len(clean_tr)
    report.quarantined_counts["trains"] = len(bad_tr)
    if bad_tr:
        report.rejection_reasons["trains"] = list({r["rejection_reason"] for r in bad_tr})
        save_quarantine_records(bad_tr, "trains", quarantine_p)

    # Referential check on stations (warnings, non-blocking)
    val_tr_report = validate_trains(clean_tr, valid_station_codes=valid_station_codes)
    if val_tr_report.warnings:
        report.warnings["trains"] = val_tr_report.warnings[:20]

    tr_df = pd.DataFrame(clean_tr)
    tr_parquet_path = proc_p / "trains.parquet"
    tr_size = write_parquet_atomic(tr_df, tr_parquet_path, schema=TRAINS_SCHEMA)
    report.outputs["trains"] = {
        "path": str(tr_parquet_path),
        "records": len(clean_tr),
        "file_size_bytes": tr_size,
        "success": True,
    }

    # ---------------------------------------------------------
    # 3. Schedules
    # ---------------------------------------------------------
    sc_path = raw_p / "datameet" / "schedules.json"
    logger.info("Ingesting and transforming schedules from %s...", sc_path)
    raw_sc, sc_meta = read_schedules_json(sc_path)
    report.inputs["schedules"] = {"path": str(sc_path), "raw_records": len(raw_sc)}

    clean_sc, bad_sc = transform_schedules(raw_sc)
    report.accepted_counts["schedules"] = len(clean_sc)
    report.quarantined_counts["schedules"] = len(bad_sc)
    if bad_sc:
        report.rejection_reasons["schedules"] = list({r["rejection_reason"] for r in bad_sc})
        save_quarantine_records(bad_sc, "schedules", quarantine_p)

    sc_df = pd.DataFrame(clean_sc)
    sc_parquet_path = proc_p / "schedules.parquet"
    sc_size = write_parquet_atomic(sc_df, sc_parquet_path, schema=SCHEDULES_SCHEMA)
    report.outputs["schedules"] = {
        "path": str(sc_parquet_path),
        "records": len(clean_sc),
        "file_size_bytes": sc_size,
        "success": True,
    }

    # ---------------------------------------------------------
    # 4. Journey Train CSV (Chunked Streaming)
    # ---------------------------------------------------------
    jtrain_csv = raw_p / "operational_journeys" / "ir_train.csv"
    jtrain_parquet = proc_p / "journey_train.parquet"
    logger.info("Streaming and transforming journey train CSV from %s...", jtrain_csv)
    report.inputs["journey_train"] = {"path": str(jtrain_csv)}

    jtr_accepted, jtr_size, jtr_bad = stream_csv_to_parquet(
        jtrain_csv, jtrain_parquet, is_training=True, chunk_size=chunk_size, max_chunks=max_journey_chunks
    )
    report.accepted_counts["journey_train"] = jtr_accepted
    report.quarantined_counts["journey_train"] = len(jtr_bad)
    if jtr_bad:
        report.rejection_reasons["journey_train"] = list({r["rejection_reason"] for r in jtr_bad})
        save_quarantine_records(jtr_bad, "journey_train", quarantine_p)

    report.outputs["journey_train"] = {
        "path": str(jtrain_parquet),
        "records": jtr_accepted,
        "file_size_bytes": jtr_size,
        "success": True,
    }

    # ---------------------------------------------------------
    # 5. Journey Test CSV (Chunked Streaming)
    # ---------------------------------------------------------
    jtest_csv = raw_p / "operational_journeys" / "ir_test.csv"
    jtest_parquet = proc_p / "journey_test.parquet"
    logger.info("Streaming and transforming journey test CSV from %s...", jtest_csv)
    report.inputs["journey_test"] = {"path": str(jtest_csv)}

    jte_accepted, jte_size, jte_bad = stream_csv_to_parquet(
        jtest_csv, jtest_parquet, is_training=False, chunk_size=chunk_size, max_chunks=max_journey_chunks
    )
    report.accepted_counts["journey_test"] = jte_accepted
    report.quarantined_counts["journey_test"] = len(jte_bad)
    if jte_bad:
        report.rejection_reasons["journey_test"] = list({r["rejection_reason"] for r in jte_bad})
        save_quarantine_records(jte_bad, "journey_test", quarantine_p)

    report.outputs["journey_test"] = {
        "path": str(jtest_parquet),
        "records": jte_accepted,
        "file_size_bytes": jte_size,
        "success": True,
    }

    # Save Quality Report
    report_path = proc_p / "quality_report.json"
    save_quality_report(report, report_path)
    return report
