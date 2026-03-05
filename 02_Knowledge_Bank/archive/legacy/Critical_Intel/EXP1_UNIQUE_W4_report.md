# Report - TASK_TMP_EXP1_UNIQUE_AFTER_CORP_ACTIONS_V1

- generated_at_utc: `2026-02-24T19:48:46.841752+00:00`
- period: `2018-07-01..2026-02-04`
- resolved_s008_candidates: `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/state/s008_candidates_global/20260224/S008_CANDIDATES_CORP_ACTIONS_V2_COMPAT/candidates/candidates_daily.parquet`
- resolved_s007_burner_status: `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/state/s007_ranking_global/20260224/S007_RANKING_FROM_RULEFLAGS_CORP_ACTIONS_V2/ranking/burners_ranking_daily.parquet`
- resolved_s006_prices: `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/state/s006_operational_base_global/20260224/S006_CANONICAL_BASE_WITH_CORP_ACTIONS_V2_COMPAT/panel/base_operacional_canonica.parquet`
- resolved_cdi_daily: `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/ssot_reference_refresh_v1/cdi_daily.parquet`

## Regras executadas (V2 overwrite)
- vendas: sinal em D e execução em D+1 a Close(D+1)
- quantidades inteiras (sem fracionamento) para BUY/SELL
- caixa nunca negativo
- CDI(D-1) aplicado no fim do dia sobre caixa após movimentações
- Equity(D) = Σ(qty(D) * Close(D-1)) + Caixa(D)

## Sanidade
- decision_days: `1888`
- trades_count: `331`
- final_equity_d_brl: `227593.797189`
- cep_buy_violations: `0`
- same_day_reentry_violations: `0`
