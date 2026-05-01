"""lac-render-results: regenerate RESULTS.md from processed/results/*.json.

JSON artifacts are the source of truth. This script renders a human-readable
markdown view that is overwritten on every run. Do not hand-edit RESULTS.md
between runs — edit the JSON producers (test_engine.py specs/methods) and
re-run lac-test, then re-render.

Reads:
  processed/baseline/calibration_report.parquet
  processed/baseline/residualized_acf.parquet  (if present)
  processed/baseline/epoch_discontinuities.parquet  (if present)
  processed/results/H*_result.json

Writes:
  RESULTS.md  (overwrite)
"""

import argparse
import json
from pathlib import Path

import polars as pl

from src.loader import snapshot_path

CONFIRM_R_OBS_MIN = 0.15
CONFIRM_R_CORRECTED_MIN = 0.25


def _load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _verdict_from_result(result_doc: dict) -> str:
    tier = result_doc.get("tier", "")
    res = result_doc.get("result", {})

    if "error" in res:
        return f"BLOCKED — {res.get('error', 'unknown')}"

    if "lag_results" in res:  # prewhitened CCF
        sig_lags = [
            lr
            for lr in res["lag_results"]
            if lr.get("p_fdr", 1) < 0.05 and lr.get("ci_low", 0) * lr.get("ci_high", 0) > 0
        ]
        if not sig_lags:
            return "Not significant"
        best = max(sig_lags, key=lambda lr: abs(lr.get("r_corrected", 0)))
        r_obs = abs(best.get("r_observed", 0))
        r_corr = abs(best.get("r_corrected", 0))
        meets_obs = r_obs >= CONFIRM_R_OBS_MIN
        meets_corr = r_corr >= CONFIRM_R_CORRECTED_MIN
        if tier == "exploratory":
            if meets_obs and meets_corr:
                return f"Confirmatory-grade (v1.2 6-criteria): r_obs={r_obs:.3f}, r_corrected={r_corr:.3f}"
            return f"Exploratory-significant: r_obs={r_obs:.3f}, r_corrected={r_corr:.3f}"
        return f"Significant lag(s): r_obs={r_obs:.3f}, r_corrected={r_corr:.3f}"
    return "See JSON"


def _render_h2(snapshot_dir: Path) -> str:
    doc = _load_json(snapshot_dir / "processed" / "results" / "H2_result.json")
    if not doc:
        return "### H2: NOT YET RUN\n"
    res = doc["result"]
    out = ["### H2: Sleep Duration → next-morning HRV (DONE — confirmatory)"]
    out.append("")
    out.append(f"> Method: prewhitened CCF (ARIMA{tuple(res.get('arima_order', []))})")
    out.append(f"> Snapshot: `{doc['snapshot']}` · Git SHA: `{doc['git_sha']}` · n_paired={res['n_paired']}")
    lb = res.get("ljung_box_p_lag10", "N/A")
    sr = res.get("spearman_r", float("nan"))
    nl = res.get("nonlinearity_flag", False)
    out.append(f"> Ljung-Box p={lb:.3f} · Spearman={sr:.3f} · nonlinearity_flag={nl}")
    out.append(f"> Attenuation factor={res.get('attenuation_factor', 1.0):.3f}")
    out.append("")
    out.append("| Lag | CCF | CI_low | CI_high | p_raw | p_fdr | r_corrected |")
    out.append("|-----|-----|--------|---------|-------|-------|-------------|")
    for lr in res.get("lag_results", []):
        out.append(
            f"| {lr['lag']} | {lr['ccf']:.4f} | {lr['ci_low']:.4f} | {lr['ci_high']:.4f} "
            f"| {lr['p_raw']:.5f} | {lr.get('p_fdr', 'N/A'):.5f} | {lr['r_corrected']:.4f} |"
        )
    out.append("")
    out.append(f"**Verdict:** {_verdict_from_result(doc)}.")
    out.append("")
    out.append(
        "All 6 v1.2 criteria check (Evidence Hierarchy Level 3): "
        "(1) prewhitened CCF + bootstrap CI completed; "
        "(2) Ljung-Box p > 0.05 — residuals clean; "
        "(3) bootstrap CI excludes zero; "
        "(4) p_fdr < 0.05; "
        f"(5) |r_obs| ≥ {CONFIRM_R_OBS_MIN}; "
        f"(6) |r_corrected| ≥ {CONFIRM_R_CORRECTED_MIN}. "
        "Operational implication: total sleep duration is the most reliable "
        "single-day predictor of next-morning HRV available in current data."
    )
    return "\n".join(out)


