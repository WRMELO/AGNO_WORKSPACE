#!/usr/bin/env python3
"""T057 - Participation-first guardrails selection via deterministic ablation."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


TASK_ID = "T057-PARTICIPATION-GUARDRAILS-V1"
ROOT = Path("/home/wilson/AGNO_WORKSPACE")
T044_SCRIPT = ROOT / "scripts/t044_anti_drift_guardrails_ablation.py"

INPUT_T040_SUBPERIOD = ROOT / "src/data_engine/portfolio/T040_METRICS_BY_SUBPERIOD.csv"
INPUT_T037_CURVE = ROOT / "src/data_engine/portfolio/T037_PORTFOLIO_CURVE.parquet"
INPUT_T039_CURVE = ROOT / "src/data_engine/portfolio/T039_PORTFOLIO_CURVE.parquet"
INPUT_T044_CURVE = ROOT / "src/data_engine/portfolio/T044_PORTFOLIO_CURVE_GUARDRAILS.parquet"
INPUT_T037_SUMMARY = ROOT / "src/data_engine/portfolio/T037_BASELINE_SUMMARY.json"
INPUT_T039_SUMMARY = ROOT / "src/data_engine/portfolio/T039_BASELINE_SUMMARY.json"
INPUT_T044_SUMMARY = ROOT / "src/data_engine/portfolio/T044_BASELINE_SUMMARY.json"
INPUT_T044_SELECTED_CFG = ROOT / "src/data_engine/portfolio/T044_GUARDRAILS_SELECTED_CONFIG.json"
INPUT_LESSONS = ROOT / "02_Knowledge_Bank/docs/process/STATE3_PHASE2_LESSONS_LEARNED_T056.md"

OUT_ABLATION = ROOT / "src/data_engine/portfolio/T057_PARTICIPATION_ABLATION_RESULTS.parquet"
OUT_SELECTED_CFG = ROOT / "src/data_engine/portfolio/T057_PARTICIPATION_SELECTED_CONFIG.json"
OUT_CURVE = ROOT / "src/data_engine/portfolio/T057_PORTFOLIO_CURVE_PARTICIPATION.parquet"
OUT_LEDGER = ROOT / "src/data_engine/portfolio/T057_PORTFOLIO_LEDGER_PARTICIPATION.parquet"
OUT_SUMMARY = ROOT / "src/data_engine/portfolio/T057_BASELINE_SUMMARY.json"
OUT_REPORT = ROOT / "outputs/governanca/T057-PARTICIPATION-GUARDRAILS-V1_report.md"
OUT_MANIFEST = ROOT / "outputs/governanca/T057-PARTICIPATION-GUARDRAILS-V1_manifest.json"
OUT_EVIDENCE_DIR = ROOT / "outputs/governanca/T057-PARTICIPATION-GUARDRAILS-V1_evidence"
OUT_SELECTION_RULE = OUT_EVIDENCE_DIR / "selection_rule.json"
OUT_CANDIDATE_SET = OUT_EVIDENCE_DIR / "candidate_set.json"


def _load_t044_module():
    spec = importlib.util.spec_from_file_location("t044_mod", T044_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Nao foi possivel carregar modulo T044: {T044_SCRIPT}")
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


def participation_metrics(curve: pd.DataFrame) -> dict[str, float]:
    c = curve.copy()
    if c.empty:
        return {
            "time_in_market_frac": np.nan,
            "avg_exposure": np.nan,
            "p50_exposure": np.nan,
            "avg_cash_weight": np.nan,
            "days_cash_ge_090_frac": np.nan,
            "days_defensive_frac": np.nan,
        }

    exposure = pd.to_numeric(c.get("exposure", pd.Series(np.nan, index=c.index)), errors="coerce")
    equity = pd.to_numeric(c.get("equity_end", pd.Series(np.nan, index=c.index)), errors="coerce")
    cash = pd.to_numeric(c.get("cash_end", pd.Series(np.nan, index=c.index)), errors="coerce")
    cash_weight = (cash / equity.replace(0.0, np.nan)).replace([np.inf, -np.inf], np.nan)
    defensivo = c.get("regime_defensivo", pd.Series(False, index=c.index)).fillna(False).astype(bool)

    return {
        "time_in_market_frac": float((exposure > 0).mean()) if len(exposure) else np.nan,
        "avg_exposure": float(exposure.mean()) if len(exposure.dropna()) else np.nan,
        "p50_exposure": float(exposure.median()) if len(exposure.dropna()) else np.nan,
        "avg_cash_weight": float(cash_weight.mean()) if len(cash_weight.dropna()) else np.nan,
        "days_cash_ge_090_frac": float((cash_weight >= 0.90).mean()) if len(cash_weight) else np.nan,
        "days_defensive_frac": float(defensivo.mean()) if len(defensivo) else np.nan,
    }


def load_subperiods() -> pd.DataFrame:
    t040 = pd.read_csv(INPUT_T040_SUBPERIOD)
    t040["period_start"] = pd.to_datetime(t040["period_start"], errors="coerce")
    t040["period_end"] = pd.to_datetime(t040["period_end"], errors="coerce")
    return (
        t040[t040["task_id"] == "T039"][["subperiod", "period_start", "period_end"]]
        .drop_duplicates()
        .sort_values("period_start")
        .reset_index(drop=True)
    )


def _rank_pct(series: pd.Series, ascending: bool) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")
    if s.notna().sum() == 0:
        return pd.Series(np.nan, index=series.index)
    return s.rank(method="average", pct=True, ascending=ascending)


def compute_objective(ablation_df: pd.DataFrame, overall_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    # Subperiod objective (robust): percentile ranks across candidates, no tunable weights.
    sub = ablation_df.copy()
    sub["r_eq_ratio_vs_t037"] = sub.groupby("subperiod")["eq_ratio_vs_t037"].transform(lambda x: _rank_pct(x, ascending=False))
    sub["r_mdd"] = sub.groupby("subperiod")["MDD"].transform(lambda x: _rank_pct(x, ascending=False))
    sub["r_time_in_market"] = sub.groupby("subperiod")["time_in_market_frac"].transform(lambda x: _rank_pct(x, ascending=False))
    sub["r_avg_exposure"] = sub.groupby("subperiod")["avg_exposure"].transform(lambda x: _rank_pct(x, ascending=False))
    sub["r_cash_090"] = sub.groupby("subperiod")["days_cash_ge_090_frac"].transform(lambda x: _rank_pct(x, ascending=True))
    sub["r_turnover"] = sub.groupby("subperiod")["turnover_total"].transform(lambda x: _rank_pct(x, ascending=True))
    sub["score_subperiod"] = sub[
        [
            "r_eq_ratio_vs_t037",
            "r_mdd",
            "r_time_in_market",
            "r_avg_exposure",
            "r_cash_090",
            "r_turnover",
        ]
    ].mean(axis=1, skipna=True)

    robust = (
        sub.groupby("candidate_id", as_index=False)["score_subperiod"]
        .min()
        .rename(columns={"score_subperiod": "robust_score"})
    )

    # Total-period objective (secondary): same idea on total metrics.
    tot = overall_df.copy()
    tot["r_eq_total"] = _rank_pct(tot["equity_final_total"], ascending=False)
    tot["r_mdd_total"] = _rank_pct(tot["MDD_total"], ascending=False)
    tot["r_time_in_market_total"] = _rank_pct(tot["time_in_market_frac_total"], ascending=False)
    tot["r_avg_exposure_total"] = _rank_pct(tot["avg_exposure_total"], ascending=False)
    tot["r_cash_090_total"] = _rank_pct(tot["days_cash_ge_090_frac_total"], ascending=True)
    tot["r_turnover_total"] = _rank_pct(tot["turnover_total_total"], ascending=True)
    tot["score_total"] = tot[
        [
            "r_eq_total",
            "r_mdd_total",
            "r_time_in_market_total",
            "r_avg_exposure_total",
            "r_cash_090_total",
            "r_turnover_total",
        ]
    ].mean(axis=1, skipna=True)

    return sub, robust.merge(tot, on="candidate_id", how="left")


def main() -> int:
    print(f"HEADER: {TASK_ID}")

    t044 = _load_t044_module()
    required_inputs = [
        t044.CANONICAL_FILE,
        t044.MACRO_FILE,
        t044.BLACKLIST_FILE,
        t044.SCORES_FILE,
        t044.INPUT_T039_CURVE,
        t044.INPUT_T039_LEDGER,
        t044.INPUT_T037_CURVE,
        t044.INPUT_T037_LEDGER,
        INPUT_T040_SUBPERIOD,
        INPUT_T037_CURVE,
        INPUT_T039_CURVE,
        INPUT_T044_CURVE,
        INPUT_T037_SUMMARY,
        INPUT_T039_SUMMARY,
        INPUT_T044_SUMMARY,
        INPUT_T044_SELECTED_CFG,
        INPUT_LESSONS,
        T044_SCRIPT,
    ]
    missing = [str(p) for p in required_inputs if not p.exists()]
    if missing:
        print("STEP GATES:")
        print(f"- G0_INPUTS_PRESENT: FAIL (missing: {', '.join(missing)})")
        print("OVERALL STATUS: [[ FAIL ]]")
        return 1

    for p in [
        OUT_ABLATION,
        OUT_SELECTED_CFG,
        OUT_CURVE,
        OUT_LEDGER,
        OUT_SUMMARY,
        OUT_REPORT,
        OUT_MANIFEST,
        OUT_SELECTION_RULE,
        OUT_CANDIDATE_SET,
    ]:
        p.parent.mkdir(parents=True, exist_ok=True)

    engine = t044.prepare_engine_data()
    subperiods = load_subperiods()
    baseline_map = t044.load_subperiods_and_baselines()[1]
    candidates, candidate_set_evidence = t044.build_candidate_set()
    candidate_set_evidence["task_id"] = TASK_ID
    candidate_set_evidence["construction_method"] = "same_as_t044_for_comparability"
    write_json_strict(OUT_CANDIDATE_SET, candidate_set_evidence)

    all_rows: list[dict[str, Any]] = []
    overall_rows: list[dict[str, Any]] = []

    print(f"INFO: candidate_count={len(candidates)}")
    for i, cand in enumerate(candidates, start=1):
        print(
            f"INFO: running {cand['candidate_id']} ({i}/{len(candidates)}) "
            f"cadence={cand['buy_cadence_days']} cap={cand['buy_turnover_cap_ratio']}"
        )
        ledger, curve, _budget, extra = t044.run_candidate(
            engine=engine,
            cadence_days=int(cand["buy_cadence_days"]),
            buy_turnover_cap_ratio=cand["buy_turnover_cap_ratio"],
        )
        rows, total_metrics = t044.evaluate_candidate_rows(cand, curve, ledger, subperiods, baseline_map)
        pm_total = participation_metrics(curve)

        for row in rows:
            start = pd.to_datetime(row["period_start"])
            end = pd.to_datetime(row["period_end"])
            c_sp = curve[(pd.to_datetime(curve["date"]) >= start) & (pd.to_datetime(curve["date"]) <= end)].copy()
            pm_sp = participation_metrics(c_sp)
            row.update(pm_sp)

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
    scored_sub_df, selection_df = compute_objective(ablation_df, overall_df)
    scored_sub_df.to_parquet(OUT_ABLATION, index=False)

    selection_df = selection_df.sort_values(
        by=[
            "robust_score",
            "score_total",
            "MDD_total",
            "days_cash_ge_090_frac_total",
            "turnover_total_total",
            "candidate_id",
        ],
        ascending=[False, False, False, True, True, True],
    ).reset_index(drop=True)
    winner = selection_df.iloc[0].to_dict()
    winner_id = str(winner["candidate_id"])
    winner_params = next(c for c in candidates if c["candidate_id"] == winner_id)

    selection_rule = {
        "task_id": TASK_ID,
        "selection_type": "deterministic_lexicographic_rank_based",
        "objective_notes": "No tunable weights. score_subperiod and score_total are unweighted means of percentile ranks.",
        "subperiod_components_higher_better": [
            "eq_ratio_vs_t037",
            "MDD",
            "time_in_market_frac",
            "avg_exposure",
        ],
        "subperiod_components_lower_better": [
            "days_cash_ge_090_frac",
            "turnover_total",
        ],
        "ranking_order": [
            "max robust_score = min(score_subperiod)",
            "max score_total",
            "max MDD_total (less negative is better)",
            "min days_cash_ge_090_frac_total",
            "min turnover_total_total",
            "min candidate_id (stable tie-breaker)",
        ],
        "winner_candidate_id": winner_id,
        "top10_candidates": selection_df.head(10).to_dict(orient="records"),
    }
    write_json_strict(OUT_SELECTION_RULE, selection_rule)
    write_json_strict(
        OUT_SELECTED_CFG,
        {
            "task_id": TASK_ID,
            "selected_candidate_id": winner_id,
            "selected_params": winner_params,
            "selection_stats": winner,
        },
    )

    ledger_w, curve_w, _budget_w, extra_w = t044.run_candidate(
        engine=engine,
        cadence_days=int(winner_params["buy_cadence_days"]),
        buy_turnover_cap_ratio=winner_params["buy_turnover_cap_ratio"],
    )
    curve_w.to_parquet(OUT_CURVE, index=False)
    ledger_w.to_parquet(OUT_LEDGER, index=False)

    pm_w = participation_metrics(curve_w)
    m_total = t044.compute_spec005_metrics(curve_w, ledger_w)
    summary = {
        "task_id": "T057",
        "selected_candidate_id": winner_id,
        "guardrails_policy": {
            "buy_cadence_days": int(winner_params["buy_cadence_days"]),
            "buy_turnover_cap_ratio": winner_params["buy_turnover_cap_ratio"],
            "selection_mode": "ablation_data_driven_participation_objective",
        },
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

    def _load_curve_metrics(path: Path) -> dict[str, float]:
        curve = pd.read_parquet(path)
        return participation_metrics(curve)

    pm_037 = _load_curve_metrics(INPUT_T037_CURVE)
    pm_039 = _load_curve_metrics(INPUT_T039_CURVE)
    pm_044 = _load_curve_metrics(INPUT_T044_CURVE)

    t037 = json.loads(INPUT_T037_SUMMARY.read_text(encoding="utf-8"))
    t039 = json.loads(INPUT_T039_SUMMARY.read_text(encoding="utf-8"))
    t044 = json.loads(INPUT_T044_SUMMARY.read_text(encoding="utf-8"))
    m044 = t044.get("metrics_total", {})

    top10 = selection_df.head(10)[
        [
            "candidate_id",
            "buy_cadence_days",
            "buy_turnover_cap_ratio",
            "robust_score",
            "score_total",
            "equity_final_total",
            "MDD_total",
            "time_in_market_frac_total",
            "avg_exposure_total",
            "days_cash_ge_090_frac_total",
            "turnover_total_total",
        ]
    ].copy()
    top10_md = top10.to_markdown(index=False)

    report_lines = [
        f"# {TASK_ID} Report",
        "",
        "## 1) Contexto",
        "- Objetivo: aumentar participacao de bolsa (exposure/time-in-market) sem reabrir deriva/drawdown.",
        "- Metodo: manter candidate set do T044 e trocar a selecao para objetivo deterministico orientado a participacao.",
        "",
        "## 2) Metricas de participacao",
        "- time_in_market_frac = frac(dias com exposure > 0)",
        "- avg_exposure / p50_exposure",
        "- avg_cash_weight e days_cash_ge_090_frac",
        "- days_defensive_frac",
        "",
        "## 3) Regra de selecao",
        f"- selection_rule: `{OUT_SELECTION_RULE}`",
        f"- winner: `{winner_id}` -> cadence={winner_params['buy_cadence_days']}, cap={winner_params['buy_turnover_cap_ratio']}",
        "",
        "## 4) Top-10 candidatos",
        "",
        top10_md,
        "",
        "## 5) Comparativo vencedor vs baselines",
        f"- equity_final: T057={m_total.get('equity_final')} | T044={m044.get('equity_final')} | T039={t039.get('equity_final')} | T037={t037.get('equity_final')}",
        f"- CAGR: T057={m_total.get('CAGR')} | T044={m044.get('CAGR')} | T039={t039.get('cagr')} | T037={t037.get('cagr')}",
        f"- MDD: T057={m_total.get('MDD')} | T044={m044.get('MDD')} | T039={t039.get('mdd')} | T037={t037.get('mdd')}",
        f"- sharpe: T057={m_total.get('sharpe')} | T044={m044.get('sharpe')} | T039={t039.get('sharpe')} | T037={t037.get('sharpe')}",
        f"- time_in_market_frac: T057={pm_w.get('time_in_market_frac')} | T044={pm_044.get('time_in_market_frac')} | T039={pm_039.get('time_in_market_frac')} | T037={pm_037.get('time_in_market_frac')}",
        f"- avg_exposure: T057={pm_w.get('avg_exposure')} | T044={pm_044.get('avg_exposure')} | T039={pm_039.get('avg_exposure')} | T037={pm_037.get('avg_exposure')}",
        f"- days_cash_ge_090_frac: T057={pm_w.get('days_cash_ge_090_frac')} | T044={pm_044.get('days_cash_ge_090_frac')} | T039={pm_039.get('days_cash_ge_090_frac')} | T037={pm_037.get('days_cash_ge_090_frac')}",
        "",
        "## 6) Artefatos",
        f"- `{OUT_ABLATION}`",
        f"- `{OUT_SELECTED_CFG}`",
        f"- `{OUT_CURVE}`",
        f"- `{OUT_LEDGER}`",
        f"- `{OUT_SUMMARY}`",
        f"- `{OUT_CANDIDATE_SET}`",
        f"- `{OUT_SELECTION_RULE}`",
        f"- `{OUT_REPORT}`",
        f"- `{OUT_MANIFEST}`",
    ]
    OUT_REPORT.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    outputs = [
        OUT_ABLATION,
        OUT_SELECTED_CFG,
        OUT_CURVE,
        OUT_LEDGER,
        OUT_SUMMARY,
        OUT_REPORT,
        OUT_CANDIDATE_SET,
        OUT_SELECTION_RULE,
    ]
    manifest = {
        "task_id": TASK_ID,
        "inputs_consumed": [str(p) for p in required_inputs],
        "outputs_produced": [str(p) for p in outputs] + [str(OUT_MANIFEST)],
        "hashes_sha256": {str(p): sha256_file(p) for p in (required_inputs + outputs)},
    }
    write_json_strict(OUT_MANIFEST, manifest)

    g0 = all(p.exists() for p in required_inputs)
    g1 = OUT_ABLATION.exists() and OUT_CANDIDATE_SET.exists() and OUT_SELECTION_RULE.exists()
    g2 = OUT_SELECTED_CFG.exists() and OUT_CURVE.exists() and OUT_LEDGER.exists() and OUT_SUMMARY.exists()
    g3 = bool(selection_rule.get("winner_candidate_id")) and winner_id in set(scored_sub_df["candidate_id"].astype(str))
    g4 = OUT_REPORT.exists()
    gx = OUT_MANIFEST.exists()

    print("STEP GATES:")
    print(f"- G0_INPUTS_PRESENT: {'PASS' if g0 else 'FAIL'}")
    print(f"- G1_ABLATION_PARTICIPATION_PRESENT: {'PASS' if g1 else 'FAIL'}")
    print(f"- G2_WINNER_OUTPUTS_PRESENT: {'PASS' if g2 else 'FAIL'}")
    print(f"- G3_SELECTION_RULE_DETERMINISTIC: {'PASS' if g3 else 'FAIL'}")
    print(f"- G4_REPORT_PRESENT: {'PASS' if g4 else 'FAIL'}")
    print(f"- Gx_HASH_MANIFEST_PRESENT: {'PASS' if gx else 'FAIL'}")
    print("ARTIFACT LINKS:")
    print(f"- {OUT_ABLATION}")
    print(f"- {OUT_SELECTED_CFG}")
    print(f"- {OUT_CURVE}")
    print(f"- {OUT_LEDGER}")
    print(f"- {OUT_SUMMARY}")
    print(f"- {OUT_CANDIDATE_SET}")
    print(f"- {OUT_SELECTION_RULE}")
    print(f"- {OUT_REPORT}")
    print(f"- {OUT_MANIFEST}")
    overall = g0 and g1 and g2 and g3 and g4 and gx
    print(f"OVERALL STATUS: [[ {'PASS' if overall else 'FAIL'} ]]")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
