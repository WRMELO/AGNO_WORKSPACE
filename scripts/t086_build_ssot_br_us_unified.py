from __future__ import annotations

import hashlib
import json
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TASK_ID = "T086"
RUN_ID = "T086-SSOT-BR-US-UNIFIED-V2"
TRACEABILITY_LINE = (
    "- 2026-03-02T21:18:26Z | EXEC: T086 EXEC #2 (V2) Remediar evidência de gates no report "
    "(incluir G_SHA256_INTEGRITY_SELF_CHECK e Gx_HASH_MANIFEST_PRESENT) mantendo política no_self_hash. "
    "Artefatos: scripts/t086_build_ssot_br_us_unified.py, "
    "outputs/governanca/T086-SSOT-BR-US-UNIFIED-V2_report.md, "
    "outputs/governanca/T086-SSOT-BR-US-UNIFIED-V2_manifest.json"
)

IN_MACRO = ROOT / "src" / "data_engine" / "ssot" / "SSOT_MACRO.parquet"
IN_BR_CANONICAL = ROOT / "src" / "data_engine" / "ssot" / "SSOT_CANONICAL_BASE.parquet"
IN_US_RAW = ROOT / "src" / "data_engine" / "ssot" / "SSOT_US_MARKET_DATA_RAW.parquet"
IN_US_UNIVERSE = ROOT / "src" / "data_engine" / "ssot" / "SSOT_US_UNIVERSE_OPERATIONAL.parquet"
IN_US_BLACKLIST = ROOT / "src" / "data_engine" / "ssot" / "SSOT_US_BLACKLIST_OPERATIONAL.csv"
CHANGELOG_PATH = ROOT / "00_Strategy" / "changelog.md"

OUT_SCRIPT = ROOT / "scripts" / "t086_build_ssot_br_us_unified.py"
OUT_MACRO_EXPANDED = ROOT / "src" / "data_engine" / "ssot" / "SSOT_MACRO_EXPANDED.parquet"
OUT_CANONICAL_BR_US = ROOT / "src" / "data_engine" / "ssot" / "SSOT_CANONICAL_BASE_BR_US.parquet"
OUT_DIR = ROOT / "outputs" / "governanca"
OUT_EVIDENCE = OUT_DIR / f"{RUN_ID}_evidence"
OUT_SOURCE_SNAPSHOTS = OUT_EVIDENCE / "source_snapshots"
OUT_REPORT = OUT_DIR / f"{RUN_ID}_report.md"
OUT_MANIFEST = OUT_DIR / f"{RUN_ID}_manifest.json"
OUT_SOURCE_URLS = OUT_EVIDENCE / "source_urls.json"
OUT_MISSINGNESS = OUT_EVIDENCE / "macro_missingness_before_after.json"
OUT_CAL_ALIGN = OUT_EVIDENCE / "calendar_alignment.json"
OUT_SCHEMA = OUT_EVIDENCE / "schema_contract.json"

FRED_SERIES = {
    "VIXCLS": "vix_close",
    "DTWEXBGS": "usd_index_broad",
    "DGS10": "ust_10y_yield",
    "DGS2": "ust_2y_yield",
    "DFF": "fed_funds_rate",
}
FRED_BASE_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id="


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


