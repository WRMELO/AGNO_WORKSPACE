from __future__ import annotations

import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TASK_ID = "T102"
RUN_ID = "T102-SSOT-BR-EXPANDED-V1"
TRACEABILITY_LINE = (
    "- 2026-03-03T22:10:00Z | EXEC: T102 SSOT BR expandido (BR + BDR/US_DIRECT em BRL) materializado. "
    "Artefatos: scripts/t102_build_ssot_br_expanded_brl.py; "
    "src/data_engine/ssot/SSOT_CANONICAL_BASE_BR_EXPANDED.parquet; "
    "src/data_engine/ssot/SSOT_UNIVERSE_OPERATIONAL_EXPANDED.parquet; "
    "outputs/governanca/T102-SSOT-BR-EXPANDED-V1_{report,manifest}.md"
)

IN_CANONICAL_BR = ROOT / "src" / "data_engine" / "ssot" / "SSOT_CANONICAL_BASE.parquet"
IN_BDR_SYNTH = ROOT / "src" / "data_engine" / "ssot" / "SSOT_BDR_SYNTH_MARKET_DATA_RAW.parquet"
IN_MACRO = ROOT / "src" / "data_engine" / "ssot" / "SSOT_MACRO.parquet"
CHANGELOG_PATH = ROOT / "00_Strategy" / "changelog.md"

OUT_SCRIPT = ROOT / "scripts" / "t102_build_ssot_br_expanded_brl.py"
OUT_CANONICAL_EXPANDED = ROOT / "src" / "data_engine" / "ssot" / "SSOT_CANONICAL_BASE_BR_EXPANDED.parquet"
OUT_UNIVERSE_EXPANDED = ROOT / "src" / "data_engine" / "ssot" / "SSOT_UNIVERSE_OPERATIONAL_EXPANDED.parquet"

OUT_DIR = ROOT / "outputs" / "governanca"
OUT_EVIDENCE = OUT_DIR / f"{RUN_ID}_evidence"
OUT_REPORT = OUT_DIR / f"{RUN_ID}_report.md"
OUT_MANIFEST = OUT_DIR / f"{RUN_ID}_manifest.json"
OUT_SCHEMA = OUT_EVIDENCE / "schema_contract.json"
OUT_COUNTS = OUT_EVIDENCE / "universe_counts.json"

REF_WINDOW_K = 60
SUBGROUP_N = 4
A2_N4 = 0.729
D4_N4 = 2.282
E2_IMR_N2 = 2.66
D4_IMR_N2 = 3.267


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


