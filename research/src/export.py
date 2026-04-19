import argparse
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import polars as pl
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import (
    DEFAULT_KEEP_LAST,
    DEFAULT_USER_ID,
    HEALTH_TABLES,
    PROD_TABLES,
    SNAPSHOTS_DIR,
)

KUBECTL_NAMESPACE = "shared-database"
KUBECTL_POD = "shared-postgres-1"
KUBECTL_DB = "lifeascode_production"
KUBECTL_USER = "postgres"

_VALID_IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")


def _validate_identifier(name: str) -> str:
    if not _VALID_IDENTIFIER.match(name):
        raise ValueError(f"Invalid SQL identifier: {name!r}")
    return name


def _snapshot_dir_name() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d_%H%M%S")


def _write_manifest(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, default=str) + "\n")


def _date_stats(df: pl.DataFrame) -> dict:
    result: dict = {"rows": df.height}
    date_cols = [c for c in df.columns if "date" in c.lower()]
    if date_cols:
        date_col = "date" if "date" in date_cols else date_cols[0]
        non_null = df.filter(pl.col(date_col).is_not_null())
        if non_null.height > 0:
            result["date_min"] = str(non_null[date_col].min())
            result["date_max"] = str(non_null[date_col].max())
        else:
            result["date_min"] = None
            result["date_max"] = None
    return result


def _sql_string_list(names: list[str]) -> str:
    return ",".join(f"'{_validate_identifier(n)}'" for n in names)


# --- connectorx mode (direct DB connection) ---


def _compute_schema_hash_connectorx(db_uri: str, table_names: list[str]) -> str:
    in_list = _sql_string_list(table_names)
    query = (
        "SELECT table_name, column_name, data_type "
        "FROM information_schema.columns "
        f"WHERE table_name IN ({in_list}) "
        "ORDER BY table_name, ordinal_position"
    )
    try:
        df = pl.read_database_uri(query, db_uri, engine="connectorx")
        raw = df.write_csv()
        return "sha256:" + hashlib.sha256(raw.encode()).hexdigest()[:16]
    except Exception:
        return "sha256:unknown"


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=1, max=10),
    reraise=True,
)
def _export_table_connectorx(
    db_uri: str, table_name: str, user_id: int, output_path: Path
) -> dict:
    safe_table = _validate_identifier(table_name)
    query = f"SELECT * FROM {safe_table} WHERE user_id = %s"
    df = pl.read_database_uri(
        query, db_uri, engine="connectorx", execute_options={"params": [user_id]}
    )
    df.write_parquet(output_path, compression="zstd")
    return _date_stats(df)


# --- kubectl exec mode ---


def _kubectl_query(sql: str) -> str:
    cmd = [
        "kubectl",
        "exec",
        "-n",
        KUBECTL_NAMESPACE,
        KUBECTL_POD,
        "-c",
        "postgres",
        "--",
        "psql",
        "-U",
        KUBECTL_USER,
        "-d",
        KUBECTL_DB,
        "-c",
        sql,
        "--csv",
        "-t",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"kubectl exec failed: {result.stderr.strip()}")
    return result.stdout


def _compute_schema_hash_kubectl(table_names: list[str]) -> str:
    in_list = _sql_string_list(table_names)
    query = (
        "SELECT table_name, column_name, data_type "
        "FROM information_schema.columns "
        f"WHERE table_name IN ({in_list}) "
        "ORDER BY table_name, ordinal_position"
    )
    try:
        csv_data = _kubectl_query(query)
        return "sha256:" + hashlib.sha256(csv_data.encode()).hexdigest()[:16]
    except Exception:
        return "sha256:unknown"


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=1, max=10),
    reraise=True,
)
def _export_table_kubectl(table_name: str, user_id: int, output_path: Path) -> dict:
    safe_table = _validate_identifier(table_name)
    safe_uid = int(user_id)
    sql = (
        f"COPY (SELECT * FROM {safe_table} "
        f"WHERE user_id = {safe_uid}) "
        f"TO STDOUT WITH (FORMAT csv, HEADER true)"
    )
    csv_data = _kubectl_query(sql)

    if not csv_data.strip():
        df = pl.DataFrame()
    else:
        df = pl.read_csv(io.StringIO(csv_data), infer_schema_length=10000)

    df.write_parquet(output_path, compression="zstd")
    return _date_stats(df)


