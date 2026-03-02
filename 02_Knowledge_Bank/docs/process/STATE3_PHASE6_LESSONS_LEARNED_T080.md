# STATE 3 Phase 6 — Lessons Learned (T080)

**Gerado em**: 2026-03-02T11:41:08Z  
**Task**: T080  
**Ciclo coberto**: T076 → T077-V3 → T078 → T079  
**Winner produto Phase 6**: C060 (thr=0.25, h_in=3, h_out=5)  

## 1) Contexto do ciclo

- **Escopo**: STATE 3 Phase 6 — ML Trigger para Forno Dual-Mode (T076→T079).
- **Objetivo-mestre**: substituir o termostato determinístico (esgotado após 7 tentativas T039→T072) por um classificador supervisionado XGBoost com walk-forward e anti-lookahead estrito.
- **Walk-forward**: TRAIN 2018-07-02 → 2022-12-30 | HOLDOUT 2023-01-02 → 2026-02-26.
- **Acid window**: 2024-11-01 → 2025-11-28 (completamente fora do TRAIN).
- **Resultado final**: Winner de produto = **C060** (thr=0.25, h_in=3, h_out=5), HOLDOUT equity=R$506,432, MDD=-18.7%, switches=13. Acid: equity=R$445,357, MDD=-5.4%.
- **Evidência de fechamento visual**: `outputs/plots/T079_STATE3_PHASE6D_COMPARATIVE.html`.
- **Referências de governança**: `00_Strategy/ROADMAP.md`, `00_Strategy/TASK_REGISTRY.md`, `00_Strategy/OPS_LOG.md`.

## 2) O que deu certo

- **LL-PH6-001** (ESTRATEGIA): O pivô para ML foi validado empiricamente. O modelo C060 entrega HOLDOUT R$506k vs T072 R$407k (+24.4%), com MDD HOLDOUT=-18.7% vs T072 MDD≈-19.5%. A hipótese c... [evidência: `T079` | `outputs/governanca/T079-PHASE6-PLOTLY-COMPARATIVE-V1_evidence/c057_vs_c060_metrics.json`]

- **LL-PH6-002** (VALIDACAO): Anti-lookahead via shift(1) global foi aplicado desde T076 e mantido em todo o pipeline. Nenhuma feature usa dado do dia D na decisão do dia D. A decisão no dia... [evidência: `T076` | `outputs/governanca/T076-EDA-FEATURE-ENGINEERING-V1_manifest.json`]

- **LL-PH6-005** (MODEL_TUNING): O threshold ótimo de recall do modelo (thr=0.05) não é o threshold ótimo financeiro. T077-V3 usou thr=0.05 para maximizar recall (0.988 HOLDOUT), mas o backtest... [evidência: `T078` | `src/data_engine/portfolio/T078_ML_TRIGGER_BACKTEST_SELECTED_CONFIG.json`]

- **LL-PH6-006** (BACKTEST): h_out (histerese de saída do modo cash) é o parâmetro com maior impacto no churn operacional. C057 (h_out=2) gerou 25 switches no HOLDOUT; C060 (h_out=5) gerou ... [evidência: `T079` | `outputs/governanca/T079-PHASE6-PLOTLY-COMPARATIVE-V1_evidence/c057_vs_c060_metrics.json`]

- **LL-PH6-008** (GOVERNANCA): A distinção entre winner formal de ablação (C057, selecionado em TRAIN-only em T078) e winner de produto (C060, decisão Owner pós-validação em T079) foi um apre... [evidência: `T079` | `outputs/governanca/T079-PHASE6-PLOTLY-COMPARATIVE-V1_manifest.json`]

- **LL-PH6-009** (VALIDACAO): A acid window (nov/2024–nov/2025), completamente fora do TRAIN, é o teste de generalização mais exigente. C060 entregou nesse período: equity=R$445k, MDD=-5.4%,... [evidência: `T079` | `outputs/governanca/T079-PHASE6-PLOTLY-COMPARATIVE-V1_evidence/c057_vs_c060_metrics.json`]