def bdr_sector_for_ticker(ticker: str) -> str:
    if re.search(r"(34|35|39)$", ticker):
        return "BDR"
    return "US_DIRECT"


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
    lines.append("- Manifest segue política no_self_hash (sem auto-referência).")
    lines.append("")
    lines.append(f"OVERALL STATUS: [[ {'PASS' if overall else 'FAIL'} ]]")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    OUT_EVIDENCE.mkdir(parents=True, exist_ok=True)
    OUT_CANONICAL_EXPANDED.parent.mkdir(parents=True, exist_ok=True)
    OUT_UNIVERSE_EXPANDED.parent.mkdir(parents=True, exist_ok=True)

    gates: list[Gate] = []
    retry_log: list[str] = []
    artifacts: list[Path] = []

    inputs_ok = (
        IN_CANONICAL_BR.exists()
        and IN_BDR_SYNTH.exists()
        and IN_MACRO.exists()
        and CHANGELOG_PATH.exists()
    )
    gates.append(
        Gate(
            "G_INPUTS_PRESENT",
            inputs_ok,
            (
                f"canonical_br={IN_CANONICAL_BR.exists()} bdr_synth={IN_BDR_SYNTH.exists()} "
                f"macro={IN_MACRO.exists()} changelog={CHANGELOG_PATH.exists()}"
            ),
        )
    )
    if not inputs_ok:
        raise RuntimeError("Inputs obrigatórios da T102 ausentes.")

    br = pd.read_parquet(IN_CANONICAL_BR).copy()
    canonical_cols = list(br.columns)

    macro = pd.read_parquet(IN_MACRO, columns=["date", "cdi_log_daily"]).copy()
    macro["date"] = pd.to_datetime(macro["date"], errors="coerce")
    macro["cdi_log_daily"] = pd.to_numeric(macro["cdi_log_daily"], errors="coerce")
    macro = macro.dropna(subset=["date"]).drop_duplicates(subset=["date"], keep="last")

    bdr = pd.read_parquet(IN_BDR_SYNTH).copy()
    bdr["ticker"] = bdr["ticker"].astype(str).str.upper().str.strip()
    bdr["date"] = pd.to_datetime(bdr["date"], errors="coerce")
    bdr["close"] = pd.to_numeric(bdr["close"], errors="coerce")
    bdr = bdr.dropna(subset=["ticker", "date", "close"]).sort_values(["ticker", "date"]).reset_index(drop=True)

    bdr["close_operational"] = bdr["close"]
    bdr["close_raw"] = bdr["close"]
    bdr["log_ret_nominal"] = np.log(bdr["close_operational"] / bdr.groupby("ticker")["close_operational"].shift(1))
    bdr["log_ret_nominal"] = bdr["log_ret_nominal"].replace([np.inf, -np.inf], np.nan)

    bdr = bdr.merge(macro, on="date", how="left")
    bdr = bdr.sort_values(["ticker", "date"]).reset_index(drop=True)
    bdr["X_real"] = bdr["log_ret_nominal"] - bdr["cdi_log_daily"]
    bdr["i_value"] = bdr["X_real"]
    bdr["mr_value"] = (bdr["i_value"] - bdr.groupby("ticker")["i_value"].shift(1)).abs()

    grp = bdr.groupby("ticker", group_keys=False)
    bdr["xbar_value"] = grp["i_value"].transform(lambda s: s.rolling(SUBGROUP_N, min_periods=SUBGROUP_N).mean())
    roll_max = grp["i_value"].transform(lambda s: s.rolling(SUBGROUP_N, min_periods=SUBGROUP_N).max())
    roll_min = grp["i_value"].transform(lambda s: s.rolling(SUBGROUP_N, min_periods=SUBGROUP_N).min())
    bdr["r_value"] = roll_max - roll_min

    bdr["center_line"] = grp["i_value"].transform(lambda s: s.rolling(REF_WINDOW_K, min_periods=REF_WINDOW_K).mean().shift(1))
    bdr["mr_bar"] = grp["mr_value"].transform(lambda s: s.rolling(REF_WINDOW_K, min_periods=REF_WINDOW_K).mean().shift(1))
    bdr["r_bar"] = grp["r_value"].transform(lambda s: s.rolling(REF_WINDOW_K, min_periods=REF_WINDOW_K).mean().shift(1))

    bdr["i_ucl"] = bdr["center_line"] + (E2_IMR_N2 * bdr["mr_bar"])
    bdr["i_lcl"] = bdr["center_line"] - (E2_IMR_N2 * bdr["mr_bar"])
    bdr["mr_ucl"] = D4_IMR_N2 * bdr["mr_bar"]
    bdr["xbar_ucl"] = bdr["center_line"] + (A2_N4 * bdr["r_bar"])
    bdr["xbar_lcl"] = bdr["center_line"] - (A2_N4 * bdr["r_bar"])
    bdr["r_ucl"] = D4_N4 * bdr["r_bar"]
    bdr["sector"] = bdr["ticker"].map(bdr_sector_for_ticker)
    bdr["splits"] = pd.to_numeric(bdr.get("splits", 0.0), errors="coerce").fillna(0.0)
    bdr["split_factor"] = pd.to_numeric(bdr.get("split_factor", 1.0), errors="coerce").fillna(1.0)
    bdr["date"] = bdr["date"].dt.strftime("%Y-%m-%d")

    bdr_out = pd.DataFrame(index=bdr.index)
    for col in canonical_cols:
        if col in bdr.columns:
            bdr_out[col] = bdr[col]
        else:
            bdr_out[col] = np.nan

    br["ticker"] = br["ticker"].astype(str).str.upper().str.strip()
    br["date"] = pd.to_datetime(br["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    br_out = br[canonical_cols].copy()

    # Harmoniza tipos com o canônico BR para evitar erro de parquet.
    if "splits" in bdr_out.columns:
        bdr_out["splits"] = ""
    if "split_factor" in bdr_out.columns:
        bdr_out["split_factor"] = pd.to_numeric(bdr_out["split_factor"], errors="coerce")

    expanded = pd.concat([br_out, bdr_out], ignore_index=True)
    expanded["ticker"] = expanded["ticker"].astype(str).str.upper().str.strip()
    expanded["date"] = expanded["date"].astype(str)
    expanded["close_operational"] = pd.to_numeric(expanded["close_operational"], errors="coerce")
    expanded["close_raw"] = pd.to_numeric(expanded["close_raw"], errors="coerce")
    expanded.loc[expanded["close_operational"] <= 0, "close_operational"] = np.nan
    expanded.loc[expanded["close_raw"] <= 0, "close_raw"] = np.nan
    expanded["close_operational"] = expanded["close_operational"].fillna(expanded["close_raw"])
    dropped_invalid_close = int(expanded["close_operational"].isna().sum())
    if dropped_invalid_close > 0:
        expanded = expanded.dropna(subset=["close_operational"]).copy()
    expanded = expanded.sort_values(["ticker", "date"]).reset_index(drop=True)

    dupes = int(expanded.duplicated(subset=["ticker", "date"]).sum())
    gates.append(Gate("G_NO_DUPES_TICKER_DATE", dupes == 0, f"duplicates={dupes}"))

    schema_ok = list(expanded.columns) == canonical_cols
    gates.append(Gate("G_SCHEMA_MATCH_CANONICAL", schema_ok, f"columns_match={schema_ok}"))

    close_nan = int(pd.to_numeric(expanded["close_operational"], errors="coerce").isna().sum())
    gates.append(Gate("G_NO_NAN_CLOSE", close_nan == 0, f"nan_close_operational={close_nan}"))

    min_date = str(pd.to_datetime(expanded["date"], errors="coerce").min().date())
    max_date = str(pd.to_datetime(expanded["date"], errors="coerce").max().date())
    gates.append(
        Gate(
            "G_DATE_RANGE_OK",
            min_date == "2018-01-02" and max_date == "2026-02-26",
            f"min={min_date} max={max_date}",
        )
    )

    ticker_count_total = int(expanded["ticker"].nunique())
    gates.append(Gate("G_TICKER_COUNT_OK", ticker_count_total >= 1150, f"ticker_count={ticker_count_total}"))

    expanded.to_parquet(OUT_CANONICAL_EXPANDED, index=False)
    artifacts.append(OUT_CANONICAL_EXPANDED)

    universe = pd.DataFrame({"ticker": sorted(expanded["ticker"].dropna().astype(str).unique().tolist())})
    universe.to_parquet(OUT_UNIVERSE_EXPANDED, index=False)
    artifacts.append(OUT_UNIVERSE_EXPANDED)

    br_tickers = set(br_out["ticker"].dropna().astype(str).tolist())
    bdr_tickers = set(bdr_out["ticker"].dropna().astype(str).tolist())
    overlap_tickers = br_tickers.intersection(bdr_tickers)
    counts_payload = {
        "n_tickers_br": int(len(br_tickers)),
        "n_tickers_bdr": int(len(bdr_tickers)),
        "n_tickers_overlap": int(len(overlap_tickers)),
        "n_tickers_total": int(ticker_count_total),
    }
    write_json(OUT_COUNTS, counts_payload)
    artifacts.append(OUT_COUNTS)

    schema_payload = {
        "canonical_columns": canonical_cols,
        "expanded_columns": list(expanded.columns),
        "date_min": min_date,
        "date_max": max_date,
        "ref_window_k": REF_WINDOW_K,
        "subgroup_n": SUBGROUP_N,
        "spc_constants": {
            "A2_N4": A2_N4,
            "D4_N4": D4_N4,
            "E2_IMR_N2": E2_IMR_N2,
            "D4_IMR_N2": D4_IMR_N2,
        },
    }
    write_json(OUT_SCHEMA, schema_payload)
    artifacts.append(OUT_SCHEMA)

    ch_ok, ch_mode = append_changelog_idempotent(TRACEABILITY_LINE)
    gates.append(Gate("G_CHLOG_UPDATED", ch_ok, f"mode={ch_mode}"))

    summary = {
        "rows_br": int(len(br_out)),
        "rows_bdr": int(len(bdr_out)),
        "rows_total": int(len(expanded)),
        "rows_dropped_invalid_close": int(dropped_invalid_close),
        "tickers_total": ticker_count_total,
        "date_min": min_date,
        "date_max": max_date,
    }

    draft_manifest = {
        "task_id": TASK_ID,
        "run_id": RUN_ID,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "inputs_consumed": [
            IN_CANONICAL_BR.relative_to(ROOT).as_posix(),
            IN_BDR_SYNTH.relative_to(ROOT).as_posix(),
            IN_MACRO.relative_to(ROOT).as_posix(),
        ],
        "outputs_produced": [OUT_SCRIPT.relative_to(ROOT).as_posix()]
        + [p.relative_to(ROOT).as_posix() for p in artifacts]
        + [OUT_REPORT.relative_to(ROOT).as_posix(), CHANGELOG_PATH.relative_to(ROOT).as_posix()],
        "hashes_sha256": {},
        "manifest_policy": "no_self_hash",
    }
    write_json(OUT_MANIFEST, draft_manifest)
    gates.append(Gate("Gx_HASH_MANIFEST_PRESENT", OUT_MANIFEST.exists(), f"path={OUT_MANIFEST.relative_to(ROOT).as_posix()}"))

    hash_targets_selfcheck = [OUT_SCRIPT] + artifacts + [CHANGELOG_PATH]
    hash_first = {p.relative_to(ROOT).as_posix(): sha256_file(p) for p in hash_targets_selfcheck}
    hash_second = {p.relative_to(ROOT).as_posix(): sha256_file(p) for p in hash_targets_selfcheck}
    mismatches = [k for k, v in hash_first.items() if hash_second.get(k) != v]
    gates.append(Gate("G_SHA256_INTEGRITY_SELF_CHECK", len(mismatches) == 0, f"mismatches={len(mismatches)}"))

    report_artifacts = artifacts + [OUT_REPORT, OUT_MANIFEST]
    report_text = render_report(gates=gates, retry_log=retry_log, artifacts=report_artifacts, summary=summary)
    OUT_REPORT.write_text(report_text, encoding="utf-8")
    artifacts.append(OUT_REPORT)

    hash_targets_final = [OUT_SCRIPT] + artifacts + [CHANGELOG_PATH]
    hash_map_final = {p.relative_to(ROOT).as_posix(): sha256_file(p) for p in hash_targets_final}
    final_manifest = {
        "task_id": TASK_ID,
        "run_id": RUN_ID,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "inputs_consumed": draft_manifest["inputs_consumed"],
        "outputs_produced": [OUT_SCRIPT.relative_to(ROOT).as_posix()]
        + [p.relative_to(ROOT).as_posix() for p in artifacts]
        + [CHANGELOG_PATH.relative_to(ROOT).as_posix()],
        "hashes_sha256": hash_map_final,
        "manifest_policy": "no_self_hash",
    }
    write_json(OUT_MANIFEST, final_manifest)

    overall = all(g.passed for g in gates)
    print(f"HEADER: {TASK_ID}")
    print("STEP GATES:")
    for g in gates:
        print(f"- {'PASS' if g.passed else 'FAIL'} | {g.name} | {g.details}")
    print("RETRY LOG:")
    if retry_log:
        for item in retry_log:
            print(f"- {item}")
    else:
        print("- none")
    print("ARTIFACT LINKS:")
    for p in [OUT_SCRIPT] + artifacts + [OUT_MANIFEST]:
        print(f"- {p.relative_to(ROOT).as_posix()}")
    print(f"OVERALL STATUS: [[ {'PASS' if overall else 'FAIL'} ]]")
    if not overall:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
