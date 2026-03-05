# Mapa de aderencia com legados (CEP_NA_BOLSA e CEP_COMPRA)

## Topico 1 - periodos development e holdout

- **CEP_NA_BOLSA:** PARCIAL
  - `/home/wilson/CEP_NA_BOLSA/outputs/fase1_calibracao/exp/20260208/baseline_scan_stability/report_baseline_scan_stability.md`
  - linhas 5 e 16: menciona **holdout interno (70/30)**.
  - `development` literal: nao encontrado nos artefatos priorizados.
- **CEP_COMPRA:** NAO ENCONTRADO
  - sem ocorrencias de `development`/`holdout` em `docs/`, `planning/` e `outputs/governanca` (inexistente).

## Topico 2 - formatos Parquet e CSV

- **CEP_NA_BOLSA:** ADERENTE
  - `/home/wilson/CEP_NA_BOLSA/docs/governanca/CEP_NA_BOLSA — Ponto de Situação (snapshot 2026-02-04).md`
  - linhas 33 e 35: SSOT com **CSV/Parquet**.
- **CEP_COMPRA:** ADERENTE
  - `/home/wilson/CEP_COMPRA/docs/task_012_m1_design.md`
  - linhas 16-18: entradas CSV (`ssot_acoes_b3.csv`, `ssot_bdr_b3.csv`) e setor em Parquet.

## Topico 3 - regra venv oficial PortfolioZero

- **CEP_NA_BOLSA:** PARCIAL
  - `/home/wilson/CEP_NA_BOLSA/docs/templates/runner_xbarr_r_plotly_v1.usage.md`
  - linha 7: `.venv (PortfolioZero)`.
- **CEP_COMPRA:** ADERENTE
  - `/home/wilson/CEP_COMPRA/docs/task_005_pre_flight_data.md`
  - linha 5: `Python/venv: /home/wilson/PortfolioZero/.venv`.

## Topico 4 - politica de worktrees

- **CEP_NA_BOLSA:** NAO ENCONTRADO (termo `worktree` nao localizado nos conjuntos priorizados).
- **CEP_COMPRA:** NAO ENCONTRADO (termo `worktree` nao localizado nos conjuntos priorizados).

## Topico 5 - definicao Variante 2

- **CEP_NA_BOLSA:** NAO ENCONTRADO (literal `Variante 2` nao localizado nos conjuntos priorizados).
- **CEP_COMPRA:** NAO ENCONTRADO (literal `Variante 2` nao localizado nos conjuntos priorizados).

## Topico 6 - politica de emendas

- **CEP_NA_BOLSA:** ADERENTE
  - `/home/wilson/CEP_NA_BOLSA/docs/00_constituicao/CEP_NA_BOLSA_CONSTITUICAO_V2_20260204.md`
  - linha 254: alteracoes fora do conjunto exigem **emenda formal da Constituicao**.
- **CEP_COMPRA:** ADERENTE
  - `/home/wilson/CEP_COMPRA/docs/emendas/EMENDA_CEP_COMPRA_V1_3_REGRAS_COMPRA_VENDA.md`
  - linhas 1-5: documento formal de **emenda** e escopo de alteracao.

## Resumo de convergencia

- Forte convergencia em governanca por emendas e uso de Parquet/CSV.
- Convergencia parcial em regra de venv oficial (mais explicita em CEP_COMPRA).
- Divergencia de maturidade semantica em `development/holdout`, politica explícita de `worktrees` e taxonomia `Variante 2`.
