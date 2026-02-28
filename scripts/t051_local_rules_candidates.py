#!/usr/bin/env python3
"""T051 - Build local rule candidates by T053 states."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd


TASK_ID = "T051-LOCAL-RULE-CANDIDATES-V1"
ROOT = Path("/home/wilson/AGNO_WORKSPACE")

INPUT_T048 = ROOT / "src/data_engine/portfolio/T048_CONDITION_LEDGER_T039.parquet"
INPUT_T053 = ROOT / "src/data_engine/portfolio/T053_STATE_SERIES_CEP_SLOPE_T048.parquet"
INPUT_PROTOCOL = ROOT / "02_Knowledge_Bank/docs/process/STATE3_LOCAL_RULE_CAPTURE_PROTOCOL.md"
INPUT_SCHEMA = ROOT / "02_Knowledge_Bank/docs/process/STATE3_CONDITION_LEDGER_SCHEMA.md"
INPUT_DECISOR_SPEC = ROOT / "02_Knowledge_Bank/docs/process/STATE3_STATE_DECISOR_CEP_SLOPE_SPEC.md"

OUTPUT_PARQUET = ROOT / "src/data_engine/portfolio/T051_LOCAL_RULE_CANDIDATES_T053.parquet"
OUTPUT_REPORT = ROOT / "outputs/governanca/T051-LOCAL-RULE-CANDIDATES-V1_report.md"
OUTPUT_SPEC = ROOT / "02_Knowledge_Bank/docs/process/STATE3_LOCAL_RULE_CANDIDATES_SPEC.md"
OUTPUT_MANIFEST = ROOT / "outputs/governanca/T051-LOCAL-RULE-CANDIDATES-V1_manifest.json"
SCRIPT_PATH = ROOT / "scripts/t051_local_rules_candidates.py"

VALID_SCOPES = {"Mercado", "Master"}
VALID_STATES = {"STRESS_SPECIAL_CAUSE", "TREND_DOWN_NORMAL", "TREND_UP_NORMAL"}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def forward_sum(series: pd.Series, horizon: int) -> pd.Series:
    arr = pd.to_numeric(series, errors="coerce").to_numpy(dtype=float)
    out = np.full(len(arr), np.nan)
    for i in range(len(arr)):
        j = i + horizon
        if j >= len(arr):
            continue
        window = arr[i + 1 : j + 1]
        if np.any(~np.isfinite(window)):
            continue
        out[i] = float(window.sum())
    return pd.Series(out, index=series.index)


def forward_min_delta_dd(drawdown: pd.Series, horizon: int) -> pd.Series:
    arr = pd.to_numeric(drawdown, errors="coerce").to_numpy(dtype=float)
    out = np.full(len(arr), np.nan)
    for i in range(len(arr)):
        j = i + horizon
        if j >= len(arr):
            continue
        now = arr[i]
        window = arr[i + 1 : j + 1]
        if not np.isfinite(now) or np.any(~np.isfinite(window)):
            continue
        out[i] = float(window.min() - now)
    return pd.Series(out, index=drawdown.index)


def write_spec(path: Path) -> None:
    content = f"""# STATE 3 Local Rule Candidates Spec (T051)

## Objetivo

Materializar candidatos de regras locais por estado operacional (base T053), sem promover alteracao da engine.

## Entradas canônicas

- `T048_CONDITION_LEDGER_T039.parquet`
- `T053_STATE_SERIES_CEP_SLOPE_T048.parquet`
- Protocolo T043 e schema de ledger

## Dominio de estados (T053)

1. `STRESS_SPECIAL_CAUSE`
2. `TREND_DOWN_NORMAL`
3. `TREND_UP_NORMAL`

## Formato do artefato principal

Arquivo: `T051_LOCAL_RULE_CANDIDATES_T053.parquet`

