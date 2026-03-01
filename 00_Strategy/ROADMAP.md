# ROADMAP Oficial - Pos T006

## Objetivo

Executar a evolucao do ambiente AGNO com foco em portabilidade, reducao de complexidade operacional e governanca orientada a `Overall PASS`.

---

## STATE 3 — Phase 3: participação sem reabrir deriva

**Objetivo do ciclo**: recuperar **participação no mercado acionário** (exposure / time-in-market) **sem** reabrir deriva/drawdown, com **seleção data-driven** (ablação + regra objetiva), evitando parâmetros arbitrários.

> Governança (original): este ROADMAP concentra **planejamento/backlog**. O `00_Strategy/TASK_REGISTRY.md` mantém apenas tarefas que definiram **estados estáveis** (DONE/COMPLETED/ARCHIVED).

### Fase 3A — Diagnóstico: dependência do período inicial (Start 2023)

**Objetivo**: testar **path-dependence** e reavaliar o comportamento a partir do 1º pregão de 2023 (rebasing R$100k), mantendo comparabilidade visual no estilo T055.

| ID | Task Name | Phase | Status | Key Artifacts / Logs | Timestamp |
|---|---|---|---|---|---|
| T058 | Start-2023 Plotly Comparative (T044/T039/T037 vs CDI/Ibov) | STATE3-P3A (Start 2023) | DONE | `outputs/plots/T058_STATE3_START2023_COMPARATIVE.html` + report + manifest | 2026-02-28 |

### Fase 3B — Solução: participação com constraints (sem “CDI-only”)

**Objetivo**: reprojetar a função-objetivo para impedir que a seleção premie “ficar no CDI”, usando **constraints determinísticas** (piso de participação + guardas de risco) e seleção lexicográfica transparente.

| ID | Task Name | Phase | Status | Key Artifacts / Logs | Timestamp |
|---|---|---|---|---|---|
| T059 | Participation Objective v2 (constraints + deterministic selection) | STATE3-P3B (Objective) | DONE | `selection_rule_v2.json` + `T059_PARTICIPATION_ABLATION_RESULTS_V2.parquet` + `T059_PARTICIPATION_SELECTED_CONFIG_V2.json` + manifest | 2026-02-28 |
| T060 | Phase 3 Comparative Plotly Final (solution vs T044/T039/T037) | STATE3-P3B (Closeout) | DONE | `outputs/plots/T060_STATE3_PHASE3_FINAL_COMPARATIVE.html` + report + manifest | 2026-02-28 |

### Fase 3C — Robustez e promoção (anti-overfit)

**Objetivo**: confirmar robustez por subperíodos e promover somente após PASS do Auditor.

| ID | Task Name | Phase | Status | Key Artifacts / Logs | Timestamp |
|---|---|---|---|---|---|
| T061 | Robustness (subperiods) for participation solution | STATE3-P3C (Robustness) | CANCELLED (MERGED) | Cobertura de robustez será incorporada no novo ciclo de correção de reentrada (armadilha do defensivo) com ablação + evidências por subperíodo. | 2026-02-28 |
| T062 | Governance closeout (Auditor PASS + Registry promotion) | STATE3-P3C (Governance) | DONE | Auditor PASS + promoção no dual-ledger concluídos (T060 registrado em `TASK_REGISTRY.md` e `OPS_LOG.md`). | 2026-02-28 |

### Fase 3D — Correção: “escape” da armadilha do defensivo (reentrada)

**Objetivo**: eliminar estado absorvente de caixa no T044 (defensivo não reverte quando `n_positions=0`), migrando o decisor de regime para sinal de **Mercado** (slope do Ibov) e calibrando **histerese** de entrada/saída via ablação.

| ID | Task Name | Phase | Status | Key Artifacts / Logs | Timestamp |
|---|---|---|---|---|---|
| T063 | Market-slope reentry fix + hysteresis ablation V2 | STATE3-P3D (Reentry) | DONE | `T063_REENTRY_SELECTED_CONFIG_V2.json` + `T063_BASELINE_SUMMARY_REENTRY_FIX_V2.json` + manifest. Audit PASS. | 2026-02-28 |

### Fase 3E — Veredicto visual e consolidação Phase 3

**Objetivo**: produzir dashboard comparativo final incluindo T063 (reentry fix) e consolidar Phase 3 para promoção.

| ID | Task Name | Phase | Status | Key Artifacts / Logs | Timestamp |
|---|---|---|---|---|---|
| T064 | Phase 3D Comparative Plotly (T063 vs T044/T037/CDI/Ibov) | STATE3-P3E (Visual) | DONE | `outputs/plots/T064_STATE3_PHASE3D_COMPARATIVE.html` + report + manifest | 2026-03-01 |
| T065 | Phase 3 Lessons Learned Consolidation | STATE3-P3E (Lessons) | DONE | `02_Knowledge_Bank/docs/process/STATE3_PHASE3_LESSONS_LEARNED_T065.md` + manifest | 2026-03-01 |
| T066 | Phase 3 Governance Closeout (Auditor PASS + Registry promotion) | STATE3-P3E (Closeout) | DONE | `T066-PHASE3-GOVERNANCE-CLOSEOUT-V1_report.md` + manifest | 2026-03-01 |
