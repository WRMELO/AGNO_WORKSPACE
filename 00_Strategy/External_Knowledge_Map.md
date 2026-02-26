# External Knowledge Map - CEP_BUNDLE_CORE

- task_id: `TASK-006-CORPUS-RAG`
- generated_at_utc: `2026-02-25T18:55:46+00:00`
- politica de leitura: somente leitura (nenhum arquivo movido/deletado no `CEP_BUNDLE_CORE`)

## Validacao de Acesso

- Raiz acessivel: `/home/wilson/CEP_BUNDLE_CORE/`
- Conteudo raiz identificado: `_tentativa2_reexecucao_completa_20260220`, `corpus`, `data`, `docs`, `outputs`, `planning`, `scripts`, `tools`.
- Observacao de estrutura real:
  - Os caminhos diretos `/home/wilson/CEP_BUNDLE_CORE/CEP_NA_BOLSA` e `/home/wilson/CEP_BUNDLE_CORE/CEP_COMPRA` nao existem na raiz.
  - O espelho de conhecimento destes modulos existe em `corpus/source/external_refs/`.

## Estrutura Mapeada (profundidade operacional)

### CEP_NA_BOLSA (espelhado)

- Base espelhada: `/home/wilson/CEP_BUNDLE_CORE/corpus/source/external_refs/CEP_NA_BOLSA/CEP_NA_BOLSA/`
- Evidencias de `report.md` (ou similares):
  - `/home/wilson/CEP_BUNDLE_CORE/corpus/source/external_refs/CEP_NA_BOLSA/CEP_NA_BOLSA/outputs/experimentos/fase1_calibracao/exp/20260208/baseline_scan_in_sample_nk/report_baseline_scan_in_sample_nk.md`
  - `/home/wilson/CEP_BUNDLE_CORE/corpus/source/external_refs/CEP_NA_BOLSA/CEP_NA_BOLSA/outputs/fase1_calibracao/exp/20260208/baseline_scan_stability/report_baseline_scan_stability.md`
  - `/home/wilson/CEP_BUNDLE_CORE/corpus/source/external_refs/CEP_NA_BOLSA/CEP_NA_BOLSA/outputs/master_gate_applicability/20260206/report_master_gate_applicability.md`
- Evidencias de regras (constitucionais/governanca):
  - `/home/wilson/CEP_BUNDLE_CORE/corpus/source/external_refs/CEP_NA_BOLSA/CEP_NA_BOLSA/docs/00_constituicao/CEP_NA_BOLSA_CONSTITUICAO_V2_20260204.md`
  - `/home/wilson/CEP_BUNDLE_CORE/corpus/source/external_refs/CEP_NA_BOLSA/CEP_NA_BOLSA/docs/governanca/CEP_NA_BOLSA — Ponto de Situação (snapshot 2026-02-04).md`

### CEP_COMPRA (espelhado)

- Base espelhada: `/home/wilson/CEP_BUNDLE_CORE/corpus/source/external_refs/CEP_COMPRA/CEP_COMPRA/`
- Estrutura observada (docs operacionais):
  - `/home/wilson/CEP_BUNDLE_CORE/corpus/source/external_refs/CEP_COMPRA/CEP_COMPRA/docs/compra_semanal_model_selection.md`
  - `/home/wilson/CEP_BUNDLE_CORE/corpus/source/external_refs/CEP_COMPRA/CEP_COMPRA/docs/protocolo_operacional_modelos.md`
  - `/home/wilson/CEP_BUNDLE_CORE/corpus/source/external_refs/CEP_COMPRA/CEP_COMPRA/docs/task_006_pre_execucao.md`
  - `/home/wilson/CEP_BUNDLE_CORE/corpus/source/external_refs/CEP_COMPRA/CEP_COMPRA/docs/task_008_pos_task.md`
  - `/home/wilson/CEP_BUNDLE_CORE/corpus/source/external_refs/CEP_COMPRA/CEP_COMPRA/docs/task_012_smoke_sell_patch.md`
- Regras de compra e acoplamento com venda diaria:
  - A compra semanal deve respeitar a rotina diaria de venda congelada.
  - Regras anti-concentracao devem vir da constituicao, sem redefinicao local.

## Indexacao do Corpus e Temas Principais

### Tema 1 - SSOT e rastreabilidade forte

- Evidencias no corpus:
  - `corpus/lessons/LESSONS_LEARNED.md` traz regras explicitas de SSOT versionado + manifest + auditoria.
  - Referencias a `manifest/report` como obrigatorios de governanca.

### Tema 2 - Acoes e BDRs

- Confirmacao de arquivos relacionados a Acoes/BDRs:
  - `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/work/external_refs/cep_na_bolsa/ssot_acoes_b3.csv`
  - `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/work/external_refs/cep_na_bolsa/ssot_bdr_b3.csv`
- Confirmacao textual no corpus:
  - `compra_semanal_model_selection.md` cita explicitamente carteira de acoes e BDRs.

### Tema 3 - Politicas de carteira (compra/venda)

- Compra semanal orientada por dados historicos, com validacao walk-forward.
- Venda diaria mantida fixa para isolar efeito do mecanismo de compra.
- Regras de integracao com caixa e restricoes de concentracao ja existentes na constituicao.

## Onde esta cada regra de negocio

### Bolsa (universo, SSOT, governanca)

- Fonte principal: `CEP_NA_BOLSA` espelhado em `corpus/source/external_refs/CEP_NA_BOLSA/CEP_NA_BOLSA/`.
- Regras estruturantes:
  - constituicao (`docs/00_constituicao/*`)
  - governanca (`docs/governanca/*`)
  - reports de validacao (`outputs/**/report*.md`)
- Dados de referencia Acoes/BDRs: `work/external_refs/cep_na_bolsa/ssot_acoes_b3.csv` e `ssot_bdr_b3.csv`.

### Compra (mecanismo semanal)

- Fonte principal: `CEP_COMPRA` espelhado em `corpus/source/external_refs/CEP_COMPRA/CEP_COMPRA/docs/`.
- Regras estruturantes:
  - `compra_semanal_model_selection.md`
  - `protocolo_operacional_modelos.md`
  - `task_*` pre/pos execucao como evidencias operacionais.

### Venda (rotina diaria)

- Regra de acoplamento no corpus de compra: venda diaria e tratada como dependencia congelada.
- Evidencia: `compra_semanal_model_selection.md` (secoes de contexto e validacao).

## Caminhos de Manifestos dos Modulos Antigos

- Manifesto do espelhamento externo:
  - `/home/wilson/CEP_BUNDLE_CORE/corpus/manifests/external_refs_manifest_v1.json`
- Manifestos do corpus versionado:
  - `/home/wilson/CEP_BUNDLE_CORE/corpus/manifests/corpus_manifest_v7.json`
  - `/home/wilson/CEP_BUNDLE_CORE/corpus/manifests/corpus_manifest_v6.json`
- Manifestos canonicos legados (cadeia S001..S008):
  - `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/ssot_audit_v1/manifest.json`
  - `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/reference_series_v1/manifest.json`
  - `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/ssot_reference_refresh_v1/manifest.json`
  - `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/s008_candidates_championship_slope45_v1/manifest.json`
