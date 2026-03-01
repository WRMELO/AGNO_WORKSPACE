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

## STATE 3 — Phase 5: Forno Dual-Mode (COMPLETED)

**Objetivo-mestre**: produzir uma estratégia que **supere T037 no rali E T044 no trecho CDI-bloqueado, simultaneamente**, unificando os dois modos de operação do forno num único motor com comutação endógena.

**Conceito**: meta-controlador que monitora a **produtividade dos burners vs CDI** e comuta entre:
- **Modo T037** (reposição rápida, tank seco, disjuntor binário) — quando burners produzem acima do CDI
- **Modo T067** (reposição lenta, tank gordo, válvula gradual) — quando burners produzem abaixo do CDI

**Evidência de base**: diagnóstico de engenharia de processos (T068/Phase 4 Lessons) demonstrou que T037 ganha +186.7% (base 100) no P1 vs +70.9% do T067, enquanto T067 ganha +101.9% no P2 vs -35.4% do T037. A diferença é estrutural: velocidade de reposição (17% vs 2.8% dos dias com compra), tipo de disjuntor (binário vs gradual) e papel do tank (5% vs 19% cash fraction).

**Tarefas previstas** (T071–T075 concluídas — Phase 5 encerrada; pivô para ML na Phase 6):

| ID | Task Name | Phase | Status | Key Artifacts / Logs | Timestamp |
|---|---|---|---|---|---|
| T071 | SPEC: Termostato do Forno (meta-controlador endógeno) | STATE3-P5A (Spec) | DONE | `SPEC-007_THERMOSTAT_FORNO_DUAL_MODE_T071.md` + changelog | 2026-03-01 |
| T072 | Dual-Mode Engine + ablação de comutação | STATE3-P5B (Engine) | DONE | `T072_DUAL_MODE_SELECTED_CONFIG.json` + `T072_STATE3_PHASE5B_COMPARATIVE.html` + manifest. Vencedor W30_T0p0005_HI2_HO4_SINAL-2_B0: HOLDOUT equity=R$407k, excess_2023plus_vs_T044=+20.7pp. Auditor PASS. | 2026-03-01 |
| T073 | Phase 5 Comparative Plotly | STATE3-P5C (Visual) | DONE | `T073_STATE3_PHASE5C_COMPARATIVE.html` + `T073-PHASE5-PLOTLY-COMPARATIVE-V1_report.md` + manifest. Diagnóstico explícito: SINAL-1=0 train-feasible e feasibility total=2/324. Auditor PASS. | 2026-03-01 |
| T074 | Phase 5 Lessons Learned | STATE3-P5D (Lessons) | DONE | `STATE3_PHASE5_LESSONS_LEARNED_T074.md` (8 lições + diagnóstico determinístico esgotado + decisão ML) | 2026-03-01 |
| T075 | Phase 5 Governance Closeout | STATE3-P5D (Closeout) | DONE | Consistência documental verificada. Phase 5 formalmente encerrada. Pivô para ML (Phase 6) autorizado pelo Owner. | 2026-03-01 |

---

## STATE 3 — Phase 6: ML Trigger para Forno Dual-Mode

**Objetivo-mestre**: substituir o termostato determinístico (threshold + histerese sobre 1 sinal escalar) por um **classificador supervisionado** (XGBoost) que decide diariamente "mercado" vs "caixa", usando exclusivamente dados até D-1 (`shift(1)`), validado por walk-forward estrito com HOLDOUT intocado.

**Motivação**: a abordagem determinística esgotou após 7 tentativas (T039→T072), com feasibility de apenas 0.6% (2/324 candidatos). O conceito do forno dual-mode está provado (T072 = R$407k, +307%), mas o termostato é lento demais. A "martelada" (forçar caixa nos dois períodos de deriva) eleva o equity para R$757k (+657%), provando que o gap é de **detecção**, não de conceito. O Owner decidiu pivotar para ML com classificação supervisionada.

**Formulação do problema**:
- **Pergunta**: "o forno **esteve** produtivo **até ontem**?" (shift(1) — anti-lookahead estrito)
- **Label binário**: "caixa" vs "mercado", derivado dos dois períodos da martelada (~33% caixa / ~67% mercado)
- **Transparência não é requisito** — confiança via validação out-of-sample é

**Walk-forward**:
- TRAIN: 2018-07-02 a 2022-12-30
- HOLDOUT: 2023-01-02 a 2026-02-26
- **Teste ácido**: o segundo período de caixa (nov/2024–nov/2025) está inteiramente no HOLDOUT — se o modelo acertar sem tê-lo visto, é evidência forte de generalização

