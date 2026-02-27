# SPEC-003 - Partial Sells (Execucao Gradual de Venda)

## Objetivo

Definir a execucao de venda parcial por severidade, preservando timing D+1, priorizacao Top-K e mecanismo de quarentena (anti-reentry).

## Regras

### 1) Tabela deterministic (score -> percentual)

Fonte: `run_experiment.py` linhas 239-246.

- `score=4` -> `25%`
- `score=5` -> `50%`
- `score>=6` -> `100%`
- `score<4` -> `0%`

### 2) Selecionador de candidatos (Top-K)

Fonte: linhas 512-516.

1. filtra `candidate=True`,
2. ordena por:
   - `score_ticker` desc,
   - `weight_ret_tie_break` asc,
   - `ticker` asc,
3. corta em `head(top_k)` (`top_k=5`).

### 3) Agendamento (D -> D+1)

Fonte: linhas 531-568.

- sinal de venda e criado em `D`,
- ordem executavel e enviada para `pending_sell_exec[D+1]`.

### 4) Execucao financeira

Fonte: linhas 387-405.

- `qty = floor(qty_cur * sell_pct/100)`, com override `qty=qty_cur` se `sell_pct>=100`,
- `notional = qty * price`,
- `fee = notional * cost_rate`,
- `cash_after = cash_before + notional - fee`.

### 5) Quarentena / anti-reentry

Fonte: linhas 317, 465-467, 570-571.

- venda com `sell_pct>0` adiciona ticker em `blocked_reentry`,
- desbloqueio ocorre quando ticker reaparece no funil elegivel e em controle.

## Parametros

- `top_k_sell_candidates = 5`
- `cost_rate = 0.00025`
- `reason = CEP_DOWNSIDE_GATE`

## Fonte (arquivo e linhas)

- `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/work/experimentos_on_flight/EXP_002_SELL_POLICY_GATE_CEP_RL_V1/run_experiment.py:239-246,317,387-405,465-467,512-516,531-571`

## Resultados do legado

Conforme summaries:
- deterministic: maior `turnover_sell` e `cost_total`, menor `missed_sell_rate`;
- hybrid_rl: menor churn/custo, maior `missed_sell_rate`, menor `false_sell_rate`.

## Adaptacao para M3

- Logica de partial sells independe do ranking de compra.
- Em motor M3, manter mesma politica de execucao e telemetria, trocando apenas o pipeline de candidatos de compra.

