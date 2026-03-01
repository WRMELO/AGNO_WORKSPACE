# SPEC-007 - Termostato do Forno Dual-Mode (T071)

## Objetivo

Definir o meta-controlador endogeno que comuta entre dois modos operacionais completos do forno (Master), sem usar comutacao por data e sem usar sinal de mercado como gatilho principal.

## Glossario operacional (referencia mandatória)

Fonte oficial: `GLOSSARY_OPERATIONAL.md`.

- **Burner**: ativo individual.
- **Master**: carteira/portfolio agregado.
- **Tank**: caixa livre remunerado por CDI.
- **Equity**: posicoes + tank.

## Modos operacionais (profiles fixos)

### Modo A - T037 (plena carga)

Fonte: `scripts/t037_m3_canonical_engine.py`.

- `buy_cadence_days = 3`
- `TOP_N = 10`
- `target_pct = 0.10`
- `max_pct = 0.15`
- `sell_policy = BURNER_STRESS_CEP` (binario: 0% ou 100%)
- `regime_defensivo = OFF`

### Modo B - T067 (controle de regime)

Fonte: `src/data_engine/portfolio/T067_AGGRESSIVE_SELECTED_CONFIG.json`.

- `cadence_days = 10`
- `buy_turnover_cap_ratio = null`
- `sell_policy = CEP_SEVERITY_GATE` (S4=25%, S5=50%, S6=100%)
- `market_mu_window = 62`
- `market_slope_window = 30`
- `in_hyst_days = 4`
- `out_hyst_days = 4`
- `regime_defensivo = ON (market-slope)`

## Telemetria minima do forno (inputs do termostato)

- `equity_end`
- `cash_end`
- `positions_value_end`
- `cdi_credit` e serie CDI diaria
- `exposure`
- `n_positions`
- `ledger.side` / `ledger.reason` (auditoria de transicao)

## Sinal endogeno de produtividade (sem sinal de mercado)

O sinal do termostato deve medir produtividade dos burners contra CDI.

### Candidato SINAL-1 (preferencial)

- `burner_ret_1d = pct_change(positions_value_end).shift(1)`
- `burner_excess_w = rolling_sum(burner_ret_1d, W) - rolling_sum(cdi_simple_1d, W)`

Justificativa: mede componente mais proximo de "producao dos burners" sem misturar regra de tank.

### Candidato SINAL-2 (fallback)

- `net_prod_1d = pct_change(equity_end - cdi_credit_cum).shift(1)`
- `net_excess_w = rolling_sum(net_prod_1d, W) - rolling_sum(cdi_simple_1d, W)`

Uso: validar robustez contra definicao alternativa.

## Regra de comutacao (maquina de estados)

Estado inicial configuravel (`MODE_A` ou `MODE_B`) e avaliado em ablação.

- Entra em `MODE_A` quando `excess_w > +thr` por `H_in` dias consecutivos.
- Entra em `MODE_B` quando `excess_w < -thr` por `H_out` dias consecutivos.
- Caso contrario, mantem estado atual.

Parametros da regra:

- `W` (janela do excesso rolling)
- `thr` (limiar de comutacao)
- `H_in` e `H_out` (histerese)

## Regras de transicao entre modos

1. Nao liquidar carteira na troca de modo.
2. Nao resetar equity nem tank.
3. Resetar apenas contador de cadencia no instante da troca.
4. Politicas BUY/SELL/regime passam a seguir profile do novo modo no pregão seguinte.
5. Proibido uso de comutacao por data fixa.

## Anti-lookahead (obrigatorio)

1. Todo sinal deve usar `shift(1)` antes de gerar decisao.
2. Thresholds e histerese devem ser calibrados em janela passada e aplicados em janela futura (walk-forward).
3. Nenhum parametro pode ser ajustado com informacao do bloco de avaliacao.

## Desenho minimo da T072 (ablação)

Grid minimo recomendado:

- `W in {30, 62, 90, 126}`
- `thr in {0.0000, 0.0005, 0.0010, 0.0015}`
- `H_in in {2, 3, 4}`
- `H_out in {2, 3, 4, 5}`
- `signal_variant in {SINAL-1, SINAL-2}`

Hard constraints minimas:

- `MDD_total >= -0.30`
- `equity_final_total > equity_final_T044`
- `excess_return_P1_vs_T037 >= -0.20`
- `excess_return_P2_vs_T067 >= -0.20`

Ranking lexicografico:

1. `equity_final_total DESC`
2. `min(excess_return_P1_vs_T037, excess_return_P2_vs_T067) DESC`
3. `Sharpe_total DESC`
4. `turnover_total ASC`
5. `candidate_id ASC`

## Artefatos esperados para T072

- Config vencedor dual-mode (`*_SELECTED_CONFIG.json`)
- Curva e ledger (`*_PORTFOLIO_CURVE*.parquet`, `*_PORTFOLIO_LEDGER*.parquet`)
- Resultado completo da ablação (`*_ABLATION_RESULTS.parquet`)
- Plotly embutido comparativo (Dual vs T037/T044/T067/CDI/Ibov)
- Report de execução
- Manifest SHA256 (sem self-hash)

## Criterios de aceite do SPEC

1. Define os dois modos (A/B) com parametros reproduziveis.
2. Define sinal endogeno baseado em produtividade vs CDI.
3. Explicita clausula anti-lookahead (`shift(1)` + walk-forward).
4. Proibe comutacao por data e por sinal primario de mercado.
5. Define regras de transicao sem reset de carteira/tank.
6. Define grid, constraints e ranking para T072.
7. Mantem coerencia com `STATE3_PHASE4_LESSONS_LEARNED_T069.md` (LL-PH4-007..010).

## Fonte (evidencias)

- `00_Strategy/ROADMAP.md` (Phase 5)
- `02_Knowledge_Bank/docs/process/STATE3_PHASE4_LESSONS_LEARNED_T069.md`
- `02_Knowledge_Bank/docs/specs/GLOSSARY_OPERATIONAL.md`
- `scripts/t037_m3_canonical_engine.py`
- `src/data_engine/portfolio/T067_AGGRESSIVE_SELECTED_CONFIG.json`
- `src/data_engine/portfolio/T068_RALLY_PROTECTION_SELECTED_CONFIG.json`
