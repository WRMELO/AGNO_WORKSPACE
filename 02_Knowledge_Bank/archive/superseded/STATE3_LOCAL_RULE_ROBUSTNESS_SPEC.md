# STATE 3 Local Rule Robustness Spec (T052)

## Objetivo

Avaliar robustez temporal dos candidatos locais (T051) por subperíodos canônicos do T040/SPEC-005 e emitir decisão de promoção.

## Subperíodos canônicos

Fonte obrigatória: `src/data_engine/portfolio/T040_METRICS_BY_SUBPERIOD.csv`

Usar `subperiod`, `period_start` e `period_end` sem criar cortes ad-hoc.

## Entradas

- `T048_CONDITION_LEDGER_T039.parquet`
- `T053_STATE_SERIES_CEP_SLOPE_T048.parquet`
- `T051_LOCAL_RULE_CANDIDATES_T053.parquet`
- `T040_METRICS_BY_SUBPERIOD.csv`

## Saída principal

`T052_RULE_ROBUSTNESS_BY_SUBPERIOD_T051.parquet`

Granularidade: 1 linha por `local_rule_id x subperiod`.

Campos mínimos:
- `local_rule_id`, `state_id`, `local_rule_scope`, `subperiod`, `period_start`, `period_end`
- `n_days_subperiod`, `n_fired`, `coverage_pct`
- `fwd_ret_1d_mean`, `fwd_ret_5d_mean`, `fwd_dd_delta_5d_mean`, `fwd_ret_5d_p05`
- `coverage_min_ok_subperiod`, `promotion_recommendation`, `promotion_reason`

## Regra de decisão (T052)

- `PROMOTE`: cobertura mínima (`n_fired>=10`) em pelo menos 3 subperíodos e consistência de sinal >= 60%.
- `HOLD`: cobertura mínima em 1-2 subperíodos, ou consistência insuficiente para promoção.
- `REJECT`: sem cobertura mínima em qualquer subperíodo.

## Governança

- Sem look-ahead nos triggers; métricas futuras apenas em avaliação offline.
- Terminologia mandatória: Mercado != Master.