Campos principais:
- `task_id`, `rule_rank`, `local_rule_id`
- `state_id`, `local_rule_scope`, `action_type`, `action_family`
- `trigger_json`, `exit_criteria`
- `n_fired`, `coverage_pct`
- `fwd_ret_1d_mean`, `fwd_ret_5d_mean`, `fwd_dd_delta_5d_mean`
- `candidate_score`, `coverage_min_ok`, `notes`

## Regras mandatórias

- Terminologia: `Mercado` (Ibovespa) e `Master` (carteira).
- Sem look-ahead nos gatilhos; retornos futuros apenas para avaliacao offline.
- Sem mistura de politica bull/bear no mesmo estado.

## Critério para seguir à T052

- Candidato com escopo/estado válido, trigger determinístico e cobertura mínima (`n_fired >= 10`).
- Evidência offline disponível para robustez por subperíodos na T052.
"""
    path.write_text(content, encoding="utf-8")


def build_candidates(df: pd.DataFrame) -> list[dict]:
    base_trend_down = (~df["market_special_cause_flag"]) & df["trend_down_flag"]
    base_trend_up = (~df["market_special_cause_flag"]) & (~df["trend_down_flag"])
    base_stress = df["market_special_cause_flag"]

    return [
        {
            "local_rule_id": "LR_STRESS_MKT_SPECIAL",
            "state_id": "STRESS_SPECIAL_CAUSE",
            "local_rule_scope": "Mercado",
            "action_type": "reduce_risk_exposure",
            "action_family": "defensive",
            "exit_criteria": "sair apos 3 dias consecutivos sem special_cause",
            "trigger_json": {
                "all": [
                    {"col": "market_special_cause_flag", "op": "==", "value": True},
                    {"col": "state_id", "op": "==", "value": "STRESS_SPECIAL_CAUSE"},
                ]
            },
            "trigger_mask": base_stress,
        },
        {
            "local_rule_id": "LR_STRESS_PERSIST_GT1",
            "state_id": "STRESS_SPECIAL_CAUSE",
            "local_rule_scope": "Mercado",
            "action_type": "pause_aggressive_entries",
            "action_family": "defensive",
            "exit_criteria": "sair quando persistence<2 por 2 dias",
            "trigger_json": {
                "all": [
                    {"col": "market_special_cause_flag", "op": "==", "value": True},
                    {"col": "market_signal_persistence", "op": ">=", "value": 2},
                ]
            },
            "trigger_mask": base_stress & (df["market_signal_persistence"] >= 2),
        },
        {
            "local_rule_id": "LR_DOWN_SLOPE_NEG",
            "state_id": "TREND_DOWN_NORMAL",
            "local_rule_scope": "Mercado",
            "action_type": "tighten_turnover",
            "action_family": "defensive",
            "exit_criteria": "sair apos 3 dias com slope positivo",
            "trigger_json": {
                "all": [
                    {"col": "trend_down_flag", "op": "==", "value": True},
                    {"col": "market_special_cause_flag", "op": "==", "value": False},
                    {"col": "state_id", "op": "==", "value": "TREND_DOWN_NORMAL"},
                ]
            },
            "trigger_mask": base_trend_down,
        },
        {
            "local_rule_id": "LR_DOWN_MASTER_DD15",
            "state_id": "TREND_DOWN_NORMAL",
            "local_rule_scope": "Master",
            "action_type": "increase_cash_buffer",
            "action_family": "defensive",
            "exit_criteria": "sair quando drawdown>-10%",
            "trigger_json": {
                "all": [
                    {"col": "trend_down_flag", "op": "==", "value": True},
                    {"col": "portfolio_drawdown", "op": "<=", "value": -0.15},
                ]
            },
            "trigger_mask": base_trend_down & (df["portfolio_drawdown"] <= -0.15),
        },
        {
            "local_rule_id": "LR_UP_SLOPE_POS",
            "state_id": "TREND_UP_NORMAL",
            "local_rule_scope": "Mercado",
            "action_type": "allow_normal_entries",
            "action_family": "offensive",
            "exit_criteria": "sair quando trend_down_flag=True por 2 dias",
            "trigger_json": {
                "all": [
                    {"col": "trend_down_flag", "op": "==", "value": False},
                    {"col": "market_special_cause_flag", "op": "==", "value": False},
                    {"col": "state_id", "op": "==", "value": "TREND_UP_NORMAL"},
                ]
            },
            "trigger_mask": base_trend_up,
        },
        {
            "local_rule_id": "LR_UP_LOW_CASH",
            "state_id": "TREND_UP_NORMAL",
            "local_rule_scope": "Master",
            "action_type": "maintain_risk_budget",
            "action_family": "offensive",
            "exit_criteria": "sair quando cash_weight>=20%",
            "trigger_json": {
                "all": [
                    {"col": "trend_down_flag", "op": "==", "value": False},
                    {"col": "portfolio_cash_weight", "op": "<", "value": 0.2},
                ]
            },
            "trigger_mask": base_trend_up & (df["portfolio_cash_weight"] < 0.2),
        },
    ]


def evaluate_candidates(df: pd.DataFrame, candidates: list[dict]) -> pd.DataFrame:
    rows: list[dict] = []
    for cand in candidates:
        mask = pd.Series(cand["trigger_mask"], index=df.index).fillna(False).astype(bool)
        n_fired = int(mask.sum())
        coverage_pct = float(n_fired / len(df) * 100.0)
        fwd1 = pd.to_numeric(df.loc[mask, "fwd_ret_1d"], errors="coerce")
        fwd5 = pd.to_numeric(df.loc[mask, "fwd_ret_5d"], errors="coerce")
        dd5 = pd.to_numeric(df.loc[mask, "fwd_dd_delta_5d"], errors="coerce")
        fwd1_mean = float(fwd1.mean()) if n_fired else float("nan")
        fwd5_mean = float(fwd5.mean()) if n_fired else float("nan")
        dd5_mean = float(dd5.mean()) if n_fired else float("nan")
        if cand["action_family"] == "defensive":
            score = float((-fwd5_mean if np.isfinite(fwd5_mean) else 0.0) * (coverage_pct / 100.0))
        else:
            score = float((fwd5_mean if np.isfinite(fwd5_mean) else 0.0) * (coverage_pct / 100.0))
        rows.append(
            {
                "task_id": TASK_ID,
                "local_rule_id": cand["local_rule_id"],
                "state_id": cand["state_id"],
                "local_rule_scope": cand["local_rule_scope"],
                "action_type": cand["action_type"],
                "action_family": cand["action_family"],
                "trigger_json": json.dumps(cand["trigger_json"], ensure_ascii=True, sort_keys=True),
                "exit_criteria": cand["exit_criteria"],
                "n_fired": n_fired,
                "coverage_pct": coverage_pct,
                "fwd_ret_1d_mean": fwd1_mean,
                "fwd_ret_5d_mean": fwd5_mean,
                "fwd_dd_delta_5d_mean": dd5_mean,
                "candidate_score": score,
                "coverage_min_ok": bool(n_fired >= 10),
                "notes": "offline_eval_only",
            }
        )
    out = pd.DataFrame(rows).sort_values(["state_id", "candidate_score"], ascending=[True, False]).reset_index(drop=True)
    out["rule_rank"] = out.groupby("state_id")["candidate_score"].rank(method="first", ascending=False).astype(int)
    out = out[
        [
            "task_id",
            "rule_rank",
            "local_rule_id",
            "state_id",
            "local_rule_scope",
            "action_type",
            "action_family",
            "trigger_json",
            "exit_criteria",
            "n_fired",
            "coverage_pct",
            "fwd_ret_1d_mean",
            "fwd_ret_5d_mean",
            "fwd_dd_delta_5d_mean",
            "candidate_score",
            "coverage_min_ok",
            "notes",
        ]
    ]
    return out


def write_report(path: Path, candidates_df: pd.DataFrame, joined_rows: int) -> None:
    lines = [
        f"# {TASK_ID} Report",
        "",
        "## 1) Integridade dos insumos",
        "",
        f"- Linhas no join T048+T053: {joined_rows}",
        f"- Estados detectados: {', '.join(sorted(candidates_df['state_id'].unique()))}",
        "",
        "## 2) Sumario por estado",
        "",
    ]
    by_state = (
        candidates_df.groupby("state_id", as_index=False)
        .agg(
            n_candidates=("local_rule_id", "count"),
            mean_coverage_pct=("coverage_pct", "mean"),
            n_coverage_min_ok=("coverage_min_ok", "sum"),
        )
        .sort_values("state_id")
    )
    lines.extend(by_state.to_string(index=False).splitlines())
    lines.extend(["", "## 3) Top candidatos por score", ""])
    top = candidates_df.sort_values(["state_id", "candidate_score"], ascending=[True, False]).copy()
    lines.extend(
        top[
            [
                "state_id",
                "rule_rank",
                "local_rule_id",
                "local_rule_scope",
                "action_type",
                "n_fired",
                "coverage_pct",
                "fwd_ret_5d_mean",
                "fwd_dd_delta_5d_mean",
                "candidate_score",
            ]
        ]
        .to_string(index=False)
        .splitlines()
    )
    lines.extend(
        [
            "",
            "## 4) Conformidade",
            "",
            "- G0: terminologia Master vs Mercado respeitada.",
            "- G3: triggers usam apenas colunas contemporaneas (sem look-ahead).",
            "- Nota: retornos futuros e deltas de drawdown sao usados apenas para avaliacao offline.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_gate_no_lookahead(candidates_df: pd.DataFrame) -> bool:
    forbidden_tokens = ("fwd_", "post_action", "future", "lead")
    ok = True
    for payload in candidates_df["trigger_json"].tolist():
        payload_l = payload.lower()
        if any(tok in payload_l for tok in forbidden_tokens):
            ok = False
            break
    return ok


def main() -> int:
    print(f"HEADER: {TASK_ID}")

    missing = [p for p in [INPUT_T048, INPUT_T053, INPUT_PROTOCOL, INPUT_SCHEMA, INPUT_DECISOR_SPEC] if not p.exists()]
    if missing:
        print("STEP GATES:")
        print(f"- G1_LOCAL_RULE_CANDIDATES_PRESENT: FAIL (missing inputs: {', '.join(str(x) for x in missing)})")
        print("OVERALL STATUS: [[ FAIL ]]")
        return 1

    t048 = pd.read_parquet(INPUT_T048).copy()
    t053 = pd.read_parquet(INPUT_T053).copy()
    t048["date"] = pd.to_datetime(t048["date"])
    t053["date"] = pd.to_datetime(t053["date"])
    t048 = t048.sort_values("date").drop_duplicates(subset=["date"], keep="last")
    t053 = t053.sort_values("date").drop_duplicates(subset=["date"], keep="last")

    merged = t048.merge(
        t053[
            [
                "date",
                "state_id",
                "state_entry_flag",
                "state_exit_flag",
                "state_transition_reason",
                "state_hysteresis_counter",
                "market_special_cause_flag",
                "trend_down_flag",
                "market_mu_slope",
            ]
        ],
        on="date",
        how="inner",
        suffixes=("_t048", "_t053"),
        validate="one_to_one",
    ).reset_index(drop=True)

    if len(merged) != 1902:
        print("STEP GATES:")
        print(f"- G1_LOCAL_RULE_CANDIDATES_PRESENT: FAIL (join rows={len(merged)}, expected 1902)")
        print("OVERALL STATUS: [[ FAIL ]]")
        return 1

    merged["market_special_cause_flag"] = merged["market_special_cause_flag_t053"].fillna(False).astype(bool)
    merged["trend_down_flag"] = merged["trend_down_flag"].fillna(False).astype(bool)
    merged["portfolio_drawdown"] = pd.to_numeric(merged["portfolio_drawdown"], errors="coerce")
    merged["portfolio_cash_weight"] = pd.to_numeric(merged["portfolio_cash_weight"], errors="coerce")
    merged["portfolio_logret_1d"] = pd.to_numeric(merged["portfolio_logret_1d"], errors="coerce")
    merged["market_signal_persistence"] = pd.to_numeric(merged["market_signal_persistence"], errors="coerce").fillna(0.0)

    merged["fwd_ret_1d"] = forward_sum(merged["portfolio_logret_1d"], horizon=1)
    merged["fwd_ret_5d"] = forward_sum(merged["portfolio_logret_1d"], horizon=5)
    merged["fwd_dd_delta_5d"] = forward_min_delta_dd(merged["portfolio_drawdown"], horizon=5)

    candidates = build_candidates(merged)
    candidates_df = evaluate_candidates(merged, candidates)

    OUTPUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_SPEC.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MANIFEST.parent.mkdir(parents=True, exist_ok=True)

    candidates_df.to_parquet(OUTPUT_PARQUET, index=False)
    write_report(OUTPUT_REPORT, candidates_df, joined_rows=len(merged))
    write_spec(OUTPUT_SPEC)

    manifest = {
        "task_id": TASK_ID,
        "inputs_consumed": [
            str(INPUT_T048),
            str(INPUT_T053),
            str(INPUT_PROTOCOL),
            str(INPUT_SCHEMA),
            str(INPUT_DECISOR_SPEC),
        ],
        "outputs_produced": [
            str(OUTPUT_PARQUET),
            str(OUTPUT_REPORT),
            str(OUTPUT_SPEC),
            str(OUTPUT_MANIFEST),
            str(SCRIPT_PATH),
        ],
        "hashes_sha256": {
            str(INPUT_T048): sha256_file(INPUT_T048),
            str(INPUT_T053): sha256_file(INPUT_T053),
            str(INPUT_PROTOCOL): sha256_file(INPUT_PROTOCOL),
            str(INPUT_SCHEMA): sha256_file(INPUT_SCHEMA),
            str(INPUT_DECISOR_SPEC): sha256_file(INPUT_DECISOR_SPEC),
            str(OUTPUT_PARQUET): sha256_file(OUTPUT_PARQUET),
            str(OUTPUT_REPORT): sha256_file(OUTPUT_REPORT),
            str(OUTPUT_SPEC): sha256_file(OUTPUT_SPEC),
            str(SCRIPT_PATH): sha256_file(SCRIPT_PATH),
        },
    }
    OUTPUT_MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    g0 = (
        set(candidates_df["local_rule_scope"].unique()).issubset(VALID_SCOPES)
        and set(candidates_df["state_id"].unique()).issubset(VALID_STATES)
    )
    g1 = OUTPUT_PARQUET.exists() and len(candidates_df) > 0
    g2 = OUTPUT_REPORT.exists() and OUTPUT_SPEC.exists()
    g3 = run_gate_no_lookahead(candidates_df)
    gx = OUTPUT_MANIFEST.exists()

    print("STEP GATES:")
    print(f"- G0_GLOSSARY_COMPLIANCE: {'PASS' if g0 else 'FAIL'}")
    print(f"- G1_LOCAL_RULE_CANDIDATES_PRESENT: {'PASS' if g1 else 'FAIL'}")
    print(f"- G2_REPORT_AND_SPEC_PRESENT: {'PASS' if g2 else 'FAIL'}")
    print(f"- G3_NO_LOOKAHEAD: {'PASS' if g3 else 'FAIL'}")
    print(f"- Gx_HASH_MANIFEST_PRESENT: {'PASS' if gx else 'FAIL'}")

    print("RETRY LOG:")
    print("- none")

    print("ARTIFACT LINKS:")
    print(f"- {OUTPUT_PARQUET}")
    print(f"- {OUTPUT_REPORT}")
    print(f"- {OUTPUT_SPEC}")
    print(f"- {OUTPUT_MANIFEST}")
    print(f"- {SCRIPT_PATH}")

    overall = g0 and g1 and g2 and g3 and gx
    print(f"OVERALL STATUS: [[ {'PASS' if overall else 'FAIL'} ]]")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
