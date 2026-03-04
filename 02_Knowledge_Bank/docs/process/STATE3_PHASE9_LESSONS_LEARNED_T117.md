# STATE 3 Phase 9 — Lessons Learned (T117)

**Gerado em**: 2026-03-04T17:00:00Z
**Task**: T117
**Ciclo coberto**: T112 → T113 → T114 → T115 → T116-CANCEL
**Winner Fábrica BR (inalterada)**: C060X (N=10, thr=0.22, h_in=3, h_out=2, universo BR+BDR): Sharpe 2.42, MDD=-6.3%, CAGR=31.1%
**Winner Fábrica US**: T115-ML-US (thr=0.45, h_in=1, h_out=3, S&P 500 índice único): Sharpe 1.20, MDD=-13.0%, CAGR=14.2% USD

## 1) Contexto do ciclo

- **Escopo**: STATE 3 Phase 9 — Duas Fábricas: construir motor ML para mercado americano (S&P 500 em USD) com ML trigger próprio e Fed funds como tank de caixa, operando em paralelo à Fábrica BR (C060X, baseline fixo).
- **Objetivo-mestre**: produzir Fábrica US com ML trigger que reduza drawdown do S&P 500 e, ao final, avaliar consolidação BR+US via ablação de split.
- **Walk-forward**: TRAIN 2018-07-02 → 2022-12-30 (1.115 pregões) | HOLDOUT 2023-01-02 → 2026-02-26 (787 pregões).
- **Dual acid window**: acid_br (2024-11-01 → 2025-11-30, 268 pregões) + acid_us (2025-03-06 → 2025-05-09, 44 pregões, tariff war), ambas 100% HOLDOUT.
- **Sub-fases**: 9A (labels oracle US), 9B (feature matrix US), 9C (XGBoost US), 9D (backtest isolado US), 9E (consolidação — cancelada), 9F (LL + closeout).
- **Resultado final**: Fábrica US operacional como escudo de drawdown, mas **não gera alfa sobre SP500 buy-hold** (Sharpe 1.20 vs 1.34). Consolidação BR+US marginal (Sharpe max 2.48 a 20%US vs 2.42 puro BR). Decisão Owner: fábricas independentes com capital próprio, sem split.
- **Evidência de fechamento visual**: `outputs/plots/T115_STATE3_PHASE9D_US_FACTORY_BACKTEST.html`.
- **Referências de governança**: `00_Strategy/ROADMAP.md`, `00_Strategy/TASK_REGISTRY.md`, `00_Strategy/OPS_LOG.md`.

## 2) O que deu certo

- **LL-PH9-001** (PIPELINE): Pipeline ML replicável cross-market — o ciclo de 4 etapas (labels → features → XGBoost → backtest) comprovou ser portátil. Transpor da Fábrica BR para US levou 4 tasks (T112-T115) com zero regressão no pipeline BR. [evidência: `T112-T115` | `00_Strategy/TASK_REGISTRY.md`]
- **LL-PH9-004** (VALIDACAO): Dual acid window é boa prática — testar com janelas de stress específicas por mercado (acid_br = nov/2024-nov/2025, acid_us = mar-mai/2025 tariff war) provou ser mais informativo que uma janela única genérica. Adotar como padrão em tasks futuras. [evidência: `T114/T115` | `outputs/governanca/T115-PHASE9D-US-BACKTEST-V1_evidence/dual_acid_metrics.json`]
- **LL-PH9-008** (GOVERNANCA): Feature guard como controle anti-contaminação — a implementação explícita de `feature_guard.json` (T114) resolveu de forma definitiva o problema recorrente de colunas auxiliares (`sp500_close`) contaminando o modelo. Finding F-01/F-02 recorrentes de T112/T113 foram eliminados. Adotar como padrão em toda task ML futura. [evidência: `T114` | `outputs/governanca/T114-PHASE9C-ML-US-V1_evidence/feature_guard.json`]

## 3) O que não deu certo — Limitações identificadas

### Diagnóstico: Motor US não gera alfa

| Métrica | Fábrica US (T115) | SP500 Buy-Hold | Diferença |
|---|---|---|---|
| CAGR HOLDOUT | 14.2% | 20.6% | -6.4pp |
| MDD HOLDOUT | -13.0% | -18.9% | +5.9pp (melhor) |
| Sharpe HOLDOUT | 1.20 | 1.34 | -0.14 |
| Precision HOLDOUT | 17.7% | n/a | 82% falsos positivos |

- **LL-PH9-002** (ESTRATEGIA): Features macro insuficientes para mercado eficiente — as 27 features macro (VIX, DXY, Treasury, Fed funds, S&P 500 derivados) geram Sharpe 1.20 no US vs 2.42 no BR com features análogas. O mercado americano é mais eficiente; features macro puras não têm poder preditivo suficiente para gerar alfa. [evidência: `T114/T115` | `src/data_engine/portfolio/T115_US_FACTORY_SUMMARY.json`]
- **LL-PH9-003** (ESTRATEGIA): ML trigger US funciona como escudo, não como gerador de alfa — no HOLDOUT, a estratégia reduziu MDD de -18.9% (SP500) para -13.0%, mas o Sharpe ficou abaixo do buy-hold (1.20 vs 1.34). O trigger destrói valor risk-adjusted porque a precision é baixa (17.7% — 82% dos sinais de cash são falsos positivos). [evidência: `T115` | `src/data_engine/portfolio/T115_US_FACTORY_SUMMARY.json`]

### Diagnóstico: Consolidação BR+US marginal

