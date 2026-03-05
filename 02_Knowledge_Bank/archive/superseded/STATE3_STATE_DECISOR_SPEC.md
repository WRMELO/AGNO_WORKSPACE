# STATE 3 State Decisor Specification (T050-STATE-DECISOR-V1)

## Objetivo

Materializar uma FSM deterministica, auditavel e sem look-ahead para classificar o estado operacional diario a partir do bloco `Mercado` do T048.

## Parametros fixos (v1)

- `IN_HYST_DAYS = 2`
- `OUT_HYST_DAYS = 3`
- `RECOVERY_DAYS = 10`

## Estados (mutuamente exclusivos)

1. `NORMAL_IN_CONTROL`
2. `STRESS_SPECIAL_CAUSE`
3. `RECOVERY_REENTRY_WINDOW`

## Fonte primaria de decisao

- `market_special_cause_flag` (derivado do Ibovespa / Mercado no T048).

## Regras de transicao (sem look-ahead)

- `NORMAL_IN_CONTROL` -> `STRESS_SPECIAL_CAUSE`:
  - quando `market_special_cause_flag == True` por `IN_HYST_DAYS` dias consecutivos.
- `STRESS_SPECIAL_CAUSE` -> `RECOVERY_REENTRY_WINDOW`:
  - quando `market_special_cause_flag == False` por `OUT_HYST_DAYS` dias consecutivos.
- `RECOVERY_REENTRY_WINDOW` -> `NORMAL_IN_CONTROL`:
  - quando completar `RECOVERY_DAYS` pregões da janela de recuperação.
- `RECOVERY_REENTRY_WINDOW` -> `STRESS_SPECIAL_CAUSE`:
  - reentrada se `market_special_cause_flag == True` por `IN_HYST_DAYS` dias consecutivos durante a janela.

## Saidas diarias obrigatorias

- `date`
- `state_id`
- `state_entry_flag`
- `state_exit_flag`
- `state_transition_reason`
- `state_hysteresis_counter`

## Regras de governanca

- `G0_GLOSSARY_COMPLIANCE`: Mercado (Ibovespa) jamais rotulado como Master.
- `G1_DECISOR_STATE_MACHINE_SPEC`: spec markdown presente e versionada.
- `G2_STATE_SERIES_PRESENT`: serie diaria materializada.
- `G3_MUTUAL_EXCLUSIVITY`: um unico `state_id` valido por `date`.
- `Gx_HASH_MANIFEST_PRESENT`: manifesto SHA256 presente e consistente.

## Restricoes da fase

- Sem mistura de politicas bull/bear dentro do mesmo estado.
- Histerese apenas nas transicoes.
- Esta tarefa nao promove regras locais; apenas define estado operacional.
