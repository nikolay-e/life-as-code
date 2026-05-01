import argparse

import numpy as np
import polars as pl

from src.config import detect_device
from src.loader import load, wide_daily


def _split(series: pl.DataFrame, metric: str, horizon: int) -> tuple[pl.DataFrame, pl.DataFrame]:
    series = series.filter(pl.col(metric).is_not_null()).sort("date")
    if series.height <= horizon + 30:
        raise ValueError(f"Not enough data for {metric}: {series.height} rows, need >{horizon + 30}")
    train = series.head(series.height - horizon)
    test = series.tail(horizon)
    return train, test


def _chronos_forecast(
    train: pl.DataFrame, metric: str, horizon: int, device: str
) -> tuple[list[float], list[float], list[float]]:
    import torch
    from chronos import BaseChronosPipeline

    pipeline = BaseChronosPipeline.from_pretrained("amazon/chronos-bolt-base", device_map=device, dtype=torch.float32)
    context = torch.tensor(train[metric].to_list(), dtype=torch.float32).unsqueeze(0)
    quantiles, _ = pipeline.predict_quantiles(context, prediction_length=horizon, quantile_levels=[0.1, 0.5, 0.9])
    p10 = quantiles[0, :, 0].tolist()
    p50 = quantiles[0, :, 1].tolist()
    p90 = quantiles[0, :, 2].tolist()
    return p10, p50, p90


def _accuracy(actual: list[float], predicted: list[float]) -> dict[str, float]:
    a = np.array(actual)
    p = np.array(predicted)
    nonzero = a != 0
    return {
        "mae": float(np.mean(np.abs(a - p))),
        "rmse": float(np.sqrt(np.mean((a - p) ** 2))),
        "mape_pct": float(np.mean(np.abs((a[nonzero] - p[nonzero]) / a[nonzero])) * 100)
        if nonzero.any()
        else float("nan"),
    }


def _compare_with_prod(metric: str, snapshot: str | None) -> None:
    try:
        prod = load("_prod_predictions", snapshot)
    except FileNotFoundError:
        print("  no _prod_predictions snapshot")
        return
    if prod.height == 0:
        print("  prod predictions table empty")
        return
    matched = prod.filter(pl.col("metric") == metric)
    if matched.height == 0:
        print(f"  no prod predictions for metric={metric}")
        return
    print(f"  prod predictions for {metric}: {matched.height} rows")
    print(matched.sort("target_date").tail(10))


def main() -> None:
    parser = argparse.ArgumentParser(description="Chronos forecast on wide_daily")
    parser.add_argument("--snapshot", type=str, default=None)
    parser.add_argument("--metric", type=str, default="hrv_garmin")
    parser.add_argument("--horizon", type=int, default=14)
    parser.add_argument(
        "--prod-metric",
        type=str,
        default=None,
        help="Metric name in _prod_predictions for comparison",
    )
    args = parser.parse_args()

    device = detect_device()
    print(f"Device: {device}")

    df = wide_daily(args.snapshot)
    if args.metric not in df.columns:
        raise SystemExit(f"Metric {args.metric} not in wide_daily. Available: {df.columns}")
    series = df.select(["date", args.metric])
    train, test = _split(series, args.metric, args.horizon)
    print(f"Train: {train.height} days, test: {test.height} days")

    p10, p50, p90 = _chronos_forecast(train, args.metric, args.horizon, device)

    actual = test[args.metric].to_list()
    metrics = _accuracy(actual, p50)
    print()
    print("== Forecast accuracy (p50 vs actual) ==")
    for k, v in metrics.items():
        print(f"  {k}: {v:.3f}")

    print()
    print("== Forecast vs actual (last horizon) ==")
    rows = [
        {"date": str(d), "actual": a, "p10": lo, "p50": m, "p90": h}
        for d, a, lo, m, h in zip(test["date"].to_list(), actual, p10, p50, p90, strict=True)
    ]
    print(pl.DataFrame(rows))

    print()
    prod_metric = args.prod_metric or args.metric
    print(f"== Compare with production predictions for {prod_metric} ==")
    _compare_with_prod(prod_metric, args.snapshot)


if __name__ == "__main__":
    main()
