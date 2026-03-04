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
| T077 | XGBoost Ablation — Feature Policy Estável (ALLOWLIST core) | STATE3-P6B (Model) | DONE | `src/data_engine/models/T077_V3_XGB_SELECTED_MODEL.json` + `T077_V3_PREDICTIONS_DAILY.parquet` + `T077_V3_ABLATION_RESULTS.parquet` + manifest (17 SHA256, 0 mismatches). HOLDOUT recall=0.988, acid recall=0.985, gap_recall=0.012. Auditor PASS. Findings F-001/F-003 delegados a T078. | 2026-03-02T00:00:00Z |

### Fase 6C — Backtest Financeiro

**Objetivo**: integrar as previsões do modelo vencedor no motor dual-mode (T072), rodar backtest completo (TRAIN + HOLDOUT), e comparar equity/MDD/Sharpe contra T072 original, martelada, CDI e Ibov. O segundo período de caixa (nov/24–nov/25) no HOLDOUT é o teste ácido.

| ID | Task Name | Phase | Status | Key Artifacts / Logs | Timestamp |
|---|---|---|---|---|---|
| T078 | Backtest Financeiro (ML trigger no motor dual-mode vs T072/martelada/CDI/Ibov) | STATE3-P6C (Backtest) | DONE | `src/data_engine/portfolio/T078_ML_TRIGGER_BACKTEST_SELECTED_CONFIG.json` (winner C057, thr=0.25, h_in=3, h_out=2) + `T078_PORTFOLIO_CURVE_ML_TRIGGER.parquet` + `T078_PORTFOLIO_CURVE_MARTELADA_ORACLE.parquet` + `T078_BASELINE_SUMMARY_ML_TRIGGER.json` + `outputs/plots/T078_STATE3_PHASE6C_BACKTEST_COMPARATIVE.html` + manifest (12 SHA256, 0 mismatches). HOLDOUT: ML=R$475k vs T072=R$407k. Acid window MDD=-7.1% (vs -19.2% T072). Seleção TRAIN-only. Auditor PASS. Findings F-001/F-002 delegados a T079. | 2026-03-02T18:00:00Z |

### Fase 6D — Consolidação e Governança

**Objetivo**: produzir dashboard comparativo final (Plotly), consolidar lições da Phase 6, e fechar a fase com governance closeout.

| ID | Task Name | Phase | Status | Key Artifacts / Logs | Timestamp |
|---|---|---|---|---|---|
| T079 | Phase 6 Comparative Plotly (ML trigger vs T072/martelada/CDI/Ibov) | STATE3-P6D (Visual) | DONE | `outputs/plots/T079_STATE3_PHASE6D_COMPARATIVE.html` + manifest (7 SHA256, 0 mismatches). C057 vs C060 comparados. **Winner produto Phase 6 = C060** (thr=0.25, h_in=3, h_out=5): HOLDOUT R$506k, MDD=-18.7%, Sharpe=0.962, switches=13. Auditor PASS. | 2026-03-02T19:20:00Z |
| T080 | Phase 6 Lessons Learned | STATE3-P6D (Lessons) | DONE | `02_Knowledge_Bank/docs/process/STATE3_PHASE6_LESSONS_LEARNED_T080.md` (253 linhas, 14 lições, 11-item checklist anti-regressão Phase 7). Manifest SHA256 3 entradas, 0 mismatches. Auditor PASS. | 2026-03-02T19:41:00Z |
| T081 | Phase 6 Governance Closeout | STATE3-P6D (Closeout) | DONE | `outputs/governanca/T081-PHASE6-GOVERNANCE-CLOSEOUT-V1_report.md` + manifest (5 SHA256, 0 mismatches). 7/7 gates PASS. 5 manifests Phase 6 validados (53 entradas, 0 mismatches). Registry 18/18. C060 winner produto confirmado. Auditor PASS. **STATE 3 Phase 6 COMPLETED.** | 2026-03-02T20:00:00Z |

---

## STATE 3 — Phase 7: Expansão Multi-Mercado (ENCERRADA — premissa substituída)

**Objetivo original**: operar sobre ~1.100 ativos (BR + 500 tickers US diretos em USD), remunerar caixa via Tesouro IPCA+, incorporar fricções cross-border diferenciadas, e superar o C060.

