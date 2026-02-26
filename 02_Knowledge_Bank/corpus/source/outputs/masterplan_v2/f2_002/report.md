# Report - F2_002 Executor Cash and Cadence Enforcement

- task_id: `TASK_CEP_BUNDLE_CORE_V2_F2_002_EXECUTOR_CASH_AND_CADENCE_ENFORCEMENT`
- generated_at_utc: `2026-02-17T07:49:16.226613+00:00`
- branch: `local/integrated-state-20260215`
- overall: `PASS`

## Validações requeridas

- Consumo de `envelope_daily.csv` e `guardrails_parameters.json` com rastreabilidade: `PASS`
  - evidências: `outputs/masterplan_v2/f2_002/evidence/input_presence.json`, `outputs/masterplan_v2/f2_002/manifest.json`
- Enforcement com exemplos concretos por guardrail (>=3): `PASS`
  - evidências: `outputs/masterplan_v2/f2_002/evidence/enforcement_examples.csv`, `outputs/masterplan_v2/f2_002/evidence/enforcement_events.csv`
- Revalidação das invariantes (custo, CDI, T+0, cadência, caixa): `PASS`
  - evidências: `outputs/masterplan_v2/f2_002/evidence/invariants_summary.json`, `outputs/masterplan_v2/f2_002/daily_portfolio_v2.parquet`, `outputs/masterplan_v2/f2_002/ledger_trades_v2.parquet`
- Métricas comparativas básicas vs baseline (turnover, cash_ratio, exposição média, trades): `PASS`
  - evidência: `outputs/masterplan_v2/f2_002/evidence/metrics_compare_baseline_vs_v2.csv`

## Exemplos concretos de enforcement

- `ENF-001` date=`2021-08-16 00:00:00` reasons=`turnover_cap` candidate=(2.888678,1.537681) executed=(0.531642,0.283000)
- `ENF-002` date=`2021-03-08 00:00:00` reasons=`turnover_cap` candidate=(3.906098,0.000000) executed=(0.859342,0.000000)
- `ENF-003` date=`2021-07-12 00:00:00` reasons=`cadence_block|turnover_cap` candidate=(2.642858,0.000000) executed=(0.000000,0.000000)
- `ENF-004` date=`2020-12-07 00:00:00` reasons=`cadence_block|turnover_cap` candidate=(2.045248,0.783476) executed=(0.000000,0.205331)
- `ENF-005` date=`2021-02-22 00:00:00` reasons=`turnover_cap` candidate=(0.000000,3.472939) executed=(0.000000,0.859342)

## Preflight

- Branch requerida: `local/integrated-state-20260215` -> `PASS`
- Repo limpo antes da execução: `PASS`
- evidência: `outputs/masterplan_v2/f2_002/evidence/preflight.json`
