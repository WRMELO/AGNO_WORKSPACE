# ARQUIVO MORTO — T024 a T036

**Data:** 2026-02-27
**Motivo:** Divergência arquitetural com Constituição V2 e MASTERPLAN V2. Ranking F1 (T027) substituído por M3 canônico. Simulações de portfólio reconstruídas a partir de T037.
**Decisão:** Owner autorizou arquivamento e reconstrução sobre base canônica aprovada.

## Artefatos arquivados

### Scripts (11 arquivos)
| Script | Task | Descrição |
|--------|------|-----------|
| t024_build_burner_diagnostics_strict.py | T024 | Engine de diagnóstico SPC com slope/vol |
| t025_plot_diagnostics.py | T025 | Validação visual de diagnósticos |
| t027_build_f1_championship.py | T027 | Campeonato F1 (ranking descartado) |
| t028_portfolio_simulation_engine_v2.py | T028 | Simulador de portfólio V2 |
| t029_plot_final_comparative.py | T029 | Plotly comparativo (versão corrigida) |
| t029_plot_final_comparison.py | T029 | Plotly comparativo (versão inicial) |
| t030_restore_exp001_mechanics.py | T030 | Histerese e emergency derivative |
| t031_rl_balancing_layer.py | T031 | Camada de balanceamento (mislabeled RL) |
| t033_corrected_logic.py | T033 | Filtro slope + ranking risk-adjusted |
| t035_exp001_clone.py | T035 | Clone exato do EXP_001 |
| t036_real_equity_visualization.py | T036 | Visualização equity real (R$) |

### Parquets de dados derivados (11 arquivos)
- `diagnostics/SSOT_BURNER_DIAGNOSTICS.parquet` — T024 output
- `features/SSOT_F1_SCORES_DAILY.parquet` — T027 output (F1 descartado)
- `features/SSOT_F1_STANDINGS.parquet` — T027 output (F1 descartado)
- `portfolio/SSOT_PORTFOLIO_LEDGER.parquet` — T031 output (sobrescreveu T028)
- `portfolio/SSOT_PORTFOLIO_CURVE.parquet` — T031 output (sobrescreveu T028)
- `portfolio/SSOT_PORTFOLIO_LEDGER_EXP001.parquet` — T030 output
- `portfolio/SSOT_PORTFOLIO_CURVE_EXP001.parquet` — T030 output
- `portfolio/SSOT_PORTFOLIO_LEDGER_CORRECTED.parquet` — T033 output
- `portfolio/SSOT_PORTFOLIO_CURVE_CORRECTED.parquet` — T033 output
- `portfolio/SSOT_PORTFOLIO_LEDGER_CLONE.parquet` — T035 output
- `portfolio/SSOT_PORTFOLIO_CURVE_CLONE.parquet` — T035 output

### Visualizações (8 arquivos)
- `verification_plots/T025_DIAGNOSTIC_CHECK/` — 3 PNGs de validação
- `verification_plots/T029_Final_Comparative.html`
- `verification_plots/T031_Portfolio_vs_CDI.html`
- `verification_plots/T033_Portfolio_vs_CDI_Overlay.html`
- `verification_plots/T035_Comparative_T031_T033_T035_CDI.html`
- `verification_plots/T036_Real_Equity_Comparison.html`

### Documentos
- `strategy/DIAGNOSTIC_REPORT_T032.md` — Relatório de diagnóstico profundo

## SSOTs PRESERVADOS (não movidos)
- `src/data_engine/ssot/SSOT_CANONICAL_BASE.parquet` — Base certificada A-001
- `src/data_engine/ssot/SSOT_MACRO.parquet` — Dados macro
- `src/data_engine/ssot/SSOT_MARKET_DATA_RAW.parquet` — Dados brutos
- `src/data_engine/ssot/SSOT_UNIVERSE_OPERATIONAL.parquet` — Universo operacional
- `src/data_engine/ssot/SSOT_QUALITY_BLACKLIST_A001.json` — Blacklist (NOVO)
