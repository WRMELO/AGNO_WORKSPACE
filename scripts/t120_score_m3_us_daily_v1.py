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

TASK_ID = "T120"
RUN_ID = "T120-M3-US-SCORES-V1"
LOOKBACK = 62
TRACEABILITY_LINE = (
    "- 2026-03-04T15:02:55Z | EXEC: T120 PASS/FAIL. Artefatos: "
    "scripts/t120_score_m3_us_daily_v1.py; "
    "src/data_engine/features/T120_M3_US_SCORES_DAILY.parquet; "
    "outputs/governanca/T120-M3-US-SCORES-V1_{report,manifest}.md"
)

IN_SSOT_US = ROOT / "src" / "data_engine" / "ssot" / "SSOT_CANONICAL_BASE_US.parquet"
IN_UNIVERSE = ROOT / "src" / "data_engine" / "ssot" / "SSOT_US_UNIVERSE_OPERATIONAL_PHASE10.parquet"
CHANGELOG_PATH = ROOT / "00_Strategy" / "changelog.md"

OUT_SCRIPT = ROOT / "scripts" / "t120_score_m3_us_daily_v1.py"
OUT_SCORES = ROOT / "src" / "data_engine" / "features" / "T120_M3_US_SCORES_DAILY.parquet"
OUT_DIR = ROOT / "outputs" / "governanca"
OUT_EVIDENCE = OUT_DIR / f"{RUN_ID}_evidence"
OUT_REPORT = OUT_DIR / f"{RUN_ID}_report.md"
OUT_MANIFEST = OUT_DIR / f"{RUN_ID}_manifest.json"
OUT_SCHEMA = OUT_EVIDENCE / "schema_contract.json"
OUT_COVERAGE = OUT_EVIDENCE / "universe_coverage.json"
OUT_EXTREMES = OUT_EVIDENCE / "extreme_logret_rows.csv"
OUT_SUMMARY = OUT_EVIDENCE / "summary_stats.json"


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


def zscore_cross_section(values: pd.Series) -> pd.Series:
    x = pd.to_numeric(values, errors="coerce").astype(float)
    mu = float(x.mean())
    sd = float(x.std(ddof=0))
    if not np.isfinite(sd) or sd <= 0:
        return pd.Series(np.zeros(len(x), dtype=float), index=x.index)
    return (x - mu) / sd


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