**Motivo do encerramento**: análise CTO (mar/2026) demonstrou que a premissa de execução cross-border (BR em BRL + US em USD) é economicamente destrutiva — custo FX+IOF de ~0.78% one-way (31x o custo de corretagem) poderia consumir até 62% do CAGR em cenários de alto churn. Diagnóstico revelou que **BDRs classe I na B3** oferecem exposição ao S&P 500 em BRL, sem FX, sem IOF, com custo idêntico a ações BR (2.5 bps). Comparação empírica: S&P 500 em BRL (via PTAX) tem mediana de Sharpe 0.52 vs 0.01 das ações BR; no Top 50 combinado por Sharpe, 86% são US. Decisão do Owner: cancelar Phase 7, manter artefatos de ingestão US (T083-T085) como insumo, e iniciar Phase 8 com modelo "BDR Bridge" (100% B3, 100% BRL).

**Artefatos preservados** (insumos para Phase 8):
- T083: SPEC pipeline US (referência de arquitetura de ingestão)
- T084: `SSOT_US_MARKET_DATA_RAW.parquet` (496 tickers S&P 500, 2018-2026) — base para síntese de BDRs via PTAX
- T085: `SSOT_US_UNIVERSE_OPERATIONAL.parquet` (496 tickers) + `SSOT_US_BLACKLIST_OPERATIONAL.csv` (3 HARD) — quality gates reutilizáveis
- T086: `SSOT_MACRO_EXPANDED.parquet` (VIX, DXY, Treasury yields, Fed funds) — features macro preservadas

**Artefato desativado**:
- T086: `SSOT_CANONICAL_BASE_BR_US.parquet` — construído com premissa de dois mercados separados (market=BR/US); será substituído por SSOT unificado em BRL na Phase 8

### Fase 7A — Cash Upgrade: Tesouro IPCA+ (CANCELADA)

**Motivo**: IPCA+ mark-to-market não é risk-free. Decisão Owner: manter CDI.

| ID | Task Name | Phase | Status | Key Artifacts / Logs | Timestamp |
|---|---|---|---|---|---|
| T082 | Cash upgrade: CDI → Tesouro IPCA+ (backtest C060 recalculado) | STATE3-P7A (Cash) | CANCELLED | Análise CTO: NTN-B curta MDD=-9.3%, vol=5.2%; NTN-B longa MDD=-22%, vol=16%. Decisão Owner: manter CDI. | 2026-03-02T17:30:00Z |

### Fase 7B — Ingestão e Qualidade de Dados US (DONE — artefatos preservados)

**Objetivo**: pipeline de ingestão S&P 500 + quality gates. Artefatos reutilizados na Phase 8.

| ID | Task Name | Phase | Status | Key Artifacts / Logs | Timestamp |
|---|---|---|---|---|---|
| T083 | SPEC: Pipeline de dados US (ingestão, qualidade, SSOT expandido) | STATE3-P7B (Spec) | DONE | `scripts/t083_spec_us_data_pipeline.py` + `SPEC-083_PIPELINE_DADOS_US_T083.md` + `sp500_current_symbols_snapshot.csv` (503 símbolos). Manifest V2 9 entradas, 0 mismatches. Auditor PASS (V2). | 2026-03-02T17:39:16Z |
| T084 | Ingestão S&P 500: OHLCV + dividendos + splits (2018-2026) | STATE3-P7B (Ingest) | DONE | `SSOT_US_MARKET_DATA_RAW.parquet` (1.006.669 linhas, 499 tickers). BRAPI. Manifest V2 10 entradas, 0 mismatches. Auditor PASS (V2). **Preservado para Phase 8.** | 2026-03-02T19:10:04Z |
| T085 | Qualidade de dados US: SPC charts + blacklist + universo operacional | STATE3-P7B (Quality) | DONE | `SSOT_US_UNIVERSE_OPERATIONAL.parquet` (496 tickers) + `SSOT_US_BLACKLIST_OPERATIONAL.csv` (3 HARD). 12 gates PASS. Auditor PASS. **Preservado para Phase 8.** | 2026-03-02T20:58:55Z |
| T086 | SSOT unificado BR+US: merge canonical base + macro expandido | STATE3-P7B (SSOT) | DONE | `SSOT_MACRO_EXPANDED.parquet` (2.025 × 12 cols) **preservado**. `SSOT_CANONICAL_BASE_BR_US.parquet` **desativado** (premissa cross-border substituída por BDR Bridge). Manifest V2 14 entradas, 0 mismatches. Auditor PASS (V2). | 2026-03-02T23:53:05Z |

