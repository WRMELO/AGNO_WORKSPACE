# SPEC-002 - Master Gate (Regime da Carteira)

## Objetivo

Padronizar o gate de regime do Master (carteira), usando slope do retorno agregado e histerese assimetrica para reduzir alternancia espuria.

## Formulas

### 1) Serie agregada do Master

Fonte: `run_experiment.py` linha 886.

- `portfolio_logret = mean(logret_wide, axis=1)`

No legado, a media foi calculada sobre os tickers disponiveis no painel do experimento.

### 2) Rolling slope

Fonte: linhas 137-149 e 275-276.

Para janela `w`:

- `x = [0, 1, ..., w-1]`
- `x_center = x - mean(x)`
- `denom = sum(x_center^2)`
- `y = janela_rolling(portfolio_logret, w)`
- `slope = sum(x_center * (y - mean(y))) / denom`

### 3) Histerese (entrada e saida)

Fonte: linhas 429-439.

- **Entrada em regime defensivo:** `slope(D) < 0 AND slope(D-1) < 0`
- **Saida para regime ofensivo:** `slope(D) > 0 AND slope(D-1) > 0 AND slope(D-2) > 0`

### 4) Telemetria de regime

Fonte: linhas 442-451 e 761.

- `regime_defensivo` (bool diario)
- `num_switches` (contador de trocas de estado)

## Parametros

- `slope_windows_to_test = [3, 4, 5]` (linha 892 + summaries)
- janelas avaliadas por variante deterministic e hybrid_rl

## Evidencia quantitativa (resumo)

Fonte: `summary.json` (ablation longa e W4 combinado).

- W3 hybrid_rl: maior equity no teste longo (`409547.24`) com baixo turnover.
- W4 hybrid_rl: comportamento nao estavel na amostra longa (`213141.82`), apesar de W4 combinado favoravel em amostra curta.
- W5: menor retorno relativo e drawdown mais alto no hybrid_rl frente ao deterministic.

## Fonte (arquivo e linhas)

- `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/work/experimentos_on_flight/EXP_002_SELL_POLICY_GATE_CEP_RL_V1/run_experiment.py:137-149,275-276,429-452,761,886,892`
- `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/experimentos/on_flight/20260224/EXP_002_S008_SELLGATE_CEP_RL_ABL345_20180701_20260204_CORPACTION_BRAPI_V1/summary.json:1-146`
- `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/experimentos/on_flight/20260224/EXP1_EXP2_W4_DET_HYB_AFTER_CORP_ACTIONS_V1/native/EXP2_W4_COMBINED/summary.json:1-50`

## Adaptacao para M3

- Formula de regime e independente de F1/M3.
- Para motor canonico, priorizar `portfolio_logret` calculado sobre burners realmente em carteira (Master operacional), mantendo histerese 2-in/3-out.

