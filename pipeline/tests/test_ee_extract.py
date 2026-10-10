from dataclasses import replace
from pathlib import Path

from pipeline.config import PIPELINE_CONFIG, day_of_season, season_bounds
from pipeline.ee_extract import extract_season, retry_earth_engine


def test_season_helpers_follow_november_based_season() -> None:
    start, end = season_bounds("2025-26")

    assert start.isoformat() == "2025-11-01"
    assert end.isoformat() == "2026-03-31"
    assert day_of_season(start, start) == 1


def test_earth_engine_retry_uses_backoff_then_returns() -> None:
    calls = 0
    delays: list[float] = []
    config = replace(
        PIPELINE_CONFIG,
        ee_retry_count=3,
        ee_retry_base_seconds=0.25,
    )

    def operation() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise OSError("temporary remote failure")
        return "ok"

    result = retry_earth_engine(operation, config, delays.append)

    assert result == "ok"
    assert calls == 3
    assert delays == [0.25, 0.5]


def test_complete_season_csv_pair_is_skipped(tmp_path: Path) -> None:
    fields = tmp_path / "fields.geojson"
    fields.write_text("{}", encoding="utf-8")
    output = tmp_path / "output"
    output.mkdir()
    (output / "ndvi_2025_26.csv").touch()
    (output / "rain_2025_26.csv").touch()

    result = extract_season(fields, output, "2025-26")

    assert result is None
