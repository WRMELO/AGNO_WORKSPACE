# Lessons Learned — Dados

> Consolidação temática de todas as lições sobre ingestão, SSOT, qualidade, alinhamento temporal e anti-lookahead.
> Fonte: phases 6, 8, 9, 10. Originais em `archive/by_phase/`.

---

## 1. Anti-lookahead estrito em todo o pipeline

**Regra**: shift(1) global — decisão no dia D usa informação até D-1. Validar com `first_row_all_nan=True` e `max_abs_diff=0.0`.

- Phase 6 (LL-PH6-002). Aplicado desde T076 sem exceção.
- Phase 8 (LL-PH8-005). 76 features, todas validadas.
- Phase 10 (LL-PH10-002). Consistente em todo o ciclo.
- Nota: labels oracle (T112) usam janela futura **por design** (target supervisionado). O shift(1) se aplica às **features**, não ao label.

## 2. Pipeline de dados em 4 etapas

**Padrão**: SPEC → ingestão → qualidade/blacklist → SSOT unificado. Cada etapa com manifest SHA256.

- Phase 8 (LL-PH8-006). T083→T086: 496 tickers US operacionais. Cobertura 2018-2026 alinhada com SSOT BR.

## 3. Alinhamento temporal obrigatório

**Regra**: todos os SSOTs devem começar na mesma data (2018-01-02) para garantir warm-up de rolling windows (62d).

- Phase 8 (LL-PH8-007). T084-V1 começou em 2018-07-02, desalinhando 6 meses do SSOT BR. Finding do Owner pós-auditoria → correção em V2.

## 4. BDRs e US_DIRECT

**Decisão**: 496 tickers do S&P 500 são sintetizados em BRL como BDRs. 446 têm BDR na B3; 50 não têm e são incluídos como `US_DIRECT` com penalidade de fricção cross-border embutida no preço (`1 - 0.0078`).

- Phase 8 (LL-PH8-008). T101-V1 excluiu os 50 → V2 incluiu com penalidade.

## 5. PTAX como fator de risco

**Evidência**: PTAX (câmbio USD/BRL) é um fator de risco real. No HOLDOUT, o dólar caiu -3.8% contra o real, penalizando posições em USD convertidas para BRL.

- Phase 9 (LL-PH9-007). PTAX BCB SGS série 1, ingerida em T101.

## 6. Contrato de semântica de input

**Regra**: validar não apenas o path do arquivo, mas o schema esperado (colunas, tipos). "Path certo + schema errado" causa falha silenciosa.

- Phase 10 (LL-PH10-008). T128 V1 usou arquivo errado como BR winner.
- Phase 10 (LL-PH10-009). Divergência de schema (`equity_end_norm` vs `equity_br_brl`) exigiu adaptação explícita.

## 7. Saneamento de retornos extremos

**Caso**: KDP 2018-07-10, log_ret=-1.718 (evento corporativo merger Keurig+Dr Pepper). Único em 1.000.601 linhas.

- Phase 10 (T119 finding, T120 saneamento). Retorno extremo zerado antes dos rollings.

---

## SSOTs operacionais do projeto

| SSOT | Conteúdo | Tickers | Origem |
|---|---|---|---|
| `SSOT_CANONICAL_BASE.parquet` | BR per-ticker com SPC | 663 | T023 |
| `SSOT_CANONICAL_BASE_BR_EXPANDED.parquet` | BR + BDR em BRL | 1.174 | T102 |
| `SSOT_CANONICAL_BASE_US.parquet` | US per-ticker com SPC | 496 | T119 |
| `SSOT_MACRO.parquet` | Ibov, CDI, S&P 500 | - | T022 |
| `SSOT_MACRO_EXPANDED.parquet` | + VIX, DXY, Treasury, Fed | - | T086 |
| `SSOT_FX_PTAX_USDBRL.parquet` | PTAX diária BCB | - | T101 |
| `SSOT_US_MARKET_DATA_RAW.parquet` | OHLCV S&P 500 | 496 | T084 |

## Checklist anti-regressão dados

1. [ ] shift(1) em toda feature, first_row_all_nan=True
2. [ ] Alinhamento temporal de todos os SSOTs (mesma data de início)
3. [ ] Pipeline 4 etapas: SPEC → ingestão → qualidade → SSOT
4. [ ] Schema contract validado antes de consumir input
5. [ ] Saneamento de retornos extremos documentado
