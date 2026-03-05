# Report - F2_001 Envelope Continuo Implementation

- task_id: `TASK_CEP_BUNDLE_CORE_V2_F2_001_ENVELOPE_CONTINUO_IMPLEMENTATION`
- generated_at_utc: `2026-02-17T07:40:36.614126+00:00`
- branch: `local/integrated-state-20260215`
- overall: `PASS`

## Validações requeridas

- Envelope contínuo persistido e com range [0,1]: `PASS`
  - evidências: `outputs/masterplan_v2/f2_001/envelope_daily.csv`, `outputs/masterplan_v2/f2_001/evidence/envelope_validations_summary.json`
- Guardrails anti-deriva materializados (histerese, turnover cap, anti-reentry, fallback): `PASS`
  - evidências: `outputs/masterplan_v2/f2_001/evidence/guardrails_parameters.json`, `outputs/masterplan_v2/f2_001/evidence/envelope_daily_sample.csv`
- Rastreabilidade com evidências e hashes no manifest: `PASS`
  - evidências: `outputs/masterplan_v2/f2_001/manifest.json`, `outputs/masterplan_v2/f2_001/evidence/input_presence.json`

## Parâmetros explícitos carregados

- `dd_on`: `-0.2`
- `dd_off`: `-0.1`
- `turnover_cap_by_regime`: `{'W1': 0.22, 'W2': 0.12, 'W3': 0.15, 'OTHER': 0.16}`
- `anti_reentry_stress_multiplier`: `0.8`
- `fallback_recovery_window_sessions`: `10`

## Preflight

- Branch requerida: `local/integrated-state-20260215` -> `PASS`
- Repo limpo antes da execução: `PASS`
- evidência: `outputs/masterplan_v2/f2_001/evidence/preflight.json`
