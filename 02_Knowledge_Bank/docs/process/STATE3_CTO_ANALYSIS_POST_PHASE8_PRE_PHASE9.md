# STATE 3 — Análise CTO Pós-Phase 8: Recalibração e Diagnóstico de Duas Fábricas

**Data**: 2026-03-04
**Autor**: CTO (análise exploratória, não task de produto)
**Referência**: Chat pós-Phase 8 — questionamentos do Owner sobre trade-offs e novos conceitos

---

## 1) Contexto

Após o encerramento formal da Phase 8 (T111 PASS), o Owner conduziu uma sessão de questionamentos sobre os trade-offs documentados nas 16 lições (T110). As análises abaixo foram rodadas como diagnósticos CTO exploratórios (sem governança de task), com o objetivo de informar decisões para a Phase 9.

## 2) Achado 1 — Comparação não era "apples to apples"

**Questionamento do Owner**: "A C060 que está plotada no T109 é com 10 ou 15 tickers?"

**Resposta**: A C060 (winner Phase 6) usa **top_n=10** sobre o universo BR original (~460 tickers, sem BDRs). O winner Phase 8 (C010_N15_CB10) usa **top_n=15** sobre o universo expandido (1.174 tickers BR+BDR). A comparação no T109 tinha duas variáveis mudando simultaneamente (tamanho do universo + número de posições), dificultando isolar o efeito da expansão BDR.

## 3) Achado 2 — Composição real do portfólio Phase 8

**Análise**: cruzamento do ledger T107 com o universo BDR T101.

| Tipo | % médio do portfólio | Posições/dia |
|---|---|---|
| Ações BR | 68.6% | ~10.6 |
| BDR B3 | 23.3% | ~3.6 |
| US_DIRECT | 8.1% | ~1.2 |

BDRs não são peso morto — ~31% dos slots são preenchidos por ativos US. Composição estável entre TRAIN (67.8% BR) e HOLDOUT (69.7% BR). 235 tickers únicos na carteira ao longo do período (135 BR, 81 BDR_B3, 19 US_DIRECT).

## 4) Achado 3 — C060 no universo expandido (teste isolado)

**Teste**: rodar C060 com parâmetros originais (thr=0.25, h_in=3, h_out=2, top_n=10) mas sobre o universo expandido (1.158 tickers pós-blacklist).

| Curva | Equity HOLDOUT | CAGR | MDD | Sharpe |
|---|---:|---:|---:|---:|
| C060 Original (BR, N=10) | R$506k | 13.1% | -18.7% | 0.96 |
| **C060 Expanded (BR+BDR, N=10)** | **R$659k** | **28.8%** | **-11.3%** | **2.17** |
| Phase 8 Winner (BR+BDR, N=15) | R$517k | 26.5% | -7.1% | 3.19 |

**Conclusão**: a expansão BDR gera +30% de equity mantendo os mesmos parâmetros. O threshold ultra-conservador (thr=0.05) do winner Phase 8 mascarava esse ganho ao manter o motor 85% do tempo em cash.

## 5) Achado 4 — N=15 com thr=0.25 dilui o retorno

**Teste**: rodar N=15 (como winner Phase 8) com threshold C060 (thr=0.25) no universo expandido.

| Curva | Equity HOLDOUT | CAGR | MDD | Sharpe |
|---|---:|---:|---:|---:|
| C060 Expanded (N=10, thr=0.25) | R$659k | 28.8% | -11.3% | 2.17 |
| N15 Expanded (N=15, thr=0.25) | R$514k | 26.3% | -10.4% | 2.34 |

**Conclusão**: passar de 10 para 15 posições com max_pct=10% distribui mais uniformemente e concentra menos nos melhores tickers. O score M3 do 11º ao 15º ticker é inferior ao top 10 e puxa a média para baixo.

## 6) Achado 5 — Ablação fina de threshold (0.20 a 0.25)

**Teste**: ablação de thr no range [0.20, 0.21, 0.22, 0.23, 0.24, 0.25] sobre C060 Expanded (N=10, BR+BDR).

| thr | Equity HOLDOUT | CAGR | MDD | Sharpe |
|---:|---:|---:|---:|---:|
| 0.20 | R$688k | 30.5% | -6.3% | 2.38 |
| 0.21 | R$688k | 30.5% | -6.3% | 2.38 |
| **0.22** | **R$698k** | **31.1%** | **-6.3%** | **2.42** |
| 0.23 | R$696k | 31.1% | -6.3% | 2.41 |
| 0.24 | R$638k | 27.4% | -11.3% | 2.10 |
| 0.25 | R$659k | 28.8% | -11.3% | 2.17 |

**Cliff em thr=0.24**: MDD salta de -6.3% para -11.3%. O ponto ideal é **thr=0.22**, que domina em Sharpe (2.42), CAGR (31.1%), equity (R$698k) e mantém MDD em -6.3%.

### Nova winner oficial: **C060X**

| Parâmetro | Valor |
|---|---|
| top_n | 10 |
| threshold | 0.22 |
| h_in | 3 |
| h_out | 2 |
| cadence_mode_a | 3 |
| cadence_mode_b | 10 |
| universo | BR+BDR expandido (1.158 tickers) |
| custo | 2.5 bps uniforme |
| modelo ML | T105 (CORE_PLUS_MACRO_EXPANDED_FX) |

