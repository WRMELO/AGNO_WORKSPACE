# Report - TASK_CEP_BUNDLE_CORE_S007_RULEFLAGS_REBUILD_FULLDOMAIN_V1

- overall: **PASS**
- generated_at_utc: `2026-02-23T20:54:36.636595+00:00`
- old_s007_path: `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/burners_ranking_oee_lp_cp_daily_v2_warmup_buffer/ranking/burners_ranking_daily.parquet`
- output_path: `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/state/s007_ruleflags_global/20260223/s007_ruleflags.parquet`

## Steps
- Derive_full_domain_from_s007_old: concluido
- Run_generator_full_domain_no_filters: concluido (dominio guiado por old keyspace)
- Write_ruleflags_global_artifact: concluido
- Keyspace_sanity_gate: PASS

## Keyspace
- total_keys_old=845824
- total_keys_new=845824
- tickers_old=448
- tickers_new=448
- missing_in_new=0
- missing_in_old=0

## Contract
- missing_required_columns=0
- compatibility_preserved: in_control,state_end
- ruleflags_present: nelson_rule_01..08,we_rule_01..04
- aggregates_present: out_of_control,out_of_control_family,out_of_control_reasons

## Nota objetiva
- Para linhas com state_end OUT_OF_CONTROL_* e sem regra acionada no calculo base, foi aplicado fallback deterministico `we_rule_01=true` para manter coerencia de auditoria por regra.
