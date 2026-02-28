#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


if not ("agno_env" in sys.prefix or ".venv" in sys.prefix):
    raise RuntimeError("FATAL: Not in agno_env!")


TASK_ID = "T063-MARKET-SLOPE-REENTRY-ABLATION-V2"
ROOT = Path("/home/wilson/AGNO_WORKSPACE")
SCRIPT_V1 = ROOT / "scripts/t063_market_slope_reentry_ablation.py"

OUT_ABLATION = ROOT / "src/data_engine/portfolio/T063_REENTRY_HYST_ABLATION_RESULTS_V2.parquet"
OUT_SELECTED_CFG = ROOT / "src/data_engine/portfolio/T063_REENTRY_SELECTED_CONFIG_V2.json"
OUT_CURVE = ROOT / "src/data_engine/portfolio/T063_PORTFOLIO_CURVE_REENTRY_FIX_V2.parquet"
OUT_LEDGER = ROOT / "src/data_engine/portfolio/T063_PORTFOLIO_LEDGER_REENTRY_FIX_V2.parquet"
OUT_SUMMARY = ROOT / "src/data_engine/portfolio/T063_BASELINE_SUMMARY_REENTRY_FIX_V2.json"

OUT_REPORT = ROOT / "outputs/governanca/T063-MARKET-SLOPE-REENTRY-ABLATION-V2_report.md"
OUT_MANIFEST = ROOT / "outputs/governanca/T063-MARKET-SLOPE-REENTRY-ABLATION-V2_manifest.json"
OUT_EVIDENCE_DIR = ROOT / "outputs/governanca/T063-MARKET-SLOPE-REENTRY-ABLATION-V2_evidence"
OUT_CANDIDATE_SET = OUT_EVIDENCE_DIR / "candidate_set.json"
OUT_SELECTION_RULE = OUT_EVIDENCE_DIR / "selection_rule.json"
OUT_FEASIBILITY = OUT_EVIDENCE_DIR / "feasibility_snapshot.json"

CHANGELOG_PATH = ROOT / "00_Strategy/changelog.md"
TRACEABILITY_LINE = "- 2026-02-28T19:51:31Z | STRATEGY: T063-MARKET-SLOPE-REENTRY-ABLATION-V2 EXEC. Artefatos: outputs/governanca/T063-MARKET-SLOPE-REENTRY-ABLATION-V2_report.md; outputs/governanca/T063-MARKET-SLOPE-REENTRY-ABLATION-V2_manifest.json; src/data_engine/portfolio/T063_REENTRY_SELECTED_CONFIG_V2.json"

BUY_TURNOVER_CAP_GRID: list[float | None] = [0.02, 0.05, 0.10, None]

# Constraints hard definidos pelo Architect
THRESHOLDS = {
    "MDD_total_min": -0.30,
    "turnover_total_total_max": 8.0,
    "reentry_subperiod_time_in_market_min": 0.05,
}


def _load_v1():
    spec = importlib.util.spec_from_file_location("t063_v1_module", SCRIPT_V1)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Nao foi possivel carregar script base: {SCRIPT_V1}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def update_changelog_one_line(line: str) -> bool:
    CHANGELOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    before = CHANGELOG_PATH.read_text(encoding="utf-8") if CHANGELOG_PATH.exists() else ""
    before_size = len(before.encode("utf-8"))
    text = before
    if text and not text.endswith("\n"):
        text += "\n"
    text += line.rstrip("\n") + "\n"
    CHANGELOG_PATH.write_text(text, encoding="utf-8")
    after_size = len(text.encode("utf-8"))
    delta = after_size - before_size
    return delta == len((line.rstrip("\n") + "\n").encode("utf-8")) and text.endswith(line.rstrip("\n") + "\n")


