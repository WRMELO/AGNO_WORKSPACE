# SPEC-083_PIPELINE_DADOS_US_T083

## 1) Objetivo
Definir a especificacao tecnica do pipeline de dados US para suportar T084 (ingestao), T085 (qualidade) e T086 (SSOT BR+US), sem executar ingestao massiva nesta task.

## 2) Escopo e premissas
- Janela alvo para alinhamento com baseline C060: 2018-07-02 a 2026-02-26.
- Universo alvo US: ~500 tickers (S&P 500).
- Dados minimos por ticker: OHLCV diario + dividendos + splits.
- T083 e SPEC-only: probes pequenos sao permitidos; ingestao completa fica para T084.

## 3) Fontes avaliadas (probe tecnico)
| Fonte | Success Rate | Cobertura media (proxy) | Dividendos | Splits |
|---|---:|---:|---|---|
| yahoo_chart_api | 0.00 | 0.00 | nao | nao |
| stooq_daily_csv | 1.00 | 0.96 | nao | nao |
| yahoo_csv_download | 0.00 | 0.00 | nao | nao |

**Fonte primaria OHLCV**: `stooq_daily_csv`
**Fonte primaria Corporate Actions**: `REQUIRES_API_KEY_PROVIDER`
**Fonte fallback**: `stooq_daily_csv`
**Nota de ambiente**: Yahoo retornou HTTP 429 no ambiente atual; para corporate actions em T084 usar provider com API key (Polygon/IEX Cloud/Nasdaq Data Link) ou retry com janela controlada.

Criterio: priorizar cobertura + eventos corporativos (dividendos/splits) + estabilidade sem credenciais.

## 4) Plano de universo US (~500)
- Fonte proposta para bootstrap: lista atual S&P 500 versionada por snapshot.
- Risco conhecido: survivorship bias quando usar apenas lista atual.
- Mitigacao ciclo 1: registrar risco e versionar snapshot de composicao usado em T084.
- Mitigacao ciclo 2: incorporar composicao historica por data efetiva.
- Probe de composicao atual encontrou `503` simbolos.
- Snapshot versionado: `outputs/governanca/T083-US-DATA-PIPELINE-SPEC-V2_evidence/sp500_current_symbols_snapshot.csv`.

## 5) Schema proposto para T084/T086
### 5.1 US RAW (`SSOT_US_MARKET_DATA_RAW.parquet`)
- Chave primaria logica: (`ticker`, `date`).
- Colunas obrigatorias: `ticker`, `date`, `open`, `high`, `low`, `close`, `adj_close`, `volume`, `dividend_cash`, `split_factor`, `currency`, `exchange`, `timezone`, `source`.
- Convencao ticker: uppercase e ponto convertido para hifen (ex.: `BRK.B` -> `BRK-B`).

### 5.2 SSOT unificado BR+US (`SSOT_CANONICAL_BASE_BR_US.parquet` - proposta T086)
- Colunas minimas adicionais: `market` (`BR`/`US`), `currency`, `close_operational` harmonizado.
- Regra de moeda: manter precos nativos por mercado; conversoes cambiais apenas quando exigidas por feature/portfolio logic.

## 6) Qualidade de dados (entrada para T085)
- Cobertura minima por ticker (pregoes esperados vs observados).
- Deteccao de gaps longos e dias duplicados.
- Coerencia OHLC (`low <= open/close <= high`).
- Eventos corporativos: splits/dividendos nulos e picos extremos.
- SPC/outlier flags para retornos diarios e volumes.
- Blacklist operacional para tickers com anomalias recorrentes.

## 7) Anti-lookahead e fusos (BR x US)
- Regra global: features e sinais usam `shift(1)`.
- Dados US (fechamento ~16:00 ET) nao podem alimentar decisao BR no mesmo dia de pregão local.
- Regra operacional recomendada: alinhar dados US em D para uso em D+1 na camada de features/sinais.

## 8) Plano de execucao por task
- **T084**: ingestao massiva US + materializacao RAW + snapshot de universo utilizado.
- **T085**: quality framework US (SPC, blacklist, cobertura, anomalias).
- **T086**: merge BR+US + macro expandido (VIX, DXY, Treasury spread, Fed funds).

## 9) Riscos e mitigacoes
- **R1_SOURCE_STABILITY**: Fonte primaria pode sofrer limitacao temporaria ou bloqueio. | Mitigacao: Definir fallback funcional e retry/backoff deterministico em T084.
- **R2_SURVIVORSHIP**: Lista atual do S&P 500 introduz survivorship bias. | Mitigacao: Registrar risco no ciclo 1 e planejar composicao historica no ciclo 2.
- **R3_CORP_ACTIONS**: Divergencias em dividendos/splits entre fontes podem distorcer retorno. | Mitigacao: Conferir consistencia por ticker e criar blacklist operacional em T085.
- **R4_TIMEZONE_LOOKAHEAD**: Uso indevido de fechamento US no mesmo dia BR gera lookahead. | Mitigacao: Aplicar regra D+1 e shift(1) global para features cross-market.
- **R5_SCHEMA_DRIFT**: Mudanca de schema de provider quebra ingestao. | Mitigacao: Validacao de schema por gate e fail-fast com diagnostico objetivo.

## 10) Artefatos de evidencia (T083)
- `outputs/governanca/T083-US-DATA-PIPELINE-SPEC-V2_evidence/source_probe_results.json`
- `outputs/governanca/T083-US-DATA-PIPELINE-SPEC-V2_evidence/schema_alignment_snapshot.json`
- `outputs/governanca/T083-US-DATA-PIPELINE-SPEC-V2_evidence/universe_plan.json`
- `outputs/governanca/T083-US-DATA-PIPELINE-SPEC-V2_evidence/risk_register.json`
- `outputs/governanca/T083-US-DATA-PIPELINE-SPEC-V2_evidence/sp500_current_symbols_snapshot.csv`

