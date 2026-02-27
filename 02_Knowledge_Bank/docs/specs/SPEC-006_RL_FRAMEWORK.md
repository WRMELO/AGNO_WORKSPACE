# SPEC-006 - RL Framework (Referencia EXP_002)

## Objetivo

Documentar integralmente o framework RL discreto do legado para futura integracao controlada, mantendo disciplina temporal anti-leakage.

## Modelagem RL

### 1) Estado

Fonte: `run_experiment.py` linhas 520-522.

- `state_bucket = clip(round(mean(score_ticker_topk)), 0, 6)`
- representa severidade media do lote Top-K no dia.

### 2) Acoes

Fonte: linhas 321-322, 523, 526.

- espaco discreto: `[0, 25, 50, 100]` (percentual global de venda no lote).

### 3) Politica epsilon-greedy

Fonte: linhas 522-529.

- com probabilidade `epsilon` (legado: `0.1`), escolhe acao aleatoria.
- senao, escolhe `argmax_a Q(state,a)` com:
  - `Q(state,a) = sum_rewards(state,a)/count(state,a)`
  - fallback `0.5` quando `count=0`.

### 4) Reward

Fonte: linhas 573-593.

- `should_sell_expost = regime_on AND (worst_cumret_3d < -2*sigma_ticker)` (linhas 579-583)
- `a = global_action / 100`
- `reward_ticker = a` se `should_sell_expost=1`, senao `1-a`
- `reward_lote = media(reward_ticker)` dos candidatos do lote.

### 5) Atualizacao de memoria (Q-table por media acumulada)

Fonte: linhas 356-363 e 587-592.

- feedback so entra quando liberado em D+3:
  - `state_action_sum[state][action] += reward`
  - `state_action_cnt[state][action] += 1`

## Regras de anti-leakage (obrigatorias)

Fonte: linhas 356-363, 927-933.

1. decisao em D usa apenas informacao disponivel ate D,
2. label ex-post so alimenta aprendizado em D+3,
3. auditoria formal persistida em `feature_leakage_audit.json`.

## Parametros do legado

- `rl_epsilon = 0.1`
- `state buckets = 0..6`
- `action_levels = [0, 25, 50, 100]`

## Evidencia de resultados

Fonte: summaries legados.

- RL reduziu turnover/custo em varias janelas.
- trade-off: maior `missed_sell_rate` em cenarios especificos, exigindo calibracao por janela/regime.

## Fonte (arquivo e linhas)

- `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/work/experimentos_on_flight/EXP_002_SELL_POLICY_GATE_CEP_RL_V1/run_experiment.py:321-324,356-363,520-529,573-593,927-933`

## Adaptacao para M3

- State/action/reward independem do ranking de compra.
- Em motor M3, RL permanece restrito a decidir "quanto vender" dos candidatos do gate de severidade.

