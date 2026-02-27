# A-001 SSOT Canonical Base Audit Report

**Generated:** 2026-02-27T07:33:41.709636+00:00
**Overall Status:** `CERTIFIED WITH NOTE (Owner Approved)`

## Gate Summary

| Gate | Status | Summary |
| --- | --- | --- |
| G1_STRUCTURAL_INTEGRITY | PASS | 21/21 colunas obrigatorias presentes. |
| G2_SPLIT_HEURISTIC_VALIDATION | PASS | Tickers com eventos de split: 94 |
| G3_RETURN_SANITY | FAIL | Registros com X_real valido: 630985 de 631944 (99.8%) |
| G4_MACRO_ALIGNMENT | FAIL | FAIL: 2 datas no CANONICAL sem correspondente no MACRO. |
| G5_CROSS_REFERENCE_RAW | PASS | close_operational == close_raw (tol=0.01) para 10 tickers sem split. |

## G1_STRUCTURAL_INTEGRITY: PASS

- 21/21 colunas obrigatorias presentes.
- Zero duplicatas em (ticker, date). Total linhas: 631944
- Tickers no CANONICAL: 679, no UNIVERSE_OPERATIONAL: 697
- AVISO: 18 tickers do UNIVERSE sem dados no CANONICAL (possivelmente sem historico).
- Estrutura integra. 679 tickers, 631944 linhas, zero duplicatas.

## G2_SPLIT_HEURISTIC_VALIDATION: PASS

- Tickers com eventos de split: 94
- Zero saltos residuais > 50%. Heuristica de splits validada para 94 tickers.
- Audit trail (heuristic_adjustments_t023.csv): 101 registros.

## G3_RETURN_SANITY: FAIL

- Registros com X_real valido: 630985 de 631944 (99.8%)
- FAIL: 28 registros com |X_real| > 1.0 (fisicamente implausivel).
-   - AFLT3 @ 2019-09-18: X_real=1.089865
-   - BIET39 @ 2024-02-27: X_real=-1.609440
-   - BIET39 @ 2024-02-28: X_real=1.609436
-   - BIET39 @ 2024-03-01: X_real=-1.609440
-   - BIHE39 @ 2024-03-01: X_real=-1.098614
-   - BIHF39 @ 2024-02-27: X_real=-1.609440
-   - BIHF39 @ 2024-02-28: X_real=1.609436
-   - BIHF39 @ 2024-03-01: X_real=-1.609440
-   - BMEB3 @ 2021-12-06: X_real=3.113110
-   - BMEB4 @ 2021-12-03: X_real=-4.541449
- Media global X_real = -0.000175 (sem vies).
- FAIL: 10 tickers com |media X_real| > 0.05 (distorcao sistematica).
-   - AZUL53: media=-0.117344
-   - BFPX39: media=-0.120208
-   - BPAR3: media=0.187110
-   - CASN3: media=-0.061035
-   - DEFT31: media=-0.050464
-   - EMAE3: media=0.108079
-   - FIGE3: media=0.626379
-   - ODER4: media=0.146498
-   - SHUL3: media=-0.691401
-   - TKNO3: media=0.059231

**Findings:**
- 28 registros com |X_real| > 1.0 (fisicamente implausivel).
- 10 tickers com |media X_real| > 0.05 (distorcao sistematica).

## G4_MACRO_ALIGNMENT: FAIL

- FAIL: 2 datas no CANONICAL sem correspondente no MACRO.
-   - 2018-01-25
-   - 2020-11-20
- FAIL: 2 datas com cdi_log_daily NaN apos merge.
- ibov_close NaN: 2, sp500_close NaN: 2
- Maior gap no calendario MACRO: 5.0 dias.

**Findings:**
- 2 datas no CANONICAL sem correspondente no MACRO.
- 2 datas com cdi_log_daily NaN apos merge.

## G5_CROSS_REFERENCE_RAW: PASS

- close_operational == close_raw (tol=0.01) para 10 tickers sem split.
- Plot gerado: 00_Strategy/Task_History/A-001/plots/A001_VIVT3_raw_vs_operational.html
- Plot gerado: 00_Strategy/Task_History/A-001/plots/A001_MGLU3_raw_vs_operational.html
- Plot gerado: 00_Strategy/Task_History/A-001/plots/A001_PETR4_raw_vs_operational.html
- Cross-reference validada. Plots de ['VIVT3', 'MGLU3', 'PETR4'] gerados.

## Veredito Final

### CERTIFICADA COM NOTA (Owner Decision: 2026-02-27)

A SSOT_CANONICAL_BASE.parquet esta **CERTIFICADA PARA USO OPERACIONAL** com as seguintes ressalvas documentadas:

**Defeitos conhecidos e aceitos:**

1. **G3 — 28 registros com |X_real| > 1.0:** Concentrados em BDRs iliquidos (BIET39, BIHF39, BIHE39) e micro-caps (BMEB3/BMEB4, AFLT3). Nenhum ticker core afetado. Acao recomendada: excluir esses tickers do ranking operacional.
2. **G3 — 10 tickers com vies sistematico:** FIGE3 (+0.63), SHUL3 (-0.69), BPAR3 (+0.19), AZUL53 (-0.12), BFPX39 (-0.12), EMAE3 (+0.11), ODER4 (+0.15), CASN3 (-0.06), DEFT31 (-0.05), TKNO3 (+0.06). Acao recomendada: watchlist para exclusao se entrarem no ranking.
3. **G4 — 2 datas orfas:** 2018-01-25 e 2020-11-20 sem correspondencia no MACRO (CDI NaN). Impacto: 2 linhas em 631.944 (0.0003%). Acao recomendada: aceitar como ruido estatistico.

**Tickers com dados nao confiaveis (blacklist de qualidade):**
`AFLT3, BIET39, BIHE39, BIHF39, BMEB3, BMEB4, FIGE3, SHUL3, BPAR3, AZUL53, BFPX39, EMAE3, ODER4, CASN3, DEFT31, TKNO3`

**Base aprovada para:** simulacao de portfolio, calculo SPC, ranking F1, diagnosticos.
**Decisao do Owner:** Certificar como esta, documentar outliers, prosseguir com evolucao do produto.