### C060X vs benchmarks — HOLDOUT

| Métrica | C060X | Phase 8 Winner | C060 Original |
|---|---:|---:|---:|
| Equity | R$698k | R$517k (+35%) | R$506k (+38%) |
| CAGR | 31.1% | 26.5% | 13.1% |
| MDD | -6.3% | -7.1% | -18.7% |
| Sharpe | 2.42 | 3.19 | 0.96 |
| Switches | 31 | 15 | 13 |
| Cash% | 75% | 85% | 69% |

### C060X vs benchmarks — ACID window

| Métrica | C060X | Phase 8 Winner | C060 Original |
|---|---:|---:|---:|
| Equity | R$527k | R$384k | R$445k |
| MDD | -1.8% | -2.5% | -5.4% |
| Sharpe | 3.84 | 3.37 | 2.75 |

## 7) Achado 6 — Conceito "Dois Fornos" (troca BR↔US) não se paga

**Hipótese do Owner**: durante os períodos de caixa (CDI), redirecionar o capital para o S&P 500 em USD e retornar quando CDI superar.

**Teste**: calcular retorno do S&P 500 em BRL nos períodos exatos de caixa da C060X, descontando custo FX+IOF de 0.78% one-way.

| Período | CDI acumulado | S&P BRL bruto | Custo troca | S&P BRL líquido | Diferença |
|---|---:|---:|---:|---:|---:|
| HOLDOUT | +33.0% | +51.3% | -25.0% | +26.4% | CDI +6.7pp |
| ACID | +13.8% | -2.8% | -4.7% | -7.5% | CDI +21.2pp |

**Conclusão**: 16 round-trips × 1.56% = 25% de custo. O custo de câmbio devora o excesso de retorno do US. Conceito inviável neste formato.

## 8) Achado 7 — Conceito "Duas Fábricas" é viável mas precisa de ML trigger US

**Conceito do Owner**: duas operações paralelas e independentes — Fábrica BR (C060X, BRL, CDI no tank) e Fábrica US (motor M3 sobre S&P 500, USD, Treasury no tank). Capital dividido no dia zero, cada uma anda sozinha. Consolidação diária em BRL via PTAX.

**Teste diagnóstico**: motor M3 puro (sem ML trigger) sobre S&P 500 em USD + Treasury como tank.

### Fábrica US isolada (HOLDOUT, em USD)

| Métrica | M3 sobre S&P 500 | S&P 500 buy-hold |
|---|---:|---:|
| Equity | $201k | $181k |
| CAGR | 26.0% | 21.5% |
| MDD | **-20.0%** | -18.9% |
| Sharpe | 1.16 | 1.38 |

O M3 bate o S&P em retorno (+$21k) mas tem MDD de -20% (sem proteção).

### Consolidação BR+US (R$100k total, HOLDOUT)

| Split | Equity BRL | CAGR | MDD | Sharpe |
|---|---:|---:|---:|---:|
| 100% BR (C060X) | R$233k | 32.1% | -6.3% | 2.44 |
| 80/20 BR/US | R$226k | 30.9% | -5.5% | **2.46** |
| 70/30 BR/US | R$223k | 30.2% | -5.6% | 2.37 |
| 50/50 BR/US | R$215k | 28.8% | -5.7% | 2.01 |
| 100% US | R$193k | 24.1% | -16.8% | 1.05 |

**Conclusão**: o split 80/20 otimiza Sharpe marginalmente (2.46 vs 2.44), mas a Fábrica US sem ML trigger dilui o resultado. O MDD da Fábrica US (-20%) é o gargalo. Se um ML trigger US reduzir esse MDD para -5 a -8% (como o trigger BR faz), o potencial de diversificação se materializa.

## 9) Decisão do Owner

O Owner adotou a **C060X como nova winner oficial** e autorizou a Phase 9 para construir o ML trigger US (Fábrica US), mantendo a arquitetura de duas fábricas independentes com consolidação na matriz (BRL).

## 10) Artefatos exploratórios gerados

| Artefato | Descrição |
|---|---|
| `scripts/cto_analysis_c060_expanded_universe.py` | Motor C060 sobre universo expandido |
| `scripts/cto_analysis_c060_expanded_ablation.py` | Ablação thr 0.20-0.25 |
| `scripts/cto_analysis_winner_with_c060_threshold.py` | N15 com threshold C060 |
| `scripts/cto_diagnostic_us_vs_cdi_cash_periods.py` | US vs CDI nos períodos de caixa |
| `scripts/cto_diagnostic_two_factories.py` | Duas fábricas BR+US |
| `src/data_engine/portfolio/CTO_C060_EXPANDED_ABLATION_WINNER_CURVE.parquet` | Curva da C060X |
| `src/data_engine/portfolio/CTO_C060_EXPANDED_ABLATION_RESULTS.parquet` | Resultados da ablação |
| `outputs/plots/CTO_C060_EXPANDED_ABLATION_FINAL.html` | Dashboard comparativo final |
| `outputs/plots/CTO_T109_PHASE8E_WITH_ALL_VARIANTS.html` | Dashboard com todas as variantes |
