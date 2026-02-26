# Report - TASK_CEP_BUNDLE_CORE_EXP_001_STRESS_SELL_BREAKDOWN_BY_NELSON_WE_RULES_V2_ADD_MD_MATRIX

- generated_at_utc: `2026-02-23T21:08:31.984245+00:00`
- exp_outputs_root: `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/experimentos/on_flight/20260223/EXP_001_S008_TOP10S45_STRESSSELL_2019_20210630_V1`
- s007_ruleflags_source: `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/state/s007_ruleflags_global/20260223/s007_ruleflags.parquet`
- overall: **PASS**

## Gates/Steps
- Locate_EXP_001_outputs_root: PASS
- Build_and_enrich_events: PASS
- Aggregate_and_build_matrix: PASS
- Render_markdown_matrix: PASS
- Write_outputs_manifest_evidence: PASS

## Metrics
- stress_sell_events_total=103
- expected_reference_events=103
- join_coverage=1.000000
- missing_joins=0
- unique_tickers=13

## Regras de join aplicadas
- decision_date = previous trading day of execution_date (D-1)
- join_key = (ticker, decision_date)
- contagens derivadas somente de flags true no S007_RULEFLAGS (sem inferencia)
