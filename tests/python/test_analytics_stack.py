"""Smoke test de interoperabilidade, sem dados reais ou algoritmo de produto."""

from pathlib import Path

import duckdb
import polars as pl


def test_polars_parquet_duckdb_roundtrip(tmp_path: Path) -> None:
    artifact = tmp_path / "smoke.parquet"
    pl.DataFrame({"value": [1, 2, 3]}).write_parquet(artifact)
    with duckdb.connect(":memory:") as connection:
        result = connection.execute(
            "SELECT sum(value) FROM read_parquet(?)", [str(artifact)]
        ).fetchone()
    assert result == (6,)
