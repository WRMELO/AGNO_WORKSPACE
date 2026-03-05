# Report - TASK_TMP_EXP2_W4_AFTER_CORP_ACTIONS_V1

- generated_at_utc: `2026-02-24T19:48:54.227671+00:00`
- period: `2018-07-01..2026-02-04`
- comparabilidade: custos/timing/universo/quarentena compartilhados entre variantes e janelas

## Leitura executiva
- `deterministic`: menor complexidade, venda proporcional ao score.
- `hybrid_rl`: mesmo gate CEP para quando/quem vender; RL discreto global para quanto vender nos Top-K.
- ablação completa em `w in {3,4,5}` com todo o resto fixo.

## Tabela comparativa (resumo)

```csv
slope_w,variant,equity_final,CAGR,MDD,time_to_recover,vol_annual,downside_dev,VaR,CVaR,turnover_total,turnover_sell,turnover_reentry,num_switches,avg_holding_time,cost_total,missed_sell_rate,false_sell_rate,regret_3d,split_events_applied,decision_rows,trade_rows
4,deterministic,287312.2251212255,0.26292289432944305,-0.4714720901794216,449.0,0.608393312178272,0.17484884592178326,-0.015536458915198325,-0.02596801248432062,11.294028027864961,5.261429946700705,4.783790303082053,319,312.0204081632653,582.6518900000001,0.0,1.0,0.01827176506980885,1,67,206
4,hybrid_rl,299539.0171481412,0.269971316670059,-0.5029289678756461,1016.0,0.764983461217274,0.27249361503421915,-0.02136046743918187,-0.044664404294122904,1.865694520779996,0.6851958050143248,0.4771830736441413,319,793.3333333333334,99.51837375000001,0.9629629629629629,0.08256880733944955,0.029563000787764776,6,136,46
```

## Tradeoff churn/custo vs drawdown/retorno
- comparar `turnover_sell` e `cost_total` contra `MDD` e `CAGR` por variante/janela.
- `missed_sell_rate` e `false_sell_rate` quantificam erro de ação ex-post no horizonte de 3 dias.
- `regret_3d` resume custo de decisão relativo ao rótulo ex-post de proteção.

## Artefatos
- `summary.json`
- `tables/metrics_by_regime.csv`
- `tables/metrics_by_subperiod.csv`
- `tables/sell_decisions_all.csv`
- `evidence/feature_leakage_audit.json`