def compute_exec_rank(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["m3_rank_us_exec"] = np.nan
    for d, g in out.groupby("date", sort=True):
        valid = g[g["score_m3_us_exec"].notna()].copy()
        if valid.empty:
            continue
        valid = valid.sort_values(["score_m3_us_exec", "ticker"], ascending=[False, True]).copy()
        valid["m3_rank_us_exec"] = np.arange(1, len(valid) + 1, dtype=int)
        out.loc[valid.index, "m3_rank_us_exec"] = valid["m3_rank_us_exec"].astype(float)
    return out


def main() -> None:
    OUT_EVIDENCE.mkdir(parents=True, exist_ok=True)
    OUT_SCORES.parent.mkdir(parents=True, exist_ok=True)

    gates: list[Gate] = []
    retry_log: list[str] = []
    artifacts = [
        OUT_SCRIPT,
        OUT_SCORES,
        OUT_SCHEMA,
        OUT_COVERAGE,
        OUT_EXTREMES,
        OUT_SUMMARY,
        OUT_REPORT,
        OUT_MANIFEST,
    ]

    inputs_ok = IN_SSOT_US.exists() and IN_UNIVERSE.exists() and CHANGELOG_PATH.exists()
    gates.append(
        Gate(
            "G_INPUTS_PRESENT",
            inputs_ok,
            f"ssot_us={IN_SSOT_US.exists()} universe={IN_UNIVERSE.exists()} changelog={CHANGELOG_PATH.exists()}",
        )
    )
    if not inputs_ok:
        raise RuntimeError("Inputs obrigatórios ausentes para T120.")

    ssot = pd.read_parquet(IN_SSOT_US, columns=["date", "ticker", "close_operational"]).copy()
    ssot["date"] = pd.to_datetime(ssot["date"], errors="coerce")
    ssot["ticker"] = ssot["ticker"].astype(str).str.upper().str.strip()
    ssot["close_operational"] = pd.to_numeric(ssot["close_operational"], errors="coerce")
    ssot = ssot.dropna(subset=["date", "ticker", "close_operational"]).copy()
    ssot = ssot[ssot["close_operational"] > 0].copy()

    universe = pd.read_parquet(IN_UNIVERSE, columns=["ticker"]).copy()
    universe["ticker"] = universe["ticker"].astype(str).str.upper().str.strip()
    tickers = sorted(set(universe["ticker"].tolist()))
    gates.append(Gate("G_UNIVERSE_496", len(tickers) == 496, f"universe_tickers={len(tickers)}"))

    ssot = ssot[ssot["ticker"].isin(tickers)].copy()

    px_wide = (
        ssot.pivot_table(index="date", columns="ticker", values="close_operational", aggfunc="first")
        .sort_index()
        .ffill()
    )

    logret = np.log(px_wide / px_wide.shift(1))
    extreme_mask = logret.abs() > 1.0
    extreme_rows = (
        logret.where(extreme_mask)
        .stack()
        .rename("logret_original")
        .reset_index()
        .rename(columns={"level_0": "date", "level_1": "ticker"})
    )
    if not extreme_rows.empty:
        extreme_rows["date"] = pd.to_datetime(extreme_rows["date"]).dt.strftime("%Y-%m-%d")
    extreme_rows = extreme_rows.sort_values(["ticker", "date"]).reset_index(drop=True)
    extreme_rows.to_csv(OUT_EXTREMES, index=False)

    logret_clean = logret.mask(extreme_mask, 0.0)
    max_abs_logret = float(logret_clean.abs().max().max())
    gates.append(
        Gate(
            "G_LOGRET_SANITIZED",
            bool(np.isfinite(max_abs_logret) and max_abs_logret <= 1.0),
            f"extreme_rows={len(extreme_rows)} max_abs_logret_clean={max_abs_logret:.6f}",
        )
    )

    score_m0 = logret_clean.rolling(window=LOOKBACK, min_periods=LOOKBACK).mean()
    ret_62 = logret_clean.rolling(window=LOOKBACK, min_periods=LOOKBACK).sum()
    vol_62 = logret_clean.rolling(window=LOOKBACK, min_periods=LOOKBACK).std(ddof=0)

    records: list[dict[str, Any]] = []
    for d in score_m0.index:
        m0_row = score_m0.loc[d].dropna()
        r_row = ret_62.loc[d].dropna()
        v_row = vol_62.loc[d].dropna()

        common = m0_row.index.intersection(r_row.index).intersection(v_row.index)
        if len(common) < 3:
            continue

        cs = pd.DataFrame(
            {
                "ticker": common,
                "score_m0_us": m0_row[common].values,
                "ret_62_us": r_row[common].values,
                "vol_62_us": v_row[common].values,
            }
        )
        cs["z_m0_us"] = zscore_cross_section(cs["score_m0_us"])
        cs["z_ret_us"] = zscore_cross_section(cs["ret_62_us"])
        cs["z_vol_us"] = zscore_cross_section(cs["vol_62_us"])
        cs["score_m3_us"] = cs["z_m0_us"] + cs["z_ret_us"] - cs["z_vol_us"]
        cs["date"] = pd.to_datetime(d).strftime("%Y-%m-%d")
        cs = cs.sort_values(["score_m3_us", "ticker"], ascending=[False, True]).reset_index(drop=True)
        cs["m3_rank_us"] = np.arange(1, len(cs) + 1, dtype=int)
        records.extend(cs.to_dict(orient="records"))

    scores = pd.DataFrame(records)
    if scores.empty:
        raise RuntimeError("Sem scores gerados para T120.")

    expected_cols = {
        "date",
        "ticker",
        "score_m0_us",
        "ret_62_us",
        "vol_62_us",
        "z_m0_us",
        "z_ret_us",
        "z_vol_us",
        "score_m3_us",
        "m3_rank_us",
    }
    gates.append(
        Gate(
            "G_SCORE_COLUMNS_PRESENT",
            expected_cols.issubset(set(scores.columns)),
            f"cols={len(scores.columns)} expected={len(expected_cols)}",
        )
    )

    scores = scores.sort_values(["ticker", "date"]).reset_index(drop=True)
    scores["score_m3_us_exec"] = scores.groupby("ticker", sort=False)["score_m3_us"].shift(1)
    scores = compute_exec_rank(scores)

    first_exec_non_nan = int(
        scores.groupby("ticker", sort=False)["score_m3_us_exec"].apply(lambda s: int(s.iloc[0:1].notna().sum())).sum()
    )
    gates.append(
        Gate(
            "G_ANTI_LOOKAHEAD_EXEC",
            first_exec_non_nan == 0,
            f"first_row_exec_non_nan={first_exec_non_nan}",
        )
    )

    n_tickers_scores = int(scores["ticker"].nunique())
    gates.append(Gate("G_TICKER_COUNT_OK", n_tickers_scores == 496, f"ticker_count={n_tickers_scores}"))

    date_min = str(pd.to_datetime(scores["date"]).min().date())
    date_max = str(pd.to_datetime(scores["date"]).max().date())
    gates.append(Gate("G_DATE_RANGE_NONEMPTY", date_min <= date_max, f"min={date_min} max={date_max}"))

    scores = scores[
        [
            "date",
            "ticker",
            "score_m0_us",
            "ret_62_us",
            "vol_62_us",
            "z_m0_us",
            "z_ret_us",
            "z_vol_us",
            "score_m3_us",
            "m3_rank_us",
            "score_m3_us_exec",
            "m3_rank_us_exec",
        ]
    ].copy()

    scores.to_parquet(OUT_SCORES, index=False)

    cov = (
        scores.groupby("date", as_index=False)
        .agg(
            tickers_valid_score=("score_m3_us", lambda s: int(pd.to_numeric(s, errors="coerce").notna().sum())),
            tickers_valid_exec=("score_m3_us_exec", lambda s: int(pd.to_numeric(s, errors="coerce").notna().sum())),
        )
        .sort_values("date")
        .reset_index(drop=True)
    )

    schema_contract = {
        "task_id": TASK_ID,
        "run_id": RUN_ID,
        "lookback": LOOKBACK,
        "formula": "score_m3_us = z(score_m0_us) + z(ret_62_us) - z(vol_62_us)",
        "score_definition": {
            "score_m0_us": "rolling mean of sanitized logret (62d)",
            "ret_62_us": "rolling sum of sanitized logret (62d)",
            "vol_62_us": "rolling std(ddof=0) of sanitized logret (62d)",
        },
        "anti_lookahead": "score_m3_us_exec = shift(1) by ticker",
        "sanitization_rule": "if |logret| > 1.0 then logret := 0.0 prior to rolling windows",
        "columns": {c: str(scores[c].dtype) for c in scores.columns},
    }
    write_json(OUT_SCHEMA, schema_contract)

    universe_coverage = {
        "universe_tickers_expected": 496,
        "tickers_in_scores": n_tickers_scores,
        "dates_with_scores": int(cov["date"].nunique()),
        "date_min": date_min,
        "date_max": date_max,
        "tickers_valid_score_min": int(cov["tickers_valid_score"].min()),
        "tickers_valid_score_p50": float(cov["tickers_valid_score"].median()),
        "tickers_valid_score_max": int(cov["tickers_valid_score"].max()),
        "tickers_valid_exec_min": int(cov["tickers_valid_exec"].min()),
        "tickers_valid_exec_p50": float(cov["tickers_valid_exec"].median()),
        "tickers_valid_exec_max": int(cov["tickers_valid_exec"].max()),
    }
    write_json(OUT_COVERAGE, universe_coverage)

    summary_stats = {
        "rows_scores": int(len(scores)),
        "tickers_scores": n_tickers_scores,
        "extreme_logret_rows_sanitized": int(len(extreme_rows)),
        "max_abs_logret_clean": max_abs_logret,
        "score_m3_us_min": float(pd.to_numeric(scores["score_m3_us"], errors="coerce").min()),
        "score_m3_us_max": float(pd.to_numeric(scores["score_m3_us"], errors="coerce").max()),
        "score_m3_us_exec_nan_rows": int(scores["score_m3_us_exec"].isna().sum()),
    }
    write_json(OUT_SUMMARY, summary_stats)

    ch_ok, ch_mode = append_changelog_idempotent(TRACEABILITY_LINE)
    gates.append(Gate("G_CHLOG_UPDATED", ch_ok, f"mode={ch_mode}"))

    exec_summary = {
        "rows_scores": int(len(scores)),
        "tickers": n_tickers_scores,
        "date_min": date_min,
        "date_max": date_max,
        "extreme_rows_sanitized": int(len(extreme_rows)),
        "universe_expected": 496,
    }

    # Passo 1: relatório preliminar (pré-manifest).
    OUT_REPORT.write_text(render_report(gates, retry_log, artifacts, exec_summary), encoding="utf-8")

    # Passo 2: manifest com hash do relatório preliminar.
    inputs = [IN_SSOT_US, IN_UNIVERSE, CHANGELOG_PATH]
    outputs = [OUT_SCRIPT, OUT_SCORES, OUT_REPORT, OUT_SCHEMA, OUT_COVERAGE, OUT_EXTREMES, OUT_SUMMARY]
    hashes: dict[str, str] = {}
    for p in inputs + outputs:
        if p.exists():
            hashes[p.relative_to(ROOT).as_posix()] = sha256_file(p)

    manifest = {
        "task_id": TASK_ID,
        "run_id": RUN_ID,
        "generated_at_utc": pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
        "inputs_consumed": [p.relative_to(ROOT).as_posix() for p in inputs],
        "outputs_produced": [p.relative_to(ROOT).as_posix() for p in outputs],
        "hashes_sha256": hashes,
        "policy": "no_self_hash",
    }
    write_json(OUT_MANIFEST, manifest)
    gates.append(Gate("Gx_HASH_MANIFEST_PRESENT", OUT_MANIFEST.exists(), f"path={OUT_MANIFEST.relative_to(ROOT).as_posix()}"))

    # Passo 3: valida integridade, reescreve relatório final e refaz manifest.
    mismatches = 0
    for rel_path, expected in manifest["hashes_sha256"].items():
        fp = ROOT / rel_path
        if not fp.exists() or sha256_file(fp) != expected:
            mismatches += 1
    gates.append(Gate("G_SHA256_INTEGRITY_SELF_CHECK", mismatches == 0, f"mismatches={mismatches}"))

    OUT_REPORT.write_text(render_report(gates, retry_log, artifacts, exec_summary), encoding="utf-8")

    hashes_final: dict[str, str] = {}
    for p in inputs + outputs:
        if p.exists():
            hashes_final[p.relative_to(ROOT).as_posix()] = sha256_file(p)
    manifest["hashes_sha256"] = hashes_final
    manifest["generated_at_utc"] = pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")
    write_json(OUT_MANIFEST, manifest)

    mismatches_final = 0
    for rel_path, expected in manifest["hashes_sha256"].items():
        fp = ROOT / rel_path
        if not fp.exists() or sha256_file(fp) != expected:
            mismatches_final += 1
    if mismatches_final != 0:
        raise RuntimeError(f"Integridade final falhou: mismatches={mismatches_final}")

    if not all(g.passed for g in gates):
        raise RuntimeError("Um ou mais gates falharam em T120.")


if __name__ == "__main__":
    main()