### Fases 7C–7H — CANCELADAS (premissa cross-border substituída)

**Motivo**: todas as tasks T087–T100 foram desenhadas para operar com dois mercados separados (BR em BRL + US em USD), com lógica de split BR/US, trigger dual, fricções diferenciadas por mercado, e IPCA+ no cash. A decisão "BDR Bridge" elimina essas necessidades. O escopo é absorvido pela Phase 8 em formato simplificado.

| ID | Task Name | Phase | Status | Key Artifacts / Logs | Timestamp |
|---|---|---|---|---|---|
| T087 | Feature engineering US: per-ticker features | STATE3-P7C | CANCELLED | Premissa cross-border substituída por BDR Bridge. Escopo absorvido por Phase 8. | 2026-03-03T16:00:00Z |
| T088 | Feature engineering cross-market: VIX, DXY, Treasury spread | STATE3-P7C | CANCELLED | Premissa cross-border substituída por BDR Bridge. Features macro preservadas via T086. | 2026-03-03T16:00:00Z |
| T089 | Feature matrix unificada + EDA + anti-lookahead | STATE3-P7C | CANCELLED | Premissa cross-border substituída. Escopo absorvido por Phase 8. | 2026-03-03T16:00:00Z |
| T090 | Motor de seleção para universo BR+US (custo uniforme) | STATE3-P7D | CANCELLED | Lógica de split BR/US desnecessária com BDR. Motor BR existente se aplica diretamente. | 2026-03-03T16:00:00Z |
| T091 | Ablação multi-mercado (n_positions, cadence, split BR/US) | STATE3-P7D | CANCELLED | Split BR/US eliminado. Ablação de n_positions (15 default) absorvida por Phase 8. | 2026-03-03T16:00:00Z |
| T092 | ML trigger retreino com features cross-market | STATE3-P7E | CANCELLED | Trigger dual BR/US desnecessário. Retreino com universo expandido absorvido por Phase 8. | 2026-03-03T16:00:00Z |
| T093 | Ablação: trigger único vs dual (BR + US) | STATE3-P7E | CANCELLED | Não há dois mercados para separar. Trigger único se mantém. | 2026-03-03T16:00:00Z |
| T094 | Threshold + histerese tuning multi-mercado | STATE3-P7E | CANCELLED | Absorvido por Phase 8 (tuning com universo expandido). | 2026-03-03T16:00:00Z |
| T095 | Backtest integrado: BR+US + ML trigger + IPCA+ cash | STATE3-P7F | CANCELLED | IPCA+ cancelada (T082). Cross-border eliminado. Backtest absorvido por Phase 8. | 2026-03-03T16:00:00Z |
| T096 | Phase 7 Comparative Plotly | STATE3-P7F | CANCELLED | Absorvido por Phase 8. | 2026-03-03T16:00:00Z |
| T097 | Sensibilidade: custo uniforme vs diferenciado | STATE3-P7G | CANCELLED | Custo uniforme 2.5 bps mantido para tudo (BDR = mesmo custo que ação BR). | 2026-03-03T16:00:00Z |
| T098 | Modelo de fricções diferenciado por mercado | STATE3-P7G | CANCELLED | Sem cross-border, sem fricção diferenciada. | 2026-03-03T16:00:00Z |
| T099 | Phase 7 Lessons Learned | STATE3-P7H | CANCELLED | Lições da Phase 7 incorporadas no encerramento desta seção. | 2026-03-03T16:00:00Z |
| T100 | Phase 7 Governance Closeout | STATE3-P7H | CANCELLED | Encerramento formalizado neste ROADMAP. | 2026-03-03T16:00:00Z |

---

## STATE 3 — Phase 8: Universo Expandido via BDR Bridge (100% B3, 100% BRL)

**Objetivo-mestre**: expandir o universo de seleção de ~460 ações BR para ~960 ativos (ações BR + BDRs classe I sintetizados a partir dos ~500 tickers S&P 500), tudo operado na B3 em BRL, e **superar o C060** (winner Phase 6: CAGR 23.5%, Sharpe 1.27, MDD=-29.8%, HOLDOUT equity=R$506k).

