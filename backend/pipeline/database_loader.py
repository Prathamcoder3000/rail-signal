
"""Load validated Parquet datasets into PostgreSQL safely."""

import os
from pathlib import Path

import pyarrow.parquet as pq
import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_values


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"
DATA_DIR = PROJECT_ROOT / "data" / "processed"

DATASETS = {
    "stations": "stations.parquet",
    "trains": "trains.parquet",
    "schedules": "schedules.parquet",
    "journey_train": "journey_train.parquet",
    "journey_test": "journey_test.parquet",
}

BATCH_SIZE = 5000


def load_env_file():
    """Read local .env values without requiring python-dotenv."""
    if not ENV_FILE.exists():
        raise FileNotFoundError(
            f"Missing {ENV_FILE}. Create it from .env.example first."
        )

    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value


def get_connection():
    """Connect using POSTGRES_* settings, not DATABASE_URL."""
    load_env_file()

    required = [
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
    ]
    missing = [
        key for key in required
        if not os.environ.get(key)
        or os.environ[key] == "YOUR_ACTUAL_POSTGRES_PASSWORD"
    ]

    if missing:
        raise ValueError(
            "Set these values in .env before loading: "
            + ", ".join(missing)
        )

    return psycopg2.connect(
        host=os.environ["POSTGRES_HOST"],
        port=int(os.environ["POSTGRES_PORT"]),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        connect_timeout=10,
    )


def load_dataset(cursor, table_name, parquet_path):
    """Insert one Parquet dataset in bounded batches."""
    parquet_file = pq.ParquetFile(parquet_path)
    columns = parquet_file.schema_arrow.names
    expected_rows = parquet_file.metadata.num_rows

    # Identifiers come from our fixed dataset mapping and Parquet schema.
    insert_query = sql.SQL("INSERT INTO {} ({}) VALUES %s").format(
        sql.Identifier(table_name),
        sql.SQL(", ").join(
            sql.Identifier(column) for column in columns
        ),
    )

    inserted = 0

    for record_batch in parquet_file.iter_batches(
        batch_size=BATCH_SIZE,
        columns=columns,
    ):
        rows = [
            tuple(row[column] for column in columns)
            for row in record_batch.to_pylist()
        ]

        if rows:
            execute_values(
                cursor,
                insert_query.as_string(cursor.connection),
                rows,
                page_size=1000,
            )
            inserted += len(rows)

        if inserted % 100000 == 0 and inserted:
            print(f"  {table_name}: inserted {inserted:,} rows")

    if inserted != expected_rows:
        raise RuntimeError(
            f"{table_name}: expected {expected_rows:,}, "
            f"inserted {inserted:,}"
        )

    cursor.execute(
        sql.SQL("SELECT COUNT(*) FROM {}").format(
            sql.Identifier(table_name)
        )
    )
    actual_rows = cursor.fetchone()[0]

    if actual_rows != expected_rows:
        raise RuntimeError(
            f"{table_name}: expected {expected_rows:,} database rows, "
            f"found {actual_rows:,}"
        )

    print(f"  {table_name}: verified {actual_rows:,} rows")


def main():
    missing_files = [
        filename
        for filename in DATASETS.values()
        if not (DATA_DIR / filename).is_file()
    ]
    if missing_files:
        raise FileNotFoundError(
            "Missing processed files: " + ", ".join(missing_files)
        )

    connection = get_connection()

    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_database()")
                database_name = cursor.fetchone()[0]

                if database_name != "rail_signal":
                    raise RuntimeError(
                        f"Wrong database: {database_name}. "
                        "Expected rail_signal."
                    )

                # Refuse to overwrite or duplicate existing data.
                for table_name in DATASETS:
                    cursor.execute(
                        sql.SQL("SELECT COUNT(*) FROM {}").format(
                            sql.Identifier(table_name)
                        )
                    )
                    existing = cursor.fetchone()[0]

                    if existing != 0:
                        raise RuntimeError(
                            f"{table_name} already contains {existing:,} "
                            "rows. No data was loaded. Investigate first."
                        )

                print(f"Connected to database: {database_name}")

                # All five loads share one transaction. An error rolls
                # back the complete load instead of leaving partial data.
                for table_name, filename in DATASETS.items():
                    parquet_path = DATA_DIR / filename
                    print(
                        f"\nLoading {filename} "
                        f"({pq.ParquetFile(parquet_path).metadata.num_rows:,} rows)"
                    )
                    load_dataset(cursor, table_name, parquet_path)

        print("\nSUCCESS: all five datasets loaded and verified.")

    finally:
        connection.close()


if __name__ == "__main__":
    main()
