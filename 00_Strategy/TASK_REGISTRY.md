# AGNO TASK REGISTRY & PRODUCT STATE

## STATE 1: CANONICAL DATA ENGINE (STABLE)

**Status:** [ COMPLETED ] | **Artifact:** `SSOT_CANONICAL_BASE.parquet`
| ID | Task Name | Phase | Status | Key Artifacts |
|---|---|---|---|---|
| T020 | Sanity (S001) | Data Engine | DONE | SSOT UNIVERSE CLEAN |
| T021 | Market Data Backfill | Data Engine | DONE | SSOT OPERATIONAL |
| T022 | Macro SSOT Builder | Data Engine | DONE | SSOT MACRO |
| T023 | Canonical Builder (SPC) | Data Engine | DONE | SSOT CANONICAL BASE |

## STATE 2: DATA QUALITY & CERTIFICATION (STABLE)

**Status:** [ COMPLETED ] | **Artifact:** `SSOT_QUALITY_BLACKLIST_A001.json`
| ID | Task Name | Phase | Status | Key Artifacts |
|---|---|---|---|---|
| A-001 | SSOT Canonical Base Audit | Audit | DONE | Auditoria forense. G1/G2/G5 PASS. Certificada com nota. |
| BL-001 | Quality Blacklist A-001 | Data Quality | DONE | 16 tickers excluídos. 663 tickers operacionais. |

## ARCHIVED: T024-T036 (DESCONTINUADO)

**Status:** [ ARCHIVED ] | **Motivo:** Divergência arquitetural com Constituição V2 e MASTERPLAN V2. Ranking F1 descartado em favor do M3 canônico.
| ID | Task Name | Phase | Status | Nota |
|---|---|---|---|---|
| T024 | Diagnostic Engine Strict | Diagnostics | ARCHIVED | Artefatos em `archive/T024_T036/` |
| T025 | Visual Validation Diagnostics | Diagnostics | ARCHIVED | Artefatos em `archive/T024_T036/` |
| T027 | F1 Championship Build | Diagnostics | ARCHIVED | F1 descartado; M3 é o ranking canônico |
| T028 | Portfolio Simulation Engine V2 | Portfolio | ARCHIVED | Baseado em F1 (não M3) |
| T029 | Portfolio Visualization | Portfolio | ARCHIVED | Artefatos em `archive/T024_T036/` |
| T030 | Restore EXP001 Mechanics | Portfolio | ARCHIVED | Histerese sem Master Gate CEP |
| T031 | RL Balancing Layer | Portfolio | ARCHIVED | Regras estáticas, não RL real |
| T032 | Deep Diagnostics Report | Audit | ARCHIVED | Achados incorporados na análise arquitetural |
| T033 | Corrective Logic Implementation | Portfolio | ARCHIVED | Correção parcial sobre base F1 |
| T034 | Audit Sizing Logic | Audit | ARCHIVED | Achados incorporados (score_m0/M3) |
| T035 | EXP001 Exact Clone | Portfolio | ARCHIVED | Clone parcial sem Master Gate CEP |
| T036 | Real Equity Visualization | Portfolio | ARCHIVED | Visualização do clone T035 |

## STATE 3: M3 CANONICAL STRATEGY ENGINE (STABLE)