- **LL-PH6-011** (ESTRATEGIA): A curva oracle (martelada perfeita — forçar cash nos dois períodos de deriva conhecidos) entrega ~R$716k no período completo. C060 no HOLDOUT entrega R$506k vs ... [evidência: `T078` | `src/data_engine/portfolio/T078_PORTFOLIO_CURVE_MARTELADA_ORACLE.parquet`]

- **LL-PH6-012** (ESTRATEGIA): Reinforcement Learning (RL) e abordagem híbrida ML+determinístico foram avaliados pelo CTO e descartados conscientemente. Razões: (a) volume de dados insuficien... [evidência: `T077` | `00_Strategy/OPS_LOG.md`]

- **LL-PH6-013** (FEATURE_ENG): ALLOWLIST_CORE_V3 (14 features estáveis validadas pelo CTO) é o conjunto de features canônico do termostato ML a partir da Phase 6. Blacklist consolidada: m3_n_... [evidência: `T077` | `src/data_engine/models/T077_V3_XGB_SELECTED_MODEL.json`]

- **LL-PH6-014** (BACKTEST): Histerese assimétrica (h_in < h_out) é a configuração ótima por design: h_in=3 (reação moderada para entrar em cash) + h_out=5 (saída conservadora do cash) mini... [evidência: `T078` | `src/data_engine/portfolio/T078_ML_TRIGGER_BACKTEST_SELECTED_CONFIG.json`]

## 3) O que não deu certo — Erros corrigidos

### Histórico de versões T077

| Versão | CV Scheme | Resultado | Causa do Problema |
|---|---|---|---|
| T077-V1 | Expanding-window (4 folds) | FAIL lógico — recall=0.000, feasible=0/48 | Folds iniciais sem classe positiva → recall sistematicamente zero |
| T077-V2 | StratifiedKFold(5, shuffle) | PASS técnico / FAIL produto — recall_cv=1.000, recall_holdout=0.145 | Features instáveis com inversão de sinal dominaram o modelo |
| T077-V3 | StratifiedKFold(5, shuffle) + ALLOWLIST_CORE_V3 | PASS — gap_recall=0.012 | Feature stability gate + allowlist 14 features estáveis |

- **LL-PH6-003** (FEATURE_ENG): T077-V2 falhou por overfitting severo causado por features instáveis: recall_cv=1.000 vs recall_holdout=0.145, gap=0.855. Features como spc_close_std, cdi_simple_1d e spc_close_mean apresentaram inver... [evidência: `T077` | `outputs/governanca/T077-V3-XGBOOST-ABLATION-V1_manifest.json`]

- **LL-PH6-004** (MODEL_TUNING): T077-V1 falhou logicamente com feasible_count=0/48 e recall=0.000 na acid window. A causa foi o uso de expanding-window CV com folds temporais iniciais que não continham a classe positiva ('caixa'), z... [evidência: `T077` | `00_Strategy/OPS_LOG.md`]

- **LL-PH6-007** (GOVERNANCA): O tie-break por candidate_id (menor ID) elegeu C057 sobre C060 em T078 de forma arbitrária. C057 e C060 tinham TRAIN idêntico (equity, MDD, switches=1); a diferença era apenas h_out (2 vs 5). C057 tin... [evidência: `T079` | `outputs/governanca/T079-PHASE6-PLOTLY-COMPARATIVE-V1_evidence/c057_vs_c060_metrics.json`]

- **LL-PH6-010** (GOVERNANCA): T079 EXEC #1 falhou auditoria por hash inconsistente no manifest: o script computava o SHA256 do report.md ANTES de escrever a linha final 'OVERALL STATUS', resultando em hash obsoleto no manifest. T0... [evidência: `T079` | `outputs/governanca/T079-PHASE6-PLOTLY-COMPARATIVE-V1_manifest.json`]

