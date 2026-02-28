#!/usr/bin/env python3
"""T052 - Robustness report by canonical subperiods."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


TASK_ID = "T052-ROBUSTNESS-SUBPERIODS-V1"
ROOT = Path("/home/wilson/AGNO_WORKSPACE")

INPUT_T048 = ROOT / "src/data_engine/portfolio/T048_CONDITION_LEDGER_T039.parquet"
INPUT_T053 = ROOT / "src/data_engine/portfolio/T053_STATE_SERIES_CEP_SLOPE_T048.parquet"
INPUT_T051 = ROOT / "src/data_engine/portfolio/T051_LOCAL_RULE_CANDIDATES_T053.parquet"
INPUT_T040_SUBP = ROOT / "src/data_engine/portfolio/T040_METRICS_BY_SUBPERIOD.csv"
INPUT_PROTOCOL = ROOT / "02_Knowledge_Bank/docs/process/STATE3_LOCAL_RULE_CAPTURE_PROTOCOL.md"
INPUT_T051_SPEC = ROOT / "02_Knowledge_Bank/docs/process/STATE3_LOCAL_RULE_CANDIDATES_SPEC.md"
INPUT_SPEC005 = ROOT / "02_Knowledge_Bank/docs/specs/SPEC-005_METRICS_SUITE.md"

OUTPUT_PARQUET = ROOT / "src/data_engine/portfolio/T052_RULE_ROBUSTNESS_BY_SUBPERIOD_T051.parquet"
OUTPUT_REPORT = ROOT / "outputs/governanca/T052-ROBUSTNESS-SUBPERIODS-V1_report.md"
OUTPUT_SPEC = ROOT / "02_Knowledge_Bank/docs/process/STATE3_LOCAL_RULE_ROBUSTNESS_SPEC.md"
OUTPUT_MANIFEST = ROOT / "outputs/governanca/T052-ROBUSTNESS-SUBPERIODS-V1_manifest.json"
SCRIPT_PATH = ROOT / "scripts/t052_robustness_report_subperiods.py"

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


def apply_condition(df: pd.DataFrame, cond: dict) -> pd.Series:
    col = cond["col"]
    op = cond["op"]
    val = cond["value"]
    series = df[col]
    if op == "==":
        return series == val
    if op == ">=":
        return pd.to_numeric(series, errors="coerce") >= float(val)
    if op == "<=":
        return pd.to_numeric(series, errors="coerce") <= float(val)
    if op == "<":
        return pd.to_numeric(series, errors="coerce") < float(val)
    if op == ">":
        return pd.to_numeric(series, errors="coerce") > float(val)
    raise ValueError(f"Unsupported op in trigger_json: {op}")


def build_trigger_mask(df: pd.DataFrame, trigger_json: str) -> pd.Series:
    payload = json.loads(trigger_json)
    conds = payload.get("all", [])
    if not conds:
        return pd.Series(False, index=df.index)
    mask = pd.Series(True, index=df.index)
    for cond in conds:
        mask &= apply_condition(df, cond).fillna(False)
    return mask.fillna(False).astype(bool)


def write_spec(path: Path) -> None:
    content = """# STATE 3 Local Rule Robustness Spec (T052)

## Objetivo

Avaliar robustez temporal dos candidatos locais (T051) por subperíodos canônicos do T040/SPEC-005 e emitir decisão de promoção.

## Subperíodos canônicos

Fonte obrigatória: `src/data_engine/portfolio/T040_METRICS_BY_SUBPERIOD.csv`

Usar `subperiod`, `period_start` e `period_end` sem criar cortes ad-hoc.

## Entradas

- `T048_CONDITION_LEDGER_T039.parquet`
- `T053_STATE_SERIES_CEP_SLOPE_T048.parquet`
- `T051_LOCAL_RULE_CANDIDATES_T053.parquet`
- `T040_METRICS_BY_SUBPERIOD.csv`

## Saída principal

`T052_RULE_ROBUSTNESS_BY_SUBPERIOD_T051.parquet`

Granularidade: 1 linha por `local_rule_id x subperiod`.

Campos mínimos:
- `local_rule_id`, `state_id`, `local_rule_scope`, `subperiod`, `period_start`, `period_end`
- `n_days_subperiod`, `n_fired`, `coverage_pct`
- `fwd_ret_1d_mean`, `fwd_ret_5d_mean`, `fwd_dd_delta_5d_mean`, `fwd_ret_5d_p05`
- `coverage_min_ok_subperiod`, `promotion_recommendation`, `promotion_reason`

## Regra de decisão (T052)

- `PROMOTE`: cobertura mínima (`n_fired>=10`) em pelo menos 3 subperíodos e consistência de sinal >= 60%.
- `HOLD`: cobertura mínima em 1-2 subperíodos, ou consistência insuficiente para promoção.
- `REJECT`: sem cobertura mínima em qualquer subperíodo.

## Governança

