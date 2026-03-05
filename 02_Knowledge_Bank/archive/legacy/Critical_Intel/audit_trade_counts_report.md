# Report - TASK_CEP_BUNDLE_CORE_EXP_001_RECONCILE_BUY_SELL_COUNTS_V1

- exp_outputs_root: `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/experimentos/on_flight/20260223/EXP_001_S008_TOP10S45_STRESSSELL_2019_20210630_V1`
- generated_at_utc: `2026-02-23T18:12:11.144781+00:00`

## Contagens operacionais
- num_compras (operacoes BUY): `382`
- num_vendas (operacoes SELL): `103`
- buy_days: `128`
- sell_days: `92`

## Tickers
- unique_buy_tickers: `15`
- unique_sell_tickers: `13`
- intersection_unique_tickers: `13`

## Conclusao sobre 382 vs 103
- status: `COMPATIVEL`
- detalhe: Diferença 382 vs 103 é consistente com contagem de operações: múltiplas compras de topup/nova entrada e menos eventos de venda por stress.
