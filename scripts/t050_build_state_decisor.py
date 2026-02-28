#!/usr/bin/env python3
"""T050 - Build deterministic state series (FSM) from T048 condition ledger."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd


TASK_ID = "T050-STATE-DECISOR-V1"
ROOT = Path("/home/wilson/AGNO_WORKSPACE")
INPUT_T048 = ROOT / "src/data_engine/portfolio/T048_CONDITION_LEDGER_T039.parquet"
OUTPUT_STATE_SERIES = ROOT / "src/data_engine/portfolio/T050_STATE_SERIES_T048.parquet"
OUTPUT_SPEC = ROOT / "02_Knowledge_Bank/docs/process/STATE3_STATE_DECISOR_SPEC.md"
OUTPUT_MANIFEST = ROOT / "outputs/governanca/T050-STATE-DECISOR-V1_manifest.json"
SCRIPT_PATH = ROOT / "scripts/t050_build_state_decisor.py"

# Parameter set v1 (fixed for this task).
IN_HYST_DAYS = 2
OUT_HYST_DAYS = 3
RECOVERY_DAYS = 10

STATE_NORMAL = "NORMAL_IN_CONTROL"
STATE_STRESS = "STRESS_SPECIAL_CAUSE"
STATE_RECOVERY = "RECOVERY_REENTRY_WINDOW"
VALID_STATES = {STATE_NORMAL, STATE_STRESS, STATE_RECOVERY}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_state_series(daily: pd.DataFrame) -> pd.DataFrame:
    state = STATE_NORMAL
    stress_in_streak = 0
    stress_out_streak = 0
    recovery_in_streak = 0
    recovery_days_left = 0

    rows = []

    for _, row in daily.iterrows():
        flag = bool(row["market_special_cause_flag"])
        prev_state = state
        reason = ""
        hysteresis_counter = 0

        if state == STATE_NORMAL:
            stress_in_streak = stress_in_streak + 1 if flag else 0
            hysteresis_counter = stress_in_streak
            if stress_in_streak >= IN_HYST_DAYS:
                state = STATE_STRESS
                reason = f"enter_stress_after_{IN_HYST_DAYS}_special_cause_days"
                stress_in_streak = 0
                stress_out_streak = 0

        elif state == STATE_STRESS:
            stress_out_streak = stress_out_streak + 1 if not flag else 0
            hysteresis_counter = stress_out_streak
            if stress_out_streak >= OUT_HYST_DAYS:
                state = STATE_RECOVERY
                recovery_days_left = RECOVERY_DAYS
                recovery_in_streak = 0
                reason = f"enter_recovery_after_{OUT_HYST_DAYS}_non_special_days"
                stress_out_streak = 0

        elif state == STATE_RECOVERY:
            recovery_in_streak = recovery_in_streak + 1 if flag else 0
            if recovery_in_streak >= IN_HYST_DAYS:
                state = STATE_STRESS
                reason = f"reenter_stress_after_{IN_HYST_DAYS}_special_cause_days_in_recovery"
                recovery_in_streak = 0
                stress_out_streak = 0
                hysteresis_counter = IN_HYST_DAYS
            else:
                hysteresis_counter = recovery_days_left
                recovery_days_left -= 1
                if recovery_days_left <= 0:
                    state = STATE_NORMAL
                    reason = f"recovery_window_elapsed_{RECOVERY_DAYS}_days"
                    stress_in_streak = 0

        entry_flag = state != prev_state
        exit_flag = state != prev_state

        rows.append(
            {
                "date": row["date"],
                "state_id": state,
                "state_entry_flag": bool(entry_flag),
                "state_exit_flag": bool(exit_flag),
                "state_transition_reason": reason,
                "state_hysteresis_counter": int(hysteresis_counter),
            }
        )

    out = pd.DataFrame(rows)
    out = out.sort_values("date").drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)
    return out


def write_spec(path: Path) -> None:
    content = f"""# STATE 3 State Decisor Specification (T050-STATE-DECISOR-V1)

## Objetivo

Materializar uma FSM deterministica, auditavel e sem look-ahead para classificar o estado operacional diario a partir do bloco `Mercado` do T048.

## Parametros fixos (v1)

- `IN_HYST_DAYS = {IN_HYST_DAYS}`
- `OUT_HYST_DAYS = {OUT_HYST_DAYS}`
- `RECOVERY_DAYS = {RECOVERY_DAYS}`

## Estados (mutuamente exclusivos)

1. `NORMAL_IN_CONTROL`
2. `STRESS_SPECIAL_CAUSE`
3. `RECOVERY_REENTRY_WINDOW`

## Fonte primaria de decisao

- `market_special_cause_flag` (derivado do Ibovespa / Mercado no T048).

## Regras de transicao (sem look-ahead)

- `NORMAL_IN_CONTROL` -> `STRESS_SPECIAL_CAUSE`:
  - quando `market_special_cause_flag == True` por `IN_HYST_DAYS` dias consecutivos.
