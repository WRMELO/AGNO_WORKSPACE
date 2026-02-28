# STATE 3 State Decisor CEP+SLOPE Spec (T053 probe)

## Objetivo

Executar probe de estados conjuntos para aumentar sensibilidade a deriva lenta antes da T051.

## Princípio constitucional

- CEP permanece fundamentado em `X_t = log(Close_t/Close_t-1)` (logret).
- O `slope` usado aqui e **derivado de X_t**, nao substitui a variavel fundamental.
- Nao usar preco bruto como variavel de controle.

## Sinais derivados

- `market_mu_w = rolling_mean(market_logret_1d, w=62)`
- `market_mu_slope = rolling_slope(market_mu_w, w=20)`
- `trend_down_flag`: histerese deterministica sobre `market_mu_slope < 0` com `IN=2` e `OUT=3`.

## Estados conjuntos (mutuamente exclusivos)

1. `STRESS_SPECIAL_CAUSE` (quando `market_special_cause_flag == True`)
2. `TREND_DOWN_NORMAL` (sem stress, mas `trend_down_flag == True`)
3. `TREND_UP_NORMAL` (sem stress, `trend_down_flag == False`)

## Regras de transicao

- Prioridade de estado: Stress > TrendDown > TrendUp.
- Sem look-ahead: toda decisao usa apenas informacao ate t.

## Entregáveis do probe

- Serie de estados diaria (`T053_STATE_SERIES_CEP_SLOPE_T048.parquet`)
- Relatorio comparando granularidade de episodios (`T050` vs `T053`)
- Manifesto SHA256 para rastreabilidade