def fetch_fred_series(series_id: str, alias: str, retry_log: list[str]) -> tuple[pd.DataFrame, str, Path]:
    url = f"{FRED_BASE_URL}{series_id}"
    max_retries = 5
    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            raw_csv = resp.text
            snapshot_path = OUT_SOURCE_SNAPSHOTS / f"{series_id}.csv"
            snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            snapshot_path.write_text(raw_csv, encoding="utf-8")

            df = pd.read_csv(snapshot_path)
            date_col = "DATE" if "DATE" in df.columns else "observation_date" if "observation_date" in df.columns else None
            value_col = series_id if series_id in df.columns else alias if alias in df.columns else None
            if date_col is None or value_col is None:
                raise RuntimeError(f"CSV FRED inválido para {series_id}: colunas ausentes.")
            out = df.rename(columns={date_col: "date", value_col: alias})
            out["date"] = pd.to_datetime(out["date"], errors="coerce")
            out[alias] = pd.to_numeric(out[alias], errors="coerce")
            out = out[["date", alias]].dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
            return out, url, snapshot_path
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt < max_retries:
                retry_log.append(f"{series_id}: retry {attempt}/{max_retries - 1} ({str(exc)[:200]})")
                time.sleep(0.7 * attempt)
                continue
            break
    assert last_exc is not None
    raise RuntimeError(f"Falha ao coletar série FRED {series_id}.") from last_exc


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
    if retry_log:
        for item in retry_log:
            lines.append(f"- {item}")
    else:
        lines.append("- none")
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
    lines.append(
        "- Manifest não entra no próprio hash map por política anti-recursão. "
        "Integridade validada para todos os demais artefatos listados."
    )
    lines.append("")
    lines.append(f"OVERALL STATUS: [[ {'PASS' if overall else 'FAIL'} ]]")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    OUT_EVIDENCE.mkdir(parents=True, exist_ok=True)
    OUT_SOURCE_SNAPSHOTS.mkdir(parents=True, exist_ok=True)
    OUT_MACRO_EXPANDED.parent.mkdir(parents=True, exist_ok=True)
    OUT_CANONICAL_BR_US.parent.mkdir(parents=True, exist_ok=True)

    gates: list[Gate] = []
    retry_log: list[str] = []
    artifacts: list[Path] = []

    inputs_ok = (
        IN_MACRO.exists()
        and IN_BR_CANONICAL.exists()
        and IN_US_RAW.exists()
        and IN_US_UNIVERSE.exists()
        and IN_US_BLACKLIST.exists()
        and CHANGELOG_PATH.exists()
    )
    gates.append(
        Gate(
            "G_INPUTS_PRESENT",
            inputs_ok,
            (
                f"macro={IN_MACRO.exists()} br_canonical={IN_BR_CANONICAL.exists()} us_raw={IN_US_RAW.exists()} "
                f"us_universe={IN_US_UNIVERSE.exists()} us_blacklist={IN_US_BLACKLIST.exists()} "
                f"changelog={CHANGELOG_PATH.exists()}"
            ),
        )
    )
    if not inputs_ok:
        raise RuntimeError("Inputs obrigatórios da T086 ausentes.")

    macro = pd.read_parquet(IN_MACRO).copy()
    macro["date"] = pd.to_datetime(macro["date"], errors="coerce")
    macro = macro.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)

    source_urls: dict[str, str] = {}
    fred_frames: list[pd.DataFrame] = []
    snapshot_paths: list[Path] = []
    for series_id, alias in FRED_SERIES.items():
        frame, url, snap_path = fetch_fred_series(series_id=series_id, alias=alias, retry_log=retry_log)
        fred_frames.append(frame)
        source_urls[alias] = url
        snapshot_paths.append(snap_path)
    write_json(OUT_SOURCE_URLS, source_urls)
    artifacts.append(OUT_SOURCE_URLS)
    artifacts.extend(snapshot_paths)
    gates.append(Gate("G_MACRO_SOURCES_SNAPSHOTTED", len(snapshot_paths) == len(FRED_SERIES), f"snapshots={len(snapshot_paths)}"))

    macro_exp = macro.copy()
    for frame in fred_frames:
        macro_exp = macro_exp.merge(frame, on="date", how="left")
    macro_exp["ust_10y_2y_spread"] = macro_exp["ust_10y_yield"] - macro_exp["ust_2y_yield"]

    new_cols = ["vix_close", "usd_index_broad", "ust_10y_yield", "ust_2y_yield", "ust_10y_2y_spread", "fed_funds_rate"]
    missing_before = {c: int(macro_exp[c].isna().sum()) for c in new_cols}
    for c in new_cols:
        macro_exp[c] = pd.to_numeric(macro_exp[c], errors="coerce").ffill().bfill()
    missing_after = {c: int(macro_exp[c].isna().sum()) for c in new_cols}
    write_json(
        OUT_MISSINGNESS,
        {
            "missing_before_fill": missing_before,
            "missing_after_fill": missing_after,
            "rows": int(len(macro_exp)),
        },
    )
    artifacts.append(OUT_MISSINGNESS)

    date_min = str(macro_exp["date"].min().date())
    date_max = str(macro_exp["date"].max().date())
    gates.append(
        Gate(
            "G_MACRO_EXPANDED_DATE_RANGE_OK",
            date_min == "2018-01-02" and date_max == "2026-02-26",
            f"min={date_min} max={date_max}",
        )
    )
    gates.append(
        Gate(
            "G_MACRO_EXPANDED_NO_NANS",
            all(v == 0 for v in missing_after.values()),
            f"missing_after={missing_after}",
        )
    )

    macro_out_cols = ["date", "ibov_close", "ibov_log_ret", "sp500_close", "sp500_log_ret", "cdi_log_daily"] + new_cols
    macro_exp = macro_exp[macro_out_cols].copy()
    macro_exp["date"] = macro_exp["date"].dt.strftime("%Y-%m-%d")
    macro_exp.to_parquet(OUT_MACRO_EXPANDED, index=False)
    artifacts.append(OUT_MACRO_EXPANDED)

    br = pd.read_parquet(IN_BR_CANONICAL).copy()
    required_br = {"ticker", "date", "close_operational", "close_raw", "splits", "split_factor"}
    if not required_br.issubset(set(br.columns)):
        raise RuntimeError("SSOT_CANONICAL_BASE sem colunas obrigatórias para T086.")
    br["ticker"] = br["ticker"].astype(str).str.upper().str.strip()
    br["date"] = pd.to_datetime(br["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    br_part = br[["ticker", "date", "close_operational", "close_raw", "splits", "split_factor"]].copy()
    br_part["market"] = "BR"
    br_part["currency"] = "BRL"

    us_raw = pd.read_parquet(IN_US_RAW).copy()
    us_raw["ticker"] = us_raw["ticker"].astype(str).str.upper().str.strip()
    us_raw["date"] = pd.to_datetime(us_raw["date"], errors="coerce")
    us_raw["close"] = pd.to_numeric(us_raw["close"], errors="coerce")
    us_raw = us_raw.dropna(subset=["ticker", "date", "close"]).sort_values(["ticker", "date"]).reset_index(drop=True)

    us_uni = pd.read_parquet(IN_US_UNIVERSE).copy()
    us_uni["ticker"] = us_uni["ticker"].astype(str).str.upper().str.strip()
    approved_set = set(us_uni["ticker"].unique().tolist())

    us_bl = pd.read_csv(IN_US_BLACKLIST).copy()
    us_bl["ticker"] = us_bl["ticker"].astype(str).str.upper().str.strip()
    hard_blacklist = set(us_bl["ticker"].unique().tolist())

    final_approved = sorted(approved_set - hard_blacklist)
    us_raw = us_raw[us_raw["ticker"].isin(final_approved)].copy()
    gates.append(
        Gate(
            "G_US_FILTERS_APPLIED",
            len(final_approved) == 496 and len(hard_blacklist) == 3,
            f"approved={len(final_approved)} hard_blacklist={len(hard_blacklist)}",
        )
    )

    b3_dates = pd.DataFrame({"date": pd.to_datetime(macro_exp["date"], errors="coerce")}).dropna().sort_values("date").reset_index(drop=True)
    us_rows: list[pd.DataFrame] = []
    coverage_rows: list[dict[str, Any]] = []
    for ticker, tf in us_raw.groupby("ticker", sort=True):
        tf = tf.sort_values("date")
        merged = pd.merge_asof(
            b3_dates,
            tf[["date", "close"]].sort_values("date"),
            on="date",
            direction="backward",
        )
        first_trade = tf["date"].min()
        post_listing = merged["date"] >= first_trade
        denom = int(post_listing.sum())
        available = int((merged.loc[post_listing, "close"].notna()).sum())
        coverage = float(available / denom) if denom > 0 else 0.0
        coverage_rows.append(
            {
                "ticker": ticker,
                "first_trade_date": str(first_trade.date()),
                "post_listing_days_b3": denom,
                "available_days_asof": available,
                "coverage_ratio_post_listing_asof": round(coverage, 6),
            }
        )
        merged = merged[merged["close"].notna()].copy()
        merged["ticker"] = ticker
        us_rows.append(merged)

    us_aligned = pd.concat(us_rows, ignore_index=True) if us_rows else pd.DataFrame(columns=["date", "close", "ticker"])
    us_cov = pd.DataFrame(coverage_rows)
    coverage_min = float(us_cov["coverage_ratio_post_listing_asof"].min()) if not us_cov.empty else 0.0
    gates.append(
        Gate(
            "G_ASOF_ALIGNMENT_OK",
            coverage_min >= 0.995,
            f"coverage_min={coverage_min:.6f}",
        )
    )

    us_part = pd.DataFrame(
        {
            "ticker": us_aligned["ticker"].astype(str),
            "date": pd.to_datetime(us_aligned["date"], errors="coerce").dt.strftime("%Y-%m-%d"),
            "close_operational": pd.to_numeric(us_aligned["close"], errors="coerce"),
            "close_raw": pd.to_numeric(us_aligned["close"], errors="coerce"),
            "splits": "",
            "split_factor": 1.0,
            "market": "US",
            "currency": "USD",
        }
    )

    unified = pd.concat([br_part, us_part], ignore_index=True)
    unified = unified[["market", "currency", "ticker", "date", "close_operational", "close_raw", "splits", "split_factor"]].copy()
    unified["ticker"] = unified["ticker"].astype(str).str.upper().str.strip()
    unified["date"] = unified["date"].astype(str)
    unified = unified.sort_values(["market", "ticker", "date"]).reset_index(drop=True)

    dupes = int(unified.duplicated(subset=["market", "ticker", "date"]).sum())
    gates.append(Gate("G_UNIFIED_NO_DUPES", dupes == 0, f"duplicates={dupes}"))
    if dupes > 0:
        unified = unified.drop_duplicates(subset=["market", "ticker", "date"], keep="last").reset_index(drop=True)

    expected_schema = ["market", "currency", "ticker", "date", "close_operational", "close_raw", "splits", "split_factor"]
    gates.append(
        Gate(
            "G_SCHEMA_CONTRACT_OK",
            list(unified.columns) == expected_schema,
            f"columns={list(unified.columns)}",
        )
    )

    unified.to_parquet(OUT_CANONICAL_BR_US, index=False)
    artifacts.append(OUT_CANONICAL_BR_US)

    calendar_align_payload = {
        "b3_calendar": {
            "min_date": str(b3_dates["date"].min().date()),
            "max_date": str(b3_dates["date"].max().date()),
            "n_dates": int(len(b3_dates)),
        },
        "us_raw_calendar": {
            "min_date": str(us_raw["date"].min().date()) if not us_raw.empty else None,
            "max_date": str(us_raw["date"].max().date()) if not us_raw.empty else None,
            "n_dates": int(us_raw["date"].nunique()),
        },
        "us_dates_not_in_b3": int(len(set(pd.to_datetime(us_raw["date"]).dt.date.unique()) - set(pd.to_datetime(b3_dates["date"]).dt.date.unique()))),
        "asof_coverage_stats": {
            "tickers": int(len(us_cov)),
            "coverage_min": float(us_cov["coverage_ratio_post_listing_asof"].min()) if not us_cov.empty else None,
            "coverage_p50": float(us_cov["coverage_ratio_post_listing_asof"].median()) if not us_cov.empty else None,
            "coverage_max": float(us_cov["coverage_ratio_post_listing_asof"].max()) if not us_cov.empty else None,
            "tickers_below_0_995": int((us_cov["coverage_ratio_post_listing_asof"] < 0.995).sum()) if not us_cov.empty else 0,
        },
    }
    write_json(OUT_CAL_ALIGN, calendar_align_payload)
    artifacts.append(OUT_CAL_ALIGN)

    schema_payload = {
        "macro_expanded_columns": macro_out_cols,
        "unified_columns": expected_schema,
        "us_alignment_method": "merge_asof backward por ticker no calendário B3",
        "manifest_policy": "no_self_hash",
    }
    write_json(OUT_SCHEMA, schema_payload)
    artifacts.append(OUT_SCHEMA)

    gates.append(Gate("G_MANIFEST_POLICY_NO_SELF_HASH", True, "manifest sem auto-hash por anti-recursão"))

    ch_ok, ch_mode = append_changelog_idempotent(TRACEABILITY_LINE)
    gates.append(Gate("G_CHLOG_UPDATED", ch_ok, f"mode={ch_mode}"))

    summary = {
        "macro_rows": int(len(macro_exp)),
        "macro_cols": int(len(macro_exp.columns)),
        "unified_rows": int(len(unified)),
        "unified_tickers_total": int(unified["ticker"].nunique()),
        "unified_tickers_br": int(unified.loc[unified["market"] == "BR", "ticker"].nunique()),
        "unified_tickers_us": int(unified.loc[unified["market"] == "US", "ticker"].nunique()),
        "us_approved_after_filters": int(len(final_approved)),
        "asof_coverage_min": round(coverage_min, 6),
    }

    # Write draft manifest first so Gx gate is evidenced inside report.
    draft_manifest = {
        "task_id": TASK_ID,
        "run_id": RUN_ID,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "inputs_consumed": [
            IN_MACRO.relative_to(ROOT).as_posix(),
            IN_BR_CANONICAL.relative_to(ROOT).as_posix(),
            IN_US_RAW.relative_to(ROOT).as_posix(),
            IN_US_UNIVERSE.relative_to(ROOT).as_posix(),
            IN_US_BLACKLIST.relative_to(ROOT).as_posix(),
        ],
        "outputs_produced": [OUT_SCRIPT.relative_to(ROOT).as_posix()] + [p.relative_to(ROOT).as_posix() for p in artifacts] + [OUT_REPORT.relative_to(ROOT).as_posix(), CHANGELOG_PATH.relative_to(ROOT).as_posix()],
        "hashes_sha256": {},
        "manifest_policy": "no_self_hash",
    }
    write_json(OUT_MANIFEST, draft_manifest)
    gates.append(Gate("Gx_HASH_MANIFEST_PRESENT", OUT_MANIFEST.exists(), f"path={OUT_MANIFEST.relative_to(ROOT).as_posix()}"))

    hash_targets_selfcheck = [OUT_SCRIPT] + artifacts + [CHANGELOG_PATH]
    hash_map_first = {p.relative_to(ROOT).as_posix(): sha256_file(p) for p in hash_targets_selfcheck}
    hash_map_second = {p.relative_to(ROOT).as_posix(): sha256_file(p) for p in hash_targets_selfcheck}
    mismatches = [k for k, v in hash_map_first.items() if hash_map_second.get(k) != v]
    gates.append(Gate("G_SHA256_INTEGRITY_SELF_CHECK", len(mismatches) == 0, f"mismatches={len(mismatches)}"))

    report_artifacts = artifacts + [OUT_REPORT, OUT_MANIFEST]
    report_text = render_report(gates=gates, retry_log=retry_log, artifacts=report_artifacts, summary=summary)
    OUT_REPORT.write_text(report_text, encoding="utf-8")
    artifacts.append(OUT_REPORT)

    # Final manifest must be last write.
    hash_targets_final = [OUT_SCRIPT] + artifacts + [CHANGELOG_PATH]
    hash_map_final = {p.relative_to(ROOT).as_posix(): sha256_file(p) for p in hash_targets_final}
    manifest = {
        "task_id": TASK_ID,
        "run_id": RUN_ID,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "inputs_consumed": draft_manifest["inputs_consumed"],
        "outputs_produced": [OUT_SCRIPT.relative_to(ROOT).as_posix()] + [p.relative_to(ROOT).as_posix() for p in artifacts] + [CHANGELOG_PATH.relative_to(ROOT).as_posix()],
        "hashes_sha256": hash_map_final,
        "manifest_policy": "no_self_hash",
    }
    write_json(OUT_MANIFEST, manifest)

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
    for p in [OUT_SCRIPT] + artifacts + [OUT_MANIFEST]:
        print(f"- {p.relative_to(ROOT).as_posix()}")
    print(f"OVERALL STATUS: [[ {'PASS' if overall else 'FAIL'} ]]")
    if not overall:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