- Sem look-ahead nos triggers; métricas futuras apenas em avaliação offline.
- Terminologia mandatória: Mercado != Master.
"""
    path.write_text(content, encoding="utf-8")


def main() -> int:
    print(f"HEADER: {TASK_ID}")

    required_inputs = [
        INPUT_T048,
        INPUT_T053,
        INPUT_T051,
        INPUT_T040_SUBP,
        INPUT_PROTOCOL,
        INPUT_T051_SPEC,
        INPUT_SPEC005,
    ]
    missing = [str(p) for p in required_inputs if not p.exists()]
    if missing:
        print("STEP GATES:")
        print(f"- G1_ROBUSTNESS_PARQUET_PRESENT: FAIL (missing inputs: {', '.join(missing)})")
        print("OVERALL STATUS: [[ FAIL ]]")
        return 1

    t048 = pd.read_parquet(INPUT_T048).copy()
    t053 = pd.read_parquet(INPUT_T053).copy()
    t051 = pd.read_parquet(INPUT_T051).copy()
    t040 = pd.read_csv(INPUT_T040_SUBP).copy()

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
        print(f"- G1_ROBUSTNESS_PARQUET_PRESENT: FAIL (join rows={len(merged)}, expected 1902)")
        print("OVERALL STATUS: [[ FAIL ]]")
        return 1

    if "state_id_t053" in merged.columns:
        merged["state_id"] = merged["state_id_t053"]
    merged["market_special_cause_flag"] = merged["market_special_cause_flag_t053"].fillna(False).astype(bool)
    merged["trend_down_flag"] = merged["trend_down_flag"].fillna(False).astype(bool)
    merged["portfolio_logret_1d"] = pd.to_numeric(merged["portfolio_logret_1d"], errors="coerce")
    merged["portfolio_drawdown"] = pd.to_numeric(merged["portfolio_drawdown"], errors="coerce")
    merged["market_signal_persistence"] = pd.to_numeric(merged["market_signal_persistence"], errors="coerce").fillna(0.0)
    merged["portfolio_cash_weight"] = pd.to_numeric(merged["portfolio_cash_weight"], errors="coerce")

    merged["fwd_ret_1d"] = forward_sum(merged["portfolio_logret_1d"], horizon=1)
    merged["fwd_ret_5d"] = forward_sum(merged["portfolio_logret_1d"], horizon=5)
    merged["fwd_dd_delta_5d"] = forward_min_delta_dd(merged["portfolio_drawdown"], horizon=5)

    subp = (
        t040[["subperiod", "period_start", "period_end"]]
        .dropna(subset=["subperiod", "period_start", "period_end"])
        .drop_duplicates()
        .copy()
    )
    subp["period_start"] = pd.to_datetime(subp["period_start"])
    subp["period_end"] = pd.to_datetime(subp["period_end"])
    subp = subp.sort_values("period_start").reset_index(drop=True)

    rows = []
    for _, rule in t051.iterrows():
        trigger_json = str(rule["trigger_json"])
        rule_mask = build_trigger_mask(merged, trigger_json)
        for _, sp in subp.iterrows():
            in_sp = (merged["date"] >= sp["period_start"]) & (merged["date"] <= sp["period_end"])
            n_days = int(in_sp.sum())
            fired_mask = in_sp & rule_mask
            n_fired = int(fired_mask.sum())
            coverage_pct = float((n_fired / n_days) * 100.0) if n_days > 0 else float("nan")
            fwd1 = pd.to_numeric(merged.loc[fired_mask, "fwd_ret_1d"], errors="coerce")
            fwd5 = pd.to_numeric(merged.loc[fired_mask, "fwd_ret_5d"], errors="coerce")
            dd5 = pd.to_numeric(merged.loc[fired_mask, "fwd_dd_delta_5d"], errors="coerce")
            rows.append(
                {
                    "task_id": TASK_ID,
                    "local_rule_id": rule["local_rule_id"],
                    "state_id": rule["state_id"],
                    "local_rule_scope": rule["local_rule_scope"],
                    "action_type": rule["action_type"],
                    "action_family": rule["action_family"],
                    "subperiod": sp["subperiod"],
                    "period_start": sp["period_start"],
                    "period_end": sp["period_end"],
                    "n_days_subperiod": n_days,
                    "n_fired": n_fired,
                    "coverage_pct": coverage_pct,
                    "fwd_ret_1d_mean": float(fwd1.mean()) if n_fired else float("nan"),
                    "fwd_ret_5d_mean": float(fwd5.mean()) if n_fired else float("nan"),
                    "fwd_dd_delta_5d_mean": float(dd5.mean()) if n_fired else float("nan"),
                    "fwd_ret_5d_p05": float(fwd5.quantile(0.05)) if n_fired >= 5 else float("nan"),
                    "coverage_min_ok_subperiod": bool(n_fired >= 10),
                    "trigger_json": trigger_json,
                    "promotion_recommendation": "",
                    "promotion_reason": "",
                }
            )

    out = pd.DataFrame(rows)

    rec_map: dict[str, tuple[str, str]] = {}
    for rid, grp in out.groupby("local_rule_id"):
        coverage_ok = grp["coverage_min_ok_subperiod"].fillna(False)
        n_cov_ok = int(coverage_ok.sum())
        eval_grp = grp[coverage_ok].copy()
        expected_positive = bool(grp["action_family"].iloc[0] == "offensive")
        if len(eval_grp) > 0:
            if expected_positive:
                consistency = float((eval_grp["fwd_ret_5d_mean"] > 0).mean())
            else:
                consistency = float((eval_grp["fwd_ret_5d_mean"] < 0).mean())
        else:
            consistency = 0.0

        if n_cov_ok >= 3 and consistency >= 0.6:
            rec = "PROMOTE"
            reason = f"coverage_ok_subperiods={n_cov_ok}, consistency={consistency:.2f}"
        elif n_cov_ok >= 1:
            rec = "HOLD"
            reason = f"coverage_ok_subperiods={n_cov_ok}, consistency={consistency:.2f}"
        else:
            rec = "REJECT"
            reason = "no subperiod reached minimum coverage (n_fired>=10)"
        rec_map[rid] = (rec, reason)

    out["promotion_recommendation"] = out["local_rule_id"].map(lambda x: rec_map[x][0])
    out["promotion_reason"] = out["local_rule_id"].map(lambda x: rec_map[x][1])
    out = out.sort_values(["local_rule_id", "period_start"]).reset_index(drop=True)

    OUTPUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_SPEC.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MANIFEST.parent.mkdir(parents=True, exist_ok=True)

    out.to_parquet(OUTPUT_PARQUET, index=False)
    write_spec(OUTPUT_SPEC)

    rule_decisions = (
        out[["local_rule_id", "state_id", "local_rule_scope", "action_family", "promotion_recommendation", "promotion_reason"]]
        .drop_duplicates()
        .sort_values(["promotion_recommendation", "local_rule_id"])
    )
    coverage_table = (
        out.groupby(["local_rule_id", "subperiod"], as_index=False)
        .agg(n_fired=("n_fired", "sum"), coverage_pct=("coverage_pct", "mean"), fwd_ret_5d_mean=("fwd_ret_5d_mean", "mean"))
        .sort_values(["local_rule_id", "subperiod"])
    )
    lines = [
        f"# {TASK_ID} Report",
        "",
        "## 1) Subperiodos canônicos (fonte T040/SPEC-005)",
        "",
        f"- Quantidade de subperiodos: {subp['subperiod'].nunique()}",
        f"- Lista: {', '.join(subp['subperiod'].tolist())}",
        "",
        "## 2) Decisao por regra",
        "",
    ]
    lines.extend(rule_decisions.to_string(index=False).splitlines())
    lines.extend(["", "## 3) Robustez por regra x subperiodo (amostra)", ""])
    lines.extend(coverage_table.to_string(index=False).splitlines())
    lines.extend(
        [
            "",
            "## 4) Notas de governança",
            "",
            "- Triggers reconstruidos a partir de `trigger_json` (T051), sem look-ahead.",
            "- Retornos futuros usados apenas para avaliacao offline.",
            "- Terminologia Mercado/Master preservada.",
        ]
    )
    OUTPUT_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    manifest = {
        "task_id": TASK_ID,
        "inputs_consumed": [str(p) for p in required_inputs],
        "outputs_produced": [
            str(OUTPUT_PARQUET),
            str(OUTPUT_REPORT),
            str(OUTPUT_SPEC),
            str(OUTPUT_MANIFEST),
            str(SCRIPT_PATH),
        ],
        "hashes_sha256": {
            **{str(p): sha256_file(p) for p in required_inputs},
            str(OUTPUT_PARQUET): sha256_file(OUTPUT_PARQUET),
            str(OUTPUT_REPORT): sha256_file(OUTPUT_REPORT),
            str(OUTPUT_SPEC): sha256_file(OUTPUT_SPEC),
            str(SCRIPT_PATH): sha256_file(SCRIPT_PATH),
        },
    }
    OUTPUT_MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    g0 = (
        set(out["local_rule_scope"].dropna().unique()).issubset(VALID_SCOPES)
        and set(out["state_id"].dropna().unique()).issubset(VALID_STATES)
    )
    g1 = OUTPUT_PARQUET.exists() and (len(out) >= len(t051) * subp["subperiod"].nunique())
    g2 = OUTPUT_REPORT.exists() and OUTPUT_SPEC.exists()
    g3 = (
        not subp.empty
        and set(subp.columns) == {"subperiod", "period_start", "period_end"}
        and out["subperiod"].isin(subp["subperiod"]).all()
    )
    gx = OUTPUT_MANIFEST.exists()

    print("STEP GATES:")
    print(f"- G0_GLOSSARY_COMPLIANCE: {'PASS' if g0 else 'FAIL'}")
    print(f"- G1_ROBUSTNESS_PARQUET_PRESENT: {'PASS' if g1 else 'FAIL'}")
    print(f"- G2_REPORT_AND_SPEC_PRESENT: {'PASS' if g2 else 'FAIL'}")
    print(f"- G3_SUBPERIODS_CANONICAL: {'PASS' if g3 else 'FAIL'}")
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