## 4) Decisões de governança

### LL-PH6-007

**Categoria**: GOVERNANCA | **Impacto**: NEGATIVO_CORRIGIDO

**Statement**: O tie-break por candidate_id (menor ID) elegeu C057 sobre C060 em T078 de forma arbitrária. C057 e C060 tinham TRAIN idêntico (equity, MDD, switches=1); a diferença era apenas h_out (2 vs 5). C057 tinha candidate_id menor e foi escolhido. C060, com h_out=5, entregou HOLDOUT R$506k vs R$475k de C057 e MDD -18.7% vs -25.4%. T079 foi necessário para reverter a decisão com evidência auditada.

**Evidência**: `T079` — `outputs/governanca/T079-PHASE6-PLOTLY-COMPARATIVE-V1_evidence/c057_vs_c060_metrics.json`

**Regra acionável**: Critério de desempate hierárquico obrigatório quando equity_train e MDD_train são idênticos: (1) switches_train ASC; (2) h_out DESC (preferir menos churn); (3) candidate_id ASC como último recurso. Documentar critério de desempate no selection_rule.json de cada ablação.

### LL-PH6-008

**Categoria**: GOVERNANCA | **Impacto**: POSITIVO

**Statement**: A distinção entre winner formal de ablação (C057, selecionado em TRAIN-only em T078) e winner de produto (C060, decisão Owner pós-validação em T079) foi um aprendizado importante de governança. T078 permanece curado com C057 como seu resultado formal de ablação — a integridade histórica do registro está preservada. C060 é o winner de produto da Phase 6 por decisão do Owner com evidência auditada.

**Evidência**: `T079` — `outputs/governanca/T079-PHASE6-PLOTLY-COMPARATIVE-V1_manifest.json`

**Regra acionável**: Em futuros ciclos: (1) registrar winner formal da ablação como resultado da task de backtest (TRAIN-only); (2) se evidência out-of-sample posterior sugerir alternativa superior, criar task de comparação (como T079) antes de sobrescrever; (3) documentar explicitamente no TASK_REGISTRY e OPS_LOG a distinção entre winner formal e winner de produto, com referência cruzada entre as duas tasks.

### LL-PH6-010

**Categoria**: GOVERNANCA | **Impacto**: NEGATIVO_CORRIGIDO

**Statement**: T079 EXEC #1 falhou auditoria por hash inconsistente no manifest: o script computava o SHA256 do report.md ANTES de escrever a linha final 'OVERALL STATUS', resultando em hash obsoleto no manifest. T079 EXEC #2 corrigiu com a sequência obrigatória: write_report_complete() → hash_all() → write_manifest(). Nenhuma escrita de artefato pode ocorrer após a computação dos hashes.

**Evidência**: `T079` — `outputs/governanca/T079-PHASE6-PLOTLY-COMPARATIVE-V1_manifest.json`

**Regra acionável**: Ordem obrigatória de finalização em todos os scripts de task: (1) Escrever TODOS os artefatos; (2) Escrever report.md COMPLETO (incluindo OVERALL STATUS); (3) Computar SHA256 de todos os artefatos + report; (4) Escrever manifest.json com os hashes; (5) NÃO escrever nada mais depois do manifest. Qualquer desvio desta ordem invalida a integridade do manifest.

## 5) Tabela comparativa de candidatos Phase 6