**Inventário de dados**:
- `T072_PORTFOLIO_CURVE_DUAL_MODE.parquet`: 1.902 pregões × 23 colunas
- `T072_PORTFOLIO_LEDGER_DUAL_MODE.parquet`: 765 trades × 13 colunas
- `T037_M3_SCORES_DAILY.parquet`: 866.863 ticker-days × 10 colunas
- `SSOT_MACRO.parquet`: 2.025 pregões × 6 colunas (ibov, sp500, cdi)
- `SSOT_CANONICAL_BASE.parquet`: 631.944 ticker-days × 21 colunas
- Feature matrix preliminar: ~17 features × 1.964 pregões (expansível para 50-100)

**Referências obrigatórias**:
- `02_Knowledge_Bank/docs/process/STATE3_PHASE5_LESSONS_LEARNED_T074.md` — diagnóstico + checklist anti-regressão
- `02_Knowledge_Bank/docs/specs/SPEC-007_THERMOSTAT_FORNO_DUAL_MODE_T071.md` — spec do termostato
- `02_Knowledge_Bank/docs/process/STATE3_PHASE4_LESSONS_LEARNED_T069.md` — diagnóstico de engenharia de processos

### Fase 6A — EDA + Feature Engineering

**Objetivo**: construir a feature matrix completa (50-100 features), validar anti-lookahead em cada feature, analisar correlações e distribuições, e gerar o label binário a partir dos períodos da martelada.

| ID | Task Name | Phase | Status | Key Artifacts / Logs | Timestamp |
|---|---|---|---|---|---|
| T076 | EDA + Feature Engineering (feature matrix + label + anti-lookahead) | STATE3-P6A (Features) | DONE | `src/data_engine/features/T076_DATASET_DAILY.parquet` (52 features, TRAIN=1.115 / HOLDOUT=787) + `T076_FEATURE_MATRIX_DAILY.parquet` + `T076_LABELS_DAILY.parquet` + `outputs/plots/T076_STATE3_PHASE6A_EDA.html` + manifest (14 SHA256, 0 mismatches). Anti-lookahead shift(1) global. Teste ácido 100% HOLDOUT. Findings F-001/F-002 → blacklist e gate em T077. Auditor PASS. | 2026-03-01T14:34:31Z |

### Fase 6B — XGBoost Ablation (walk-forward)

**Objetivo**: treinar XGBoost com grid de hiperparâmetros sobre o TRAIN, aplicar hard constraints financeiros (anti-lookahead, estabilidade de previsão, transições mínimas), e selecionar o melhor modelo exclusivamente com métricas do TRAIN. Avaliar no HOLDOUT sem ajuste.

| ID | Task Name | Phase | Status | Key Artifacts / Logs | Timestamp |
|---|---|---|---|---|---|
| T077 | XGBoost Ablation (grid search + walk-forward + hard constraints) | STATE3-P6B (Model) | PENDING | — | — |

### Fase 6C — Backtest Financeiro

**Objetivo**: integrar as previsões do modelo vencedor no motor dual-mode (T072), rodar backtest completo (TRAIN + HOLDOUT), e comparar equity/MDD/Sharpe contra T072 original, martelada, CDI e Ibov. O segundo período de caixa (nov/24–nov/25) no HOLDOUT é o teste ácido.

| ID | Task Name | Phase | Status | Key Artifacts / Logs | Timestamp |
|---|---|---|---|---|---|
| T078 | Backtest Financeiro (ML trigger no motor dual-mode vs T072/martelada/CDI/Ibov) | STATE3-P6C (Backtest) | PENDING | — | — |

### Fase 6D — Consolidação e Governança

**Objetivo**: produzir dashboard comparativo final (Plotly), consolidar lições da Phase 6, e fechar a fase com governance closeout.

| ID | Task Name | Phase | Status | Key Artifacts / Logs | Timestamp |
|---|---|---|---|---|---|
| T079 | Phase 6 Comparative Plotly (ML trigger vs T072/martelada/CDI/Ibov) | STATE3-P6D (Visual) | PENDING | — | — |
| T080 | Phase 6 Lessons Learned | STATE3-P6D (Lessons) | PENDING | — | — |
| T081 | Phase 6 Governance Closeout | STATE3-P6D (Closeout) | PENDING | — | — |