**Premissa central — "BDR Bridge"**: a exposição ao mercado americano é obtida via BDRs classe I (Brazilian Depositary Receipts) negociados na B3 em BRL. O preço do BDR embute naturalmente o câmbio (BDR_BRL ≈ US_USD × PTAX × paridade). Resultado: moeda única (R$), custo de fricção uniforme (2.5 bps), zero FX/IOF, settlement uniforme D+2 B3. O motor existente se aplica sem modificação estrutural — apenas com universo maior.

**Decisões do Owner incorporadas**:
- Queimadores: **15** (target_pct ≈ 6.67%, max_pct ≈ 10%), com ablação no range [10, 12, 15, 18, 20] para confirmação empírica.
- Moeda-base: **R$** (sem ambiguidade, sem conversão).
- SSOT de câmbio: **PTAX diária (BCB série 1)** — usado para sintetizar BDRs e como feature macro.
- Custo de fricção: **2.5 bps uniforme** (emenda `ARB_COST_0_025PCT_MOVED` mantida sem alteração).
- Cash: **CDI** (mantido da Phase 6).
- Winner/baseline: **C060** (mantido da Phase 6).

**Justificativa empírica (diagnóstico CTO)**:
- S&P 500 em BRL: mediana Sharpe 0.52 vs 0.01 ações BR (BRL depreciou 7.8% p.a. desde 2018).
- No Top 50 por Sharpe (BRL), 86% são US, 14% são BR.
- No Top 10% do ranking combinado, 90% são US.
- O motor "se dolariza" naturalmente quando BDRs dominam o ranking em cenários de USD forte.

**Insumos herdados da Phase 7**:
- `SSOT_US_MARKET_DATA_RAW.parquet` (T084): OHLCV S&P 500, base para síntese de BDRs.
- `SSOT_US_UNIVERSE_OPERATIONAL.parquet` (T085): 496 tickers aprovados + blacklist.
- `SSOT_MACRO_EXPANDED.parquet` (T086): VIX, DXY, Treasury yields, Fed funds.

**Walk-forward**: TRAIN 2018-07-02 → 2022-12-30 | HOLDOUT 2023-01-02 → 2026-02-26 (mantido Phase 6).

**Checklist anti-regressão Phase 6**: todas as 14 lições de `STATE3_PHASE6_LESSONS_LEARNED_T080.md` aplicam-se integralmente.

**Regras de fase**:
- Anti-lookahead estrito (shift(1)) mantido em todas as features.
- Toda task deve superar C060 ou justificar por que não (com diagnóstico).
- Custo de transação uniforme 2.5 bps para tudo (ações BR e BDRs).
- Operação manual via B3 (BTG doméstico). Sem conta internacional necessária.

### Fase 8A — Ingestão PTAX e Síntese de BDRs

**Objetivo**: ingerir PTAX diária (BCB série 1, 2018-2026), construir mapeamento BDR classe I ↔ ticker S&P 500 com razão de paridade, e sintetizar preços BDR históricos em BRL para o período completo (2018+). Materializar o SSOT BR expandido que inclui ações BR + BDRs sintéticos, tudo em BRL.

| ID | Task Name | Phase | Status | Key Artifacts / Logs | Timestamp |
|---|---|---|---|---|---|
| T101 | Ingestão PTAX diária (BCB série 1) + mapeamento BDR↔S&P500 + síntese de preços BDR | STATE3-P8A (PTAX+BDR) | DONE | `scripts/t101_ingest_ptax_bdr_synth.py` + `SSOT_FX_PTAX_USDBRL.parquet` + `SSOT_BDR_B3_UNIVERSE.parquet` (496: 446 B3 + 50 US_DIRECT) + `SSOT_BDR_SYNTH_MARKET_DATA_RAW.parquet` (988.968 linhas). Manifest V2 SHA256: 11 entradas, 0 mismatches. Auditor PASS. | 2026-03-03T21:00:00Z |
| T102 | SSOT BR expandido: ações BR + BDRs sintéticos (unificado em BRL) | STATE3-P8A (SSOT-BRL) | DONE | `scripts/t102_build_ssot_br_expanded_brl.py` + `SSOT_CANONICAL_BASE_BR_EXPANDED.parquet` (1.620.910 linhas, 1.174 tickers, schema 21 colunas, 0 dupes, 0 NaN close_operational) + `SSOT_UNIVERSE_OPERATIONAL_EXPANDED.parquet` (1.174 tickers). 9 gates PASS. SHA256 7/7 PASS (reauditoria independente). Reauditoria por troca de LLM: PASS. | 2026-03-03T22:10:00Z |

