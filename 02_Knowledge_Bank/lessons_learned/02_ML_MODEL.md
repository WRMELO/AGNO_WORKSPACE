# Lessons Learned — ML Model

> Consolidação temática de todas as lições sobre treino, validação cruzada, threshold, overfitting e generalização.
> Fonte: phases 5, 6, 8, 9. Originais em `archive/by_phase/`.

---

## 1. Walk-forward com split TRAIN/HOLDOUT explícito

**Regra**: TRAIN 2018-07-02 → 2022-12-30, HOLDOUT 2023-01-02 → 2026-02-26. Seleção de winner exclusivamente no TRAIN. O HOLDOUT é cego — não participa de nenhuma decisão de calibração.

- Phase 5 (LL-PH5-003). O winner T072 passou nos gates do HOLDOUT sem ajuste.
- Mantido em todas as phases ML subsequentes (6, 8, 9, 10) sem exceção.

## 2. CV scheme: StratifiedKFold, não expanding-window

**Regra**: StratifiedKFold(5, shuffle) é o esquema correto para este problema. Expanding-window falha quando folds temporais iniciais não contêm a classe minoritária.

- Phase 6 (LL-PH6-004). T077-V1 falhou com feasible_count=0/48 e recall=0.000 na acid window por usar expanding-window. StratifiedKFold em V2/V3 corrigiu.
- Exceção documentada e justificada: o label tem eventos raros (~30% cash), e folds temporais puros ficam sem classe positiva nos primeiros anos.

## 3. Threshold de recall ≠ threshold financeiro

**Regra**: o threshold que maximiza recall do modelo (thr=0.05, recall=0.988) **não é** o threshold que maximiza equity no backtest (thr=0.25 na Phase 6, thr=0.22 na recalibração C060X). Os dois devem ser calibrados em etapas separadas: (1) ablação ML para recall, (2) ablação financeira para equity/MDD/Sharpe.

- Phase 6 (LL-PH6-005). T077-V3 usou thr=0.05; T078 (backtest) encontrou ótimo em thr=0.25.
- Risco: threshold agressivo (thr=0.05) maximiza proteção (cash 85%) mas underperforma em bull markets prolongados (LL-PH8-010, materializado na ACID window Phase 8).

## 4. Acid window como teste de generalização

**Regra**: a acid window (nov/2024–nov/2025 para BR; mar-mai/2025 para US) é o teste mais exigente de generalização. Completamente fora do TRAIN, cobre o segundo período de deriva.

- Phase 6 (LL-PH6-009). C060: equity=R$445k, MDD=-5.4%, Sharpe≈2.75 na acid window (vs T072 MDD=-19.2%).
- Phase 9 (LL-PH9-004): **dual acid window** (acid_br + acid_us) é mais informativa que janela única genérica. Padrão adotado.

## 5. Esgotamento do espaço determinístico

**Contexto**: antes do pivô para ML, 7 tentativas determinísticas (T039→T072) produziram feasibility de apenas 0.6% (2/324 candidatos). O winner T072 operava na fronteira dos constraints (MDD_train = -29.78% vs limite -30.00%, margem de 0.22pp).

- Phase 5 (LL-PH5-006). O espaço de busca determinístico (rolling window + threshold + histerese) esgotou.
- A "martelada" (forçar caixa nos períodos de deriva) eleva equity de R$407k para R$757k, provando que o gap é de **detecção**, não de conceito (LL-PH5-007).

## 6. Pivô ML validado empiricamente

**Evidência**: C060 (ML trigger) entrega HOLDOUT R$506k vs T072 (determinístico) R$407k (+24.4%), com MDD -18.7% vs -19.5%. Gap capture rate: C060 captura ~38% do gap entre T072 e o oracle (LL-PH6-011).

- Phase 6 (LL-PH6-001). Hipótese central confirmada out-of-sample.

## 7. RL descartado conscientemente

**Decisão**: Reinforcement Learning e abordagem híbrida ML+determinístico foram avaliados e descartados. Razões: (a) ~1.900 pregões insuficientes para RL estável; (b) recompensa esparsa; (c) problema é de classificação supervisionada; (d) complexidade sem ganho.

- Phase 6 (LL-PH6-012).

## 8. Recall vs equity podem divergir

**Observação**: na Phase 8, a variante CORE pura teve recall HOLDOUT superior (0.988 vs 0.940 da CORE_PLUS_MACRO), mas equity inferior no backtest financeiro. A decisão final deve ser no backtest, não na ablação ML.

- Phase 8 (LL-PH8-009). Owner optou por CORE_PLUS_MACRO e confirmou na ablação financeira T106.

## 9. ML trigger US = escudo, não alfa

**Evidência**: no mercado americano, o ML trigger reduziu MDD de -18.9% para -13.0% mas o Sharpe ficou abaixo do SP500 buy-hold (1.20 vs 1.34). Precision 17.7% — 82% dos sinais de cash são falsos positivos.

- Phase 9 (LL-PH9-003). Features macro puras insuficientes para mercado eficiente (LL-PH9-002).

## 10. Complexidade incremental com ganho marginal

**Regra**: quando o ganho técnico marginal vem com custo alto de complexidade (feature stack + modelo + tuning + histerese), padronizar o baseline mais simples. T126 (trigger US v2) foi abandonado para produção em favor de T122 (motor puro).

- Phase 10 (LL-PH10-007). Decisão Owner: simplicidade vencedora.

---

## Checklist anti-regressão ML

1. [ ] Walk-forward estrito: seleção 100% TRAIN, HOLDOUT cego
2. [ ] StratifiedKFold(5, shuffle) como CV scheme padrão
3. [ ] Calibrar threshold em duas etapas: recall ML → equity financeira
4. [ ] Acid window(s) como gate de generalização
5. [ ] Feature guard em toda task ML
6. [ ] Registrar gap_capture_rate (equity ML vs oracle vs determinístico)
7. [ ] Avaliar custo-benefício antes de adicionar complexidade
