# Report - F1_002 Accounting Plotly Decomposition

- task_id: `TASK_CEP_BUNDLE_CORE_V2_F1_002_ACCOUNTING_PLOTLY_DECOMPOSITION`
- generated_at_utc: `2026-02-16T23:28:46.169667+00:00`
- branch: `local/integrated-state-20260215`
- overall: `PASS`

## Validações requeridas

- Decomposição contábil (equity = posições_MTM + caixa): `PASS`
  - evidências: `outputs/masterplan_v2/f1_002/evidence/decomposition_sample.csv`, `outputs/masterplan_v2/f1_002/evidence/validations_summary.json`
- Custo 0.025% (série cumulativa + amostras): `PASS`
  - evidências: `outputs/masterplan_v2/f1_002/plots/cumulative_costs_timeseries.html`, `outputs/masterplan_v2/f1_002/evidence/decomposition_sample.csv`
- CDI no caixa (diário + cumulativo): `PASS`
  - evidências: `outputs/masterplan_v2/f1_002/plots/cdi_accrual_timeseries.html`, `outputs/masterplan_v2/f1_002/evidence/decomposition_sample.csv`
- Cadência BUY (checagem tabular + marcação visual): `PASS`
  - evidências: `outputs/masterplan_v2/f1_002/evidence/buy_cadence_check.csv`, `outputs/masterplan_v2/f1_002/plots/turnover_timeseries.html`
- Compra só com caixa (check resumido cash >= 0): `PASS`
  - evidência: `outputs/masterplan_v2/f1_002/evidence/validations_summary.json`

## Plotly gerados

- `outputs/masterplan_v2/f1_002/plots/equity_vs_cash_timeseries.html`
- `outputs/masterplan_v2/f1_002/plots/cumulative_costs_timeseries.html`
- `outputs/masterplan_v2/f1_002/plots/cdi_accrual_timeseries.html`
- `outputs/masterplan_v2/f1_002/plots/positions_value_timeseries.html`
- `outputs/masterplan_v2/f1_002/plots/turnover_timeseries.html`

## Preflight

- Branch requerida: `local/integrated-state-20260215` -> `PASS`
- Repo limpo antes da execução: `PASS`
- evidência: `outputs/masterplan_v2/f1_002/evidence/preflight.json`
