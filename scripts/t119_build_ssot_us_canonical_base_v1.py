from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TASK_ID = "T119"
RUN_ID = "T119-SSOT-US-CANONICAL-V1"
TRACEABILITY_LINE = (
    "- 2026-03-04T18:00:00Z | EXEC: T119 SSOT canônico per-ticker US (496 tickers, SPC metrics, USD) materializado. "
    "Artefatos: scripts/t119_build_ssot_us_canonical_base_v1.py; "
    "src/data_engine/ssot/SSOT_CANONICAL_BASE_US.parquet; "
    "src/data_engine/ssot/SSOT_US_UNIVERSE_OPERATIONAL_PHASE10.parquet; "
    "outputs/governanca/T119-SSOT-US-CANONICAL-V1_{report,manifest}.md"
)

IN_US_RAW = ROOT / "src" / "data_engine" / "ssot" / "SSOT_US_MARKET_DATA_RAW.parquet"
IN_MACRO = ROOT / "src" / "data_engine" / "ssot" / "SSOT_MACRO_EXPANDED.parquet"
IN_BLACKLIST = ROOT / "src" / "data_engine" / "ssot" / "SSOT_US_BLACKLIST_OPERATIONAL.csv"
IN_UNIVERSE = ROOT / "src" / "data_engine" / "ssot" / "SSOT_US_UNIVERSE_OPERATIONAL.parquet"
IN_BR_CANONICAL = ROOT / "src" / "data_engine" / "ssot" / "SSOT_CANONICAL_BASE.parquet"
CHANGELOG_PATH = ROOT / "00_Strategy" / "changelog.md"

OUT_SCRIPT = ROOT / "scripts" / "t119_build_ssot_us_canonical_base_v1.py"
OUT_SSOT_US = ROOT / "src" / "data_engine" / "ssot" / "SSOT_CANONICAL_BASE_US.parquet"
OUT_UNIVERSE_US = ROOT / "src" / "data_engine" / "ssot" / "SSOT_US_UNIVERSE_OPERATIONAL_PHASE10.parquet"
OUT_DIR = ROOT / "outputs" / "governanca"
OUT_EVIDENCE = OUT_DIR / f"{RUN_ID}_evidence"
OUT_REPORT = OUT_DIR / f"{RUN_ID}_report.md"
OUT_MANIFEST = OUT_DIR / f"{RUN_ID}_manifest.json"
OUT_SCHEMA = OUT_EVIDENCE / "schema_contract.json"
OUT_COUNTS = OUT_EVIDENCE / "universe_counts.json"
OUT_COVERAGE = OUT_EVIDENCE / "coverage_summary.csv"

REF_WINDOW_K = 60
SUBGROUP_N = 4
A2_N4 = 0.729
D4_N4 = 2.282
E2_IMR_N2 = 2.66
D4_IMR_N2 = 3.267

REQUIRED_COLS = [
    "ticker",
    "date",
    "close_operational",
    "close_raw",
    "X_real",
    "i_value",
    "i_ucl",
    "i_lcl",
    "mr_value",
    "mr_ucl",
    "xbar_value",
    "xbar_ucl",
    "xbar_lcl",
    "r_value",
    "r_ucl",
    "sector",
    "mr_bar",
    "r_bar",
    "center_line",
    "splits",
    "split_factor",
]


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


