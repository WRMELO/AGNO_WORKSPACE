# Report - TASK_CEP_BUNDLE_CORE_EXP_001_AUDIT_DRAWDOWN_WINDOWS_V1

- exp_outputs_root: `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/experimentos/on_flight/20260223/EXP_001_S008_TOP10S45_STRESSSELL_2019_20210630_V1`
- generated_at_utc: `2026-02-23T18:12:11.136601+00:00`

## Janelas auditadas
- W1: 2019-11-18..2019-12-05
- W2: 2020-02-28..2020-03-24
- W3: 2020-07-31..2020-10-13
- W4: 2021-02-12..2021-03-08

## Entregas
- windows_summary.parquet
- trades_in_windows.parquet
- stress_events_in_windows.parquet
- ticker_contrib_in_windows.parquet
- plot_windows_base1.html

## Causas comuns (baseadas em evidências cruzadas)
- stress_sell_signal_count_por_janela: {'W1': 3, 'W2': 9, 'W3': 6, 'W4': 1}
- trades_por_janela_side:
  - W1: BUY=11, SELL=3
  - W2: BUY=15, SELL=10
  - W3: BUY=25, SELL=6
  - W4: BUY=8, SELL=2
- comparativo_retornos_por_janela:
  - W1: equity=-0.111988, bvsp=0.040199, sp500=-0.001473
  - W2: equity=-0.039361, bvsp=-0.330636, sp500=-0.171582
  - W3: equity=-0.100453, bvsp=-0.042842, sp500=0.073617
  - W4: equity=-0.067309, bvsp=-0.071393, sp500=-0.028840