### Fase 8B — Feature Engineering (universo expandido)

**Objetivo**: recalcular a feature matrix com o universo expandido (~960 tickers em BRL). Incorporar features macro expandidas (VIX, DXY, Treasury spread, USDBRL como feature) ao pipeline existente. Validar anti-lookahead e estabilidade cross-split em todas as features novas.

| ID | Task Name | Phase | Status | Key Artifacts / Logs | Timestamp |
|---|---|---|---|---|---|
| T103 | Feature engineering: features macro expandidas (VIX, DXY, Treasury, USDBRL) + per-ticker BDR | STATE3-P8B (Features) | DONE | `scripts/t103_feature_engineering_expanded_universe.py` + `T103_MACRO_FEATURES_EXPANDED_DAILY.parquet` (2025 linhas, 20 features macro, shift(1), 0 mismatches SHA256) + `T103_BDR_TICKER_METADATA.parquet` (496 tickers: 446 B3 + 50 US_DIRECT). 8 gates PASS. Auditor PASS. | 2026-03-03T23:00:00Z |
| T104 | Feature matrix unificada (BR+BDR) + EDA + validação anti-lookahead | STATE3-P8B (Matrix) | DONE | `scripts/t104_eda_feature_engineering_ml_trigger_expanded.py` + `T104_FEATURE_MATRIX_DAILY.parquet` (1.902 × 77 cols, 76 features) + `T104_LABELS_DAILY.parquet` (TRAIN=1.115/HOLDOUT=787) + `T104_DATASET_DAILY.parquet` + `T104_STATE3_PHASE8B_EDA.html`. 8 gates PASS. SHA256 11/11 PASS. Anti-lookahead confirmado. Auditor PASS (reauditoria por troca de LLM). | 2026-03-03T23:30:00Z |

### Fase 8C — ML Trigger (universo expandido)

**Objetivo**: retreinar o XGBoost com a feature matrix expandida, mantendo walk-forward estrito. Testar se features macro (VIX, DXY, Treasury spread, USDBRL) melhoram a detecção de regimes. Ablação de threshold + histerese com n_positions=15.

| ID | Task Name | Phase | Status | Key Artifacts / Logs | Timestamp |
|---|---|---|---|---|---|
| T105 | XGBoost retreino com features expandidas (walk-forward) | STATE3-P8C (ML-Retrain) | DONE | `T105_V1_XGB_SELECTED_MODEL.json` + `T105_V1_PREDICTIONS.parquet` + `T105_V1_ABLATION_RESULTS.parquet` + manifest (17 SHA256, 0 mismatches). Winner: CORE_PLUS_MACRO_EXPANDED_FX_C043 (38 features, thr=0.12). HOLDOUT recall=0.940, acid recall=0.925. Finding F-001: CORE superior no HOLDOUT (decisão Owner: manter winner, testar no T106). Auditor PASS. | 2026-03-03T21:17:16Z |
| T106 | Ablação threshold + histerese (n_positions=15, universo expandido) | STATE3-P8C (ML-Tuning) | DONE | `scripts/t106_threshold_hysteresis_ablation_expanded_v1.py` + `T106_ML_TRIGGER_EXPANDED_SELECTED_CONFIG.json` (winner CORE_PLUS_MACRO_EXPANDED_FX_C009: thr=0.05, h_in=3, h_out=2) + `T106_PORTFOLIO_CURVE_ML_TRIGGER_EXPANDED.parquet` + `T106_STATE3_PHASE8C_ML_TUNING_COMPARATIVE.html` (791 KB) + manifest (14 SHA256, 0 mismatches). Ablação dupla 168 candidatos (CORE+FX + CORE). HOLDOUT equity=R$475k, MDD=-11.8%, Sharpe=1.34. Acid equity=R$409k, MDD=-6.4%, switches=2. Auditor PASS. | 2026-03-04T00:00:00Z |