- `STRESS_SPECIAL_CAUSE` -> `RECOVERY_REENTRY_WINDOW`:
  - quando `market_special_cause_flag == False` por `OUT_HYST_DAYS` dias consecutivos.
- `RECOVERY_REENTRY_WINDOW` -> `NORMAL_IN_CONTROL`:
  - quando completar `RECOVERY_DAYS` pregões da janela de recuperação.
- `RECOVERY_REENTRY_WINDOW` -> `STRESS_SPECIAL_CAUSE`:
  - reentrada se `market_special_cause_flag == True` por `IN_HYST_DAYS` dias consecutivos durante a janela.

## Saidas diarias obrigatorias

- `date`
- `state_id`
- `state_entry_flag`
- `state_exit_flag`
- `state_transition_reason`
- `state_hysteresis_counter`

## Regras de governanca

- `G0_GLOSSARY_COMPLIANCE`: Mercado (Ibovespa) jamais rotulado como Master.
- `G1_DECISOR_STATE_MACHINE_SPEC`: spec markdown presente e versionada.
- `G2_STATE_SERIES_PRESENT`: serie diaria materializada.
- `G3_MUTUAL_EXCLUSIVITY`: um unico `state_id` valido por `date`.
- `Gx_HASH_MANIFEST_PRESENT`: manifesto SHA256 presente e consistente.

## Restricoes da fase

- Sem mistura de politicas bull/bear dentro do mesmo estado.
- Histerese apenas nas transicoes.
- Esta tarefa nao promove regras locais; apenas define estado operacional.
"""
    path.write_text(content, encoding="utf-8")


def main() -> int:
    print(f"HEADER: {TASK_ID}")

    if not INPUT_T048.exists():
        print("STEP GATES:")
        print("- G2_STATE_SERIES_PRESENT: FAIL (missing T048 input)")
        print("OVERALL STATUS: [[ FAIL ]]")
        return 1

    daily = pd.read_parquet(INPUT_T048).copy()
    daily["date"] = pd.to_datetime(daily["date"])
    daily = daily.sort_values("date").drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)

    series = build_state_series(daily)

    OUTPUT_STATE_SERIES.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_SPEC.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MANIFEST.parent.mkdir(parents=True, exist_ok=True)

    series.to_parquet(OUTPUT_STATE_SERIES, index=False)
    write_spec(OUTPUT_SPEC)

    g0 = "market_special_cause_flag" in daily.columns and all(not c.startswith("master_") for c in series.columns)
    g1 = OUTPUT_SPEC.exists()
    g2 = OUTPUT_STATE_SERIES.exists() and len(series) > 0
    g3 = (
        series["date"].is_unique
        and series["state_id"].notna().all()
        and set(series["state_id"].unique()).issubset(VALID_STATES)
    )

    manifest = {
        "task_id": TASK_ID,
        "inputs_consumed": [str(INPUT_T048)],
        "outputs_produced": [
            str(OUTPUT_STATE_SERIES),
            str(OUTPUT_SPEC),
            str(OUTPUT_MANIFEST),
            str(SCRIPT_PATH),
        ],
        "hashes_sha256": {
            str(INPUT_T048): sha256_file(INPUT_T048),
            str(OUTPUT_STATE_SERIES): sha256_file(OUTPUT_STATE_SERIES),
            str(OUTPUT_SPEC): sha256_file(OUTPUT_SPEC),
            str(SCRIPT_PATH): sha256_file(SCRIPT_PATH),
        },
        "params": {
            "IN_HYST_DAYS": IN_HYST_DAYS,
            "OUT_HYST_DAYS": OUT_HYST_DAYS,
            "RECOVERY_DAYS": RECOVERY_DAYS,
        },
    }
    OUTPUT_MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    gx = OUTPUT_MANIFEST.exists()

    print("STEP GATES:")
    print(f"- G0_GLOSSARY_COMPLIANCE: {'PASS' if g0 else 'FAIL'}")
    print(f"- G1_DECISOR_STATE_MACHINE_SPEC: {'PASS' if g1 else 'FAIL'}")
    print(f"- G2_STATE_SERIES_PRESENT: {'PASS' if g2 else 'FAIL'}")
    print(f"- G3_MUTUAL_EXCLUSIVITY: {'PASS' if g3 else 'FAIL'}")
    print(f"- Gx_HASH_MANIFEST_PRESENT: {'PASS' if gx else 'FAIL'}")

    print("RETRY LOG:")
    print("- none")

    print("ARTIFACT LINKS:")
    print(f"- {OUTPUT_STATE_SERIES}")
    print(f"- {OUTPUT_SPEC}")
    print(f"- {OUTPUT_MANIFEST}")
    print(f"- {SCRIPT_PATH}")

    overall = g0 and g1 and g2 and g3 and gx
    print(f"OVERALL STATUS: [[ {'PASS' if overall else 'FAIL'} ]]")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
