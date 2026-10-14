
import pytest

from backend.pipeline import database_loader as loader


def test_dataset_mapping_contains_all_five_tables():
    assert set(loader.DATASETS) == {
        "stations",
        "trains",
        "schedules",
        "journey_train",
        "journey_test",
    }


def test_batch_size_is_positive():
    assert loader.BATCH_SIZE > 0


def test_get_connection_rejects_missing_password(monkeypatch):
    for key in (
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
    ):
        monkeypatch.delenv(key, raising=False)

    monkeypatch.setattr(loader, "ENV_FILE", loader.PROJECT_ROOT / "missing.env")

    with pytest.raises(FileNotFoundError):
        loader.get_connection()


def test_get_connection_rejects_password_placeholder(monkeypatch):
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("POSTGRES_DB", "rail_signal")
    monkeypatch.setenv("POSTGRES_USER", "postgres")
    monkeypatch.setenv(
        "POSTGRES_PASSWORD",
        "YOUR_ACTUAL_POSTGRES_PASSWORD",
    )

    monkeypatch.setattr(loader, "load_env_file", lambda: None)

    with pytest.raises(ValueError, match="POSTGRES_PASSWORD"):
        loader.get_connection()