| Split US% | Sharpe | CAGR | MDD | Equity BRL |
|---|---|---|---|---|
| 0% (só BR) | 2.42 | 31.1% | -6.3% | R$232k |
| 20% (ótimo) | 2.48 | 27.9% | -5.3% | R$215k |
| 50% | 2.13 | 22.7% | -8.9% | R$189k |
| 100% (só US) | 0.91 | 12.8% | -20.4% | R$145k |

- **LL-PH9-005** (ESTRATEGIA): Consolidação marginal com ativo inferior — quando uma fábrica tem Sharpe muito superior à outra (2.42 vs 1.20), consolidar reduz retorno sem compensar proporcionalmente em risco. O ponto ótimo (20% US, +0.06 Sharpe) não justifica -3.2pp CAGR e complexidade operacional. [evidência: análise CTO exploratória]
- **LL-PH9-006** (ESTRATEGIA): Correlação baixa não garante ganho — correlação diária BR vs US(BRL) = 0.13 (excelente para diversificação teórica), mas como a Fábrica US rende menos, diversificar dilui em vez de amplificar. [evidência: análise CTO exploratória]
- **LL-PH9-007** (FX): PTAX como fator de risco real — no HOLDOUT, o dólar caiu -3.8% contra o real. Posições em USD convertidas para BRL sofrem penalidade cambial em períodos de real forte. [evidência: `src/data_engine/ssot/SSOT_FX_PTAX_USDBRL.parquet`]

## 4) Decisões do Owner

- **LL-PH9-009** (DECISAO): Fábricas independentes com capital próprio — o Owner decidiu que as duas fábricas operam como entidades completamente separadas, sem split de alocação, sem interdependência. A consolidação em BRL via PTAX é apenas visualização financeira, não decisão de alocação. Simplifica monitoramento e elimina risco de otimização de split sobre retornos passados. [decisão: chat Phase 9, pré-T116]
- **LL-PH9-010** (DIRECAO): Motor US precisa de melhoria para uso em produção — Sharpe 1.20 < SP500 1.34 significa que o motor destrói valor risk-adjusted. Direções identificadas pelo CTO para a Phase 10: (a) seleção de ações por scoring M3-US (não índice único), (b) features mais granulares (earnings, credit spreads, flows), (c) threshold/histerese recalibrados. A hipótese central é que aplicar stock selection (como a Fábrica BR faz com sucesso) sobre as ~496 ações individuais do S&P 500 pode gerar o alfa que o timing sobre índice não consegue. [decisão: chat Phase 9, pós-análise CTO]

## 5) Tabela comparativa — Fábrica BR vs Fábrica US (HOLDOUT)

| Métrica | Fábrica BR (C060X) | Fábrica US (T115) | SP500 BH | Cash Fed Funds |
|---|---|---|---|---|
| Equity | R$232.817 | $151.583 USD | $179.484 USD | $115.562 USD |
| CAGR | 31.1% | 14.2% | 20.6% | 4.7% |
| MDD | -6.3% | -13.0% | -18.9% | ~0% |
| Sharpe | 2.42 | 1.20 | 1.34 | n/a |
| Cash fraction | ~15% | 14.4% | 0% | 100% |
| Switches | ~20 | 22 | 0 | 0 |

## 6) Checklist anti-regressão Phase 10

1. Anti-lookahead estrito (`shift(1)`) em toda feature — sem exceção.
2. Walk-forward: TRAIN 2018-07-02 → 2022-12-30, HOLDOUT 2023-01-02 → 2026-02-26.
3. Feature guard obrigatório em toda task ML (`feature_guard.json`).
4. Dual acid window obrigatório (acid_br + acid_us).
5. Fábrica BR (C060X) é baseline fixo — não alterar.
6. Fábricas BR e US operam com capital próprio, sem split (decisão Owner Phase 9).
7. Benchmark US a bater: Sharpe > 1.34 (SP500 buy-hold HOLDOUT).
8. Custo operação US: 1 bp por transação.
9. Tank US: Fed funds rate (SSOT_MACRO_EXPANDED).
10. Script incluído em `outputs_produced` no manifest (LL-PH9 recorrente T112/T113, corrigido em T114).
11. Changelog idempotente (LL-PH8-013).
12. Report.md com evidência de todos os gates (LL-PH8 T086 V1→V2).

## 7) Artefatos de referência

| Artefato | Path |
|---|---|
| T112 labels oracle US | `src/data_engine/features/T112_US_LABELS_DAILY.parquet` |
| T113 feature matrix US | `src/data_engine/features/T113_US_FEATURE_MATRIX_DAILY.parquet` |
| T114 ML predictions US | `src/data_engine/features/T114_US_ML_PREDICTIONS_DAILY.parquet` |
| T114 selected config | `src/data_engine/features/T114_US_ML_SELECTED_CONFIG.json` |
| T115 US factory curve | `src/data_engine/portfolio/T115_US_FACTORY_CURVE_DAILY.parquet` |
| T115 summary | `src/data_engine/portfolio/T115_US_FACTORY_SUMMARY.json` |
| T115 dashboard | `outputs/plots/T115_STATE3_PHASE9D_US_FACTORY_BACKTEST.html` |
| C060X curve (BR) | `src/data_engine/portfolio/CTO_C060_EXPANDED_ABLATION_WINNER_CURVE.parquet` |
| SSOT macro | `src/data_engine/ssot/SSOT_MACRO_EXPANDED.parquet` |
| SSOT PTAX | `src/data_engine/ssot/SSOT_FX_PTAX_USDBRL.parquet` |
| SSOT US market data | `src/data_engine/ssot/SSOT_US_MARKET_DATA_RAW.parquet` |
| SSOT US universe | `src/data_engine/ssot/SSOT_US_UNIVERSE_OPERATIONAL.parquet` |
