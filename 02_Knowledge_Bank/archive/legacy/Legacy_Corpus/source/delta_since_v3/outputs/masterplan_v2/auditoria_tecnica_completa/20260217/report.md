# Auditoria Tecnica Completa - CDI e Equity (F1/F2)

- generated_at_utc: `2026-02-20T17:43:34.954117+00:00`
- branch: `local/integrated-state-20260215`
- head: `dfcd9d6866989c18bfdcd2f840850b402f45a92f`
- overall_audit: `FAIL`

## Conclusao executiva

- O uso de CDI **diario** no executor F2_002 esta coerente (residuo ~0 no accrual de caixa).
- A principal origem da explosao de equity V2 nao e CDI acumulado aplicado diretamente, e sim dinamica de enforcement com **net sell muito positivo** sem prova de restricao de inventario por ativo.
- Existe risco real de validade economica: o modelo passa reconciliacoes internas, mas permite resultado implausivel.

## Resposta a hipotese CDI acumulado

- Hipotese "CDI acumulado usado como diario" foi **parcialmente verdadeira em etapa de gate** (F2_004 inicial), corrigida via `pct_change` em serie index-like.
- Na execucao F2_002 auditada, o CDI aplicado vem de `cdi_ret_t` diario e nao de `cdi_index_norm` bruto.

## Achados prioritarios

- [HIGH] `AUD-001` Equity V2 economic plausibility breached despite reported PASS
  - detalhe: V2 final equity ~183x while baseline ~2.385x; major driver is net sells +117.3 notional with CDI accruing over inflated cash.
  - evidencia: outputs/masterplan_v2/auditoria_tecnica_completa/20260217/evidence/economic_plausibility_diagnostics.json, outputs/masterplan_v2/f2_003/evidence/equity_compare_summary.json, outputs/masterplan_v2/auditoria_tecnica_completa/20260217/plots/audit_equity_baseline_vs_v2.html
- [HIGH] `AUD-002` Executor ledger lacks inventory dimensions (ticker/qty), preventing asset-level sell feasibility checks
  - detalhe: Without ticker/qty in ledger_v2, SELL constraints cannot be validated by position, enabling economically inconsistent cash generation.
  - evidencia: outputs/masterplan_v2/auditoria_tecnica_completa/20260217/evidence/economic_plausibility_diagnostics.json, outputs/masterplan_v2/f2_002/ledger_trades_v2.parquet
- [MEDIUM] `AUD-003` CDI accumulated vs daily confusion occurred in gate logic and was patched
  - detalhe: SSOT contains both index level and daily return. Using index directly as daily rate is wrong; current runner patch converts index-like series via pct_change where needed.
  - evidencia: outputs/masterplan_v2/auditoria_tecnica_completa/20260217/evidence/cdi_scale_and_usage_check.json, outputs/masterplan_v2/auditoria_tecnica_completa/20260217/evidence/cdi_cash_application_summary.json, outputs/masterplan_v2/f2_004/report.md
- [MEDIUM] `AUD-004` Reported PASS statuses are internally consistent but not sufficient for economic validity
  - detalhe: Reconciliations pass mathematically inside the implemented model, yet model assumptions allow implausible outcomes.
  - evidencia: outputs/masterplan_v2/auditoria_tecnica_completa/20260217/evidence/reported_status_matrix.csv, outputs/masterplan_v2/auditoria_tecnica_completa/20260217/evidence/cash_equity_reconciliation_summary.json

## Metricas chave observadas

- v2_sum_buy_notional: `26.039166`
- v2_sum_sell_notional: `143.339846`
- v2_net_sell_minus_buy: `117.300679`
- v2_cdi_cumulative_gain: `63.553670`
- v2_final_cash: `180.812005`
- v2_final_equity: `183.197445`
- baseline_final_equity_reported: `2.385440`

## Recomendacao operacional

- `block_f3_f4`: `true` (recomendado)
- Abrir task de bugfix minimo para inventario por ativo e rerun sequencial F2_002 -> F2_003 -> F2_004.

## Artefatos da auditoria

- `outputs/masterplan_v2/auditoria_tecnica_completa/20260217/report.md`
- `outputs/masterplan_v2/auditoria_tecnica_completa/20260217/manifest.json`
- `outputs/masterplan_v2/auditoria_tecnica_completa/20260217/evidence/findings.json`
- `outputs/masterplan_v2/auditoria_tecnica_completa/20260217/plots/audit_equity_baseline_vs_v2.html`