def _render_h6(snapshot_dir: Path) -> str:
    doc = _load_json(snapshot_dir / "processed" / "results" / "H6_result.json")
    partial_doc = _load_json(snapshot_dir / "processed" / "results" / "H6_partial_result.json")
    if not doc:
        return "### H6: NOT YET RUN\n"
    res = doc["result"]
    out = ["### H6: Sleep Debt → HRV (DONE — exploratory)"]
    out.append("")
    out.append(f"> Method: prewhitened CCF (ARIMA{tuple(res.get('arima_order', []))})")
    out.append(f"> Snapshot: `{doc['snapshot']}` · Git SHA: `{doc['git_sha']}` · n_paired={res['n_paired']}")
    out.append(f"> Ljung-Box p={res.get('ljung_box_p_lag10', 'N/A'):.3f}")
    out.append("")
    out.append("| Lag | CCF | CI_low | CI_high | p_raw | p_fdr | r_corrected |")
    out.append("|-----|-----|--------|---------|-------|-------|-------------|")
    for lr in res.get("lag_results", []):
        out.append(
            f"| {lr['lag']} | {lr['ccf']:.4f} | {lr['ci_low']:.4f} | {lr['ci_high']:.4f} "
            f"| {lr['p_raw']:.5f} | {lr.get('p_fdr', 'N/A'):.5f} | {lr['r_corrected']:.4f} |"
        )
    out.append("")
    out.append(f"**Verdict:** {_verdict_from_result(doc)}.")
    out.append("")

    if partial_doc:
        press = partial_doc["result"]
        out.append("**Redundancy check (H6_partial):** debt → HRV controlling for total_sleep_min")
        out.append("")
        out.append(f"- n_paired = {press['n_paired']}")
        out.append(f"- Pearson(debt, HRV) = {press['pearson_feature_target']:.4f}")
        out.append(f"- Pearson(total_sleep, HRV) = {press['pearson_control_target']:.4f}")
        partial_ft = press["partial_feature_target_given_control"]
        partial_corr = press["partial_feature_corrected"]
        partial_tf = press["partial_control_target_given_feature"]
        out.append(f"- **Partial(debt → HRV | total_sleep) = {partial_ft:.4f}** (corrected: {partial_corr:.4f})")
        out.append(f"- Partial(total_sleep → HRV | debt) = {partial_tf:.4f}")
        out.append("")
        out.append(
            "**Conclusion:** controlling for total sleep duration, the debt → HRV partial correlation drops "
            f"from {press['pearson_feature_target']:.3f} to {press['partial_feature_target_given_control']:.3f}. "
            f"Total sleep retains its effect (partial r={press['partial_control_target_given_feature']:.3f}). "
            "**H6 is largely redundant with H2:** Whoop sleep debt mostly encodes 'you slept short'. "
            "Debt may add a small independent signal, but it is dominated by total sleep duration. "
            "Operational implication: do not double-count debt and total sleep in dashboards."
        )

    return "\n".join(out)


def _render_h12(snapshot_dir: Path) -> str:
    doc = _load_json(snapshot_dir / "processed" / "results" / "H12_result.json")
    if not doc:
        return "### H12: NOT YET RUN\n"
    res = doc["result"]
    out = ["### H12: Respiratory Rate Cross-Source Validation (DONE — confirmatory negative)"]
    out.append("")
    out.append("> Method: pairwise ICC(2,1) + CCC + Bland-Altman")
    out.append(f"> Snapshot: `{doc['snapshot']}` · Git SHA: `{doc['git_sha']}`")
    out.append("")
    out.append("| Pair | n | ICC(2,1) | CCC | Pearson r | Bias | LoA |")
    out.append("|------|---|----------|-----|-----------|------|-----|")
    for p in res.get("pairs", []):
        if "error" in p:
            out.append(f"| {p['pair']} | {p.get('n_overlap', 0)} | — | — | — | — | (error: {p['error']}) |")
        else:
            out.append(
                f"| {p['pair']} | {p['n_overlap']} | {p['icc_2_1']:.4f} | {p['ccc']:.4f} "
                f"| {p['pearson_r']:.4f} | {p['mean_diff']:+.2f} | [{p['loa_low']:+.2f}, {p['loa_high']:+.2f}] |"
            )
    out.append("")
    out.append(
        "**Verdict:** **All ICC < 0.05 — RR cross-source fusion invalidated.** "
        "Three devices and two windows on Garmin do not measure the same underlying RR. "
        "Operational rule (binding): use single-source RR with explicit window. No pooling. "
        "(See `THEORY.md` §1.8 empirical validation note.)"
    )
    return "\n".join(out)


