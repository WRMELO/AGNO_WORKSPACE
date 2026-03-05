# Report - TASK_CEP_BUNDLE_CORE_EXP_001_TICKER_ROTATION_FULLPERIOD_V1

- generated_at_utc: `2026-02-23T20:00:46.863980+00:00`
- exp_outputs_root: `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/experimentos/on_flight/20260223/EXP_001_S008_TOP10S45_STRESSSELL_2019_20210630_V1`
- period_requested: `2019-01-01..2021-06-30`
- calendar_used_from_ledger: `2019-01-02..2021-06-30`
- positions_real_range: `2019-01-02..2021-06-30`

## Definicoes aplicadas
- entry = transicao qty 0 -> >0 em fim de dia
- exit = transicao qty >0 -> 0 em fim de dia
- roundtrip = entry seguida de exit subsequente
- holding_period = dias inclusivos entre entry_date e exit_date
- gap_out = dias entre exit e proxima entry
- quick_reentry_threshold_days = 5

## Agregados
- tickers_used_count = 15
- mediana_roundtrips = 7.00
- mediana_quick_reentries = 1.00
- distribuicao_roundtrips: 0=2, 1=0, 2=2, 3+=11
- discrepancies_count = 15

## Destaque solicitado
- ALUP11: roundtrips=6 (mediana=7.00), quick_reentries=1 (mediana=1.00), days_held_total=567
- BEES3: roundtrips=5 (mediana=7.00), quick_reentries=2 (mediana=1.00), days_held_total=548

## Discrepancias positions vs trades
- Ver `discrepancies.parquet` para tickers com diferenças e amostras de datas.

## Complemento visual solicitado
- plot_html: `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/experimentos/on_flight/20260223/EXP_001_S008_TOP10S45_STRESSSELL_2019_20210630_V1/audit_trade_counts/rotation_fullperiod/plotly_equity_tickers_vs_portfolio_fullperiod.html`
- series_parquet: `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/experimentos/on_flight/20260223/EXP_001_S008_TOP10S45_STRESSSELL_2019_20210630_V1/audit_trade_counts/rotation_fullperiod/equity_tickers_vs_portfolio_series.parquet`
- definicao usada por ticker: `equity_individual_brl = qty * close_d_1`
- curva da carteira: `equity_d_brl` (ledger/equity_curve)
