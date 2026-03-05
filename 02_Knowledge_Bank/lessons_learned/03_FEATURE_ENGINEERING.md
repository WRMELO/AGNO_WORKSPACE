# Lessons Learned — Feature Engineering

> Consolidação temática de todas as lições sobre construção, seleção e validação de features.
> Fonte: phases 6, 8, 9. Originais em `archive/by_phase/`.

---

## 1. Anti-lookahead estrito: shift(1) global

**Regra**: toda feature deve usar `shift(1)` — a decisão no dia D usa apenas informação até D-1. Validar com `first_row_all_nan=True` e `max_abs_diff=0.0` (comparação entre feature bruta e feature com shift).

- Phase 6 (LL-PH6-002). Aplicado desde T076 e mantido em 100% do pipeline.
- Phase 8 (LL-PH8-005). 76 features no dataset expandido, todas validadas.
- Phase 10 (LL-PH10-002). Consistente em todo o ciclo.

## 2. Feature stability gate (ALLOWLIST vs BLACKLIST)

**Regra**: features com inversão de sinal entre TRAIN e HOLDOUT ou alta correlação temporal (corr_date > 0.9) devem ser excluídas. Usar uma allowlist curada (não uma blacklist parcial).

- Phase 6 (LL-PH6-003). T077-V2 falhou por overfitting severo: recall_cv=1.000 vs recall_holdout=0.145, gap=0.855. Features como `spc_close_std`, `cdi_simple_1d`, `spc_close_mean` inverteram sinal.
- T077-V3 corrigiu com ALLOWLIST_CORE_V3 (14 features estáveis). Gap recall caiu para 0.012.
- Phase 6 (LL-PH6-013). Blacklist consolidada: `m3_n_tickers` e `spc_n_tickers` (proxies temporais, corr > 0.9). 36 features descartadas por instabilidade.

## 3. Features macro expandidas agregam valor

**Evidência**: VIX, DXY, Treasury spread, USDBRL e Fed Funds adicionaram +15% equity HOLDOUT quando combinadas com features core (38 features vs 14).

- Phase 8 (LL-PH8-004). Variante CORE_PLUS_MACRO_EXPANDED_FX superou CORE pura em T105/T106.
- Phase 9 (LL-PH9-002). No mercado americano, features macro sozinhas são insuficientes — Sharpe 1.20 US vs 2.42 BR. O mercado US é mais eficiente.

## 4. Time-proxy scan obrigatório

**Regra**: escanear todas as features para correlação com o tempo (abs_corr_date). Threshold: > 0.95 → blacklist automática. Features com corr 0.60-0.95 são monitoradas.

- Phase 6 (LL-PH6-013): `m3_n_tickers` corr=0.97, `spc_n_tickers` corr=0.76 → blacklistadas.
- Phase 10 (T123/T124): scan aplicado a 60 features, max abs_corr_date=0.60, 2 blacklistadas (`m3_exec_valid_tickers` corr=0.97, `us_n_tickers_raw` corr=0.96).

## 5. Features 100% NaN devem ser removidas antes do treino

**Caso**: `sector_ret_dispersion` e `sector_dispersion_delta_1d` no US tinham 100% NaN porque o SSOT usava sector='US' para todos os 496 tickers (1 único grupo → std = NaN).

- Phase 10 (T123 F-01, corrigido em T124). Architect deve remover features inertes antes de entregar ao modelo.

## 6. Número de features por pipeline

| Phase | Features | Resultado |
|---|---|---|
| Phase 6 (BR) | 14 (ALLOWLIST_CORE_V3) | Gap recall 0.012, HOLDOUT equity R$506k |
| Phase 8 (BR+BDR) | 76 (core + macro expandidas) | Sharpe HOLDOUT 3.19, MDD -7.1% |
| Phase 9 (US macro) | 27 (macro only) | Sharpe HOLDOUT 1.20 (escudo, não alfa) |
| Phase 10 (US v2) | 60 (macro + credit + cross-section) | Trigger abandonado por complexidade |

---

## Checklist anti-regressão features

1. [ ] shift(1) global em toda feature, validar com first_row_all_nan
2. [ ] Time-proxy scan (corr_date > 0.95 → blacklist)
3. [ ] Allowlist curada > blacklist parcial
4. [ ] Remover features 100% NaN antes do treino
5. [ ] Feature guard JSON em toda task ML
6. [ ] Documentar feature_inventory.csv com todas as features e proveniência
