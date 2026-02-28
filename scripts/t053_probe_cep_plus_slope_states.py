#!/usr/bin/env python3
"""T053 - Probe CEP + Slope joint states before T051."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


TASK_ID = "T053-CEP-SLOPE-STATE-TESTS-V1"
ROOT = Path("/home/wilson/AGNO_WORKSPACE")
INPUT_T048 = ROOT / "src/data_engine/portfolio/T048_CONDITION_LEDGER_T039.parquet"
INPUT_T050 = ROOT / "src/data_engine/portfolio/T050_STATE_SERIES_T048.parquet"
OUTPUT_STATE = ROOT / "src/data_engine/portfolio/T053_STATE_SERIES_CEP_SLOPE_T048.parquet"
OUTPUT_REPORT = ROOT / "outputs/governanca/T053-CEP-SLOPE-STATE-TESTS-V1_report.md"
OUTPUT_MANIFEST = ROOT / "outputs/governanca/T053-CEP-SLOPE-STATE-TESTS-V1_manifest.json"
OUTPUT_SPEC = ROOT / "02_Knowledge_Bank/docs/process/STATE3_STATE_DECISOR_CEP_SLOPE_SPEC.md"
SCRIPT_PATH = ROOT / "scripts/t053_probe_cep_plus_slope_states.py"

MU_WINDOW = 62
SLOPE_WINDOW = 20
IN_HYST_DAYS = 2
OUT_HYST_DAYS = 3


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def rolling_slope(y: pd.Series, w: int) -> pd.Series:
    x = np.arange(w, dtype=float)
    xc = x - x.mean()
    denom = (xc**2).sum()
    arr = y.to_numpy(dtype=float)
    out = np.full(len(arr), np.nan)
    for i in range(w - 1, len(arr)):
        window = arr[i - w + 1 : i + 1]
        if np.any(~np.isfinite(window)):
            continue
        yw = window - window.mean()
        out[i] = float((xc * yw).sum() / denom)
    return pd.Series(out, index=y.index)


def episode_count_from_state(state: pd.Series) -> int:
    if len(state) == 0:
        return 0
    return int(state.ne(state.shift(1)).astype(int).cumsum().max())


def write_spec(path: Path) -> None:
    content = f"""# STATE 3 State Decisor CEP+SLOPE Spec (T053 probe)

## Objetivo

Executar probe de estados conjuntos para aumentar sensibilidade a deriva lenta antes da T051.

## Princípio constitucional

- CEP permanece fundamentado em `X_t = log(Close_t/Close_t-1)` (logret).
- O `slope` usado aqui e **derivado de X_t**, nao substitui a variavel fundamental.
- Nao usar preco bruto como variavel de controle.

## Sinais derivados

- `market_mu_w = rolling_mean(market_logret_1d, w={MU_WINDOW})`
- `market_mu_slope = rolling_slope(market_mu_w, w={SLOPE_WINDOW})`
- `trend_down_flag`: histerese deterministica sobre `market_mu_slope < 0` com `IN={IN_HYST_DAYS}` e `OUT={OUT_HYST_DAYS}`.

## Estados conjuntos (mutuamente exclusivos)

1. `STRESS_SPECIAL_CAUSE` (quando `market_special_cause_flag == True`)
2. `TREND_DOWN_NORMAL` (sem stress, mas `trend_down_flag == True`)
3. `TREND_UP_NORMAL` (sem stress, `trend_down_flag == False`)

## Regras de transicao

- Prioridade de estado: Stress > TrendDown > TrendUp.
- Sem look-ahead: toda decisao usa apenas informacao ate t.

## Entregáveis do probe