| Candidato | Task | thr | h_in | h_out | TRAIN Equity | HOLDOUT Equity | HOLDOUT MDD | HOLDOUT Switches | Acid Equity | Acid MDD | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| C045 (XGB winner) | T077-V3 | 0.05 | — | — | — | HOLDOUT recall=0.988 | — | — | Acid recall=0.985 | — | Winner ablação modelo |
| C057 (backtest) | T078 | 0.25 | 3 | 2 | R$344,523 | R$475,075 | -25.4% | 25 | R$411,130 | -7.1% | Winner formal T078 (TRAIN-only) |
| C060 (produto) | T079 | 0.25 | 3 | 5 | R$344,523 | R$506,432 | -18.7% | 13 | R$445,357 | -5.4% | **WINNER PRODUTO PHASE 6** (Owner T079) |
| T072 (baseline) | T072 | — | — | — | R$244.630 | R$407.082 | -19.5% | — | ~R$320k | -19.2% | Baseline determinístico |
| Oracle (teto) | T078 | — | — | — | — | ~R$716k | — | — | — | — | Teto máximo teórico |

## 6) Checklist anti-regressão para Phase 7

Derivado das `actionable_rule` das 14 lições:

- [ ] Aplicar shift(1) global em todas as features — gate explícito de anti-lookahead (LL-PH6-002)
- [ ] Verificar estabilidade cross-split de cada feature antes de ablação (KS-stat, sinal correlação) (LL-PH6-003)
- [ ] Usar StratifiedKFold com shuffle para qualquer problema com classe minoritária < 40% (LL-PH6-004)
- [ ] Calibrar threshold de classificação (recall) e threshold operacional (financeiro) em etapas separadas (LL-PH6-005)
- [ ] Incluir h_out ∈ [2,3,4,5,6,7] no grid, com h_out ≥ h_in como constraint hard (LL-PH6-006, LL-PH6-014)
- [ ] Documentar critério de desempate hierárquico no selection_rule.json (switches_train ASC → h_out DESC → candidate_id) (LL-PH6-007)
- [ ] Definir acid window explicitamente antes de iniciar o ciclo; incluir acid_mdd e acid_sharpe no selection_rule (LL-PH6-009)
- [ ] Seguir a ordem: write_all_artifacts → write_report_complete → hash_all → write_manifest (LL-PH6-010)
- [ ] Reportar gap_capture_rate = (ML_equity - T072_equity) / (oracle_equity - T072_equity); meta > 50% (LL-PH6-011)
- [ ] Partir de ALLOWLIST_CORE_V3 (14 features); novas features precisam passar no gate G_GENERALIZATION_GAP_RECALL < 0.15 (LL-PH6-013)
- [ ] Nunca reabrir discussão de RL sem ≥ 5.000 pregões ou ganho demonstrado > 20% de gap_capture_rate (LL-PH6-012)

## 7) Artefatos da Phase 6