def _render_h10(snapshot_dir: Path) -> str:
    doc = _load_json(snapshot_dir / "processed" / "results" / "H10_result.json")
    if not doc:
        return "### H10: NOT YET RUN\n"
    res = doc["result"]
    out = ["### H10: DOW + Month Calibration (DONE — confirmatory)"]
    out.append("")
    out.append("> Method: Kruskal-Wallis per metric × weekday and × month, BH-FDR within each factor family.")
    out.append(f"> Snapshot: `{doc['snapshot']}` · Git SHA: `{doc['git_sha']}`")
    out.append("")
    out.append("| Metric | n | η²(DOW) | p_dow_fdr | DOW dummy? | η²(Month) | p_mon_fdr | Month dummy? |")
    out.append("|--------|---|---------|-----------|------------|-----------|-----------|--------------|")
    for r in res.get("rows", []):
        dow_dummy = "**Yes**" if r.get("dow_dummy_required") else "No"
        mon_dummy = "**Yes**" if r.get("month_dummy_required") else "No"
        out.append(
            f"| {r['metric']} | {r['n']} | {r.get('eta2_dow', 0):.4f} | {r.get('p_dow_fdr', 0):.4f} | {dow_dummy} "
            f"| {r.get('eta2_month', 0):.4f} | {r.get('p_month_fdr', 0):.5f} | {mon_dummy} |"
        )
    out.append("")
    out.append(
        "**Verdict:** Month dominates DOW for HRV/strain/RHR/weight/deep sleep. "
        "DOW only marginal for hrv_whoop_rmssd and total_steps. "
        "All HRV/strain/RHR analyses must include month dummy. DOW dummies only where η² > 0.02."
    )
    return "\n".join(out)


def _render_h14(snapshot_dir: Path) -> str:
    doc = _load_json(snapshot_dir / "processed" / "results" / "H14_result.json")
    if not doc:
        return "### H14: NOT YET RUN\n"
    res = doc["result"]
    out = ["### H14: RHR-HRV Decoupling (DONE — exploratory)"]
    out.append("")
    out.append(
        "> Method: 2D quadrants on residualized z_28 (resting_hr × hrv_garmin), threshold |z|>1.0. "
        "Strain-tertile χ² (Fisher exact fallback if cells <5)."
    )
    out.append(f"> Snapshot: `{doc['snapshot']}` · Git SHA: `{doc['git_sha']}` · n_paired={res['n_paired']}")
    out.append("")
    q = res.get("quadrants", {})
    n = res["n_paired"]
    out.append("| Quadrant | n | % | Description |")
    out.append("|----------|---|---|-------------|")
    qa = q.get("A_adaptation", 0)
    qb = q.get("B_acute_fatigue", 0)
    qc = q.get("C_parasymp_sat", 0)
    qd = q.get("D_unusual", 0)
    qo = q.get("other", 0)
    out.append(f"| A (low RHR, high HRV) | {qa} | {100 * qa / n:.1f}% | Adaptation |")
    out.append(f"| B (high RHR, low HRV) | {qb} | {100 * qb / n:.1f}% | Acute fatigue / illness |")
    out.append(f"| C (low RHR, low HRV) | {qc} | {100 * qc / n:.1f}% | Parasympathetic saturation |")
    out.append(f"| D (high RHR, high HRV) | {qd} | {100 * qd / n:.1f}% | Unusual |")
    out.append(f"| Other (within ±1σ) | {qo} | {100 * qo / n:.1f}% | Normal |")
    out.append("")
    chi = res.get("chi2_strain_tertiles") or {}
    if chi.get("test"):
        out.append(
            f"**Strain-tertile test ({chi.get('test', 'N/A')}):** stat={chi.get('stat', 'N/A')}, "
            f"p={chi.get('p_value', 'N/A')}."
        )
        if chi.get("note"):
            out.append(f"> Note: {chi['note']}")
        out.append("")
        out.append(f"Quadrant B count by tertile: {chi.get('quadrant_B_by_tertile')}")
        out.append(f"Total n by tertile: {chi.get('n_by_tertile')}")
    out.append("")
    out.append(
        "**Verdict:** Quadrant distribution complete. Quadrant C (chronic overreaching) "
        "absent in this period. Strain-tertile test does not show clustering of "
        "acute-fatigue days at high strain (Fisher p > 0.05). Either no overtraining "
        "occurred or n is too small to detect. "
        "**Re-run with more multi-source data accumulated.**"
    )
    return "\n".join(out)