### Fase 8D — Backtest e Ablação de Seleção

**Objetivo**: rodar backtest completo com motor dual-mode + ML trigger + universo expandido. Ablação de n_positions [10, 12, 15, 18, 20]. Comparar contra C060, CDI, Ibovespa. Winner Phase 8 deve superar C060 em CAGR e Sharpe.

| ID | Task Name | Phase | Status | Key Artifacts / Logs | Timestamp |
|---|---|---|---|---|---|
| T107 | Backtest integrado: universo expandido + ML trigger (vs C060/CDI/Ibov) | STATE3-P8D (Backtest) | DONE | `scripts/t107_backtest_integrated_expanded_ml_trigger_v1.py` + `T107_PORTFOLIO_CURVE_DUAL_MODE_EXPANDED.parquet` + `T107_PORTFOLIO_CURVE_DUAL_MODE_EXPANDED_ML_TRIGGER.parquet` + `T107_STATE3_PHASE8D_BACKTEST_INTEGRATED_COMPARATIVE.html`. HOLDOUT: equity=R$516.964, CAGR=26.5%, MDD=-7.1%, Sharpe=3.19. Supera C060 (+2.1%). Acid: equity=R$383.680, MDD=-2.5%. Manifest SHA256 14/14 OK. Auditor PASS. | 2026-03-04T10:00:00Z |
| T108 | Ablação n_positions [10,12,15,18,20] + cadence [5,10,15,20] — universo expandido + ML trigger fixado | STATE3-P8D (Ablation) | DONE | `T108_SELECTED_CONFIG_NPOS_CADENCE_EXPANDED.json` (winner C010_N15_CB10: top_n=15, cadence_mode_b=10) + `T108_PORTFOLIO_CURVE_DUAL_MODE_EXPANDED_ML_TRIGGER_WINNER.parquet` + `T108_ABLATION_RESULTS_NPOS_CADENCE_EXPANDED.parquet` + `T108_STATE3_PHASE8D_ABLATION_NPOS_CADENCE_COMPARATIVE.html` + `T108-ABLATION-NPOS-CADENCE-EXPANDED-V1_manifest.json` (14 SHA256 OK). HOLDOUT: equity=R$516.964 vs C060=R$506.432 (+2.08%), Sharpe=3.19. Auditor PASS. | 2026-03-04T10:20:00Z |

### Fase 8E — Consolidação e Governança

**Objetivo**: comparativo visual final, lições aprendidas, governance closeout. Promover winner Phase 8 como novo baseline de produto.

| ID | Task Name | Phase | Status | Key Artifacts / Logs | Timestamp |
|---|---|---|---|---|---|
| T109 | Phase 8 Comparative Plotly (winner Phase 8 vs C060 vs benchmarks) | STATE3-P8E (Visual) | DONE | `outputs/plots/T109_STATE3_PHASE8E_COMPARATIVE.html` + `outputs/governanca/T109-PHASE8-PLOTLY-COMPARATIVE-V1_report.md` + `outputs/governanca/T109-PHASE8-PLOTLY-COMPARATIVE-V1_manifest.json` (8 SHA256 OK). HOLDOUT: Phase8+ML=R$516.964 vs C060=R$506.432 (+2.08%), Sharpe=3.19, MDD=-7.1%. ACID: Phase8=R$383.680, Sharpe=3.37, MDD=-2.5%. Auditor PASS. | 2026-03-04T12:00:00Z |
| T110 | Phase 8 Lessons Learned | STATE3-P8E (Lessons) | DONE | `02_Knowledge_Bank/docs/process/STATE3_PHASE8_LESSONS_LEARNED_T110.md` (16 lições). Manifest SHA256: 5/5 OK. Auditor PASS. | 2026-03-04T13:00:00Z |
| T111 | Phase 8 Governance Closeout | STATE3-P8E (Closeout) | DONE | 10/10 tasks verified, 110 SHA256 entries 0 mismatches. Winner C010_N15_CB10 snapshot. Phase 8 CLOSED. Manifest: `outputs/governanca/T111-PHASE8-GOVERNANCE-CLOSEOUT-V1_manifest.json`. | 2026-03-04T14:00:00Z |
