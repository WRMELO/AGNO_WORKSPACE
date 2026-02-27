# SPEC-005 - Metrics Suite (Legado EXP_002)

## Objetivo

Padronizar o pacote completo de metricas para avaliacao de performance, risco, eficiencia de execucao e qualidade da decisao.

## Metricas primarias (17)

Fonte: `run_experiment.py` linhas 184-214 e 729-770.

1. `equity_final` = ultimo valor da equity (BRL)
2. `CAGR` = `((eq_final/eq_ini)^(1/years))-1` (razao anual)
3. `MDD` = `min(eq/cummax(eq)-1)` (razao)
4. `time_to_recover` = dias para recuperar pico apos pior DD (dias)
5. `vol_annual` = `std(ret_diario)*sqrt(252)` (razao anual)
6. `downside_dev` = `std(min(ret_diario,0))*sqrt(252)` (razao anual)
7. `VaR` = `quantile(ret_diario,0.05)` (razao)
8. `CVaR` = `mean(ret_diario <= VaR)` (razao)
9. `turnover_total` = `(notional_buy + notional_sell)/avg_equity` (x do equity medio)
10. `turnover_sell` = `notional_sell/avg_equity` (x do equity medio)
11. `turnover_reentry` = `notional_buy_reentry/avg_equity` (x do equity medio)
12. `num_switches` = trocas de regime defensivo (inteiro)
13. `avg_holding_time` = media de holding_days (dias)
14. `cost_total` = soma de custos de trade (BRL)
15. `missed_sell_rate` = `count(should=1 and sell=0)/count(should=1)` (proporcao)
16. `false_sell_rate` = `count(should=0 and sell>0)/count(should=0)` (proporcao)
17. `regret_3d` = `mean(abs(action01-oracle)*abs(worst_cumret_3d))` (razao)

## Segmentacao obrigatoria

Fonte: linhas 772-797 e 920-925.

- `metrics_by_regime.csv`: metricas por `regime_defensivo` (True/False).
- `metrics_by_subperiod.csv`: metricas por subperiodos (2019, 2020, 2021H1 no legado).

## Parametros de calculo

- `ANN_FACTOR = 252`
- retornos diarios da equity via `pct_change`.
- `avg_equity = mean(equity_d_brl)`.

## Evidencia quantitativa (summaries)

- Amostra longa (`2018-07-01..2026-02-04`) e W4 combinado foram publicados em JSON.
- As 17 metricas estao materializadas por variante e janela.

## Fonte (arquivo e linhas)

- `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/work/experimentos_on_flight/EXP_002_SELL_POLICY_GATE_CEP_RL_V1/run_experiment.py:184-214,729-770,772-797,920-925`
- `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/experimentos/on_flight/20260224/EXP_002_S008_SELLGATE_CEP_RL_ABL345_20180701_20260204_CORPACTION_BRAPI_V1/summary.json:1-146`
- `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/experimentos/on_flight/20260224/EXP1_EXP2_W4_DET_HYB_AFTER_CORP_ACTIONS_V1/native/EXP2_W4_COMBINED/summary.json:1-50`

## Adaptacao para M3

- Este pacote e agnostico ao ranking de compra.
- Deve ser mantido sem alteracao de formula para comparabilidade historica entre F1 legado e M3 canonico.

