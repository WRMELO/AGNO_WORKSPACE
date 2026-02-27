# SPEC-001 - Severity Score (Master = Carteira)

## Objetivo

Definir, de forma reproduzivel, o score de severidade por burner em carteira para acionar vendas defensivas graduais.

## Formulas

### 1) Normalizacao base (z-score rolling)

Fonte: `run_experiment.py` linhas 130-134, 278-281.

- `z_ticker(d,t) = (logret(d,t) - mu_rolling(d,t)) / sigma_rolling(d,t)`
- `mu_rolling` e `sigma_rolling` calculados com janela `lookback=60` e `min_periods=20`.

### 2) Downside band

Fonte: linhas 152-161.

- `band = 0` se `z` nao finito ou `z >= 0`
- `band = 1` se `-2 <= z < -1`
- `band = 2` se `-3 <= z < -2`
- `band = 3` se `z < -3`

### 3) Persistencia temporal de queda

Fonte: linhas 475-482.

- `neg_count = I(z<0) + I(z_1<0) + I(z_2<0)`
- `persistence = 1` se `neg_count >= 2`, senao `0`
- incremento adicional: `persistence += 1` se `(z < -2) AND (z_1 < -2)`

### 4) Evidencia estatistica (rule evidence)

Fonte: linhas 483-487.

- `rule_evidence = 0`
- `rule_evidence += 1` se `any_rule_map[(d,t)] == True`
- `rule_evidence += 2` se `strong_rule_map[(d,t)] == True`

### 5) Score composto

Fonte: linha 488.

- `score_ticker = min(6, band + persistence + rule_evidence)`

### 6) Gate de candidatura para venda

Fonte: linha 506.

- `candidate = regime_on AND isfinite(z) AND (z < 0) AND (score_ticker >= 4)`

## Parametros

- `zscore_lookback_days = 60`
- `zscore_min_periods = 20`
- `score_threshold = 4`
- `score_cap = 6`
- estado de regime: `regime_on` (definido no SPEC-002)

## Fonte (arquivo e linhas)

- `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/work/experimentos_on_flight/EXP_002_SELL_POLICY_GATE_CEP_RL_V1/run_experiment.py:130-134,152-161,278-281,475-488,506`

## Resultados do legado (evidencia quantitativa)

Fonte: `summary.json` (ablation W3/W4/W5 e W4 combinado).

- `missed_sell_rate` e `false_sell_rate` foram mensurados em todas as variantes.
- o score sustentou politicas com trade-off observavel entre custo/churn e drawdown.

## Adaptacao para M3

- O Severity Score e ortogonal ao ranking de compra.
- Migracao F1 -> M3 nao altera a matematica do score.
- M3 altera o universo de entradas; severidade continua operando sobre burners em carteira.

