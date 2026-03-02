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

## STATE 3 — Phase 7: Expansão Multi-Mercado (BR + US + Tesouro IPCA+)

**Objetivo-mestre**: construir um mecanismo completo que opere sobre um universo expandido de ~1.100 ativos (BR + 500 tickers US), remunere o caixa via Tesouro IPCA+ em vez de CDI, incorpore fricções reais diferenciadas por mercado (settlement, custos de transação, impostos), e **supere o C060** (winner Phase 6: CAGR 23.5%, Sharpe 1.27, HOLDOUT R$506k) em retorno ajustado ao risco.

**Motivação**: análise CTO pós-Phase 6 demonstrou que:
- O alpha do C060 vem 70% do stock picking (+16.3pp Jensen) e 30% do ML timing (~7pp). Expandir o universo de seleção de ~90 para ~1.100 ativos multiplica o potencial de alpha (top 1.5% de 1.100 >> top 12% de 90).
- Mercados BR e US têm correlação parcial (0.48): em 79% dos meses pelo menos um está positivo — mais oportunidades de seleção.
- Trocar CDI por Tesouro IPCA+ no cash gera ~1pp CAGR adicional com risco zero.
- Owner possui conta BTG Internacional com US$ 183k já dolarizados. Custos operacionais BTG: US$ 1-7.50/ordem, sem câmbio recorrente. Diferença de fricção BR vs US estimada em ~1.4pp/ano — amplamente compensada pelo alpha potencial.

**Baseline de referência (C060)**: CAGR=23.5%, Sharpe=1.27, MDD=-29.8%, HOLDOUT equity=R$506k, 14 switches em 7.7 anos.

**Infraestrutura operacional**: BTG Pactual (BR doméstico + Internacional em USD). Operação manual via app. Mercado US: 11:30-18:00 BRT.

**Regras de fase**:
- Custo de transação uniforme simplificado no primeiro ciclo; refinamento diferenciado na consolidação.
- Regra fiscal simplificada: penalizar withholding 30% sobre dividendos US; remover isenção R$20k para ativos US.
- Anti-lookahead estrito (shift(1)) mantido em todas as features, incluindo cross-market.
- Walk-forward: TRAIN / HOLDOUT com mesma disciplina da Phase 6.
- Toda task deve superar C060 ou justificar por que não (com diagnóstico).

### Fase 7A — Cash Upgrade: Tesouro IPCA+ (CANCELADA)

**Objetivo original**: substituir a remuneração do caixa de CDI para Tesouro IPCA+ no motor dual-mode existente (C060).

**Motivo do cancelamento**: análise CTO com dados reais do Tesouro Transparente (PU diário de NTN-B) demonstrou que Tesouro IPCA+ mark-to-market **não é substituto de cash sem risco**. Título curto (venc. ~5 anos): CAGR +2.3pp vs CDI, mas vol 5.2% e MDD -9.3%. Título longo (venc. 2035): vol 16% e MDD -22%. O C060 fica 47% do tempo em cash para proteção — introduzir volatilidade no caixa contradiz a lógica do ML trigger. Decisão do Owner: manter CDI e focar no pipeline US (alpha real).

| ID | Task Name | Phase | Status | Key Artifacts / Logs | Timestamp |
|---|---|---|---|---|---|
| T082 | Cash upgrade: CDI → Tesouro IPCA+ (backtest C060 recalculado) | STATE3-P7A (Cash) | CANCELLED | Análise CTO: IPCA+ mark-to-market não é risk-free. NTN-B curta (5y): MDD=-9.3%, vol=5.2%. NTN-B longa (2035): MDD=-22%, vol=16%. Decisão Owner: manter CDI, focar pipeline US. | 2026-03-02T17:30:00Z |

### Fase 7B — Ingestão e Qualidade de Dados US

**Objetivo**: construir pipeline de ingestão para ~500 tickers do S&P 500 (OHLCV diário + dividendos + splits), aplicar o mesmo framework de qualidade de dados do BR (SPC charts, blacklist, universo operacional), e produzir SSOT expandido com tickers BR + US normalizados.

| ID | Task Name | Phase | Status | Key Artifacts / Logs | Timestamp |
|---|---|---|---|---|---|
| T083 | SPEC: Pipeline de dados US (ingestão, qualidade, SSOT expandido) | STATE3-P7B (Spec) | DONE | `scripts/t083_spec_us_data_pipeline.py` + `02_Knowledge_Bank/docs/specs/SPEC-083_PIPELINE_DADOS_US_T083.md` + `sp500_current_symbols_snapshot.csv` (503 símbolos). Manifest V2 SHA256: 9 entradas, 0 mismatches. Auditor PASS (V2). | 2026-03-02T17:39:16Z |
| T084 | Ingestão S&P 500: OHLCV + dividendos + splits (2018-2026) | STATE3-P7B (Ingest) | DONE | `scripts/t084_ingest_sp500_brapi_us_market_data.py` + `src/data_engine/ssot/SSOT_US_MARKET_DATA_RAW.parquet` (1.006.669 linhas, 499 tickers, 2018-01-02..2026-02-26). Fonte: BRAPI. Dividendos derivados via close/adjusted_close. Manifest V2 SHA256: 10 entradas, 0 mismatches. Auditor PASS (V2). | 2026-03-02T19:10:04Z |
| T085 | Qualidade de dados US: SPC charts + blacklist + universo operacional | STATE3-P7B (Quality) | DONE | `scripts/t085_us_data_quality_spc_blacklist.py` + `src/data_engine/ssot/SSOT_US_UNIVERSE_OPERATIONAL.parquet` (496 tickers) + `src/data_engine/ssot/SSOT_US_BLACKLIST_OPERATIONAL.csv` (3 HARD). Manifest SHA256: 11 entradas, 0 mismatches. 12 gates PASS. Auditor PASS. | 2026-03-02T20:58:55Z |
| T086 | SSOT unificado BR+US: merge canonical base + macro expandido (VIX, DXY, Treasury yield, Fed funds) | STATE3-P7B (SSOT) | DONE | `scripts/t086_build_ssot_br_us_unified.py` + `src/data_engine/ssot/SSOT_MACRO_EXPANDED.parquet` (2.025 linhas × 12 cols, 6 séries FRED) + `src/data_engine/ssot/SSOT_CANONICAL_BASE_BR_US.parquet` (1.620.912 linhas, 1.175 tickers BR+US). Manifest V2 SHA256: 14 entradas, 0 mismatches. 12 gates PASS. Auditor PASS (V2). | 2026-03-02T23:53:05Z |