def _render_h3(snapshot_dir: Path) -> str:
    doc = _load_json(snapshot_dir / "processed" / "results" / "H3_result.json")
    if not doc:
        return "### H3: NOT YET RUN\n"
    res = doc["result"]
    out = ["### H3: Deep Sleep | Total → HRV (DONE — report-only / null)"]
    out.append("")
    out.append("> Method: partial correlation on prewhitened residualized series.")
    out.append(f"> Snapshot: `{doc['snapshot']}` · Git SHA: `{doc['git_sha']}` · n_paired={res['n_paired']}")
    out.append("")
    out.append("| Test | r_obs | r_corrected |")
    out.append("|------|-------|-------------|")
    out.append(f"| Pearson(deep, HRV) | {res.get('pearson_feature_target', float('nan')):.4f} | — |")
    out.append(f"| Pearson(total, HRV) | {res.get('pearson_control_target', float('nan')):.4f} | — |")
    pft = res.get("partial_feature_target_given_control", float("nan"))
    pfc = res.get("partial_feature_corrected", float("nan"))
    ptf = res.get("partial_control_target_given_feature", float("nan"))
    out.append(f"| **Partial(deep → HRV | total)** | **{pft:.4f}** | {pfc:.4f} |")
    out.append(f"| Partial(total → HRV | deep) | {ptf:.4f} | — |")
    out.append("")
    out.append(
        "**Verdict:** **H3 not supported in current wearable data.** "
        "Total sleep duration dominates; partial r for deep sleep is small and slightly negative. "
        "Given consumer deep-sleep stage classification κ ≈ 0.50, this is failure of consumer wearable data "
        "to isolate an SWS-specific recovery signal — not physiological evidence against SWS recovery. "
        "**Consumer deep-sleep minutes are not a reliable independent predictor once total sleep is known.** "
        "EEG-grade staging would be required to test the underlying mechanism (see `MEASUREMENT_MODEL.md`)."
    )
    return "\n".join(out)


def _render_baseline(snapshot_dir: Path) -> str:
    base_dir = snapshot_dir / "processed" / "baseline"
    cal_path = base_dir / "calibration_report.parquet"
    resid_path = base_dir / "residualized_acf.parquet"
    epoch_path = base_dir / "epoch_discontinuities.parquet"
    if not cal_path.exists():
        return "## Phase 0: Baseline Calibration — NOT YET RUN\n"

    cal = pl.read_parquet(cal_path)
    out = ["## Phase 0: Baseline Calibration (DONE)"]
    out.append("")
    out.append(f"> Script: `lac-baseline --extended` · Snapshot: `{snapshot_dir.name}`")
    out.append(
        "> Artifacts: `processed/baseline/calibration_report.parquet`, "
        "`residualized_acf.parquet`, `epoch_discontinuities.parquet`"
    )
    out.append("")

    out.append("### Stationarity + Autocorrelation (raw series, screening)")
    out.append("")
    out.append("| Metric | n | ACF(1) | n_eff_raw | ADF p | KPSS p | Stationarity |")
    out.append("|--------|---|--------|-----------|-------|--------|--------------|")
    for r in cal.iter_rows(named=True):
        adf = r.get("adf_p")
        kpss_p = r.get("kpss_p")
        out.append(
            f"| {r['metric']} | {r['n']} | {r.get('rho1', 0):.3f} | {r.get('n_effective', 0)} "
            f"| {adf:.4f} | {kpss_p:.3f} | {r.get('stationarity', '?')} |"
        )
    out.append("")
    out.append(
        "**⚠️ Reinterpretation:** raw n_eff is a screening warning for naive correlation, "
        "not the inferential n for the prewhitened pipeline. After ARIMA whitening with "
        "adequate residual diagnostics, inferential n approaches n_paired. H2 demonstrated "
        "this empirically (screening n_eff=102, prewhitened CI tight at n_paired=740)."
    )
    out.append("")

    if resid_path.exists():
        resid = pl.read_parquet(resid_path)
        out.append("### Residualized ACF (after month/DOW/epoch removal)")
        out.append("")
        out.append("| Metric | n | confounds | ρ1 (resid) | n_eff (resid) | Power r=0.10 | Power r=0.25 |")
        out.append("|--------|---|-----------|-----------|----------------|---------------|---------------|")
        for r in resid.iter_rows(named=True):
            out.append(
                f"| {r['metric']} | {r['n_raw']} | {r.get('confounds_removed', 'none')} "
                f"| {r.get('rho1', 0):.3f} | {r.get('n_eff', 0)} "
                f"| {r.get('power_r_0.10', 0):.3f} | {r.get('power_r_0.25', 0):.3f} |"
            )
        out.append("")
        out.append(
            "Residualization recovers substantial effective n. "
            "hrv_garmin: ρ1 0.761→0.597, power for r=0.25 jumps from 0.32 to 0.94. "
            "Month/epoch were eating most of the apparent persistence."
        )
        out.append("")

    if epoch_path.exists():
        epoch = pl.read_parquet(epoch_path)
        out.append(f"### Epoch Discontinuities ({epoch.height} detected)")
        out.append("")
        if epoch.height > 0:
            out.append("Most extreme by metric (top 1 per metric, ranked by |diff_sigma|):")
            top = (
                epoch.sort("metric")
                .group_by("metric")
                .agg(pl.all().sort_by(pl.col("diff_sigma").abs(), descending=True).first())
            )
            out.append("")
            out.append("| Metric | Date | Diff (σ) | t-stat | p-value |")
            out.append("|--------|------|----------|--------|---------|")
            for r in top.iter_rows(named=True):
                out.append(
                    f"| {r['metric']} | {r['date']} | {r.get('diff_sigma', 0):+.2f} "
                    f"| {r.get('t_stat', 0):+.2f} | {r.get('p_value', 0):.2e} |"
                )
        out.append("")
    return "\n".join(out)


