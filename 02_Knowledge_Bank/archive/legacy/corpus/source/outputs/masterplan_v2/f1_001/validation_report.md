# Validation Report - F1_001 Ledger Daily Portfolio Integrity

- task_id: `TASK_CEP_BUNDLE_CORE_V2_F1_001_LEDGER_DAILY_PORTFOLIO_INTEGRITY`
- generated_at_utc: `2026-02-16T23:23:39.432146+00:00`
- branch: `local/integrated-state-20260215`
- overall: `PASS`

## Resultado das validações requeridas

- Custo operacional 0.00025 por trade (BUY/SELL): `PASS`
  - evidências: `outputs/masterplan_v2/f1_001/evidence/cost_validation_sample.csv`, `outputs/masterplan_v2/f1_001/evidence/cost_validation_summary.json`
- CDI diário no caixa: `PASS`
  - evidências: `outputs/masterplan_v2/f1_001/evidence/cdi_validation_sample.csv`, `outputs/masterplan_v2/f1_001/evidence/cdi_validation_summary.json`
- Liquidação T+0 operacional (SELL credita caixa no mesmo passo): `PASS`
  - evidências: `outputs/masterplan_v2/f1_001/evidence/t0_liquidity_sample.csv`, `outputs/masterplan_v2/f1_001/evidence/t0_liquidity_summary.json`
- Restrição de caixa (sem BUY com caixa insuficiente / sem caixa negativo): `PASS`
  - evidências: `outputs/masterplan_v2/f1_001/evidence/cash_constraint_sample.csv`, `outputs/masterplan_v2/f1_001/evidence/cash_constraint_summary.json`
- Cadência de compra (BUY somente a cada 3 sessões): `PASS`
  - evidências: `outputs/masterplan_v2/f1_001/evidence/buy_cadence_check.csv`, `outputs/masterplan_v2/f1_001/evidence/buy_cadence_summary.json`
- Integridade contábil (equity = MTM + caixa, por reconstrução disponível): `PASS`
  - evidências: `outputs/masterplan_v2/f1_001/evidence/equity_reconciliation_sample.csv`, `outputs/masterplan_v2/f1_001/evidence/equity_reconciliation_summary.json`

## Preflight

- Branch requerida: `local/integrated-state-20260215` -> `PASS`
- Repo limpo antes da execução: `FAIL`
- evidência: `outputs/masterplan_v2/f1_001/evidence/preflight.json`

## Observações

- Esta task usa evidências de ledger/daily_portfolio do legado e série diária instrumentada do bundle.
- Baseline M3 readonly validado por hash before/after.
