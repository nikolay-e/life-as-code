import json
import re
import warnings
from pathlib import Path

import duckdb
import polars as pl

from src.config import SNAPSHOTS_DIR

_VALID_IDENTIFIER = re.compile(r"^_?[a-z][a-z0-9_]*$")


def snapshot_path(name: str | None = None) -> Path:
    if name:
        path = SNAPSHOTS_DIR / name
        if not path.exists():
            raise FileNotFoundError(f"Snapshot not found: {path}")
        return path

    latest = SNAPSHOTS_DIR / "latest"
    if latest.is_symlink():
        resolved = latest.resolve()
        if resolved.exists():
            _validate_manifest(resolved)
            return resolved

    dirs = sorted(
        (d for d in SNAPSHOTS_DIR.iterdir() if d.is_dir() and not d.name.startswith(".")),
        key=lambda d: d.name,
        reverse=True,
    )
    if not dirs:
        raise FileNotFoundError(f"No snapshots found in {SNAPSHOTS_DIR}. Run: uv run export-snapshot")
    _validate_manifest(dirs[0])
    return dirs[0]


def _validate_manifest(path: Path) -> None:
    manifest_path = path / "manifest.json"
    if not manifest_path.exists():
        warnings.warn(f"No manifest.json in {path.name}", stacklevel=3)
        return
    data = json.loads(manifest_path.read_text())
    status = data.get("status")
    if status == "partial":
        failed = data.get("failed_tables", [])
        warnings.warn(
            f"Snapshot {path.name} is partial. Failed tables: {failed}",
            stacklevel=3,
        )
    elif status == "in_progress":
        warnings.warn(
            f"Snapshot {path.name} export was interrupted (status: in_progress)",
            stacklevel=3,
        )


def scan(table: str, snapshot: str | None = None) -> pl.LazyFrame:
    base = snapshot_path(snapshot)
    path = base / f"{table}.parquet"
    if not path.exists():
        path = base / f"_prod_{table}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Table '{table}' not found in snapshot {base.name}")
    return pl.scan_parquet(path)


def load(table: str, snapshot: str | None = None) -> pl.DataFrame:
    return scan(table, snapshot).collect()


def db(
    snapshot: str | None = None,
) -> duckdb.DuckDBPyConnection:
    base = snapshot_path(snapshot)
    conn = duckdb.connect()
    for pq in base.glob("*.parquet"):
        view_name = pq.stem
        if not _VALID_IDENTIFIER.match(view_name):
            continue
        conn.execute(f"CREATE VIEW \"{view_name}\" AS SELECT * FROM read_parquet('{pq}')")
    return conn


def available_tables(snapshot: str | None = None) -> list[str]:
    base = snapshot_path(snapshot)
    return sorted(p.stem for p in base.glob("*.parquet"))


def manifest(snapshot: str | None = None) -> dict:
    base = snapshot_path(snapshot)
    manifest_path = base / "manifest.json"
    if not manifest_path.exists():
        return {}
    return json.loads(manifest_path.read_text())


def wide_daily(snapshot: str | None = None) -> pl.DataFrame:
    base = snapshot_path(snapshot)
    path = base / "processed" / "wide_daily.parquet"
    if not path.exists():
        raise FileNotFoundError(f"wide_daily not built for {base.name}. Run: uv run lac-preprocess")
    return pl.read_parquet(path)


def wide_daily_features(snapshot: str | None = None) -> pl.DataFrame:
    base = snapshot_path(snapshot)
    path = base / "processed" / "wide_daily_features.parquet"
    if not path.exists():
        raise FileNotFoundError(f"wide_daily_features not built for {base.name}. Run: uv run lac-features")
    return pl.read_parquet(path)
