# Decision Package — Sizing (V2, MDD real)

## Resumo executivo
- Universo do grid: 108 configurações.
- Guardrail MDD real: >= -0.12
- Validação de regime: compras em RISK_OFF = 0.

## Configurações (recomendada + alternativas)
| tipo | w_base | w_def | w_cap | persist_on | persist_off | equity_final | mdd_real | turnover | max_weight | avg_hhi | avg_cash |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| recomendada | 0.08 | 0.03 | 0.15 | 3.0 | 1.0 | 0.988420809476916 | -0.1119339954063143 | 50.39999999999995 | 0.08 | 0.0438330019880702 | 0.4520874751491128 |
| conservadora | 0.08 | 0.03 | 0.15 | 3.0 | 1.0 | 0.988420809476916 | -0.1119339954063143 | 50.39999999999995 | 0.08 | 0.0438330019880702 | 0.4520874751491128 |
| agressiva | 0.1 | 0.05 | 0.15 | 1.0 | 1.0 | 1.1207823174751217 | -0.0945867791194053 | 77.0 | 0.1 | 0.086033797216697 | 0.139662027833002 |

## Justificativa numérica
- Ranking pós-guardrail: min(max_weight) -> min(avg_hhi) -> min(turnover) -> max(equity_final).
- MDD real calculado diretamente (não proxy).

## Conformidade de regime
- Compras em RISK_OFF: 0 (sem violações).
- Cap violations: 0.

## Em caso de erro na resposta (não no código)
- Prioridade entre estabilidade/controle e métricas financeiras deve ser reafirmada se o guardrail filtrar demais.

Gerado em: 2026-02-09T18:23:45Z
