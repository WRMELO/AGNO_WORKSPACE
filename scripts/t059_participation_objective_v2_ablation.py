#!/usr/bin/env python3
"""T059 - Participation objective v2 with deterministic hard constraints."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


TASK_ID = "T059-PARTICIPATION-OBJECTIVE-V2"
ROOT = Path("/home/wilson/AGNO_WORKSPACE")
T044_SCRIPT = ROOT / "scripts/t044_anti_drift_guardrails_ablation.py"
T057_SCRIPT = ROOT / "scripts/t057_participation_guardrails_ablation.py"

INPUT_T040_SUBPERIOD = ROOT / "src/data_engine/portfolio/T040_METRICS_BY_SUBPERIOD.csv"
INPUT_T037_CURVE = ROOT / "src/data_engine/portfolio/T037_PORTFOLIO_CURVE.parquet"
INPUT_T039_CURVE = ROOT / "src/data_engine/portfolio/T039_PORTFOLIO_CURVE.parquet"
INPUT_T044_CURVE = ROOT / "src/data_engine/portfolio/T044_PORTFOLIO_CURVE_GUARDRAILS.parquet"
INPUT_T037_SUMMARY = ROOT / "src/data_engine/portfolio/T037_BASELINE_SUMMARY.json"
INPUT_T039_SUMMARY = ROOT / "src/data_engine/portfolio/T039_BASELINE_SUMMARY.json"
INPUT_T044_SUMMARY = ROOT / "src/data_engine/portfolio/T044_BASELINE_SUMMARY.json"
INPUT_T044_SELECTED_CFG = ROOT / "src/data_engine/portfolio/T044_GUARDRAILS_SELECTED_CONFIG.json"
INPUT_LESSONS = ROOT / "02_Knowledge_Bank/docs/process/STATE3_PHASE2_LESSONS_LEARNED_T056.md"

OUT_ABLATION = ROOT / "src/data_engine/portfolio/T059_PARTICIPATION_ABLATION_RESULTS_V2.parquet"
OUT_SELECTED_CFG = ROOT / "src/data_engine/portfolio/T059_PARTICIPATION_SELECTED_CONFIG_V2.json"
OUT_CURVE = ROOT / "src/data_engine/portfolio/T059_PORTFOLIO_CURVE_PARTICIPATION_V2.parquet"
OUT_LEDGER = ROOT / "src/data_engine/portfolio/T059_PORTFOLIO_LEDGER_PARTICIPATION_V2.parquet"
OUT_SUMMARY = ROOT / "src/data_engine/portfolio/T059_BASELINE_SUMMARY_V2.json"
OUT_REPORT = ROOT / "outputs/governanca/T059-PARTICIPATION-OBJECTIVE-V2_report.md"
OUT_MANIFEST = ROOT / "outputs/governanca/T059-PARTICIPATION-OBJECTIVE-V2_manifest.json"
OUT_EVIDENCE_DIR = ROOT / "outputs/governanca/T059-PARTICIPATION-OBJECTIVE-V2_evidence"
OUT_SELECTION_RULE = OUT_EVIDENCE_DIR / "selection_rule_v2.json"
OUT_CANDIDATE_SET = OUT_EVIDENCE_DIR / "candidate_set.json"
OUT_FEASIBILITY = OUT_EVIDENCE_DIR / "feasibility_snapshot.json"

CHANGELOG_PATH = ROOT / "00_Strategy/changelog.md"
TRACEABILITY_LINE = (
    "- 2026-02-28T18:03:08Z | STRATEGY: T059-PARTICIPATION-OBJECTIVE-V2 EXEC. "
    "Artefatos: outputs/governanca/T059-PARTICIPATION-OBJECTIVE-V2_report.md; "
    "outputs/governanca/T059-PARTICIPATION-OBJECTIVE-V2_manifest.json; "
    "src/data_engine/portfolio/T059_PARTICIPATION_SELECTED_CONFIG_V2.json"
)

THRESHOLDS = {
    "time_in_market_frac_total_min": 0.40,
    "avg_exposure_total_min": 0.15,
    "days_cash_ge_090_frac_total_max": 0.85,
    "MDD_total_min": -0.30,
    "turnover_total_total_max": 8.0,
}


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Nao foi possivel carregar modulo: {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.floating, float)):
        v = float(value)
        return v if np.isfinite(v) else None
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if pd.isna(value):
        return None
    return value


def write_json_strict(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(_json_safe(payload), indent=2, sort_keys=True, allow_nan=False)
    path.write_text(text + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _rank_pct(series: pd.Series, ascending: bool) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")
    if s.notna().sum() == 0:
        return pd.Series(np.nan, index=series.index)
    return s.rank(method="average", pct=True, ascending=ascending)


def compute_objective_v2(ablation_df: pd.DataFrame, overall_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    sub = ablation_df.copy()
    sub["r_eq_ratio_vs_t037"] = sub.groupby("subperiod")["eq_ratio_vs_t037"].transform(lambda x: _rank_pct(x, ascending=False))
    sub["r_mdd"] = sub.groupby("subperiod")["MDD"].transform(lambda x: _rank_pct(x, ascending=False))
    sub["r_time_in_market"] = sub.groupby("subperiod")["time_in_market_frac"].transform(lambda x: _rank_pct(x, ascending=False))
    sub["r_avg_exposure"] = sub.groupby("subperiod")["avg_exposure"].transform(lambda x: _rank_pct(x, ascending=False))
    sub["r_turnover"] = sub.groupby("subperiod")["turnover_total"].transform(lambda x: _rank_pct(x, ascending=True))
    sub["score_subperiod_v2"] = sub[
        ["r_eq_ratio_vs_t037", "r_mdd", "r_time_in_market", "r_avg_exposure", "r_turnover"]
    ].mean(axis=1, skipna=True)
    robust = (
        sub.groupby("candidate_id", as_index=False)["score_subperiod_v2"]
        .min()
        .rename(columns={"score_subperiod_v2": "robust_score"})
    )

    tot = overall_df.copy()
    tot["r_eq_total"] = _rank_pct(tot["equity_final_total"], ascending=False)
    tot["r_mdd_total"] = _rank_pct(tot["MDD_total"], ascending=False)
    tot["r_time_total"] = _rank_pct(tot["time_in_market_frac_total"], ascending=False)
    tot["r_exp_total"] = _rank_pct(tot["avg_exposure_total"], ascending=False)
    tot["r_cash_total"] = _rank_pct(tot["days_cash_ge_090_frac_total"], ascending=True)
    tot["r_turn_total"] = _rank_pct(tot["turnover_total_total"], ascending=True)
    tot["score_total_v2"] = tot[
        ["r_eq_total", "r_mdd_total", "r_time_total", "r_exp_total", "r_cash_total", "r_turn_total"]
    ].mean(axis=1, skipna=True)

    sel = robust.merge(tot, on="candidate_id", how="left")
    sel["viol_time_in_market"] = sel["time_in_market_frac_total"] < THRESHOLDS["time_in_market_frac_total_min"]
    sel["viol_avg_exposure"] = sel["avg_exposure_total"] < THRESHOLDS["avg_exposure_total_min"]
    sel["viol_cash_090"] = sel["days_cash_ge_090_frac_total"] > THRESHOLDS["days_cash_ge_090_frac_total_max"]
    sel["viol_mdd"] = sel["MDD_total"] < THRESHOLDS["MDD_total_min"]
    sel["viol_turnover"] = sel["turnover_total_total"] > THRESHOLDS["turnover_total_total_max"]
    sel["is_feasible_total"] = ~(
        sel["viol_time_in_market"]
        | sel["viol_avg_exposure"]
        | sel["viol_cash_090"]
        | sel["viol_mdd"]
        | sel["viol_turnover"]
    )
    return sub, sel


def update_changelog_one_line() -> bool:
    CHANGELOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    before = CHANGELOG_PATH.read_text(encoding="utf-8") if CHANGELOG_PATH.exists() else ""
    before_len = len(before.encode("utf-8"))
    with CHANGELOG_PATH.open("a", encoding="utf-8") as f:
        if before and not before.endswith("\n"):
            f.write("\n")
        f.write(TRACEABILITY_LINE + "\n")
    after = CHANGELOG_PATH.read_text(encoding="utf-8")
    return len(after.encode("utf-8")) > before_len and after.endswith(TRACEABILITY_LINE + "\n")


def main() -> int:
    print(f"HEADER: {TASK_ID}")
    t044 = _load_module(T044_SCRIPT, "t044_mod")
    t057 = _load_module(T057_SCRIPT, "t057_mod")

    required_inputs = [
        t044.CANONICAL_FILE, t044.MACRO_FILE, t044.BLACKLIST_FILE, t044.SCORES_FILE,
        t044.INPUT_T039_CURVE, t044.INPUT_T039_LEDGER, t044.INPUT_T037_CURVE, t044.INPUT_T037_LEDGER,
        INPUT_T040_SUBPERIOD, INPUT_T037_CURVE, INPUT_T039_CURVE, INPUT_T044_CURVE,
        INPUT_T037_SUMMARY, INPUT_T039_SUMMARY, INPUT_T044_SUMMARY, INPUT_T044_SELECTED_CFG,
        INPUT_LESSONS, T044_SCRIPT, T057_SCRIPT,
    ]
    missing = [str(p) for p in required_inputs if not p.exists()]
    if missing:
        print("STEP GATES:")
        print(f"- G0_INPUTS_PRESENT: FAIL (missing: {', '.join(missing)})")
        print("OVERALL STATUS: [[ FAIL ]]")
        return 1

    for p in [OUT_ABLATION, OUT_SELECTED_CFG, OUT_CURVE, OUT_LEDGER, OUT_SUMMARY, OUT_REPORT, OUT_MANIFEST, OUT_SELECTION_RULE, OUT_CANDIDATE_SET, OUT_FEASIBILITY]:
        p.parent.mkdir(parents=True, exist_ok=True)

    engine = t044.prepare_engine_data()
    subperiods = t057.load_subperiods()
    baseline_map = t044.load_subperiods_and_baselines()[1]
    candidates, candidate_set_evidence = t044.build_candidate_set()
    candidate_set_evidence["task_id"] = TASK_ID
    candidate_set_evidence["construction_method"] = "same_as_t044_for_comparability"
    write_json_strict(OUT_CANDIDATE_SET, candidate_set_evidence)

    all_rows: list[dict[str, Any]] = []
    overall_rows: list[dict[str, Any]] = []
    print(f"INFO: candidate_count={len(candidates)}")
    for i, cand in enumerate(candidates, start=1):
        print(f"INFO: running {cand['candidate_id']} ({i}/{len(candidates)}) cadence={cand['buy_cadence_days']} cap={cand['buy_turnover_cap_ratio']}")
        ledger, curve, _budget, extra = t044.run_candidate(
            engine=engine,
            cadence_days=int(cand["buy_cadence_days"]),
            buy_turnover_cap_ratio=cand["buy_turnover_cap_ratio"],
        )
        rows, total_metrics = t044.evaluate_candidate_rows(cand, curve, ledger, subperiods, baseline_map)
        pm_total = t057.participation_metrics(curve)
        for row in rows:
            start = pd.to_datetime(row["period_start"])
            end = pd.to_datetime(row["period_end"])
            c_sp = curve[(pd.to_datetime(curve["date"]) >= start) & (pd.to_datetime(curve["date"]) <= end)].copy()
            row.update(t057.participation_metrics(c_sp))
        all_rows.extend(rows)
        overall_rows.append(
            {
                "candidate_id": cand["candidate_id"],
                "buy_cadence_days": cand["buy_cadence_days"],
                "buy_turnover_cap_ratio": cand["buy_turnover_cap_ratio"],
                "params_json": cand["params_json"],
                "equity_final_total": total_metrics.get("equity_final", np.nan),
                "CAGR_total": total_metrics.get("CAGR", np.nan),
                "MDD_total": total_metrics.get("MDD", np.nan),
                "sharpe_total": total_metrics.get("sharpe", np.nan),
                "turnover_total_total": total_metrics.get("turnover_total", np.nan),
                "cost_total_total": total_metrics.get("cost_total", np.nan),
                "num_switches_total": total_metrics.get("num_switches", np.nan),
                "n_buy_blocked_by_cadence": extra["n_buy_blocked_by_cadence"],
                "n_buy_blocked_by_budget": extra["n_buy_blocked_by_budget"],
                "days_with_budget_binding": extra["days_with_budget_binding"],
                "days_with_cadence_binding": extra["days_with_cadence_binding"],
                **{f"{k}_total": v for k, v in pm_total.items()},
            }
        )

    ablation_df = pd.DataFrame(all_rows)
    overall_df = pd.DataFrame(overall_rows)
    scored_sub_df, selection_df = compute_objective_v2(ablation_df, overall_df)
    scored_sub_df.to_parquet(OUT_ABLATION, index=False)

    feasible_df = selection_df[selection_df["is_feasible_total"]].copy()
    feasibility = {
        "task_id": TASK_ID,
        "thresholds_total_hard": THRESHOLDS,
        "total_candidate_count": int(len(selection_df)),
        "feasible_count": int(len(feasible_df)),
        "feasible_candidate_ids": feasible_df["candidate_id"].astype(str).tolist(),
    }
    feasibility_top = selection_df[
        [
            "candidate_id", "buy_cadence_days", "buy_turnover_cap_ratio",
            "time_in_market_frac_total", "avg_exposure_total", "days_cash_ge_090_frac_total",
            "MDD_total", "turnover_total_total", "is_feasible_total",
            "viol_time_in_market", "viol_avg_exposure", "viol_cash_090", "viol_mdd", "viol_turnover",
        ]
    ].copy()
    feasibility_top = feasibility_top.sort_values(by=["is_feasible_total", "candidate_id"], ascending=[False, True]).head(10)
    feasibility["top10_with_violation_flags"] = feasibility_top.to_dict(orient="records")
    write_json_strict(OUT_FEASIBILITY, feasibility)

    if feasible_df.empty:
        gch = update_changelog_one_line()
        report_lines = [
            f"# {TASK_ID} Report",
            "",
            "## Resultado",
            "- Nenhum candidato factivel com os thresholds hard atuais.",
            f"- thresholds: `{THRESHOLDS}`",
            f"- evidence: `{OUT_FEASIBILITY}`",
            "",
            "## Recomendacao",
            "- Relaxamento minimo sugerido: reduzir `time_in_market_frac_total_min` de 0.40 para 0.35 e reexecutar.",
        ]
        OUT_REPORT.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
        manifest_outputs = [OUT_ABLATION, OUT_REPORT, OUT_FEASIBILITY, OUT_CANDIDATE_SET]
        write_json_strict(
            OUT_MANIFEST,
            {
                "task_id": TASK_ID,
                "inputs_consumed": [str(p) for p in required_inputs],
                "outputs_produced": [str(p) for p in manifest_outputs] + [str(OUT_MANIFEST)],
                "hashes_sha256": {str(p): sha256_file(p) for p in (required_inputs + manifest_outputs)},
            },
        )
        print("STEP GATES:")
        print("- G0_INPUTS_PRESENT: PASS")
        print("- G1_ABLATION_PARTICIPATION_PRESENT: PASS")
        print("- G2_FEASIBLE_SET_PRESENT: FAIL (feasible_count=0)")
        print("- G3_SELECTION_RULE_DETERMINISTIC: FAIL")
        print(f"- G_CHLOG_UPDATED: {'PASS' if gch else 'FAIL'}")
        print("- Gx_HASH_MANIFEST_PRESENT: PASS")
        print("OVERALL STATUS: [[ FAIL ]]")
        return 1

    ranked = feasible_df.sort_values(
        by=[
            "days_cash_ge_090_frac_total", "time_in_market_frac_total", "avg_exposure_total",
            "robust_score", "score_total_v2", "candidate_id",
        ],
        ascending=[True, False, False, False, False, True],
    ).reset_index(drop=True)
    winner = ranked.iloc[0].to_dict()
    winner_id = str(winner["candidate_id"])
    winner_params = next(c for c in candidates if c["candidate_id"] == winner_id)

    selection_rule = {
        "task_id": TASK_ID,
        "selection_type": "deterministic_lexicographic_feasible_first_v2",
        "feasibility_hard_thresholds_total": THRESHOLDS,
        "subperiod_policy": "soft_diagnostic_only_non_blocking",
        "ranking_order": [
            "min days_cash_ge_090_frac_total",
            "max time_in_market_frac_total",
            "max avg_exposure_total",
            "max robust_score (min score_subperiod_v2)",
            "max score_total_v2",
            "min candidate_id (stable tie-breaker)",
        ],
        "winner_candidate_id": winner_id,
        "feasible_count": int(len(ranked)),
        "top10_candidates": ranked.head(10).to_dict(orient="records"),
    }
    write_json_strict(OUT_SELECTION_RULE, selection_rule)
    write_json_strict(OUT_SELECTED_CFG, {"task_id": TASK_ID, "selected_candidate_id": winner_id, "selected_params": winner_params, "selection_stats": winner})

    ledger_w, curve_w, _budget_w, extra_w = t044.run_candidate(
        engine=engine,
        cadence_days=int(winner_params["buy_cadence_days"]),
        buy_turnover_cap_ratio=winner_params["buy_turnover_cap_ratio"],
    )
    curve_w.to_parquet(OUT_CURVE, index=False)
    ledger_w.to_parquet(OUT_LEDGER, index=False)

    pm_w = t057.participation_metrics(curve_w)
    m_total = t044.compute_spec005_metrics(curve_w, ledger_w)
    summary = {
        "task_id": "T059",
        "selected_candidate_id": winner_id,
        "guardrails_policy": {
            "buy_cadence_days": int(winner_params["buy_cadence_days"]),
            "buy_turnover_cap_ratio": winner_params["buy_turnover_cap_ratio"],
            "selection_mode": "ablation_data_driven_participation_objective_v2_constraints",
        },
        "thresholds_total_hard": THRESHOLDS,
        "metrics_total": {**m_total, **pm_w},
        "enforcement": {
            "n_buy_blocked_by_cadence": int(extra_w["n_buy_blocked_by_cadence"]),
            "n_buy_blocked_by_budget": int(extra_w["n_buy_blocked_by_budget"]),
            "n_buy_blocked_notional_budget": float(extra_w["n_buy_blocked_notional_budget"]),
            "days_with_budget_binding": int(extra_w["days_with_budget_binding"]),
            "days_with_cadence_binding": int(extra_w["days_with_cadence_binding"]),
        },
    }
    write_json_strict(OUT_SUMMARY, summary)

    t037 = json.loads(INPUT_T037_SUMMARY.read_text(encoding="utf-8"))
    t039 = json.loads(INPUT_T039_SUMMARY.read_text(encoding="utf-8"))
    t044s = json.loads(INPUT_T044_SUMMARY.read_text(encoding="utf-8"))
    pm_037 = t057.participation_metrics(pd.read_parquet(INPUT_T037_CURVE))
    pm_039 = t057.participation_metrics(pd.read_parquet(INPUT_T039_CURVE))
    pm_044 = t057.participation_metrics(pd.read_parquet(INPUT_T044_CURVE))

    top10_md = ranked.head(10)[
        [
            "candidate_id", "buy_cadence_days", "buy_turnover_cap_ratio",
            "days_cash_ge_090_frac_total", "time_in_market_frac_total",
            "avg_exposure_total", "robust_score", "score_total_v2", "MDD_total", "turnover_total_total",
        ]
    ].to_markdown(index=False)
    report_lines = [
        f"# {TASK_ID} Report",
        "",
        "## 1) Thresholds hard (anti CDI-only)",
        f"- {THRESHOLDS}",
        f"- feasible_count={len(ranked)} de total={len(selection_df)}",
        "",
        "## 2) Winner",
        f"- candidate_id={winner_id}, cadence={winner_params['buy_cadence_days']}, cap={winner_params['buy_turnover_cap_ratio']}",
        "",
        "## 3) Top-10 factiveis",
        "",
        top10_md,
        "",
        "## 4) Comparativo (vencedor vs baselines)",
        f"- equity_final: T059={m_total.get('equity_final')} | T044={t044s.get('metrics_total', {}).get('equity_final')} | T039={t039.get('equity_final')} | T037={t037.get('equity_final')}",
        f"- CAGR: T059={m_total.get('CAGR')} | T044={t044s.get('metrics_total', {}).get('CAGR')} | T039={t039.get('cagr')} | T037={t037.get('cagr')}",
        f"- MDD: T059={m_total.get('MDD')} | T044={t044s.get('metrics_total', {}).get('MDD')} | T039={t039.get('mdd')} | T037={t037.get('mdd')}",
        f"- sharpe: T059={m_total.get('sharpe')} | T044={t044s.get('metrics_total', {}).get('sharpe')} | T039={t039.get('sharpe')} | T037={t037.get('sharpe')}",
        f"- time_in_market_frac: T059={pm_w.get('time_in_market_frac')} | T044={pm_044.get('time_in_market_frac')} | T039={pm_039.get('time_in_market_frac')} | T037={pm_037.get('time_in_market_frac')}",
        f"- avg_exposure: T059={pm_w.get('avg_exposure')} | T044={pm_044.get('avg_exposure')} | T039={pm_039.get('avg_exposure')} | T037={pm_037.get('avg_exposure')}",
        f"- days_cash_ge_090_frac: T059={pm_w.get('days_cash_ge_090_frac')} | T044={pm_044.get('days_cash_ge_090_frac')} | T039={pm_039.get('days_cash_ge_090_frac')} | T037={pm_037.get('days_cash_ge_090_frac')}",
    ]
    OUT_REPORT.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    outputs = [OUT_ABLATION, OUT_SELECTED_CFG, OUT_CURVE, OUT_LEDGER, OUT_SUMMARY, OUT_REPORT, OUT_CANDIDATE_SET, OUT_SELECTION_RULE, OUT_FEASIBILITY]
    write_json_strict(
        OUT_MANIFEST,
        {
            "task_id": TASK_ID,
            "inputs_consumed": [str(p) for p in required_inputs],
            "outputs_produced": [str(p) for p in outputs] + [str(OUT_MANIFEST)],
            "hashes_sha256": {str(p): sha256_file(p) for p in (required_inputs + outputs)},
        },
    )

    g0 = all(p.exists() for p in required_inputs)
    g1 = OUT_ABLATION.exists() and OUT_CANDIDATE_SET.exists() and OUT_FEASIBILITY.exists()
    g2 = len(ranked) > 0
    g3 = OUT_SELECTION_RULE.exists() and bool(selection_rule.get("winner_candidate_id"))
    g4 = OUT_SELECTED_CFG.exists() and OUT_CURVE.exists() and OUT_LEDGER.exists() and OUT_SUMMARY.exists() and OUT_REPORT.exists()
    gch = update_changelog_one_line()
    gx = OUT_MANIFEST.exists()

    print("STEP GATES:")
    print(f"- G_MODEL_ROUTING: PASS_MODEL_ROUTING_UNVERIFIED (sem evidencia explicita no chat)")
    print(f"- G0_INPUTS_PRESENT: {'PASS' if g0 else 'FAIL'}")
    print(f"- G1_ABLATION_PARTICIPATION_PRESENT: {'PASS' if g1 else 'FAIL'}")
    print(f"- G2_FEASIBLE_SET_PRESENT: {'PASS' if g2 else 'FAIL'} (feasible_count={len(ranked)})")
    print(f"- G3_SELECTION_RULE_DETERMINISTIC: {'PASS' if g3 else 'FAIL'}")
    print(f"- G4_WINNER_OUTPUTS_PRESENT: {'PASS' if g4 else 'FAIL'}")
    print(f"- G_CHLOG_UPDATED: {'PASS' if gch else 'FAIL'}")
    print(f"- Gx_HASH_MANIFEST_PRESENT: {'PASS' if gx else 'FAIL'}")
    print("ARTIFACT LINKS:")
    for p in [OUT_ABLATION, OUT_SELECTED_CFG, OUT_CURVE, OUT_LEDGER, OUT_SUMMARY, OUT_REPORT, OUT_CANDIDATE_SET, OUT_SELECTION_RULE, OUT_FEASIBILITY, OUT_MANIFEST, CHANGELOG_PATH]:
        print(f"- {p}")
    overall = g0 and g1 and g2 and g3 and g4 and gch and gx
    print(f"OVERALL STATUS: [[ {'PASS' if overall else 'FAIL'} ]]")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