| Artefato | Task | Tipo |
|---|---|---|
| `scripts/t076_eda_feature_engineering_ml_trigger.py` | T076 | Script EDA + Feature Engineering |
| `src/data_engine/features/T076_FEATURE_MATRIX.parquet` | T076 | Feature matrix (1.902 pregões × 50+ features) |
| `outputs/governanca/T076-EDA-FEATURE-ENGINEERING-V1_manifest.json` | T076 | Manifest SHA256 |
| `scripts/t077_xgboost_ablation_walkforward_v2.py` | T077-V3 | Script ablação XGBoost |
| `src/data_engine/models/T077_V3_XGB_SELECTED_MODEL.json` | T077-V3 | Modelo vencedor (C045, 120 estimadores, thr=0.05) |
| `src/data_engine/features/T077_V3_PREDICTIONS_DAILY.parquet` | T077-V3 | Predições diárias (TRAIN+HOLDOUT) |
| `src/data_engine/features/T077_V3_ABLATION_RESULTS.parquet` | T077-V3 | Resultados ablação (96 candidatos) |
| `outputs/plots/T077_V3_STATE3_PHASE6B_MODEL_DIAGNOSTICS.html` | T077-V3 | Diagnóstico visual do modelo |
| `outputs/governanca/T077-V3-XGBOOST-ABLATION-V1_manifest.json` | T077-V3 | Manifest SHA256 (17 entradas) |
| `scripts/t078_ml_trigger_backtest_dual_mode.py` | T078 | Script backtest financeiro |
| `src/data_engine/portfolio/T078_ML_TRIGGER_BACKTEST_SELECTED_CONFIG.json` | T078 | Config winner C057 (formal) |
| `src/data_engine/portfolio/T078_PORTFOLIO_CURVE_ML_TRIGGER.parquet` | T078 | Curva equity C057 |
| `src/data_engine/portfolio/T078_PORTFOLIO_CURVE_MARTELADA_ORACLE.parquet` | T078 | Curva oracle (teto) |
| `outputs/plots/T078_STATE3_PHASE6C_BACKTEST_COMPARATIVE.html` | T078 | Plotly backtest comparativo |
| `outputs/governanca/T078-ML-TRIGGER-BACKTEST-V1_manifest.json` | T078 | Manifest SHA256 (12 entradas) |
| `scripts/t079_plotly_phase6_comparative.py` | T079 | Script comparativo C057 vs C060 |
| `outputs/plots/T079_STATE3_PHASE6D_COMPARATIVE.html` | T079 | Dashboard Plotly 4 painéis |
| `outputs/governanca/T079-PHASE6-PLOTLY-COMPARATIVE-V1_evidence/c057_vs_c060_metrics.json` | T079 | Métricas comparativas auditadas |
| `outputs/governanca/T079-PHASE6-PLOTLY-COMPARATIVE-V1_manifest.json` | T079 | Manifest SHA256 (7 entradas) |
| `02_Knowledge_Bank/docs/process/STATE3_PHASE6_LESSONS_LEARNED_T080.md` | T080 | Este documento |

## 8) Lições detalhadas (todas as 14)

### LL-PH6-001 — ESTRATEGIA (POSITIVO)

**Statement**: O pivô para ML foi validado empiricamente. O modelo C060 entrega HOLDOUT R$506k vs T072 R$407k (+24.4%), com MDD HOLDOUT=-18.7% vs T072 MDD≈-19.5%. A hipótese central da Phase 6 — que o gap é de detecção, não de conceito — foi confirmada out-of-sample.

**Evidência**: Task `T079` — `outputs/governanca/T079-PHASE6-PLOTLY-COMPARATIVE-V1_evidence/c057_vs_c060_metrics.json`

**Regra acionável**: Em próximos ciclos ML, usar o mesmo protocolo: label binário derivado de períodos conhecidos de deriva + walk-forward + acid window. O conceito do termostato ML é a arquitetura padrão do projeto a partir da Phase 6.

### LL-PH6-002 — VALIDACAO (POSITIVO)

**Statement**: Anti-lookahead via shift(1) global foi aplicado desde T076 e mantido em todo o pipeline. Nenhuma feature usa dado do dia D na decisão do dia D. A decisão no dia D usa informação até D-1. Esse controle foi validado como gate de aceitação em T076 e confirmado na auditoria de cada task subsequente.

**Evidência**: Task `T076` — `outputs/governanca/T076-EDA-FEATURE-ENGINEERING-V1_manifest.json`

**Regra acionável**: Qualquer nova feature adicionada ao pipeline DEVE ter gate explícito de anti-lookahead antes de entrar em ablação. Features sem esse controle são causa de contaminação de todo o pipeline e devem ser bloqueadas na porta de entrada.

### LL-PH6-003 — FEATURE_ENG (NEGATIVO_CORRIGIDO)

**Statement**: T077-V2 falhou por overfitting severo causado por features instáveis: recall_cv=1.000 vs recall_holdout=0.145, gap=0.855. Features como spc_close_std, cdi_simple_1d e spc_close_mean apresentaram inversão de sinal entre TRAIN e HOLDOUT. T077-V3 corrigiu com ALLOWLIST_CORE_V3 (14 features estáveis) e gate de generalização G_GENERALIZATION_GAP_RECALL (gap < 0.15). Gap final V3: 0.012.

