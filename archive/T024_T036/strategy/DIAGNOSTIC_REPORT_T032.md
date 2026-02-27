# DIAGNOSTIC REPORT T032

## Escopo e fontes
- Ledger analisado: `/home/wilson/AGNO_WORKSPACE/src/data_engine/portfolio/SSOT_PORTFOLIO_LEDGER.parquet`
- Curve analisada: `/home/wilson/AGNO_WORKSPACE/src/data_engine/portfolio/SSOT_PORTFOLIO_CURVE.parquet`
- Standings: `/home/wilson/AGNO_WORKSPACE/src/data_engine/features/SSOT_F1_STANDINGS.parquet`
- Diagnostics: `/home/wilson/AGNO_WORKSPACE/src/data_engine/diagnostics/SSOT_BURNER_DIAGNOSTICS.parquet`
- Canonical preços: `/home/wilson/AGNO_WORKSPACE/src/data_engine/ssot/SSOT_CANONICAL_BASE.parquet`
- Nota factual: arquivo `*_RL.parquet` não encontrado; usada a trilha ativa (`SSOT_PORTFOLIO_LEDGER/ CURVE.parquet`).

## 1) Investigação crônica (sangramento 2021-2022)
| Ticker | Compra | Venda | Retorno % | Rank F1 na Compra | Slope60 na Compra | Diagnóstico |
|---|---|---|---:|---:|---:|---|
| MAPT4 | 2021-07-29 | 2021-12-22 | -40.31% | 1 | -0.760171 | faca_caindo=SIM |
| NORD3 | 2022-11-29 | 2022-12-26 | -38.25% | 5 | -0.028754 | faca_caindo=SIM |
| JOPA4 | 2021-06-16 | 2021-12-21 | -38.04% | 1 | NA | faca_caindo=NAO |
| AVLL3 | 2022-08-23 | 2022-09-27 | -34.09% | 1 | -0.074275 | faca_caindo=SIM |
| AVLL3 | 2022-08-26 | 2022-09-27 | -34.09% | 1 | -0.066044 | faca_caindo=SIM |

Observação factual: flag `faca_caindo=SIM` foi marcada quando `slope_60 <= 0` na data da compra.

## 2) Investigação aguda (dias de maior queda diária)
| Data | Retorno diário carteira | Equity |
|---|---:|---:|
| 2019-09-23 | -6.30% | 123010.87 |
| 2018-07-13 | -4.29% | 102422.07 |
| 2019-01-08 | -3.72% | 117074.55 |

### Composição e stop-check em 2019-09-23
- Top composição (até 10): ['CEBR5', 'HBTS5', 'NORD3', 'WLMM3', 'BALM4', 'SOND5', 'CBEE3', 'AHEB3', 'RSUL4', 'CTKA4']
- Tickers com sinal SELL no dia: []
- Tickers efetivamente vendidos no dia: []
- Não houve sinal SELL para a composição principal nesse dia.

### Composição e stop-check em 2018-07-13
- Top composição (até 10): ['FHER3', 'PLAS3', 'PRIO3', 'ENMT3', 'CTSA3', 'FESA3', 'JFEN3', 'RCSL3', 'CTKA4', 'SOND5']
- Tickers com sinal SELL no dia: []
- Tickers efetivamente vendidos no dia: []
- Não houve sinal SELL para a composição principal nesse dia.

### Composição e stop-check em 2019-01-08
- Top composição (até 10): ['HETA4', 'CBEE3', 'HBTS5', 'DTCY3', 'AZEV4', 'WLMM3', 'PLAS3', 'ENMT4', 'AXIA5', 'SOND5']
- Tickers com sinal SELL no dia: []
- Tickers efetivamente vendidos no dia: ['PLAS3']
- Não houve sinal SELL para a composição principal nesse dia.

## 3) Arqueologia EXP_001 (código legado)
- Arquivo EXP_001 analisado: `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/work/experimentos_on_flight/EXP_001_S008_TOP10S45_STRESSSELL_2019_20210630_V1/run_experiment.py`
- Documento de baseline/ranking: `/home/wilson/CEP_BUNDLE_CORE/docs/MASTERPLAN_V2.md`
- Documento operacional compra: `/home/wilson/CEP_BUNDLE_CORE/corpus/source/external_refs/CEP_COMPRA/CEP_COMPRA/docs/compra_semanal_model_selection.md`

### Busca explícita por regras
| Regra buscada | Evidência no script EXP_001 |
|---|---|
| ATR | NÃO ENCONTRADA |
| Compression | NÃO ENCONTRADA |
| ADX | NÃO ENCONTRADA |
| MovingAverageAlignment | NÃO ENCONTRADA |

- Fórmula de ranking encontrada no legado documental: `score_m3 = z(score_m0) + z(ret_lookback_62) - z(vol_lookback_62)`
- Fato observado no documento de compra semanal: baseline de ranking por retorno médio em janela K e regras sequenciais de caixa (top-up + novas entradas).

## 4) Cruzamento factual (causa-raiz observada)
- Entre os 5 piores trades do período, 4/5 foram iniciados com `slope_60 <= 0` (proxy de tendência desfavorável na entrada).
- No código EXP_001 analisado, não foram encontradas regras explícitas de ATR/ADX/Compression/Moving-Average-Alignment; o núcleo operacional observado usa ranking + elegibilidade CEP + stress sell.
- O documento de baseline registra ranking com penalização de risco via volatilidade (`- z(vol_lookback_62)`), diferente de ranking puramente por retorno.
- Este relatório descreve apenas evidências observadas nos artefatos carregados (sem proposta de solução).