### Fase 7C — Feature Engineering Multi-Mercado

**Objetivo**: expandir a feature matrix para incluir features cross-market (VIX, DXY, Treasury yield spread, momentum relativo BR/US, correlação rolling) e features per-ticker US (mesma lógica BR adaptada). Validar anti-lookahead em todas as features novas.

| ID | Task Name | Phase | Status | Key Artifacts / Logs | Timestamp |
|---|---|---|---|---|---|
| T087 | Feature engineering US: per-ticker features (momentum, SPC, volume) | STATE3-P7C (Features-US) | PENDING | | |
| T088 | Feature engineering cross-market: VIX, DXY, Treasury spread, momentum relativo BR/US | STATE3-P7C (Features-Cross) | PENDING | | |
| T089 | Feature matrix unificada + EDA + validação anti-lookahead | STATE3-P7C (Matrix) | PENDING | | |

### Fase 7D — Stock Picking Multi-Mercado

**Objetivo**: adaptar o motor de seleção de ativos (campeonato F1 / score ranking) para operar sobre o universo unificado de ~1.100 tickers, com custo de transação uniforme simplificado e regra fiscal simplificada (penalização de dividendos US). Rodar ablação de parâmetros de seleção (n_positions, cadence, alocação BR/US).

| ID | Task Name | Phase | Status | Key Artifacts / Logs | Timestamp |
|---|---|---|---|---|---|
| T090 | Adaptação do motor de seleção para universo BR+US (custo uniforme) | STATE3-P7D (Selector) | PENDING | | |
| T091 | Ablação de seleção multi-mercado (n_positions, cadence, split BR/US) | STATE3-P7D (Ablation) | PENDING | | |

### Fase 7E — ML Trigger Multi-Mercado

**Objetivo**: retreinar o ML trigger (XGBoost) com features expandidas (cross-market), mantendo walk-forward estrito e anti-lookahead. Avaliar se o trigger deve ser único (cash/mercado global) ou dual (trigger BR + trigger US independentes). Ablação de hiperparâmetros + threshold + histerese.

| ID | Task Name | Phase | Status | Key Artifacts / Logs | Timestamp |
|---|---|---|---|---|---|
| T092 | ML trigger retreino com features cross-market (XGBoost walk-forward) | STATE3-P7E (ML-Retrain) | PENDING | | |
| T093 | Ablação: trigger único vs dual (BR independente + US independente) | STATE3-P7E (ML-Ablation) | PENDING | | |
| T094 | Threshold + histerese tuning para trigger multi-mercado | STATE3-P7E (ML-Tuning) | PENDING | | |

### Fase 7F — Backtest Integrado e Comparativo

**Objetivo**: integrar stock picking multi-mercado + ML trigger + Tesouro IPCA+ no cash. Rodar backtest completo (TRAIN + HOLDOUT). Comparar contra C060 (baseline), CDI, Ibovespa, S&P 500. O winner Phase 7 deve superar C060 em CAGR e Sharpe, com MDD controlado.

| ID | Task Name | Phase | Status | Key Artifacts / Logs | Timestamp |
|---|---|---|---|---|---|
| T095 | Backtest integrado: BR+US + ML trigger + IPCA+ cash (vs C060/CDI/Ibov/SP500) | STATE3-P7F (Backtest) | PENDING | | |
| T096 | Phase 7 Comparative Plotly (winner Phase 7 vs C060 vs benchmarks) | STATE3-P7F (Visual) | PENDING | | |

### Fase 7G — Refinamento de Fricções (condicional)

**Objetivo**: se a diferença entre custo uniforme e custo real diferenciado for > 1pp CAGR, implementar modelo de fricções detalhado (settlement D+2/D+1, custos BTG reais por ordem, modelo fiscal completo com isenção BR e tributação US, withholding de dividendos). Caso contrário, manter simplificação.

| ID | Task Name | Phase | Status | Key Artifacts / Logs | Timestamp |
|---|---|---|---|---|---|
| T097 | Análise de sensibilidade: custo uniforme vs diferenciado (gate > 1pp) | STATE3-P7G (Friction-Gate) | PENDING | | |
| T098 | Modelo de fricções diferenciado por mercado (se gate T097 ativado) | STATE3-P7G (Friction-Model) | PENDING | | |

### Fase 7H — Consolidação e Governança

**Objetivo**: consolidar lições da Phase 7, fechar a fase com governance closeout, e promover o winner Phase 7 como novo baseline de produto.

| ID | Task Name | Phase | Status | Key Artifacts / Logs | Timestamp |
|---|---|---|---|---|---|
| T099 | Phase 7 Lessons Learned | STATE3-P7H (Lessons) | PENDING | | |
| T100 | Phase 7 Governance Closeout | STATE3-P7H (Closeout) | PENDING | | |
