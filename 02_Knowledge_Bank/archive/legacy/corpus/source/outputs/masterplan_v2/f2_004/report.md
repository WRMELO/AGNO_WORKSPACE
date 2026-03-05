# Report - F2_004 Equity CDI Sanity and Reconciliation Gate

- task_id: `TASK_CEP_BUNDLE_CORE_V2_F2_004_EQUITY_CDI_SANITY_AND_RECONCILIATION_GATE`
- generated_at_utc: `2026-02-17T08:48:16.999269+00:00`
- branch: `local/integrated-state-20260215`
- overall: `PASS`

## Gates

- `GATE_CDI_PLAUSIBILITY`: `PASS`
  - evidência: `outputs/masterplan_v2/f2_004/evidence/cdi_daily_stats.json`
- `GATE_CASH_ONLY_BENCHMARK`: `PASS`
  - evidências: `outputs/masterplan_v2/f2_004/evidence/cash_only_benchmark.csv`, `outputs/masterplan_v2/f2_004/evidence/cash_only_benchmark_summary.json`
- `GATE_CASH_FLOW_RECONCILIATION`: `PASS`
  - evidências: `outputs/masterplan_v2/f2_004/evidence/cash_flow_reconciliation_sample.csv`, `outputs/masterplan_v2/f2_004/evidence/cash_flow_reconciliation_summary.json`
- `GATE_EQUITY_RECONCILIATION`: `PASS`
  - evidências: `outputs/masterplan_v2/f2_004/evidence/equity_reconciliation_sample.csv`, `outputs/masterplan_v2/f2_004/evidence/equity_reconciliation_summary.json`
- `GATE_EQUITY_NORMALIZATION`: `PASS`
  - evidência: `outputs/masterplan_v2/f2_004/evidence/equity_normalization_summary.json`
- `GATE_PLOTS_PRESENT`: `PASS`
  - evidência: `outputs/masterplan_v2/f2_004/plots/baseline_vs_v2_equity_timeseries_recomputed.html`

## Decisão de bloqueio

- `block_f3_f4`: `false`

## Preflight

- Branch requerida: `local/integrated-state-20260215` -> `PASS`
- Repo limpo antes da execução: `PASS`
