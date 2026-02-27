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

## STATE 3: M3 CANONICAL STRATEGY ENGINE (ACTIVE)

**Status:** [ IN PROGRESS ] | **Baseline:** M3 = `z(score_m0) + z(ret_62) - z(vol_62)` | **Governança:** Constituição V2 + MASTERPLAN V2
| ID | Task Name | Phase | Status | Objective |
|---|---|---|---|---|
| T037 | M3 Canonical Engine | Strategy | DONE | Baseline M3 estabelecido. Artefatos: `T037_M3_SCORES_DAILY.parquet` (866K ticker-days), `T037_PORTFOLIO_LEDGER.parquet`, `T037_PORTFOLIO_CURVE.parquet`, `T037_BASELINE_SUMMARY.json`. CAGR=6.4%, MDD=-49.8%, Sharpe=0.43. Audit PASS. |
| T038 | Master Gate Integration | Strategy | PENDING | Regime da Carteira (Master Gate): slope do `portfolio_logret` com histerese 2-in/3-out sobre T037 (per SPEC-002 e Glossario fixado). |
| T039 | Severity Score + Partial Sells | Strategy | PENDING | Severity Score (SPEC-001), Partial Sells (SPEC-003), Nelson Proxies (SPEC-004), Anti-Drift: histerese + turnover cap + anti-reentry (MASTERPLAN V2). |
