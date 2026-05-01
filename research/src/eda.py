import argparse

import polars as pl

from src.loader import available_tables, db, load, manifest


def _print_overview() -> None:
    meta = manifest()
    print(f"Snapshot exported_at: {meta.get('exported_at', 'unknown')}")
    print(f"Status: {meta.get('status', 'unknown')}")
    print(f"Mode: {meta.get('mode', 'unknown')}")
    print(f"Schema hash: {meta.get('schema_hash', 'unknown')}")
    print()


def _print_table_shapes() -> None:
    print("== Table shapes ==")
    for t in available_tables():
        df = load(t)
        print(f"  {t}: {df.shape[0]:,} rows x {df.shape[1]} cols")
    print()


def _print_coverage() -> None:
    print("== Coverage timeline (date_min..date_max, rows) ==")
    rows = []
    for t in available_tables():
        if t.startswith("_prod_"):
            continue
        df = load(t)
        date_cols = [c for c in df.columns if "date" in c.lower()]
        if not date_cols:
            continue
        date_col = "date" if "date" in date_cols else date_cols[0]
        non_null = df.filter(pl.col(date_col).is_not_null())
        if non_null.height == 0:
            continue
        rows.append(
            {
                "table": t,
                "date_min": str(non_null[date_col].min()),
                "date_max": str(non_null[date_col].max()),
                "rows": non_null.height,
            }
        )
    print(pl.DataFrame(rows).sort("date_min"))
    print()


def _print_distribution(table: str, column: str) -> None:
    df = load(table)
    if df.height == 0 or column not in df.columns:
        return
    series = df[column].drop_nulls()
    if series.len() == 0:
        return
    stats = {
        "n": series.len(),
        "mean": float(series.mean() or 0),
        "std": float(series.std() or 0),
        "min": float(series.min() or 0),
        "p25": float(series.quantile(0.25) or 0),
        "median": float(series.median() or 0),
        "p75": float(series.quantile(0.75) or 0),
        "p95": float(series.quantile(0.95) or 0),
        "max": float(series.max() or 0),
    }
    print(f"  {table}.{column}: " + ", ".join(f"{k}={v:.2f}" for k, v in stats.items()))


def _print_distributions() -> None:
    print("== Key metric distributions ==")
    targets = [
        ("sleep", "total_sleep_minutes"),
        ("hrv", "hrv_avg"),
        ("heart_rate", "resting_hr"),
        ("weight", "weight_kg"),
        ("stress", "avg_stress"),
        ("steps", "total_steps"),
        ("energy", "active_energy"),
        ("whoop_recovery", "recovery_score"),
        ("whoop_sleep", "sleep_performance"),
    ]
    for table, column in targets:
        _print_distribution(table, column)
    print()


def _print_nulls() -> None:
    print("== Columns with nulls (% per table) ==")
    targets = [
        "sleep",
        "hrv",
        "heart_rate",
        "stress",
        "steps",
        "energy",
        "weight",
        "whoop_recovery",
        "whoop_sleep",
        "eight_sleep_sessions",
    ]
    for t in targets:
        try:
            df = load(t)
        except FileNotFoundError:
            continue
        if df.height == 0:
            print(f"  {t}: empty")
            continue
        null_pcts = {
            col: round(df[col].null_count() / df.height * 100, 1) for col in df.columns if df[col].null_count() > 0
        }
        if null_pcts:
            print(f"  {t}:")
            for col, pct in sorted(null_pcts.items(), key=lambda x: -x[1]):
                print(f"    {col}: {pct}%")
    print()


def _print_joined_sample() -> None:
    print("== Latest 20 days joined (sleep + hrv + resting_hr) ==")
    conn = db()
    result = conn.sql(
        """
        SELECT
            s.date,
            s.total_sleep_minutes,
            h.hrv_avg,
            hr.resting_hr
        FROM sleep s
        LEFT JOIN hrv h USING (date, user_id)
        LEFT JOIN heart_rate hr USING (date, user_id)
        ORDER BY s.date DESC
        LIMIT 20
        """
    ).pl()
    print(result)
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="EDA report against latest snapshot")
    parser.add_argument("--snapshot", type=str, default=None)
    args = parser.parse_args()
    if args.snapshot:
        import os

        os.environ["LAC_SNAPSHOT"] = args.snapshot

    _print_overview()
    _print_table_shapes()
    _print_coverage()
    _print_distributions()
    _print_nulls()
    _print_joined_sample()


if __name__ == "__main__":
    main()