**Evidência**: Task `T077` — `outputs/governanca/T077-V3-XGBOOST-ABLATION-V1_manifest.json`

**Regra acionável**: NUNCA submeter feature a ablação sem verificação prévia de estabilidade cross-split (comparar distribuição TRAIN vs HOLDOUT, sinal de correlação TRAIN vs HOLDOUT). Feature com inversão de sinal ou KS-stat > threshold deve ir para blacklist antes de qualquer grid search.

### LL-PH6-004 — MODEL_TUNING (NEGATIVO_CORRIGIDO)

**Statement**: T077-V1 falhou logicamente com feasible_count=0/48 e recall=0.000 na acid window. A causa foi o uso de expanding-window CV com folds temporais iniciais que não continham a classe positiva ('caixa'), zerando o recall sistematicamente. StratifiedKFold(5, shuffle) em V2/V3 corrigiu o problema garantindo representação balanceada da classe minoritária em cada fold.

**Evidência**: Task `T077` — `00_Strategy/OPS_LOG.md`

**Regra acionável**: Em problemas com classes raras (< 40% de prevalência) e séries temporais de comprimento moderado (< 5.000 amostras), usar sempre StratifiedKFold com shuffle. Expanding-window CV é inadequado quando a classe positiva se concentra em períodos específicos do TRAIN.

### LL-PH6-005 — MODEL_TUNING (POSITIVO)

**Statement**: O threshold ótimo de recall do modelo (thr=0.05) não é o threshold ótimo financeiro. T077-V3 usou thr=0.05 para maximizar recall (0.988 HOLDOUT), mas o backtest financeiro em T078 mostrou que thr=0.25 (C057/C060) entrega melhor equity por reduzir falsos positivos que geram trocas desnecessárias. Os dois thresholds têm funções distintas e devem ser calibrados em etapas separadas.

**Evidência**: Task `T078` — `src/data_engine/portfolio/T078_ML_TRIGGER_BACKTEST_SELECTED_CONFIG.json`

**Regra acionável**: Separar pipeline em duas etapas: (1) calibração de threshold de classificação no TRAIN-CV para maximizar recall; (2) calibração de threshold operacional no backtest financeiro TRAIN para maximizar equity/Sharpe com constraints de MDD e switches. Nunca usar o threshold de recall diretamente como threshold operacional.

### LL-PH6-006 — BACKTEST (POSITIVO)

**Statement**: h_out (histerese de saída do modo cash) é o parâmetro com maior impacto no churn operacional. C057 (h_out=2) gerou 25 switches no HOLDOUT; C060 (h_out=5) gerou 13 switches — redução de 48%. Maior h_out também melhorou equity (R$506k vs R$475k) e MDD (-18.7% vs -25.4%) porque evita reentradas prematuras no mercado durante períodos de deriva.

**Evidência**: Task `T079` — `outputs/governanca/T079-PHASE6-PLOTLY-COMPARATIVE-V1_evidence/c057_vs_c060_metrics.json`

**Regra acionável**: Incluir h_out no range [2, 3, 4, 5, 6, 7] como dimensão obrigatória no grid de histerese. Preferir h_out assimétrico (h_out > h_in) por design: reação rápida para entrar em cash (h_in pequeno), saída conservadora do cash (h_out grande). Usar switches_holdout como métrica de custo operacional ao lado de equity e MDD.

### LL-PH6-007 — GOVERNANCA (NEGATIVO_CORRIGIDO)

**Statement**: O tie-break por candidate_id (menor ID) elegeu C057 sobre C060 em T078 de forma arbitrária. C057 e C060 tinham TRAIN idêntico (equity, MDD, switches=1); a diferença era apenas h_out (2 vs 5). C057 tinha candidate_id menor e foi escolhido. C060, com h_out=5, entregou HOLDOUT R$506k vs R$475k de C057 e MDD -18.7% vs -25.4%. T079 foi necessário para reverter a decisão com evidência auditada.

