# SPEC-004 - Integracao Nelson/WE Rules (Gap Analysis Completo)

## Objetivo

Preservar a logica de evidencia estatistica do EXP_002 e explicitar o gap entre as flags legadas de ruleflags (S007) e o `SSOT_CANONICAL_BASE` atual.

## Regras no legado (EXP_002)

Fonte: `run_experiment.py` linhas 292-311 e 483-487.

- `any_rule_map = (any_nelson == 1) OR (any_we == 1)` -> contribui `+1`.
- `strong_rule_map = (we_rule_01 == 1) OR (nelson_rule_01 == 1) OR (nelson_rule_05 == 1) OR (nelson_rule_06 == 1)` -> contribui `+2`.

Contribuicao ao score:
- `rule_evidence = 0`
- `rule_evidence += 1` se `any_rule_map[(d,t)]`
- `rule_evidence += 2` se `strong_rule_map[(d,t)]`

## Verificacao real do canonical (via .venv)

Execucao validada com `/home/wilson/AGNO_WORKSPACE/.venv/bin/python` + `pyarrow` + `pandas`.

Colunas reais encontradas em `SSOT_CANONICAL_BASE.parquet`:
- `ticker`, `date`, `close_operational`, `close_raw`, `X_real`,
- `i_value`, `i_ucl`, `i_lcl`,
- `mr_value`, `mr_ucl`,
- `xbar_value`, `xbar_ucl`, `xbar_lcl`,
- `r_value`, `r_ucl`,
- `sector`, `mr_bar`, `r_bar`, `center_line`, `splits`, `split_factor`.

## Gap analysis (S007 legado -> canonical atual)

### Flags legadas ausentes no canonical atual

- `in_control`
- `we_rule_01`
- `any_we`
- `nelson_rule_01`
- `nelson_rule_05`
- `nelson_rule_06`
- `any_nelson`

**Diagnostico:** Ausentes como colunas nativas, portanto precisam ser derivadas.

### Proxies viaveis de curto prazo (T039)

1. `we_rule_01_proxy = (i_value < i_lcl) OR (i_value > i_ucl)`
2. `amp_out_proxy = (mr_value > mr_ucl) OR (r_value > r_ucl)`
3. `xbar_out_proxy = (xbar_value < xbar_lcl) OR (xbar_value > xbar_ucl)`
4. `any_we_proxy = we_rule_01_proxy OR amp_out_proxy OR xbar_out_proxy`
5. `strong_rule_proxy = we_rule_01_proxy OR amp_out_proxy`
6. `in_control_proxy = NOT(any_we_proxy)`

## Limites dos proxies

- Nelson 05/06 requerem padroes sequenciais temporais; nao podem ser reproduzidas fielmente com regra ponto-a-ponto.
- Proxies sao aceitaveis para bootstrap do T039, com necessidade de recalibracao posterior.

## Recomendacao de implementacao

1. **Curto prazo (T039):** usar `any_we_proxy`/`strong_rule_proxy`.
2. **Medio prazo:** construir gerador de ruleflags temporal no AGNO (S007-like) a partir do canonical.
3. **Longo prazo:** substituir proxies por flags Nelson/WE completas e revalidar score.

## Fonte (arquivo e linhas)

- `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/work/experimentos_on_flight/EXP_002_SELL_POLICY_GATE_CEP_RL_V1/run_experiment.py:292-311,483-487`
- `SSOT_CANONICAL_BASE.parquet` lido no `.venv` do workspace (consulta de schema em 2026-02-27)

## Adaptacao para M3

- Evidencia Nelson/WE e orthogonal ao ranking de compra.
- Em M3, o bloco `rule_evidence` permanece valido desde que flags/proxies sejam disponibilizadas por ticker/dia.