- Serie de estados diaria (`T053_STATE_SERIES_CEP_SLOPE_T048.parquet`)
- Relatorio comparando granularidade de episodios (`T050` vs `T053`)
- Manifesto SHA256 para rastreabilidade
"""
    path.write_text(content, encoding="utf-8")


def main() -> int:
    print(f"HEADER: {TASK_ID}")

    if not INPUT_T048.exists():
        print("STEP GATES:")
        print("- G1_STATE_SERIES_PRESENT: FAIL (missing T048 input)")
        print("OVERALL STATUS: [[ FAIL ]]")
        return 1

    df = pd.read_parquet(INPUT_T048).copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)

    logret = pd.to_numeric(df["market_logret_1d"], errors="coerce").fillna(0.0)
    special = df["market_special_cause_flag"].fillna(False).astype(bool)

    df["market_mu_w"] = logret.rolling(MU_WINDOW, min_periods=20).mean()
    df["market_mu_slope"] = rolling_slope(df["market_mu_w"], SLOPE_WINDOW)

    in_streak = 0
    out_streak = 0
    trend_down = False
    trend_flags: list[bool] = []
    hysteresis_ctr: list[int] = []
    reasons: list[str] = []

    for slope in df["market_mu_slope"].fillna(0.0).to_numpy():
        reason = ""
        if not trend_down:
            in_streak = in_streak + 1 if slope < 0 else 0
            if in_streak >= IN_HYST_DAYS:
                trend_down = True
                in_streak = 0
                out_streak = 0
                reason = f"enter_trend_down_after_{IN_HYST_DAYS}"
            ctr = in_streak
        else:
            out_streak = out_streak + 1 if slope > 0 else 0
            if out_streak >= OUT_HYST_DAYS:
                trend_down = False
                out_streak = 0
                in_streak = 0
                reason = f"exit_trend_down_after_{OUT_HYST_DAYS}"
            ctr = out_streak

        trend_flags.append(bool(trend_down))
        hysteresis_ctr.append(int(ctr))
        reasons.append(reason)

    trend_flags_s = pd.Series(trend_flags, index=df.index)
    state_id = np.where(
        special,
        "STRESS_SPECIAL_CAUSE",
        np.where(trend_flags_s, "TREND_DOWN_NORMAL", "TREND_UP_NORMAL"),
    )

    state_df = pd.DataFrame(
        {
            "date": df["date"],
            "state_id": state_id,
            "state_entry_flag": pd.Series(state_id).ne(pd.Series(state_id).shift(1)).fillna(True),
            "state_exit_flag": pd.Series(state_id).ne(pd.Series(state_id).shift(1)).fillna(True),
            "state_transition_reason": reasons,
            "state_hysteresis_counter": hysteresis_ctr,
            "market_special_cause_flag": special.astype(bool),
            "market_mu_w": df["market_mu_w"],
            "market_mu_slope": df["market_mu_slope"],
            "trend_down_flag": trend_flags_s.astype(bool),
        }
    ).sort_values("date")

    OUTPUT_STATE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_SPEC.parent.mkdir(parents=True, exist_ok=True)

    state_df.to_parquet(OUTPUT_STATE, index=False)
    write_spec(OUTPUT_SPEC)

    t050_episodes = None
    if INPUT_T050.exists():
        t050 = pd.read_parquet(INPUT_T050).sort_values("date").reset_index(drop=True)
        t050_episodes = episode_count_from_state(t050["state_id"])

    t053_episodes = episode_count_from_state(state_df["state_id"])
    post = state_df[state_df["date"] >= pd.Timestamp("2021-08-01")]
    post_episodes = episode_count_from_state(post["state_id"]) if len(post) > 0 else 0
    down_frac_post = float((post["trend_down_flag"] == True).mean()) if len(post) > 0 else float("nan")

    report_lines = [
        f"# {TASK_ID} Report",
        "",
        "## 1) Contagem de episodios por metodo",
        "",
        f"- T050 (FSM especial-causa): {t050_episodes if t050_episodes is not None else 'N/A'} episodios",
        f"- T053 (CEP+SLOPE): {t053_episodes} episodios",
        "",
        "## 2) Cobertura pos-2021-08-01",
        "",
        f"- Dias no corte: {len(post)}",
        f"- Episodios no corte (T053): {post_episodes}",
        f"- Fracao de dias com `trend_down_flag=true`: {down_frac_post:.6f}",
        "",
        "## 3) Parametros testados",
        "",
        f"- MU_WINDOW={MU_WINDOW}",
        f"- SLOPE_WINDOW={SLOPE_WINDOW}",
        f"- IN_HYST_DAYS={IN_HYST_DAYS}",
        f"- OUT_HYST_DAYS={OUT_HYST_DAYS}",
        "",
        "## 4) Distribuicao de estados T053",
        "",
        state_df["state_id"].value_counts().to_string(),
        "",
        "## 5) Nota",
        "",
        "- Probe para decisao de desenho do decisor antes da T051; nao promove regra local nesta task.",
    ]
    OUTPUT_REPORT.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    valid_states = {"STRESS_SPECIAL_CAUSE", "TREND_DOWN_NORMAL", "TREND_UP_NORMAL"}
    g0 = set(state_df["state_id"].unique()).issubset(valid_states) and all(
        not c.startswith("master_") for c in state_df.columns
    )
    g1 = OUTPUT_STATE.exists() and state_df["date"].is_unique and state_df["state_id"].notna().all()
    g2 = OUTPUT_SPEC.exists() and OUTPUT_REPORT.exists()
    manifest = {
        "task_id": TASK_ID,
        "inputs_consumed": [str(INPUT_T048)] + ([str(INPUT_T050)] if INPUT_T050.exists() else []),
        "outputs_produced": [
            str(OUTPUT_STATE),
            str(OUTPUT_REPORT),
            str(OUTPUT_SPEC),
            str(OUTPUT_MANIFEST),
            str(SCRIPT_PATH),
        ],
        "hashes_sha256": {
            str(INPUT_T048): sha256_file(INPUT_T048),
            str(OUTPUT_STATE): sha256_file(OUTPUT_STATE),
            str(OUTPUT_REPORT): sha256_file(OUTPUT_REPORT),
            str(OUTPUT_SPEC): sha256_file(OUTPUT_SPEC),
            str(SCRIPT_PATH): sha256_file(SCRIPT_PATH),
            **({str(INPUT_T050): sha256_file(INPUT_T050)} if INPUT_T050.exists() else {}),
        },
        "params": {
            "MU_WINDOW": MU_WINDOW,
            "SLOPE_WINDOW": SLOPE_WINDOW,
            "IN_HYST_DAYS": IN_HYST_DAYS,
            "OUT_HYST_DAYS": OUT_HYST_DAYS,
        },
    }
    OUTPUT_MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    gx = OUTPUT_MANIFEST.exists()

    print("STEP GATES:")
    print(f"- G0_GLOSSARY_AND_STATE_DOMAIN: {'PASS' if g0 else 'FAIL'}")
    print(f"- G1_STATE_SERIES_PRESENT: {'PASS' if g1 else 'FAIL'}")
    print(f"- G2_REPORT_AND_SPEC_PRESENT: {'PASS' if g2 else 'FAIL'}")
    print(f"- Gx_HASH_MANIFEST_PRESENT: {'PASS' if gx else 'FAIL'}")

    print("RETRY LOG:")
    print("- none")

    print("ARTIFACT LINKS:")
    print(f"- {OUTPUT_STATE}")
    print(f"- {OUTPUT_REPORT}")
    print(f"- {OUTPUT_SPEC}")
    print(f"- {OUTPUT_MANIFEST}")
    print(f"- {SCRIPT_PATH}")

    overall = g0 and g1 and g2 and gx
    print(f"OVERALL STATUS: [[ {'PASS' if overall else 'FAIL'} ]]")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