**Evidência**: Task `T079` — `outputs/governanca/T079-PHASE6-PLOTLY-COMPARATIVE-V1_evidence/c057_vs_c060_metrics.json`

**Regra acionável**: Critério de desempate hierárquico obrigatório quando equity_train e MDD_train são idênticos: (1) switches_train ASC; (2) h_out DESC (preferir menos churn); (3) candidate_id ASC como último recurso. Documentar critério de desempate no selection_rule.json de cada ablação.

### LL-PH6-008 — GOVERNANCA (POSITIVO)

**Statement**: A distinção entre winner formal de ablação (C057, selecionado em TRAIN-only em T078) e winner de produto (C060, decisão Owner pós-validação em T079) foi um aprendizado importante de governança. T078 permanece curado com C057 como seu resultado formal de ablação — a integridade histórica do registro está preservada. C060 é o winner de produto da Phase 6 por decisão do Owner com evidência auditada.

**Evidência**: Task `T079` — `outputs/governanca/T079-PHASE6-PLOTLY-COMPARATIVE-V1_manifest.json`

**Regra acionável**: Em futuros ciclos: (1) registrar winner formal da ablação como resultado da task de backtest (TRAIN-only); (2) se evidência out-of-sample posterior sugerir alternativa superior, criar task de comparação (como T079) antes de sobrescrever; (3) documentar explicitamente no TASK_REGISTRY e OPS_LOG a distinção entre winner formal e winner de produto, com referência cruzada entre as duas tasks.

### LL-PH6-009 — VALIDACAO (POSITIVO)

**Statement**: A acid window (nov/2024–nov/2025), completamente fora do TRAIN, é o teste de generalização mais exigente. C060 entregou nesse período: equity=R$445k, MDD=-5.4%, 4 switches, Sharpe≈2.75. O T072 original tinha MDD=-19.2% nesse mesmo período. A redução de MDD de -19.2% para -5.4% no período mais difícil é a evidência mais forte de que o modelo generalizou e não decorou o TRAIN.

**Evidência**: Task `T079` — `outputs/governanca/T079-PHASE6-PLOTLY-COMPARATIVE-V1_evidence/c057_vs_c060_metrics.json`

**Regra acionável**: Definir acid window explicitamente no início de cada phase como o período mais recente e mais difícil do HOLDOUT. Se o modelo não passar na acid window, considerar FAIL independente de métricas agregadas do HOLDOUT. Incluir acid_mdd e acid_sharpe como métricas obrigatórias no selection_rule.json de backtests futuros.

### LL-PH6-010 — GOVERNANCA (NEGATIVO_CORRIGIDO)

**Statement**: T079 EXEC #1 falhou auditoria por hash inconsistente no manifest: o script computava o SHA256 do report.md ANTES de escrever a linha final 'OVERALL STATUS', resultando em hash obsoleto no manifest. T079 EXEC #2 corrigiu com a sequência obrigatória: write_report_complete() → hash_all() → write_manifest(). Nenhuma escrita de artefato pode ocorrer após a computação dos hashes.

**Evidência**: Task `T079` — `outputs/governanca/T079-PHASE6-PLOTLY-COMPARATIVE-V1_manifest.json`

**Regra acionável**: Ordem obrigatória de finalização em todos os scripts de task: (1) Escrever TODOS os artefatos; (2) Escrever report.md COMPLETO (incluindo OVERALL STATUS); (3) Computar SHA256 de todos os artefatos + report; (4) Escrever manifest.json com os hashes; (5) NÃO escrever nada mais depois do manifest. Qualquer desvio desta ordem invalida a integridade do manifest.

### LL-PH6-011 — ESTRATEGIA (POSITIVO)

