from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TASK_ID = "T085"
RUN_ID = "T085-US-DATA-QUALITY-V1"
PERIOD_END = date(2026, 2, 26)
TRACEABILITY_LINE = (
    "- 2026-03-02T20:55:15Z | STATE3-P7B: T085 Qualidade US (SPC charts + blacklist + universo operacional). "
    "Artefatos: scripts/t085_us_data_quality_spc_blacklist.py, src/data_engine/ssot/SSOT_US_UNIVERSE_OPERATIONAL.parquet, "
    "src/data_engine/ssot/SSOT_US_BLACKLIST_OPERATIONAL.csv, outputs/governanca/T085-US-DATA-QUALITY-V1_report.md, "
    "outputs/governanca/T085-US-DATA-QUALITY-V1_manifest.json"
)

IN_US_RAW = ROOT / "src" / "data_engine" / "ssot" / "SSOT_US_MARKET_DATA_RAW.parquet"
IN_MACRO = ROOT / "src" / "data_engine" / "ssot" / "SSOT_MACRO.parquet"
CHANGELOG_PATH = ROOT / "00_Strategy" / "changelog.md"

OUT_US_UNIVERSE = ROOT / "src" / "data_engine" / "ssot" / "SSOT_US_UNIVERSE_OPERATIONAL.parquet"
OUT_US_BLACKLIST = ROOT / "src" / "data_engine" / "ssot" / "SSOT_US_BLACKLIST_OPERATIONAL.csv"
OUT_DIR = ROOT / "outputs" / "governanca"
OUT_EVIDENCE = OUT_DIR / f"{RUN_ID}_evidence"
OUT_REPORT = OUT_DIR / f"{RUN_ID}_report.md"
OUT_MANIFEST = OUT_DIR / f"{RUN_ID}_manifest.json"
OUT_COVERAGE = OUT_EVIDENCE / "coverage_by_ticker.csv"
OUT_GAPS = OUT_EVIDENCE / "gap_analysis_by_ticker.csv"
OUT_OHLC = OUT_EVIDENCE / "ohlc_integrity_violations.csv"
OUT_SPC_SUMMARY = OUT_EVIDENCE / "spc_outlier_summary.json"
OUT_MACRO_ALIGN = OUT_EVIDENCE / "macro_alignment_check.json"
OUT_SCHEMA = OUT_EVIDENCE / "schema_contract.json"
OUT_CHARTS = OUT_EVIDENCE / "spc_charts_us.html"


@dataclass
class Gate:
    name: str
    passed: bool
    details: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def append_changelog_idempotent(line: str) -> tuple[bool, str]:
    if not CHANGELOG_PATH.exists():
        return False, "missing_changelog"
    content = CHANGELOG_PATH.read_text(encoding="utf-8")
    if line in content:
        return True, "already_present"
    with CHANGELOG_PATH.open("a", encoding="utf-8") as f:
        if not content.endswith("\n"):
            f.write("\n")
        f.write(line + "\n")
    return True, "appended"


def render_report(gates: list[Gate], summary: dict[str, Any], artifacts: list[Path]) -> str:
    overall = all(g.passed for g in gates)
    lines: list[str] = []
    lines.append(f"# HEADER: {TASK_ID}")
    lines.append("")
    lines.append("## STEP GATES")
    for g in gates:
        lines.append(f"- {'PASS' if g.passed else 'FAIL'} | {g.name} | {g.details}")
    lines.append("")
    lines.append("## EXECUTIVE SUMMARY")
    for k, v in summary.items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## ARTIFACT LINKS")
    for p in artifacts:
        lines.append(f"- {p.relative_to(ROOT).as_posix()}")
    lines.append("")
    lines.append(f"OVERALL STATUS: [[ {'PASS' if overall else 'FAIL'} ]]")
    lines.append("")
    return "\n".join(lines)


def to_datetime_series(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, errors="coerce", utc=False).dt.tz_localize(None)


