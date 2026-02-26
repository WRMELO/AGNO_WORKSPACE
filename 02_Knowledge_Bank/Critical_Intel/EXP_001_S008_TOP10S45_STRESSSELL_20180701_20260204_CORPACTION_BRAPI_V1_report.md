# Report - TASK_CEP_DISC_013_REEXEC_EXP_001_FULLPERIOD_CORPACTION_BRAPI_V1

- generated_at_utc: `2026-02-24T16:51:05.792673+00:00`
- period: `2018-07-01..2026-02-04`
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
- decision_days: `1888`
- trades_count: `749`
- final_equity_d_brl: `409882.341698`
- cep_buy_violations: `0`
- same_day_reentry_violations: `0`
