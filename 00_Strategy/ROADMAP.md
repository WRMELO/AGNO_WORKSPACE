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

---

## STATE 3 — Phase 4: superar T044 no trecho CDI-bloqueado

**Objetivo-mestre**: produzir uma estratégia que **vença a T044 winner (Phase 2)** no período em que ela ficou presa ao CDI (~2023 em diante), substituindo caixa por compras efetivas de ação. A mecânica de regime por market-slope (T063) é mantida; o que muda é a velocidade e o volume de alocação.

**Status**: [ COMPLETED ] — T067 atingiu o objetivo no trecho 2023+ (+68.4pp vs T044). T068 provou que ajuste paramétrico não resolve a perda de rali. Diagnóstico de engenharia de processos documentado em T069. Governance closeout T070 PASS (20/20). Problema do rali migra para Phase 5 (Forno Dual-Mode).

**Abordagem**: partir da alocação máxima (sem cap, estilo T044 original) e reduzir gradualmente até encontrar o ponto ótimo. Direção "de cima para baixo".

**Regra de fase**: toda task de ablação deve incluir Plotly comparativo embutido no mesmo script (winner vs T044/T063/T037/CDI/Ibov).

### Fase 4A — Ablação: alocação agressiva com regime market-slope

**Objetivo**: testar combinações de `buy_turnover_cap_ratio` (null a 0.10) e `cadence_days` (5 a 25 pregões) sobre o regime T063 (SW=30, IN_HYST=4, OUT_HYST=4). Hard constraint único: MDD >= -0.30. Ranking lexicográfico: CAGR desc > Sharpe desc > turnover asc. Plotly embutido.

| ID | Task Name | Phase | Status | Key Artifacts / Logs | Timestamp |
|---|---|---|---|---|---|
| T067 | Aggressive allocation ablation (cap×cadence) + Plotly | STATE3-P4A (Ablation) | DONE | `T067_AGGRESSIVE_SELECTED_CONFIG.json` + `T067_STATE3_PHASE4A_COMPARATIVE.html` + manifest | 2026-03-01 |

### Fase 4B — Rally protection (ablação paramétrica)

**Objetivo**: testar se ajuste paramétrico (histerese assimétrica, filtro híbrido de tendência) resolve a perda de rali jun/20-jul/21 do T067.

**Resultado**: ajuste paramétrico **não resolve**. Winner idêntico a T067. Diagnóstico de engenharia de processos revelou causa-raiz estrutural (dois modos de forno distintos).

| ID | Task Name | Phase | Status | Key Artifacts / Logs | Timestamp |
|---|---|---|---|---|---|
| T068 | Rally protection ablation (hysteresis + hybrid trend) | STATE3-P4B (Adjust) | DONE | `T068_RALLY_PROTECTION_SELECTED_CONFIG.json` + `T068_STATE3_PHASE4B_COMPARATIVE.html` + manifest. Audit PASS (finding médio: objetivo funcional de rali não atingido). | 2026-03-01 |

### Fase 4C — Consolidação e promoção

**Objetivo**: consolidar lições da Phase 4 (incluindo diagnóstico de engenharia de processos) e fechar a fase com governance closeout.

| ID | Task Name | Phase | Status | Key Artifacts / Logs | Timestamp |
|---|---|---|---|---|---|
| T069 | Phase 4 Lessons Learned | STATE3-P4C (Lessons) | DONE | `STATE3_PHASE4_LESSONS_LEARNED_T069.md` (12 lições + diagnóstico de engenharia de processos) | 2026-03-01 |
| T070 | Phase 4 Governance Closeout | STATE3-P4C (Closeout) | DONE | 20/20 consistency checks PASS. Phase 4 formalmente encerrada. | 2026-03-01 |

---

## STATE 3 — Phase 5: Forno Dual-Mode (PLANEJAMENTO)

**Objetivo-mestre**: produzir uma estratégia que **supere T037 no rali E T044 no trecho CDI-bloqueado, simultaneamente**, unificando os dois modos de operação do forno num único motor com comutação endógena.

**Conceito**: meta-controlador que monitora a **produtividade dos burners vs CDI** e comuta entre:
- **Modo T037** (reposição rápida, tank seco, disjuntor binário) — quando burners produzem acima do CDI
- **Modo T067** (reposição lenta, tank gordo, válvula gradual) — quando burners produzem abaixo do CDI

**Evidência de base**: diagnóstico de engenharia de processos (T068/Phase 4 Lessons) demonstrou que T037 ganha +186.7% (base 100) no P1 vs +70.9% do T067, enquanto T067 ganha +101.9% no P2 vs -35.4% do T037. A diferença é estrutural: velocidade de reposição (17% vs 2.8% dos dias com compra), tipo de disjuntor (binário vs gradual) e papel do tank (5% vs 19% cash fraction).

**Tarefas previstas** (a detalhar após T069/T070):

| ID | Task Name | Phase | Status | Key Artifacts / Logs | Timestamp |
|---|---|---|---|---|---|
| T071 | SPEC: Termostato do Forno (meta-controlador endógeno) | STATE3-P5A (Spec) | PENDING | — | — |
| T072 | Dual-Mode Engine + ablação de comutação | STATE3-P5B (Engine) | PENDING | — | — |
| T073 | Phase 5 Comparative Plotly | STATE3-P5C (Visual) | PENDING | — | — |
| T074 | Phase 5 Lessons Learned | STATE3-P5D (Lessons) | PENDING | — | — |
| T075 | Phase 5 Governance Closeout | STATE3-P5D (Closeout) | PENDING | — | — |
