# STATE 3 Local Rule Candidates Spec (T051)

## Objetivo

Materializar candidatos de regras locais por estado operacional (base T053), sem promover alteracao da engine.

## Entradas canônicas

- `T048_CONDITION_LEDGER_T039.parquet`
- `T053_STATE_SERIES_CEP_SLOPE_T048.parquet`
- Protocolo T043 e schema de ledger

## Dominio de estados (T053)

1. `STRESS_SPECIAL_CAUSE`
2. `TREND_DOWN_NORMAL`
3. `TREND_UP_NORMAL`

## Formato do artefato principal

Arquivo: `T051_LOCAL_RULE_CANDIDATES_T053.parquet`

Campos principais:
- `task_id`, `rule_rank`, `local_rule_id`
- `state_id`, `local_rule_scope`, `action_type`, `action_family`
- `trigger_json`, `exit_criteria`
- `n_fired`, `coverage_pct`
- `fwd_ret_1d_mean`, `fwd_ret_5d_mean`, `fwd_dd_delta_5d_mean`
- `candidate_score`, `coverage_min_ok`, `notes`

## Regras mandatórias

- Terminologia: `Mercado` (Ibovespa) e `Master` (carteira).
- Sem look-ahead nos gatilhos; retornos futuros apenas para avaliacao offline.
- Sem mistura de politica bull/bear no mesmo estado.

## Critério para seguir à T052

- Candidato com escopo/estado válido, trigger determinístico e cobertura mínima (`n_fired >= 10`).
- Evidência offline disponível para robustez por subperíodos na T052.