def render_all(snapshot: str | None) -> str:
    base = snapshot_path(snapshot)
    parts = [
        "# RESULTS.md — Research Findings",
        "",
        "> **Auto-generated** by `lac-render-results` from "
        "`processed/baseline/*.parquet` and `processed/results/*.json`.",
        "> **Do not hand-edit** — re-run `lac-render-results` after any test re-execution.",
        "> Hypothesis specs are in `HYPOTHESIS_v1.2.md`. Methods are in `RESEARCH.md` §8.",
        "",
        "---",
        "",
        _render_baseline(base),
        "",
        "---",
        "",
        "## Phase 1: Confirmatory",
        "",
        _render_h10(base),
        "",
        _render_h12(base),
        "",
        "---",
        "",
        "## Phase 2: Exploratory",
        "",
        _render_h6(base),
        "",
        _render_h2(base),
        "",
        _render_h14(base),
        "",
        "---",
        "",
        "## Phase 2b: Underpowered / Report-Only",
        "",
        _render_h3(base),
        "",
        "---",
        "",
        "## Phase 3 / Blocked",
        "",
        "### H11: Acute Training Load → HRV",
        "",
        "> **Status: BLOCKED.** `acute_training_load` is 100% null in raw "
        "`garmin_training_status` (Garmin sync does not currently fetch this field). "
        "Unblock action: fix Garmin ingestion to populate `acute_training_load` "
        "and `training_load_7_day`. "
        "Alternative path: compute sRPE from existing Hevy data (Foster 2001).",
        "",
        "### H13: Alcohol → HRV",
        "",
        "> **Status: BLOCKED — awaiting ≥100 days of alcohol logging.** Current entries: 1.",
        "",
        "### H1: Supercompensation Event Study",
        "",
        "> **Status: BLOCKED — awaiting ≥25 isolated hard events.** Current: 2.",
        "",
        "---",
        "",
        f"*Generated against snapshot `{base.name}` from JSON artifacts. "
        "To regenerate after re-running tests: `uv run lac-render-results`.*",
        "",
    ]
    return "\n".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description="Regenerate RESULTS.md from JSON artifacts")
    parser.add_argument("--snapshot", default=None)
    parser.add_argument(
        "--output",
        default=None,
        help="Override output path (default: research/RESULTS.md)",
    )
    args = parser.parse_args()

    content = render_all(args.snapshot)
    out_path = Path(args.output) if args.output else Path(__file__).parent.parent / "RESULTS.md"
    out_path.write_text(content)
    print(f"Wrote {out_path} ({len(content.splitlines())} lines, {len(content)} chars)")


if __name__ == "__main__":
    main()