**Statement**: A curva oracle (martelada perfeita — forçar cash nos dois períodos de deriva conhecidos) entrega ~R$716k no período completo. C060 no HOLDOUT entrega R$506k vs T072 R$407k. C060 captura ~38% do gap entre T072 e o oracle no HOLDOUT. Esse percentual de captura do gap é a métrica de eficiência do termostato ML e serve como referência para Phase 7 e ciclos futuros.

**Evidência**: Task `T078` — `src/data_engine/portfolio/T078_PORTFOLIO_CURVE_MARTELADA_ORACLE.parquet`

**Regra acionável**: Sempre manter a curva oracle como benchmark de teto. Reportar 'gap_capture_rate = (ML_equity - T072_equity) / (oracle_equity - T072_equity)' como KPI de evolução do termostato entre phases. Meta para Phase 7: gap_capture_rate > 50%.

### LL-PH6-012 — ESTRATEGIA (POSITIVO)

**Statement**: Reinforcement Learning (RL) e abordagem híbrida ML+determinístico foram avaliados pelo CTO e descartados conscientemente. Razões: (a) volume de dados insuficiente para RL estável (~1.900 pregões); (b) recompensa esparsa (poucos períodos de regime real); (c) a natureza do problema é de classificação supervisionada, não decisão sequencial com recompensa acumulada; (d) híbrido adicionaria complexidade sem evidência de ganho marginal sobre XGBoost puro com features bem validadas.

**Evidência**: Task `T077` — `00_Strategy/OPS_LOG.md`

**Regra acionável**: Não reabrir a discussão de RL ou híbrido sem nova evidência concreta: (a) pelo menos 5.000 pregões disponíveis; ou (b) demonstração de ganho > 20% de gap_capture_rate sobre o XGBoost puro em validação out-of-sample. Qualquer proposta sem essas condições deve ser bloqueada na fase de gate check do Architect.

### LL-PH6-013 — FEATURE_ENG (POSITIVO)

**Statement**: ALLOWLIST_CORE_V3 (14 features estáveis validadas pelo CTO) é o conjunto de features canônico do termostato ML a partir da Phase 6. Blacklist consolidada: m3_n_tickers e spc_n_tickers (proxies temporais — correlação > 0.9 com tempo). 36 features candidatas descartadas por instabilidade cross-split. Gap recall CV→HOLDOUT com ALLOWLIST_CORE_V3: 0.012 (< 0.15 — gate PASS).

**Evidência**: Task `T077` — `src/data_engine/models/T077_V3_XGB_SELECTED_MODEL.json`

**Regra acionável**: ALLOWLIST_CORE_V3 deve ser o ponto de partida para Phase 7. Novas features precisam passar pelo gate de estabilidade (KS-stat, sinal de correlação, G_GENERALIZATION_GAP_RECALL < 0.15) antes de serem adicionadas à allowlist. m3_n_tickers e spc_n_tickers permanecem na blacklist permanente até revisão fundamentada.

### LL-PH6-014 — BACKTEST (POSITIVO)

**Statement**: Histerese assimétrica (h_in < h_out) é a configuração ótima por design: h_in=3 (reação moderada para entrar em cash) + h_out=5 (saída conservadora do cash) minimiza falsos alarmes de retorno ao mercado durante deriva prolongada. A configuração h_in=h_out ou h_out < h_in aumenta o churn sem ganho de equity. Grid com h_out simétrico (h_out=h_in) produziu candidatos com switches_holdout > 20, causando custos operacionais elevados.

**Evidência**: Task `T078` — `src/data_engine/portfolio/T078_ML_TRIGGER_BACKTEST_SELECTED_CONFIG.json`

**Regra acionável**: Grid de histerese em backtests futuros deve usar h_out ≥ h_in como restrição hard. Candidatos com h_out < h_in devem ser descartados antes da avaliação de métricas financeiras. Incluir switches_holdout ≤ 20 como constraint adicional de feasibility nos próximos ciclos (além de equity, MDD, switches_train).
