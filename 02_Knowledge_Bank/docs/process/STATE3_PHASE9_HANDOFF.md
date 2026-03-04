# HANDOFF: Phase 9 — Duas Fábricas (BR + US)

## Estado do projeto

- **STATE 3 Phase 8** (BDR Bridge): formalmente encerrada em 2026-03-04 (T111 PASS).
- **Análise CTO pós-Phase 8**: conduzida no mesmo dia. Recalibrou winner, testou conceitos alternativos, diagnosticou viabilidade de duas fábricas.
- **Nova winner oficial**: **C060X** (N=10, thr=0.22, h_in=3, h_out=2, universo BR+BDR expandido, modelo T105 CORE_PLUS_MACRO_EXPANDED_FX).
  - HOLDOUT: equity=R$697.606, CAGR=31.1%, MDD=-6.3%, Sharpe=2.42, switches=31
  - ACID: equity=R$527.337, MDD=-1.8%, Sharpe=3.84
  - vs C060 original: +38% equity, -12.4pp MDD, +1.46 Sharpe
  - vs Phase 8 winner (C010_N15_CB10): +35% equity, +0.8pp MDD melhor, -0.77 Sharpe (trade-off aceito pelo Owner)
- **Governança dual-ledger**: TASK_REGISTRY e OPS_LOG atualizados até T111.

## Decisões do Owner incorporadas

1. **C060X é a nova winner de produto** — substitui tanto o C060 (Phase 6) quanto o C010_N15_CB10 (Phase 8) como baseline.
2. **Phase 9 autorizada**: construir Fábrica US (ML trigger US sobre S&P 500 em USD) e consolidar com Fábrica BR (C060X) em arquitetura de duas fábricas independentes.
3. **Conceito "troca BR↔US" (forno 2 com migração de capital) descartado** — custo FX+IOF de 1.56% por round-trip consome o excesso de retorno (16 trocas no HOLDOUT = 25% de custo).

## Conceito Phase 9: Duas Fábricas

```
FÁBRICA BR (BRL)                    FÁBRICA US (USD)
┌─────────────────────┐             ┌─────────────────────┐
│ Capital: X% de 100k │             │ Capital: Y% de 100k │
│ Motor: C060X        │             │ Motor: C060X-US     │
│ Universo: BR+BDR    │             │ Universo: S&P 500   │
│ ML Trigger: XGB BR  │             │ ML Trigger: XGB US  │
│ Tank: CDI           │             │ Tank: Treasury/FF   │
│ Custo: 2.5 bps      │             │ Custo: ~1 bp        │
│ Moeda: BRL           │             │ Moeda: USD          │
└────────┬────────────┘             └────────┬────────────┘
         │         CONSOLIDAÇÃO MATRIZ        │
         └────────►│ Equity = BR + US×PTAX │◄──┘
                   │ Relatório diário BRL  │
                   └───────────────────────┘
```

### Premissas-chave

- **Capital**: R$100k divididos no dia zero entre BR e US. Split a otimizar via ablação.
- **Conversão FX**: one-shot no dia zero (FX+IOF 0.78%). Depois cada fábrica opera na sua moeda, sem mais conversão.
- **Fábrica BR**: já existe (C060X). Sem alteração.
- **Fábrica US**: precisa ser construída. Motor M3 sobre S&P 500 em USD + ML trigger US + Treasury como tank.
- **Consolidação**: contábil via PTAX diária. Equity total = Equity BR (BRL) + Equity US (USD) × PTAX.
- **Walk-forward**: mesmo do projeto — TRAIN 2018-07-02 → 2022-12-30, HOLDOUT 2023-01-02 → 2026-02-26.

### O que já existe (reutilizável)