# --- shared logic ---


def _cleanup_old_snapshots(keep_last: int, exclude: Path | None = None) -> None:
    if keep_last <= 0:
        return
    dirs = sorted(
        (
            d
            for d in SNAPSHOTS_DIR.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ),
        key=lambda d: d.name,
        reverse=True,
    )
    for old_dir in dirs[keep_last:]:
        if exclude and old_dir.resolve() == exclude.resolve():
            continue
        shutil.rmtree(old_dir)
        print(f"  Removed old snapshot: {old_dir.name}")


def _update_latest_symlink(snapshot_dir: Path) -> None:
    latest = SNAPSHOTS_DIR / "latest"
    if latest.is_symlink() or latest.exists():
        latest.unlink()
    latest.symlink_to(snapshot_dir.name)


def export_snapshot(
    user_id: int,
    table_filter: list[str] | None = None,
    keep_last: int = DEFAULT_KEEP_LAST,
    db_uri: str | None = None,
    via_kubectl: bool = False,
) -> Path:
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    snapshot_dir = SNAPSHOTS_DIR / _snapshot_dir_name()
    snapshot_dir.mkdir()

    all_tables: dict[str, tuple[str, str]] = {}
    for logical, real in HEALTH_TABLES.items():
        if table_filter and logical not in table_filter:
            continue
        all_tables[logical] = (real, f"{logical}.parquet")
    for logical, real in PROD_TABLES.items():
        if table_filter and logical not in table_filter:
            continue
        all_tables[logical] = (real, f"_prod_{logical}.parquet")

    manifest = {
        "status": "in_progress",
        "exported_at": datetime.now(UTC).isoformat(),
        "user_id": user_id,
        "mode": "kubectl" if via_kubectl else "connectorx",
        "tables": {},
    }
    manifest_path = snapshot_dir / "manifest.json"
    _write_manifest(manifest_path, manifest)

    real_table_names = [real for real, _ in all_tables.values()]
    if via_kubectl:
        manifest["schema_hash"] = _compute_schema_hash_kubectl(real_table_names)
    else:
        manifest["schema_hash"] = _compute_schema_hash_connectorx(
            db_uri or "", real_table_names
        )

    failed = []
    for logical, (real_table, filename) in all_tables.items():
        output_path = snapshot_dir / filename
        try:
            if via_kubectl:
                info = _export_table_kubectl(real_table, user_id, output_path)
            else:
                info = _export_table_connectorx(
                    db_uri or "", real_table, user_id, output_path
                )
            manifest["tables"][logical] = info
            print(f"  {logical}: {info['rows']} rows")
        except Exception as e:
            print(
                f"  {logical}: FAILED after retries — {e}",
                file=sys.stderr,
            )
            failed.append(logical)

    manifest["status"] = "partial" if failed else "complete"
    if failed:
        manifest["failed_tables"] = failed
    _write_manifest(manifest_path, manifest)

    _update_latest_symlink(snapshot_dir)
    _cleanup_old_snapshots(keep_last, exclude=snapshot_dir)

    return snapshot_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Export health data to parquet")
    parser.add_argument("--user-id", type=int, default=DEFAULT_USER_ID)
    parser.add_argument(
        "--tables",
        type=str,
        default=None,
        help="Comma-separated table names",
    )
    parser.add_argument("--keep-last", type=int, default=DEFAULT_KEEP_LAST)
    parser.add_argument("--db-url", type=str, default=None)
    parser.add_argument(
        "--via-kubectl",
        action="store_true",
        help="Export via kubectl exec instead of direct DB",
    )
    args = parser.parse_args()

    table_filter = args.tables.split(",") if args.tables else None

    if not args.via_kubectl and not args.db_url:
        from src.config import DEFAULT_DB_URL

        args.db_url = DEFAULT_DB_URL

    mode = "kubectl" if args.via_kubectl else "connectorx"
    print(f"Exporting snapshot (user_id={args.user_id}, mode={mode})...")
    snapshot_dir = export_snapshot(
        user_id=args.user_id,
        table_filter=table_filter,
        keep_last=args.keep_last,
        db_uri=args.db_url,
        via_kubectl=args.via_kubectl,
    )
    print(f"Done: {snapshot_dir}")


if __name__ == "__main__":
    main()
