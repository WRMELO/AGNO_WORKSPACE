# Decisão de Governança — SIZING_DEFAULT_V2

ID formal: DEC_SIZING_20260209_V2
Data de vigência: 2026-02-09

## Parâmetros congelados
- w_base: 0.08
- w_def: 0.03
- w_cap: 0.15
- persist_on: 3
- persist_off: 1

## Guardrail (regra operacional bloqueante)
- Definição: mdd_real = min_t(E_t / max_{s<=t}E_s - 1), negativo
- Escopo: história inteira, incluindo PRESERVACAO_TOTAL
- Threshold: -0.12
- Regra PASS/FAIL: mdd_real >= -0.12

## Evidências
- decision_package_md: `outputs/experimentos/fase1_calibracao/cal/20260209/decision_package_sizing_v2/decision_package.md`
- selected_config_json: `outputs/experimentos/fase1_calibracao/cal/20260209/decision_package_sizing_v2/selected_config.json`
- auditoria (dir): `outputs/experimentos/fase1_calibracao/aud/20260209/verify_mdd_guardrail_v2/`
  - arquivos: mdd_recalc_table.csv, guardrail_verdict.json, mdd_recalc_notes.md, manifest.json

## Regras de mudança
- Qualquer alteração futura exige novo grid + novo decision package + auditoria + nova decisão.
- Emenda na Constituição deve ser feita em passo separado.

## Em caso de erro na resposta (não no código)
- Revalidar escopo do MDD e regra operacional bloqueante antes de nova decisão.

Gerado em: 2026-02-09T18:47:07Z