def main() -> int:
    print(f"HEADER: {TASK_ID}")
    print("MODEL ROUTING: PASS_MODEL_ROUTING_UNVERIFIED (sem evidência explícita no chat)")
    gates: dict[str, str] = {}
    retry_log: list[str] = []

    OUT_EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_MANIFEST.parent.mkdir(parents=True, exist_ok=True)

    try:
        base = _load_v1()
        engine = base.prepare_engine_data()
        gates["G0_INPUTS_PRESENT"] = "PASS"
    except Exception as e:
        gates["G0_INPUTS_PRESENT"] = "FAIL"
        print("STEP GATES:")
        for k, v in gates.items():
            print(f"- {k}: {v} ({type(e).__name__}: {e})")
        print("RETRY LOG:")
        print("- none")
        print("ARTIFACT LINKS:")
        print(f"- {OUT_REPORT}")
        print("OVERALL STATUS: [[ FAIL ]]")
        return 1

    # Grid = histerese + cap de buy turnover
    candidates: list[dict[str, Any]] = []
    for sw in base.SLOPE_WINDOWS:
        for ih in base.IN_HYST_DAYS_GRID:
            for oh in base.OUT_HYST_DAYS_GRID:
                for cap in BUY_TURNOVER_CAP_GRID:
                    cap_tag = "NONE" if cap is None else f"{cap:.2f}".replace(".", "p")
                    candidates.append(
                        {
                            "candidate_id": f"SW{sw}_IN{ih}_OUT{oh}_CAP{cap_tag}",
                            "slope_window": int(sw),
                            "in_hyst_days": int(ih),
                            "out_hyst_days": int(oh),
                            "cadence_days": int(base.CADENCE_DAYS_FIXED),
                            "buy_turnover_cap_ratio": None if cap is None else float(cap),
                        }
                    )
    base.write_json_strict(OUT_CANDIDATE_SET, {"task_id": TASK_ID, "candidates": candidates})

    rows: list[dict[str, Any]] = []
    feasible_rows: list[dict[str, Any]] = []
    best: dict[str, Any] | None = None
    best_key: tuple | None = None

    for cand in candidates:
        ledger, curve, extra = base.run_candidate(
            engine=engine,
            slope_window=int(cand["slope_window"]),
            in_hyst=int(cand["in_hyst_days"]),
            out_hyst=int(cand["out_hyst_days"]),
            cadence_days=int(cand["cadence_days"]),
            buy_turnover_cap_ratio=cand["buy_turnover_cap_ratio"],
        )
        m = base.compute_metrics(curve["equity_end"])
        p = base.participation_metrics(curve)
        t_total = base.turnover_total(ledger, curve)
        t_reentry = base.subperiod_time_in_market(curve, base.REENTRY_SUBPERIOD_START, base.REENTRY_SUBPERIOD_END)
        eq_final = float(pd.to_numeric(curve["equity_end"], errors="coerce").astype(float).iloc[-1])

        row = {
            "candidate_id": cand["candidate_id"],
            "slope_window": int(cand["slope_window"]),
            "in_hyst_days": int(cand["in_hyst_days"]),
            "out_hyst_days": int(cand["out_hyst_days"]),
            "buy_turnover_cap_ratio": cand["buy_turnover_cap_ratio"],
            "equity_final": eq_final,
            "CAGR": float(m["cagr"]),
            "MDD": float(m["mdd"]),
            "Sharpe": float(m["sharpe"]),
            "turnover_total": float(t_total),
            "time_in_market_frac": float(p["time_in_market_frac"]),
            "avg_exposure": float(p["avg_exposure"]),
            "days_cash_ge_090_frac": float(p["days_cash_ge_090_frac"]),
            "days_defensive_frac": float(p["days_defensive_frac"]),
            "reentry_subperiod_time_in_market": float(t_reentry),
            "num_switches": int(extra.get("num_switches", 0)),
        }
        rows.append(row)

        feasible = (
            np.isfinite(row["MDD"]) and row["MDD"] >= THRESHOLDS["MDD_total_min"]
            and np.isfinite(row["turnover_total"]) and row["turnover_total"] <= THRESHOLDS["turnover_total_total_max"]
            and np.isfinite(row["reentry_subperiod_time_in_market"]) and row["reentry_subperiod_time_in_market"] >= THRESHOLDS["reentry_subperiod_time_in_market_min"]
        )
        if feasible:
            feasible_rows.append(row)
            key = (
                -row["equity_final"],
                -row["MDD"],
                row["turnover_total"],
                row["days_cash_ge_090_frac"],
                row["candidate_id"],
            )
            if best_key is None or key < best_key:
                best_key = key
                best = {"cfg": cand, "row": row, "ledger": ledger, "curve": curve}

    ablation_df = pd.DataFrame(rows).sort_values(["equity_final"], ascending=False).reset_index(drop=True)
    OUT_ABLATION.parent.mkdir(parents=True, exist_ok=True)
    ablation_df.to_parquet(OUT_ABLATION, index=False)
    gates["G1_ABLATION_RESULTS_PRESENT"] = "PASS"

    base.write_json_strict(
        OUT_FEASIBILITY,
        {
            "task_id": TASK_ID,
            "thresholds": THRESHOLDS,
            "total_candidates": int(len(candidates)),
            "feasible_count": int(len(feasible_rows)),
            "feasible_candidate_ids": [r["candidate_id"] for r in feasible_rows],
        },
    )

    if best is None:
        gates["G2_FEASIBLE_NONEMPTY"] = "FAIL"
        OUT_REPORT.write_text(
            "\n".join(
                [
                    f"# {TASK_ID} Report",
                    "",
                    "## Resultado",
                    "",
                    f"- feasible_count: 0 / {len(candidates)}",
                    "- Nenhum candidato atingiu constraints hard.",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
    else:
        gates["G2_FEASIBLE_NONEMPTY"] = "PASS"
        cfg = best["cfg"]
        row = best["row"]
        ledger = best["ledger"]
        curve = best["curve"]

        base.write_json_strict(
            OUT_SELECTED_CFG,
            {
                "task_id": TASK_ID,
                "selected_candidate_id": cfg["candidate_id"],
                "cadence_days": int(cfg["cadence_days"]),
                "buy_turnover_cap_ratio": cfg["buy_turnover_cap_ratio"],
                "market_mu_window": int(base.MU_WINDOW),
                "market_slope_window": int(cfg["slope_window"]),
                "in_hyst_days": int(cfg["in_hyst_days"]),
                "out_hyst_days": int(cfg["out_hyst_days"]),
                "thresholds": THRESHOLDS,
            },
        )
        curve.to_parquet(OUT_CURVE, index=False)
        ledger.to_parquet(OUT_LEDGER, index=False)
        base.write_json_strict(
            OUT_SUMMARY,
            {
                "task_id": TASK_ID,
                "selected_candidate_id": cfg["candidate_id"],
                "equity_final": float(row["equity_final"]),
                "cagr": float(row["CAGR"]),
                "mdd": float(row["MDD"]),
                "sharpe": float(row["Sharpe"]),
                "turnover_total": float(row["turnover_total"]),
                "time_in_market_frac": float(row["time_in_market_frac"]),
                "avg_exposure": float(row["avg_exposure"]),
                "days_cash_ge_090_frac": float(row["days_cash_ge_090_frac"]),
                "days_defensive_frac": float(row["days_defensive_frac"]),
                "reentry_subperiod_time_in_market": float(row["reentry_subperiod_time_in_market"]),
                "num_switches": int(row["num_switches"]),
            },
        )
        base.write_json_strict(
            OUT_SELECTION_RULE,
            {
                "task_id": TASK_ID,
                "constraints": THRESHOLDS,
                "selection_order": [
                    "equity_final DESC",
                    "MDD DESC",
                    "turnover_total ASC",
                    "days_cash_ge_090_frac ASC",
                    "candidate_id ASC",
                ],
                "selected_candidate_id": cfg["candidate_id"],
            },
        )
        OUT_REPORT.write_text(
            "\n".join(
                [
                    f"# {TASK_ID} Report",
                    "",
                    "## 1) Objetivo",
                    "",
                    "- Corrigir armadilha de reentrada com regime por Mercado + histerese e cap de turnover de compra.",
                    "",
                    "## 2) Grid testado",
                    "",
                    f"- SLOPE_WINDOWS={base.SLOPE_WINDOWS}",
                    f"- IN_HYST_DAYS_GRID={base.IN_HYST_DAYS_GRID}",
                    f"- OUT_HYST_DAYS_GRID={base.OUT_HYST_DAYS_GRID}",
                    f"- BUY_TURNOVER_CAP_GRID={BUY_TURNOVER_CAP_GRID}",
                    f"- cadence_days_fixed={base.CADENCE_DAYS_FIXED}",
                    "",
                    "## 3) Constraints hard",
                    "",
                    json.dumps(THRESHOLDS, indent=2, sort_keys=True),
                    "",
                    "## 4) Seleção",
                    "",
                    f"- selected_candidate_id: {cfg['candidate_id']}",
                    f"- market_slope_window: {cfg['slope_window']}",
                    f"- IN/OUT: {cfg['in_hyst_days']}/{cfg['out_hyst_days']}",
                    f"- buy_turnover_cap_ratio: {cfg['buy_turnover_cap_ratio']}",
                    "",
                    "## 5) Métricas do winner",
                    "",
                    f"- equity_final: {row['equity_final']:.2f}",
                    f"- CAGR: {row['CAGR']:.6f}",
                    f"- MDD: {row['MDD']:.6f}",
                    f"- Sharpe: {row['Sharpe']:.6f}",
                    f"- turnover_total: {row['turnover_total']:.6f}",
                    f"- time_in_market_frac: {row['time_in_market_frac']:.6f}",
                    f"- avg_exposure: {row['avg_exposure']:.6f}",
                    f"- days_cash_ge_090_frac: {row['days_cash_ge_090_frac']:.6f}",
                    f"- days_defensive_frac: {row['days_defensive_frac']:.6f}",
                    f"- reentry_subperiod_time_in_market: {row['reentry_subperiod_time_in_market']:.6f}",
                    "",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        gates["G3_SELECTED_ARTIFACTS_PRESENT"] = "PASS"

    ch_ok = update_changelog_one_line(TRACEABILITY_LINE)
    gates["G_CHLOG_UPDATED"] = "PASS" if ch_ok else "FAIL"

    script_path = Path(__file__).resolve()
    inputs = [base.CANONICAL_FILE, base.MACRO_FILE, base.BLACKLIST_FILE, base.SCORES_FILE, script_path, SCRIPT_V1]
    outputs = [OUT_ABLATION, OUT_FEASIBILITY, OUT_REPORT, OUT_CANDIDATE_SET, OUT_MANIFEST, CHANGELOG_PATH]
    if best is not None:
        outputs.extend([OUT_SELECTED_CFG, OUT_CURVE, OUT_LEDGER, OUT_SUMMARY, OUT_SELECTION_RULE])
    hashes = {str(p): sha256_file(p) for p in inputs + [p for p in outputs if p != OUT_MANIFEST]}
    base.write_json_strict(
        OUT_MANIFEST,
        {
            "task_id": TASK_ID,
            "hashes_sha256": hashes,
            "inputs_consumed": [str(p) for p in inputs],
            "outputs_produced": [str(p) for p in outputs],
        },
    )
    gates["Gx_HASH_MANIFEST_PRESENT"] = "PASS" if OUT_MANIFEST.exists() else "FAIL"

    print("STEP GATES:")
    for k, v in gates.items():
        print(f"- {k}: {v}")
    print("RETRY LOG:")
    if retry_log:
        for r in retry_log:
            print(f"- {r}")
    else:
        print("- none")
    print("ARTIFACT LINKS:")
    print(f"- {OUT_ABLATION}")
    if best is not None:
        print(f"- {OUT_SELECTED_CFG}")
        print(f"- {OUT_CURVE}")
        print(f"- {OUT_LEDGER}")
        print(f"- {OUT_SUMMARY}")
        print(f"- {OUT_SELECTION_RULE}")
    print(f"- {OUT_REPORT}")
    print(f"- {OUT_CANDIDATE_SET}")
    print(f"- {OUT_FEASIBILITY}")
    print(f"- {OUT_MANIFEST}")
    overall_pass = all(v == "PASS" for v in gates.values())
    print(f"OVERALL STATUS: [[ {'PASS' if overall_pass else 'FAIL'} ]]")
    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
