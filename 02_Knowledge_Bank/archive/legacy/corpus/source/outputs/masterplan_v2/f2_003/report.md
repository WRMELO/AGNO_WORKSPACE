# Report - F2_003 Envelope Plotly Audit

- task_id: `TASK_CEP_BUNDLE_CORE_V2_F2_003_ENVELOPE_PLOTLY_AUDIT`
- generated_at_utc: `2026-02-17T08:18:01.388912+00:00`
- branch: `local/integrated-state-20260215`
- overall: `PASS`

## Validações requeridas

- Plots Plotly mínimos gerados e referenciados: `PASS`
  - evidência: `outputs/masterplan_v2/f2_003/evidence/plot_inventory.json`
- Sobreposição ENF-xxx em gráfico temporal: `PASS`
  - evidências: `outputs/masterplan_v2/f2_003/plots/envelope_timeseries.html`, `outputs/masterplan_v2/f2_002/evidence/enforcement_examples.csv`
- Comparação baseline vs V2 com evidência tabular linkada: `PASS`
  - evidência: `outputs/masterplan_v2/f2_002/evidence/metrics_compare_baseline_vs_v2.csv`
- Métricas equity/drawdown sem NaN: `PASS`
  - evidências: `outputs/masterplan_v2/f2_003/evidence/equity_compare_summary.json`, `outputs/masterplan_v2/f2_003/evidence/equity_compare_sample.csv`
- Manifest com hashes de inputs críticos: `PASS`
  - evidência: `outputs/masterplan_v2/f2_003/manifest.json`

## Equity baseline vs V2

- equity_final_baseline: `2.3854396269`
- equity_final_v2: `183.1974446034`
- delta_abs: `180.8120049765`
- delta_pct: `7579.818954%`
- mdd_baseline: `-0.6803348625`
- mdd_v2: `-0.1781568763`
- colunas usadas: baseline(date=`date`, equity=`equity`, cash=`cash`), v2(date=`date`, equity=`equity_v2`, cash=`cash_v2`, positions_value=`positions_value_ref`)

## Plotly gerados

- `outputs/masterplan_v2/f2_003/plots/envelope_timeseries.html`
- `outputs/masterplan_v2/f2_003/plots/guardrails_timeseries.html`
- `outputs/masterplan_v2/f2_003/plots/enforcement_events_timeline.html`
- `outputs/masterplan_v2/f2_003/plots/baseline_vs_v2_turnover.html`
- `outputs/masterplan_v2/f2_003/plots/baseline_vs_v2_cash_ratio.html`
- `outputs/masterplan_v2/f2_003/plots/baseline_vs_v2_exposure.html`
- `outputs/masterplan_v2/f2_003/plots/baseline_vs_v2_trade_count.html`
- `outputs/masterplan_v2/f2_003/plots/baseline_vs_v2_equity_timeseries.html`
- `outputs/masterplan_v2/f2_003/plots/baseline_vs_v2_drawdown_timeseries.html`

## Preflight

- Branch requerida: `local/integrated-state-20260215` -> `PASS`
- Repo limpo antes da execução: `PASS`
- evidência: `outputs/masterplan_v2/f2_003/evidence/preflight.json`