def build_spc_html(df: pd.DataFrame, outliers: pd.Series, out_path: Path) -> None:
    by_volume = (
        df.groupby("ticker", as_index=False)["volume"]
        .mean()
        .sort_values("volume", ascending=False)["ticker"]
        .head(5)
        .tolist()
    )
    by_outliers = (
        df.assign(outlier=outliers.values)
        .groupby("ticker", as_index=False)["outlier"]
        .sum()
        .sort_values("outlier", ascending=False)["ticker"]
        .head(5)
        .tolist()
    )
    spotlight = [t for t in ["AAPL", "MSFT"] if t in set(df["ticker"].unique())]
    selected = list(dict.fromkeys(by_volume + by_outliers + spotlight))
    if not selected:
        selected = sorted(df["ticker"].astype(str).unique().tolist())[:5]

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        subplot_titles=("Close (normalizado em 100 na 1a data)", "X_real e flags de outlier"),
        vertical_spacing=0.12,
    )

    for ticker in selected:
        tf = df[df["ticker"] == ticker].sort_values("date")
        if tf.empty:
            continue
        base = float(tf["close"].iloc[0]) if pd.notna(tf["close"].iloc[0]) else np.nan
        close_norm = (tf["close"] / base) * 100.0 if base and np.isfinite(base) else tf["close"]
        fig.add_trace(
            go.Scatter(
                x=tf["date"],
                y=close_norm,
                mode="lines",
                name=f"{ticker} close_norm",
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=tf["date"],
                y=tf["X_real"],
                mode="lines",
                name=f"{ticker} X_real",
                opacity=0.7,
            ),
            row=2,
            col=1,
        )
        tof = tf[tf["outlier_any"]]
        if not tof.empty:
            fig.add_trace(
                go.Scatter(
                    x=tof["date"],
                    y=tof["X_real"],
                    mode="markers",
                    marker=dict(size=6),
                    name=f"{ticker} outliers",
                ),
                row=2,
                col=1,
            )

    fig.update_layout(
        title="T085 - SPC/Outliers US (amostra operacional)",
        template="plotly_white",
        height=900,
        legend_orientation="h",
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(fig.to_html(full_html=True, include_plotlyjs="cdn"), encoding="utf-8")


def main() -> None:
    OUT_EVIDENCE.mkdir(parents=True, exist_ok=True)
    OUT_US_UNIVERSE.parent.mkdir(parents=True, exist_ok=True)

    gates: list[Gate] = []
    artifacts: list[Path] = []
    retry_log: list[str] = []

    gates.append(
        Gate(
            "G_INPUTS_PRESENT",
            IN_US_RAW.exists() and IN_MACRO.exists() and CHANGELOG_PATH.exists(),
            f"us_raw={IN_US_RAW.exists()} macro={IN_MACRO.exists()} changelog={CHANGELOG_PATH.exists()}",
        )
    )
    if not gates[-1].passed:
        raise RuntimeError("Inputs obrigatorios ausentes para T085.")

    us = pd.read_parquet(IN_US_RAW)
    macro = pd.read_parquet(IN_MACRO)

    required_us = {
        "ticker",
        "date",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "adjusted_close",
        "dividends",
        "splits",
    }
    required_macro = {"date", "cdi_log_daily"}
    schema_ok = required_us.issubset(set(us.columns)) and required_macro.issubset(set(macro.columns))
    gates.append(
        Gate(
            "G_SCHEMA_CONTRACT",
            schema_ok,
            f"us_has={sorted(required_us.issubset(set(us.columns)) for _ in [0])[0]} macro_has={required_macro.issubset(set(macro.columns))}",
        )
    )
    if not schema_ok:
        raise RuntimeError("Schema invalido para inputs da T085.")

    us = us.copy()
    us["ticker"] = us["ticker"].astype(str).str.upper().str.strip()
    us["date"] = to_datetime_series(us["date"])
    macro = macro.copy()
    macro["date"] = to_datetime_series(macro["date"])

    numeric_cols = ["open", "high", "low", "close", "volume", "adjusted_close", "dividends"]
    for c in numeric_cols:
        us[c] = pd.to_numeric(us[c], errors="coerce")
    us = us.dropna(subset=["ticker", "date"]).sort_values(["ticker", "date"]).reset_index(drop=True)

    dup_mask = us.duplicated(subset=["ticker", "date"], keep=False)
    dup_count = int(dup_mask.sum())
    dup_tickers = sorted(us.loc[dup_mask, "ticker"].unique().tolist())
    gates.append(Gate("G_NO_DUPES_TICKER_DATE", dup_count == 0, f"duplicates={dup_count}"))
    if dup_count > 0:
        us = us.drop_duplicates(subset=["ticker", "date"], keep="last").reset_index(drop=True)

    ohlc_invalid = (
        us["open"].isna()
        | us["high"].isna()
        | us["low"].isna()
        | us["close"].isna()
        | (us["low"] > us["high"])
        | (us["low"] > us[["open", "close"]].min(axis=1))
        | (us["high"] < us[["open", "close"]].max(axis=1))
        | (us[["open", "high", "low", "close"]] <= 0).any(axis=1)
    )
    ohlc_viol = us.loc[ohlc_invalid, ["ticker", "date", "open", "high", "low", "close"]].copy()
    ohlc_viol["reason"] = "ohlc_integrity_violation"
    ohlc_viol["date"] = ohlc_viol["date"].dt.strftime("%Y-%m-%d")
    ohlc_viol.to_csv(OUT_OHLC, index=False)
    artifacts.append(OUT_OHLC)
    ohlc_viol_tickers = set(ohlc_viol["ticker"].astype(str).tolist())

    expected_calendar = np.array(sorted(us["date"].dropna().unique()))
    expected_calendar = pd.to_datetime(expected_calendar)
    expected_idx = pd.Index(expected_calendar)

    rows: list[dict[str, Any]] = []
    for ticker, tf in us.groupby("ticker", sort=True):
        tfs = tf.sort_values("date")
        first_date = pd.Timestamp(tfs["date"].iloc[0])
        last_date = pd.Timestamp(tfs["date"].iloc[-1])
        n_rows = int(len(tfs))
        post_listing_dates = expected_idx[(expected_idx >= first_date) & (expected_idx <= pd.Timestamp(PERIOD_END))]
        expected_post = int(len(post_listing_dates))
        coverage = float(n_rows / expected_post) if expected_post > 0 else 0.0
        diffs = tfs["date"].diff().dt.days.fillna(0)
        max_gap = int(diffs.max()) if len(diffs) else 0
        rows.append(
            {
                "ticker": ticker,
                "first_date": first_date.date().isoformat(),
                "last_date": last_date.date().isoformat(),
                "n_rows": n_rows,
                "expected_days_post_listing": expected_post,
                "coverage_ratio_post_listing": round(coverage, 6),
                "max_gap_days": max_gap,
            }
        )

    metrics = pd.DataFrame(rows).sort_values("ticker").reset_index(drop=True)
    metrics.to_csv(OUT_COVERAGE, index=False)
    artifacts.append(OUT_COVERAGE)
    metrics[["ticker", "first_date", "last_date", "max_gap_days", "expected_days_post_listing"]].to_csv(OUT_GAPS, index=False)
    artifacts.append(OUT_GAPS)

    soft_excl = (
        (metrics["n_rows"] < 252)
        | (metrics["coverage_ratio_post_listing"] < 0.80)
        | (metrics["max_gap_days"] > 20)
    )
    soft_count = int(soft_excl.sum())
    hard_tickers = set(dup_tickers) | set(ohlc_viol_tickers)
    op_count = int(len(metrics) - soft_count - len([t for t in hard_tickers if t in set(metrics["ticker"])]))
    gates.append(
        Gate(
            "G_COVERAGE_AND_GAPS",
            op_count >= 450,
            f"operational={op_count} total={len(metrics)} soft_excluded={soft_count} hard_excluded={len(hard_tickers)}",
        )
    )

    macro_unique = macro[["date", "cdi_log_daily"]].drop_duplicates(subset=["date"], keep="last").sort_values("date")
    merged_dates = us[["date"]].drop_duplicates().sort_values("date").merge(macro_unique, on="date", how="left")
    missing_cdi_raw = int(merged_dates["cdi_log_daily"].isna().sum())
    merged_dates["cdi_log_daily_filled"] = merged_dates["cdi_log_daily"].ffill().bfill()
    missing_cdi_after_fill = int(merged_dates["cdi_log_daily_filled"].isna().sum())
    macro_payload = {
        "us_dates_count": int(len(merged_dates)),
        "macro_dates_count": int(len(macro_unique)),
        "missing_cdi_raw_after_merge": missing_cdi_raw,
        "missing_cdi_after_fill": missing_cdi_after_fill,
        "us_min_date": str(merged_dates["date"].min().date()),
        "us_max_date": str(merged_dates["date"].max().date()),
    }
    write_json(OUT_MACRO_ALIGN, macro_payload)
    artifacts.append(OUT_MACRO_ALIGN)
    gates.append(
        Gate(
            "G_MACRO_ALIGNMENT",
            missing_cdi_after_fill == 0,
            f"missing_raw={missing_cdi_raw} missing_after_fill={missing_cdi_after_fill}",
        )
    )

    us = us.sort_values(["ticker", "date"]).reset_index(drop=True)
    us["logret"] = np.log(us["close"] / us.groupby("ticker")["close"].shift(1))
    us["logret"] = us["logret"].replace([np.inf, -np.inf], np.nan)
    us = us.merge(merged_dates[["date", "cdi_log_daily_filled"]], on="date", how="left")
    us["X_real"] = us["logret"] - us["cdi_log_daily_filled"]

    grp = us.groupby("ticker")["X_real"]
    rolling_mean = grp.transform(lambda s: s.rolling(60, min_periods=60).mean().shift(1))
    rolling_std = grp.transform(lambda s: s.rolling(60, min_periods=60).std(ddof=0).shift(1))
    zscore = (us["X_real"] - rolling_mean) / rolling_std.replace(0, np.nan)

    us["outlier_abs"] = us["X_real"].abs() > 1.0
    us["outlier_z"] = zscore.abs() > 8.0
    us["outlier_any"] = us["outlier_abs"] | us["outlier_z"]
    outlier_count = int(us["outlier_any"].sum())
    gates.append(Gate("G_SPC_OUTLIERS_COMPUTED", outlier_count >= 0, f"outlier_rows={outlier_count}"))

    by_ticker_out = us.groupby("ticker", as_index=False)["outlier_any"].sum().rename(columns={"outlier_any": "outlier_count"})
    metrics = metrics.merge(by_ticker_out, on="ticker", how="left")
    metrics["outlier_count"] = metrics["outlier_count"].fillna(0).astype(int)

    summary_payload = {
        "task_id": TASK_ID,
        "run_id": RUN_ID,
        "ticker_count_total": int(metrics["ticker"].nunique()),
        "outlier_rows_total": outlier_count,
        "tickers_with_outliers": int((metrics["outlier_count"] > 0).sum()),
        "max_outliers_single_ticker": int(metrics["outlier_count"].max() if not metrics.empty else 0),
        "rules": {
            "outlier_abs": "|X_real| > 1.0",
            "outlier_z": "|zscore_rolling60_shift1| > 8.0",
            "soft_exclusion": "n_rows<252 OR coverage_ratio_post_listing<0.80 OR max_gap_days>20",
        },
    }
    write_json(OUT_SPC_SUMMARY, summary_payload)
    artifacts.append(OUT_SPC_SUMMARY)

    build_spc_html(us[["ticker", "date", "close", "volume", "X_real", "outlier_any"]].copy(), us["outlier_any"], OUT_CHARTS)
    artifacts.append(OUT_CHARTS)

    black_rows: list[dict[str, Any]] = []
    soft_map = metrics.set_index("ticker").to_dict(orient="index")
    for ticker in sorted(set(metrics["ticker"])):
        info = soft_map[ticker]
        if ticker in hard_tickers:
            hard_reasons: list[str] = []
            if ticker in set(dup_tickers):
                hard_reasons.append("duplicate_ticker_date")
            if ticker in set(ohlc_viol["ticker"]):
                hard_reasons.append("ohlc_integrity_violation")
            black_rows.append(
                {
                    "ticker": ticker,
                    "severity": "HARD",
                    "reason": ";".join(hard_reasons),
                    "details": f"n_rows={info['n_rows']} coverage={info['coverage_ratio_post_listing']} max_gap={info['max_gap_days']}",
                }
            )
            continue
        reasons: list[str] = []
        if int(info["n_rows"]) < 252:
            reasons.append("n_rows_lt_252")
        if float(info["coverage_ratio_post_listing"]) < 0.80:
            reasons.append("coverage_lt_0_80")
        if int(info["max_gap_days"]) > 20:
            reasons.append("max_gap_gt_20")
        if reasons:
            black_rows.append(
                {
                    "ticker": ticker,
                    "severity": "SOFT",
                    "reason": ";".join(reasons),
                    "details": f"n_rows={info['n_rows']} coverage={info['coverage_ratio_post_listing']} max_gap={info['max_gap_days']}",
                }
            )

    black = pd.DataFrame(black_rows).sort_values(["severity", "ticker"]).reset_index(drop=True)
    if black.empty:
        black = pd.DataFrame(columns=["ticker", "severity", "reason", "details"])
    black.to_csv(OUT_US_BLACKLIST, index=False)
    artifacts.append(OUT_US_BLACKLIST)
    gates.append(Gate("G_BLACKLIST_WRITTEN", OUT_US_BLACKLIST.exists(), f"rows={len(black)}"))
    hard_blacklisted_tickers = set(black.loc[black["severity"] == "HARD", "ticker"].astype(str).tolist())
    ohlc_handled = ohlc_viol_tickers.issubset(hard_blacklisted_tickers)
    gates.append(
        Gate(
            "G_OHLC_INTEGRITY",
            ohlc_handled,
            f"violations={len(ohlc_viol)} violating_tickers={len(ohlc_viol_tickers)} handled_by_blacklist={ohlc_handled}",
        )
    )

    approved = metrics[~metrics["ticker"].isin(set(black["ticker"].tolist()))].copy()
    approved = approved.sort_values("ticker").reset_index(drop=True)
    approved.to_parquet(OUT_US_UNIVERSE, index=False)
    artifacts.append(OUT_US_UNIVERSE)
    gates.append(Gate("G_UNIVERSE_OPERATIONAL_WRITTEN", OUT_US_UNIVERSE.exists(), f"rows={len(approved)}"))

    schema_payload = {
        "input_required_columns": sorted(required_us),
        "output_universe_columns": approved.columns.tolist(),
        "blacklist_columns": ["ticker", "severity", "reason", "details"],
        "coverage_formula": "coverage_ratio_post_listing = n_rows / expected_days_post_listing",
        "expected_days_note": "expected_days_post_listing usa calendario observado no SSOT US entre first_date e PERIOD_END.",
    }
    write_json(OUT_SCHEMA, schema_payload)
    artifacts.append(OUT_SCHEMA)

    ch_ok, ch_mode = append_changelog_idempotent(TRACEABILITY_LINE)
    gates.append(Gate("G_CHLOG_UPDATED", ch_ok, f"mode={ch_mode}"))

    summary = {
        "tickers_total": int(metrics["ticker"].nunique()),
        "tickers_any_data": int(metrics["ticker"].nunique()),
        "tickers_operational": int(approved["ticker"].nunique()),
        "tickers_blacklisted_hard": int((black["severity"] == "HARD").sum()) if not black.empty else 0,
        "tickers_blacklisted_soft": int((black["severity"] == "SOFT").sum()) if not black.empty else 0,
        "missing_cdi_raw_after_merge": missing_cdi_raw,
        "missing_cdi_after_fill": missing_cdi_after_fill,
        "ohlc_integrity_violations": int(len(ohlc_viol)),
    }

    report_text = render_report(gates=gates, summary=summary, artifacts=artifacts + [OUT_REPORT, OUT_MANIFEST])
    OUT_REPORT.write_text(report_text, encoding="utf-8")
    artifacts.append(OUT_REPORT)

    hashes = {p.relative_to(ROOT).as_posix(): sha256_file(p) for p in artifacts + [CHANGELOG_PATH]}
    manifest = {
        "task_id": TASK_ID,
        "run_id": RUN_ID,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "inputs_consumed": [
            IN_US_RAW.relative_to(ROOT).as_posix(),
            IN_MACRO.relative_to(ROOT).as_posix(),
        ],
        "outputs_produced": [p.relative_to(ROOT).as_posix() for p in artifacts] + [CHANGELOG_PATH.relative_to(ROOT).as_posix()],
        "hashes_sha256": hashes,
    }
    write_json(OUT_MANIFEST, manifest)
    gates.append(Gate("Gx_HASH_MANIFEST_PRESENT", OUT_MANIFEST.exists(), f"path={OUT_MANIFEST.relative_to(ROOT).as_posix()}"))

    recalculated = {k: sha256_file(ROOT / k) for k in manifest["hashes_sha256"]}
    mismatches = [k for k, v in recalculated.items() if manifest["hashes_sha256"].get(k) != v]
    gates.append(Gate("G_SHA256_INTEGRITY_SELF_CHECK", len(mismatches) == 0, f"mismatches={len(mismatches)}"))

    overall = all(g.passed for g in gates)
    print(f"# HEADER: {TASK_ID}")
    print("## STEP GATES")
    for g in gates:
        print(f"- {'PASS' if g.passed else 'FAIL'} | {g.name} | {g.details}")
    print("## RETRY LOG")
    if retry_log:
        for item in retry_log:
            print(f"- {item}")
    else:
        print("- none")
    print("## ARTIFACT LINKS")
    for p in artifacts + [OUT_MANIFEST]:
        print(f"- {p.relative_to(ROOT).as_posix()}")
    print(f"OVERALL STATUS: [[ {'PASS' if overall else 'FAIL'} ]]")
    if not overall:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
