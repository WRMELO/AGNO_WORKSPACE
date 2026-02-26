# Report - TASK_CEP_BUNDLE_CORE_EXP_001_STRESS_REASON_NELSON_WE_BREAKDOWN_V1

- overall: **FAIL**
- generated_at_utc: `2026-02-23T20:27:28.244100+00:00`
- exp_outputs_root: `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/experimentos/on_flight/20260223/EXP_001_S008_TOP10S45_STRESSSELL_2019_20210630_V1`

## Gates
- S1_LOCATE_EXP_OUTPUTS: PASS - outputs_root reutilizado
- S2_RESOLVE_S007_SOURCE: PASS - 3 arquivo(s) S007 resolvido(s)
- S3_SCHEMA_HAS_RULE_LEVEL_FLAGS: FAIL - faltam flags por regra Nelson/W.E. no S007 materializado
- S4_BUILD_SELL_EVENTS: PASS - 103 SELL por stress no periodo
- S5_JOIN_AND_DERIVE_REASONS: FAIL - schema sem flags por regra Nelson/W.E.; atribuicao por regra bloqueada por no_inference_without_evidence

## Falha materializada (sem inferencia)
- O S007 consumido pelo EXP_001 fornece estado agregado (`state_end`/`in_control`), sem flags por regra Nelson/W.E.
- Portanto, a atribuicao por regra individual nao pode ser feita sem instrumentacao adicional.

## Instrumentacao minima recomendada (Plano B)
- nelson_rule_flags (ex.: nelson_r1..nelson_r8)
- we_rule_flags (ex.: we_r1..we_r4)
- out_of_control_family (NELSON/WE/AMBOS)
- out_of_control_rules_triggered (lista de regras no dia D)