**Status:** [ COMPLETED ] | **Baseline:** M3 = `z(score_m0) + z(ret_62) - z(vol_62)` | **Encerramento (Plotly):** `outputs/plots/T041_STATE3_PHASE1_COMPARATIVE.html` | **Governança:** Constituição V2 + MASTERPLAN V2
| ID | Task Name | Phase | Status | Objective |
|---|---|---|---|---|
| T037 | M3 Canonical Engine | Strategy | DONE | Baseline M3 estabelecido. Artefatos: `T037_M3_SCORES_DAILY.parquet` (866K ticker-days), `T037_PORTFOLIO_LEDGER.parquet`, `T037_PORTFOLIO_CURVE.parquet`, `T037_BASELINE_SUMMARY.json`. CAGR=8.8%, MDD=-45.0%, Sharpe=0.56. Audit PASS. |
| T038 | Master Gate Integration | Strategy | DONE | Master Gate implementado: slope `portfolio_logret` W=4, histerese 2-in/3-out. Artefatos: `T038_PORTFOLIO_LEDGER.parquet`, `T038_PORTFOLIO_CURVE.parquet`, `T038_BASELINE_SUMMARY.json`. CAGR=2.8%, MDD=-47.9%, Sharpe=0.25, days_defensive=71.9%, num_switches=300. Audit PASS. |
| T039 | Severity Score + Partial Sells | Strategy | DONE | Severity Score multi-fator (SPEC-001) + Partial Sells D+1 em 3 níveis (SPEC-003) + Nelson Proxies (SPEC-004) + Anti-Reentry. Artefatos: `T039_PORTFOLIO_LEDGER.parquet`, `T039_PORTFOLIO_CURVE.parquet`, `T039_BASELINE_SUMMARY.json`, `T039_M3_SCORES_DAILY.parquet`. CAGR=3.0%, MDD=-44.9%, Sharpe=0.25. Sells: 25%=97, 50%=61, 100%=95. Audit PASS. |
| T040 | Metrics Suite Formal (SPEC-005) | Strategy | DONE | Materialização do pacote de métricas para T037/T038/T039 com `ANN_FACTOR=252`. Artefatos: `T040_METRICS_COMPARATIVE.json`, `T040_METRICS_BY_REGIME.csv`, `T040_METRICS_BY_SUBPERIOD.csv`. Coerência com baselines confirmada (CAGR diff < 0.1pp). Audit PASS. |
| T041 | Plotly Comparativo STATE 3 Phase 1 | Visualization | DONE | HTML interativo com 5 curvas (T037/T038/T039/CDI/Ibov) normalizadas base R$100k, shading de regime defensivo (150 intervalos), tabela T040 com 11 métricas e anotações de eventos. Artefato: `outputs/plots/T041_STATE3_PHASE1_COMPARATIVE.html` (~419KB). Baseline visual oficial STATE 3 Phase 1. Audit PASS. |

### NEXT — STATE 3 Phase 2 (PLANNED)

| ID | Task Name | Phase | Status | Objective |
|---|---|---|---|---|
| T043 | Local Rule Capture Protocol + Condition Ledger Schema | Strategy | DONE | Protocolo de captura de regras locais (CEP/Nelson/WE) sob condições determinadas + schema do Condition Ledger (blocos Mercado/Master). Terminologia mandatória fixada (Master=Carteira, Mercado=Ibov). Artefatos: `02_Knowledge_Bank/docs/process/STATE3_LOCAL_RULE_CAPTURE_PROTOCOL.md`, `STATE3_CONDITION_LEDGER_SCHEMA.md`. Audit PASS. |
| T048 | Condition Ledger Implementation (Mercado vs Master) | Strategy | PENDING | Implementar geração do ledger diário conforme `02_Knowledge_Bank/docs/process/STATE3_CONDITION_LEDGER_SCHEMA.md` com gate terminológico `G0_GLOSSARY_COMPLIANCE` e manifesto SHA256. |
| T049 | Episode Catalog Builder | Strategy | PENDING | Segmentar episódios por persistência de sinais do Mercado e materializar catálogo com métricas de deriva/custos por episódio. |
| T050 | State Decisor (Finite State Machine) | Strategy | PENDING | Implementar especificação do decisor (estados mutuamente exclusivos) baseado primariamente em condições do Mercado; sem mistura bull/bear; com histerese apenas em transição. |
| T051 | Local Rules Candidates (CEP/Nelson/WE) | Strategy | PENDING | Capturar e documentar regras locais fortes por estado, com critérios de promoção/robustez por subperíodo. |
| T052 | Robustness Report (Subperiods) | Strategy | PENDING | Consolidar relatório de robustez e decisão de promoção de regras locais antes de qualquer ajuste de guardrails. |
| T045 | Plotly Accounting Decomposition (P&L/Cost/Cash) | Visualization | PENDING | Decomposição interativa baseada no ledger (inspirado no spec Masterplan V2 F1_002). |
| T046 | Envelope / Guardrails Plotly Audit | Visualization | PENDING | Auditoria visual do envelope/fallback (inspirado no spec Masterplan V2 F2_003). |
| T044 | Anti-Drift Guardrails (turnover/cadence caps) | Strategy | PENDING | Implementar guardrails e validar impacto em métricas T040 (sem quebrar reprodutibilidade), somente após `T052`. |
| T047 | Oracle-dependent Metrics (definitions + implementation) | Metrics | PENDING | Definir e implementar métricas `missed_sell_rate`, `false_sell_rate`, `regret_3d` com critérios objetivos e evidência, após baseline estabilizado. |