| Artefato | O que é | Como usar |
|---|---|---|
| `SSOT_US_MARKET_DATA_RAW.parquet` (T084) | OHLCV S&P 500 em USD, 496 tickers, 2018-2026 | Base para motor M3 US |
| `SSOT_US_UNIVERSE_OPERATIONAL.parquet` (T085) | 496 tickers aprovados + blacklist | Universo da Fábrica US |
| `SSOT_MACRO_EXPANDED.parquet` (T086) | VIX, DXY, Treasury yields, Fed funds | Features para ML trigger US + tank rate |
| `SSOT_FX_PTAX_USDBRL.parquet` (T101) | PTAX diária BCB, 2018-2026 | Consolidação BRL |
| `CTO_C060_EXPANDED_ABLATION_WINNER_CURVE.parquet` | Curva da C060X completa | Fábrica BR pronta |
| Motor M3 + dual-mode (T072) | Motor de backtest | Reutilizar estrutura para US |
| Pipeline ML Phase 6/8 (T076-T078, T104-T106) | EDA → XGBoost → ablação → backtest | Espelhar processo para US |

### O que falta construir

1. **Labels de regime US** — equivalente à "martelada" da Phase 6, mas para o S&P 500. Identificar períodos de caixa vs mercado no TRAIN.
2. **Feature matrix US** — features macro US (VIX, Treasury spread, DXY, Fed funds, S&P slope, etc.) com shift(1) anti-lookahead.
3. **ML trigger US (XGBoost)** — treinar com walk-forward estrito, ablação de threshold + histerese.
4. **Motor M3 US com ML trigger** — backtest completo da Fábrica US isolada.
5. **Ablação de split BR/US** — testar [20/80, 30/70, ..., 80/20] e selecionar por Sharpe consolidado.
6. **Dashboard consolidado** — equity BR, equity US, equity total em BRL, comparativo vs benchmarks.

### Diagnóstico CTO prévio (referência)

- **Fábrica US sem ML trigger**: CAGR=26.0% em USD, MDD=-20.0%, Sharpe=1.16 (HOLDOUT).
- **M3 bate S&P 500 buy-hold** por +$21k (+4.5pp CAGR), mas MDD e Sharpe piores.
- **Split 80/20 BR/US otimiza Sharpe marginalmente** (2.46 vs 2.44), mas o MDD de -20% da Fábrica US sem trigger dilui o resultado.
- **Se ML trigger US reduzir MDD para -5 a -8%**, o potencial de diversificação se materializa.

### Trade-offs conhecidos a endereçar

1. **Label de regime US**: como definir? Oracle (períodos de queda >X%)? Regra de drawdown? Precisa de diagnóstico CTO antes.
2. **Tank US**: Fed funds rate como proxy de T-Bill? Ou buscar dados de T-Bill 3M? Fed funds já disponível no SSOT_MACRO_EXPANDED.
3. **Custo de operação US**: 1 bp? 0? Depende da corretora. Usar 1 bp como conservador.
4. **Correlação BR-US**: quando ambas as fábricas estão em caixa simultaneamente, o capital não trabalha em nenhum lado. Medir.
5. **Tributação**: IR sobre ganho de capital nos EUA. Dividendos retidos 30% na fonte. Não modelar no backtest, mas documentar.

## Documentação a consultar

- `02_Knowledge_Bank/docs/process/STATE3_CTO_ANALYSIS_POST_PHASE8_PRE_PHASE9.md` — análise CTO completa com 7 achados e todos os diagnósticos
- `02_Knowledge_Bank/docs/process/STATE3_PHASE8_LESSONS_LEARNED_T110.md` — 16 lições Phase 8, checklist anti-regressão
- `02_Knowledge_Bank/docs/process/STATE3_PHASE6_LESSONS_LEARNED_T080.md` — 14 lições Phase 6 (referência para pipeline ML)
- `00_Strategy/ROADMAP.md` — mapa geral do projeto
- `00_Strategy/TASK_REGISTRY.md` — registro de tasks T001→T111
- `00_Strategy/OPS_LOG.md` — registro de operações/auditorias

## Skills AGNO disponíveis

`/agno-cto`, `/agno-architect`, `/agno-executor`, `/agno-auditor`, `/agno-registry-curator`
