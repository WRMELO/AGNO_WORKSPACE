# Report - TASK_CEP_BUNDLE_CORE_EXP_001_S008_TOP10S45_STRESSSELL_2019_20210630_OVERWRITE_V2

- generated_at_utc: `2026-02-23T17:09:34.332128+00:00`
- period: `2019-01-01..2021-06-30`
- resolved_s008_candidates: `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/s008_candidates_championship_slope45_v1/candidates/candidates_daily.parquet`
- resolved_s007_burner_status: `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/burners_ranking_oee_lp_cp_daily_v2_warmup_buffer/ranking/burners_ranking_daily.parquet`
- resolved_s006_prices: `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/base_operacional_canonica_completa_v2_448_cdi_excess_v1/panel/base_operacional_canonica.parquet`
- resolved_cdi_daily: `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/ssot_reference_refresh_v1/cdi_daily.parquet`

## Regras executadas (V2 overwrite)
- vendas: sinal em D e execução em D+1 a Close(D+1)
- quantidades inteiras (sem fracionamento) para BUY/SELL
- caixa nunca negativo
- CDI(D-1) aplicado no fim do dia sobre caixa após movimentações
- Equity(D) = Σ(qty(D) * Close(D-1)) + Caixa(D)

## Sanidade
- decision_days: `618`
- trades_count: `485`
- final_equity_d_brl: `193716.299774`
- cep_buy_violations: `0`
- same_day_reentry_violations: `0`