def render_report(gates: list[Gate], retry_log: list[str], artifacts: list[Path], summary: dict[str, Any]) -> str:
    overall = all(g.passed for g in gates)
    lines: list[str] = []
    lines.append(f"# HEADER: {TASK_ID}")
    lines.append("")
    lines.append("## STEP GATES")
    for g in gates:
        lines.append(f"- {'PASS' if g.passed else 'FAIL'} | {g.name} | {g.details}")
    lines.append("")
    lines.append("## RETRY LOG")
    lines.extend([f"- {item}" for item in retry_log] if retry_log else ["- none"])
    lines.append("")
    lines.append("## EXECUTIVE SUMMARY")
    for k, v in summary.items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## ARTIFACT LINKS")
    for p in artifacts:
        lines.append(f"- {p.relative_to(ROOT).as_posix()}")
    lines.append("")
    lines.append("## MANIFEST POLICY")
    lines.append("- policy=no_self_hash (manifest não se auto-hasheia).")
    lines.append("")
    lines.append(f"OVERALL STATUS: [[ {'PASS' if overall else 'FAIL'} ]]")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    OUT_EVIDENCE.mkdir(parents=True, exist_ok=True)
    OUT_SSOT_US.parent.mkdir(parents=True, exist_ok=True)
    OUT_UNIVERSE_US.parent.mkdir(parents=True, exist_ok=True)

    gates: list[Gate] = []
    retry_log: list[str] = []
    artifacts: list[Path] = []

    inputs_ok = all(p.exists() for p in [IN_US_RAW, IN_MACRO, IN_BLACKLIST, IN_UNIVERSE, IN_BR_CANONICAL, CHANGELOG_PATH])
    gates.append(
        Gate(
            "G_INPUTS_PRESENT",
            inputs_ok,
            (
                f"us_raw={IN_US_RAW.exists()} macro={IN_MACRO.exists()} blacklist={IN_BLACKLIST.exists()} "
                f"universe={IN_UNIVERSE.exists()} br_canonical={IN_BR_CANONICAL.exists()} changelog={CHANGELOG_PATH.exists()}"
            ),
        )
    )
    if not inputs_ok:
        raise RuntimeError("Inputs obrigatórios ausentes para T119.")

    br_canonical = pd.read_parquet(IN_BR_CANONICAL)
    br_cols = list(br_canonical.columns)
    gates.append(Gate("G_SCHEMA_REFERENCE_21COLS", br_cols == REQUIRED_COLS, f"schema_cols={len(br_cols)}"))

    us_raw = pd.read_parquet(IN_US_RAW).copy()
    us_raw["ticker"] = us_raw["ticker"].astype(str).str.upper().str.strip()
    us_raw["date"] = pd.to_datetime(us_raw["date"], errors="coerce")
    us_raw["close"] = pd.to_numeric(us_raw["close"], errors="coerce")
    us_raw["splits"] = us_raw["splits"].astype(str).fillna("")
    us_raw["split_factor"] = 1.0

    blacklist = pd.read_csv(IN_BLACKLIST).copy()
    blacklist["ticker"] = blacklist["ticker"].astype(str).str.upper().str.strip()
    hard = set(
        blacklist.loc[blacklist["severity"].astype(str).str.upper().eq("HARD"), "ticker"]
        .astype(str)
        .tolist()
    )
    raw_tickers = int(us_raw["ticker"].nunique())
    us_raw = us_raw[~us_raw["ticker"].isin(hard)].copy()
    post_blacklist_tickers = int(us_raw["ticker"].nunique())
    gates.append(
        Gate(
            "G_BLACKLIST_APPLIED",
            post_blacklist_tickers == 496,
            f"raw={raw_tickers} hard_removed={len(hard)} after={post_blacklist_tickers}",
        )
    )

    us_raw = us_raw.dropna(subset=["ticker", "date", "close"]).sort_values(["ticker", "date"]).reset_index(drop=True)
    us_raw.loc[us_raw["close"] <= 0, "close"] = np.nan
    us_raw = us_raw.dropna(subset=["close"]).copy()

    us_raw["close_operational"] = us_raw["close"]
    us_raw["close_raw"] = us_raw["close"]
    us_raw["log_ret_nominal"] = np.log(us_raw["close_operational"] / us_raw.groupby("ticker")["close_operational"].shift(1))
    us_raw["log_ret_nominal"] = us_raw["log_ret_nominal"].replace([np.inf, -np.inf], np.nan)
    us_raw["sector"] = "US"

    macro = pd.read_parquet(IN_MACRO, columns=["date", "fed_funds_rate"]).copy()
    macro["date"] = pd.to_datetime(macro["date"], errors="coerce")
    macro["fed_funds_rate"] = pd.to_numeric(macro["fed_funds_rate"], errors="coerce")
    macro = macro.dropna(subset=["date"]).drop_duplicates(subset=["date"], keep="last").sort_values("date")
    macro["fed_funds_rate"] = macro["fed_funds_rate"].ffill().bfill()
    macro["cash_log_daily_us"] = np.log1p((macro["fed_funds_rate"] / 100.0) / 252.0)

    merged = us_raw.merge(macro[["date", "cash_log_daily_us"]], on="date", how="left")
    merged["cash_log_daily_us"] = merged["cash_log_daily_us"].ffill().bfill()
    merged["X_real"] = merged["log_ret_nominal"] - merged["cash_log_daily_us"]
    merged["i_value"] = merged["X_real"]
    merged["mr_value"] = (merged["i_value"] - merged.groupby("ticker")["i_value"].shift(1)).abs()

    grp = merged.groupby("ticker", group_keys=False)
    merged["xbar_value"] = grp["i_value"].transform(lambda s: s.rolling(SUBGROUP_N, min_periods=SUBGROUP_N).mean())
    roll_max = grp["i_value"].transform(lambda s: s.rolling(SUBGROUP_N, min_periods=SUBGROUP_N).max())
    roll_min = grp["i_value"].transform(lambda s: s.rolling(SUBGROUP_N, min_periods=SUBGROUP_N).min())
    merged["r_value"] = roll_max - roll_min

    merged["center_line"] = grp["i_value"].transform(lambda s: s.rolling(REF_WINDOW_K, min_periods=REF_WINDOW_K).mean().shift(1))
    merged["mr_bar"] = grp["mr_value"].transform(lambda s: s.rolling(REF_WINDOW_K, min_periods=REF_WINDOW_K).mean().shift(1))
    merged["r_bar"] = grp["r_value"].transform(lambda s: s.rolling(REF_WINDOW_K, min_periods=REF_WINDOW_K).mean().shift(1))

    merged["i_ucl"] = merged["center_line"] + (E2_IMR_N2 * merged["mr_bar"])
    merged["i_lcl"] = merged["center_line"] - (E2_IMR_N2 * merged["mr_bar"])
    merged["mr_ucl"] = D4_IMR_N2 * merged["mr_bar"]
    merged["xbar_ucl"] = merged["center_line"] + (A2_N4 * merged["r_bar"])
    merged["xbar_lcl"] = merged["center_line"] - (A2_N4 * merged["r_bar"])
    merged["r_ucl"] = D4_N4 * merged["r_bar"]

    out = merged[REQUIRED_COLS].copy()
    out["date"] = pd.to_datetime(merged["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    out["split_factor"] = pd.to_numeric(out["split_factor"], errors="coerce").fillna(1.0)
    out["splits"] = out["splits"].astype(str).fillna("")
    out = out.sort_values(["ticker", "date"]).reset_index(drop=True)

    duplicates = int(out.duplicated(subset=["ticker", "date"]).sum())
    gates.append(Gate("G_NO_DUPES_TICKER_DATE", duplicates == 0, f"duplicates={duplicates}"))

    close_nan = int(pd.to_numeric(out["close_operational"], errors="coerce").isna().sum())
    close_raw_nan = int(pd.to_numeric(out["close_raw"], errors="coerce").isna().sum())
    gates.append(Gate("G_NO_NAN_CLOSE", close_nan == 0 and close_raw_nan == 0, f"nan_close_operational={close_nan} nan_close_raw={close_raw_nan}"))

    min_date = str(pd.to_datetime(out["date"], errors="coerce").min().date())
    max_date = str(pd.to_datetime(out["date"], errors="coerce").max().date())
    gates.append(Gate("G_DATE_RANGE_OK", min_date == "2018-01-02" and max_date == "2026-02-26", f"min={min_date} max={max_date}"))

    gates.append(Gate("G_TICKER_COUNT_OK", int(out["ticker"].nunique()) == 496, f"ticker_count={int(out['ticker'].nunique())}"))

    out.to_parquet(OUT_SSOT_US, index=False)
    artifacts.append(OUT_SSOT_US)

    calendar = sorted(pd.to_datetime(out["date"], errors="coerce").dropna().unique())
    calendar_series = pd.Series(calendar)
    records: list[dict[str, Any]] = []
    for ticker, g in out.groupby("ticker"):
        d = pd.to_datetime(g["date"], errors="coerce").dropna().sort_values()
        if d.empty:
            continue
        first = d.iloc[0]
        last = d.iloc[-1]
        mask = (calendar_series >= first) & (calendar_series <= last)
        expected = int(mask.sum())
        n_rows = int(len(g))
        coverage = float(n_rows / expected) if expected > 0 else 0.0
        max_gap = int(d.diff().dt.days.dropna().max()) if len(d) > 1 else 0
        records.append(
            {
                "ticker": ticker,
                "first_date": first.strftime("%Y-%m-%d"),
                "last_date": last.strftime("%Y-%m-%d"),
                "n_rows": n_rows,
                "expected_days_post_listing": expected,
                "coverage_ratio_post_listing": coverage,
                "max_gap_days": max_gap,
            }
        )

    universe = pd.DataFrame(records).sort_values("ticker").reset_index(drop=True)
    universe.to_parquet(OUT_UNIVERSE_US, index=False)
    artifacts.append(OUT_UNIVERSE_US)

    universe.to_csv(OUT_COVERAGE, index=False)
    artifacts.append(OUT_COVERAGE)

    schema_payload = {
        "task_id": TASK_ID,
        "run_id": RUN_ID,
        "schema_columns": REQUIRED_COLS,
        "column_count": len(REQUIRED_COLS),
        "spc_params": {
            "ref_window_k": REF_WINDOW_K,
            "subgroup_n": SUBGROUP_N,
            "A2_N4": A2_N4,
            "D4_N4": D4_N4,
            "E2_IMR_N2": E2_IMR_N2,
            "D4_IMR_N2": D4_IMR_N2,
        },
        "cash_formula": "cash_log_daily_us = log(1 + (fed_funds_rate/100)/252)",
    }
    write_json(OUT_SCHEMA, schema_payload)
    artifacts.append(OUT_SCHEMA)

    counts_payload = {
        "raw_tickers": raw_tickers,
        "hard_blacklist_count": len(hard),
        "post_blacklist_tickers": post_blacklist_tickers,
        "canonical_tickers": int(out["ticker"].nunique()),
        "canonical_rows": int(len(out)),
        "date_min": min_date,
        "date_max": max_date,
        "coverage_min": float(universe["coverage_ratio_post_listing"].min()),
        "coverage_p50": float(universe["coverage_ratio_post_listing"].median()),
        "coverage_max": float(universe["coverage_ratio_post_listing"].max()),
    }
    write_json(OUT_COUNTS, counts_payload)
    artifacts.append(OUT_COUNTS)

    gates.append(Gate("G_REQUIRED_COLS_PRESENT", all(c in out.columns for c in REQUIRED_COLS), f"required_cols={len(REQUIRED_COLS)}"))
    gates.append(Gate("G_COVERAGE_SUMMARY_PRESENT", OUT_COVERAGE.exists(), f"path={OUT_COVERAGE.relative_to(ROOT).as_posix()}"))

    summary = {
        "rows": int(len(out)),
        "tickers": int(out["ticker"].nunique()),
        "date_min": min_date,
        "date_max": max_date,
        "hard_blacklist_removed": len(hard),
    }

    ch_ok, ch_mode = append_changelog_idempotent(TRACEABILITY_LINE)
    gates.append(Gate("G_CHLOG_UPDATED", ch_ok, f"mode={ch_mode}"))

    # Report preliminar (sem gates de hash), apenas para materialização inicial.
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    pre_report = render_report(gates, retry_log, artifacts + [OUT_SCRIPT, OUT_REPORT, OUT_MANIFEST], summary)
    OUT_REPORT.write_text(pre_report, encoding="utf-8")
    artifacts.append(OUT_REPORT)

    manifest_paths = [
        IN_US_RAW,
        IN_MACRO,
        IN_BLACKLIST,
        IN_UNIVERSE,
        IN_BR_CANONICAL,
        CHANGELOG_PATH,
        OUT_SCRIPT,
        OUT_SSOT_US,
        OUT_UNIVERSE_US,
        OUT_SCHEMA,
        OUT_COUNTS,
        OUT_COVERAGE,
        OUT_REPORT,
    ]

    # Passo 1: grava manifest preliminar.
    hashes_v1 = {p.relative_to(ROOT).as_posix(): sha256_file(p) for p in manifest_paths}
    manifest = {
        "task_id": TASK_ID,
        "run_id": RUN_ID,
        "generated_at_utc": "2026-03-04T18:00:00Z",
        "inputs_consumed": [
            IN_US_RAW.relative_to(ROOT).as_posix(),
            IN_MACRO.relative_to(ROOT).as_posix(),
            IN_BLACKLIST.relative_to(ROOT).as_posix(),
            IN_UNIVERSE.relative_to(ROOT).as_posix(),
            IN_BR_CANONICAL.relative_to(ROOT).as_posix(),
            CHANGELOG_PATH.relative_to(ROOT).as_posix(),
        ],
        "outputs_produced": [
            OUT_SCRIPT.relative_to(ROOT).as_posix(),
            OUT_SSOT_US.relative_to(ROOT).as_posix(),
            OUT_UNIVERSE_US.relative_to(ROOT).as_posix(),
            OUT_REPORT.relative_to(ROOT).as_posix(),
            OUT_SCHEMA.relative_to(ROOT).as_posix(),
            OUT_COUNTS.relative_to(ROOT).as_posix(),
            OUT_COVERAGE.relative_to(ROOT).as_posix(),
        ],
        "hashes_sha256": hashes_v1,
        "policy": "no_self_hash",
    }
    write_json(OUT_MANIFEST, manifest)
    artifacts.append(OUT_MANIFEST)

    # Gate de presença do manifest.
    gates.append(Gate("Gx_HASH_MANIFEST_PRESENT", OUT_MANIFEST.exists(), f"path={OUT_MANIFEST.relative_to(ROOT).as_posix()}"))

    # Report final com todos os gates (incluindo Gx), depois recalcula hashes e regrava manifest final.
    final_report = render_report(gates, retry_log, artifacts, summary)
    OUT_REPORT.write_text(final_report, encoding="utf-8")

    hashes_v2 = {p.relative_to(ROOT).as_posix(): sha256_file(p) for p in manifest_paths}
    manifest["hashes_sha256"] = hashes_v2
    write_json(OUT_MANIFEST, manifest)

    mismatch = 0
    for path_str, expected in hashes_v2.items():
        real = sha256_file(ROOT / path_str)
        if real != expected:
            mismatch += 1
    gates.append(Gate("G_SHA256_INTEGRITY_SELF_CHECK", mismatch == 0, f"mismatches={mismatch}"))

    # Congela report final agora com todos os gates, incluindo self-check.
    final_report = render_report(gates, retry_log, artifacts, summary)
    OUT_REPORT.write_text(final_report, encoding="utf-8")

    # Regrava manifest uma última vez com hash do report congelado.
    hashes_v3 = {p.relative_to(ROOT).as_posix(): sha256_file(p) for p in manifest_paths}
    manifest["hashes_sha256"] = hashes_v3
    write_json(OUT_MANIFEST, manifest)

    print(f"HEADER: {TASK_ID}")
    print("STEP GATES:")
    for g in gates:
        print(f"- {'PASS' if g.passed else 'FAIL'} | {g.name} | {g.details}")
    print("RETRY LOG:")
    print("- none")
    print("ARTIFACT LINKS:")
    for p in artifacts:
        print(f"- {p.relative_to(ROOT).as_posix()}")
    overall = all(g.passed for g in gates)
    print(f"OVERALL STATUS: [[ {'PASS' if overall else 'FAIL'} ]]")


if __name__ == "__main__":
    main()
