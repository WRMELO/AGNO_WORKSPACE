# 02_Knowledge_Bank — Índice

> Última atualização: 2026-03-05
> Reorganização temática: lições consolidadas por tema do projeto, não por fase.

---

## Lessons Learned (SSOT)

Base de conhecimento consolidada do projeto. Cada documento agrupa **todas** as lições de **todas as fases** sobre um tema.

| # | Documento | Escopo | Lições |
|---|---|---|---|
| 01 | [`lessons_learned/01_GOVERNANCA.md`](lessons_learned/01_GOVERNANCA.md) | Manifest, changelog, registry, auditoria, cadeia de comando | 12 regras + checklist |
| 02 | [`lessons_learned/02_ML_MODEL.md`](lessons_learned/02_ML_MODEL.md) | Treino, CV, threshold, overfitting, generalização | 10 regras + checklist |
| 03 | [`lessons_learned/03_FEATURE_ENGINEERING.md`](lessons_learned/03_FEATURE_ENGINEERING.md) | Construção, seleção, validação de features | 6 regras + checklist |
| 04 | [`lessons_learned/04_BACKTEST.md`](lessons_learned/04_BACKTEST.md) | Ablação, histerese, custos, constraints, motor | 11 regras + checklist |
| 05 | [`lessons_learned/05_ARQUITETURA.md`](lessons_learned/05_ARQUITETURA.md) | Motor, forno dual-mode, fábricas, sinais | 9 princípios |
| 06 | [`lessons_learned/06_DADOS.md`](lessons_learned/06_DADOS.md) | Ingestão, SSOT, qualidade, anti-lookahead | 7 regras + tabela SSOTs + checklist |
| 07 | [`lessons_learned/07_PROCESSO.md`](lessons_learned/07_PROCESSO.md) | Workflow, evidência visual, ciclo de execução | 8 princípios |
| 08 | [`lessons_learned/08_PRODUTO.md`](lessons_learned/08_PRODUTO.md) | Winners, decisões do Owner, operação real | Estado do produto + diagrama |

---

## Documentação ativa

### Normas e emendas
| Documento | Escopo | Status |
|---|---|---|
| [`docs/CONSTITUICAO.md`](docs/CONSTITUICAO.md) | Constituição V1 — princípios normativos e decisões seed | ATIVO |
| [`docs/emendas/EMENDA_COST_MODEL_ARB_0025PCT_V1.md`](docs/emendas/EMENDA_COST_MODEL_ARB_0025PCT_V1.md) | Custo 2.5 bps sobre notional | ATIVO |
| [`docs/emendas/EMENDA_CASH_REMUNERACAO_CDI_V1.md`](docs/emendas/EMENDA_CASH_REMUNERACAO_CDI_V1.md) | Remuneração de caixa por CDI | ATIVO |

### Specs técnicas
| Documento | Escopo |
|---|---|
| [`docs/specs/SPEC-007_THERMOSTAT_FORNO_DUAL_MODE_T071.md`](docs/specs/SPEC-007_THERMOSTAT_FORNO_DUAL_MODE_T071.md) | Termostato endógeno do forno dual-mode |
| [`docs/specs/SPEC-083_PIPELINE_DADOS_US_T083.md`](docs/specs/SPEC-083_PIPELINE_DADOS_US_T083.md) | Pipeline de dados US (S&P 500) |
| [`docs/specs/SPEC-001_SEVERITY_SCORE.md`](docs/specs/SPEC-001_SEVERITY_SCORE.md) | Severity Score multi-fator |
| [`docs/specs/SPEC-002_MASTER_GATE_REGIME.md`](docs/specs/SPEC-002_MASTER_GATE_REGIME.md) | Master Gate de regime |
| [`docs/specs/SPEC-003_PARTIAL_SELLS.md`](docs/specs/SPEC-003_PARTIAL_SELLS.md) | Partial Sells D+1 |
| [`docs/specs/SPEC-004_NELSON_RULES_INTEGRATION.md`](docs/specs/SPEC-004_NELSON_RULES_INTEGRATION.md) | Nelson Rules para SPC |
| [`docs/specs/SPEC-005_METRICS_SUITE.md`](docs/specs/SPEC-005_METRICS_SUITE.md) | Suite de métricas formais |
| [`docs/specs/SPEC-006_RL_FRAMEWORK.md`](docs/specs/SPEC-006_RL_FRAMEWORK.md) | Framework RL (descartado — ver LL-PH6-012) |
| [`docs/specs/GLOSSARY_OPERATIONAL.md`](docs/specs/GLOSSARY_OPERATIONAL.md) | Glossário operacional |

### Análises e handoffs
| Documento | Escopo |
|---|---|
| [`docs/process/STATE3_CTO_ANALYSIS_POST_PHASE8_PRE_PHASE9.md`](docs/process/STATE3_CTO_ANALYSIS_POST_PHASE8_PRE_PHASE9.md) | Análise CTO com 7 achados (fundamenta Phase 9) |
| [`docs/process/STATE3_PHASE9_HANDOFF.md`](docs/process/STATE3_PHASE9_HANDOFF.md) | Handoff Phase 8→9 (conceito Duas Fábricas) |

### Referências fundacionais
| Documento | Escopo |
|---|---|
| [`docs/fundacional/LL-20260220-W1-METHODOLOGY-001.json`](docs/fundacional/LL-20260220-W1-METHODOLOGY-001.json) | Gênese da regra "sem pacote governado = inválido" |
| [`docs/fundacional/LL-20260221-EXECUTION-DUAL-PASS-001.json`](docs/fundacional/LL-20260221-EXECUTION-DUAL-PASS-001.json) | Origem do critério dual-pass |

---

## Arquivo histórico

### Por fase (lessons learned originais)
`archive/by_phase/` — 8 documentos originais de lessons learned por fase (phases 2, 3, 4, 5, 6, 8, 9, 10). Preservados para rastreabilidade cronológica.

### Supersedidos
`archive/superseded/` — documentos que foram substituídos por evolução do projeto: Masterplan V1/V2, FSM decisor V1, specs de regras locais, transfer packages.

### Legado
`archive/legacy/` — corpus legado do CEP_BUNDLE_CORE: Critical_Intel, Legacy_Corpus, VectorStore RAG, outputs e planning legados. Valor apenas como audit trail.
