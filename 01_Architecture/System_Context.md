# System Context - AGNO Project

## Legacy Source Package

- Source MD: `00_Strategy/00_Legacy_Imports/TRANSFER_PACKAGE_ATTEMPT2_PRE_20260224_S001_S008.md`
- Source JSON: `00_Strategy/00_Legacy_Imports/TRANSFER_PACKAGE_ATTEMPT2_PRE_20260224_S001_S008.json`
- generated_at_utc: `2026-02-24T21:17:13.905403+00:00`
- overall: `PARTIAL_PASS_TOKEN_PENDING`

## Business Goals (from legacy MD)

1. Preservar e transferir estado operacional confirmado de `S001` ate `S008` sem regressao semantica.
2. Manter rastreabilidade completa por gates, manifests, evidencias e hashes.
3. Consolidar a cadeia de progresso `S001 -> S002 -> S003 -> S004 -> S005 -> S006 -> S007 -> S008`.
4. Sustentar governanca por papeis (Owner/CTO/Agente) com disciplina de execucao.
5. Viabilizar continuidade operacional sobre artefatos canonicos pre-`2026-02-24`.

## Constraints (from legacy MD)

- Snapshot policy congelada em `PRE_2026_02_24` por `git_before_cutoff`.
- `git_hash` de referencia: `142c631ac8f0af65acff05b145da9e17161cb044` (`2026-02-23T17:59:45-03:00`).
- Excludes aplicados: `/20260224/`, `20260224`, `CORP_ACTIONS_V2`, `policy_fix_vivt3`, `CORPACTION_BRAPI_V1`, `ACTIVE_S006_POINTER.json`.
- Regra de dados: `Parquet-first`; `CSV` apenas para leitura humana quando necessario.
- Estado de segredo: `BRAPI_TOKEN` ausente no ambiente legado (S6/S6A/S6B em `FAIL`).
- Politica de seed: `corpus_seed` como somente leitura.

## Narrative Context

O pacote legado registra uma linha de producao orientada a estados, com promocao progressiva de artefatos auditaveis entre `S001` e `S008`. O foco operacional e manter outputs canonicos e equivalencia de dominio com governanca formal (gates, manifests, hashes e evidencias). O estado final ingerido referencia `S008` como selecao diaria de candidatos por campeonato F1 com `slope_45` e filtro `slope_60>0`, sustentado por ativos de `S007` e `S006`.

## Technical Specs (strict from legacy JSON)

### Tech Stack

- Python runtime utilizado: `/home/wilson/PortfolioZero/.venv/bin/python`
- Data formats: `parquet`, `json`, `md`, `csv`
- Orquestracao por task specs em: `work/task_specs` e `planning/task_specs`
- Convencoes de materializacao:
  - `outputs/<estado>_vN`
  - `outputs/state/s007_ruleflags_global/YYYYMMDD`
  - `outputs/experimentos/on_flight/YYYYMMDD`

### Gate Status (strict)

- `S1_RESOLVE_SNAPSHOT_PRE_20260224`: `PASS`
- `S2_INDEX_ALL_ACTIVE_STATES_S001_S008_IN_ATTEMPT2`: `PASS`
- `S3_EXTRACT_RULES_AND_EVIDENCE_PER_STATE`: `PASS`
- `S4_EXTRACT_PROGRESS_LOGIC_S001_TO_S008`: `PASS`
- `S5_EXTRACT_GOVERNANCE_ROLE_RULES`: `PASS`
- `S6_BUILD_BRAPl_SECRETS_INSTRUCTIONS_REDACTED`: `FAIL`
- `S6A_CAPTURE_BRAPl_TOKEN_VALUE_REDACTED`: `FAIL`
- `S6B_WRITE_TOKEN_FILE_AND_VALIDATE_NONEMPTY`: `FAIL`
- `S7_COPY_CORPUS_LL_SEED_AND_HASH`: `PASS`
- `S8_BUILD_ARTIFACT_INVENTORY_AND_HASH_MANIFEST`: `PASS`
- `S9_WRITE_TRANSFER_PACKAGE_MD_AND_JSON`: `PASS`

### Canonical File Paths (strict)

- `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/ssot_audit_v1/manifest.json`
- `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/reference_series_v1/cdi_daily.parquet`
- `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/reference_series_v1/sp500_daily.parquet`
- `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/ssot_reference_refresh_v1/ssot_ref_acoes.parquet`
- `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/ssot_reference_refresh_v1/ssot_ref_bdrs.parquet`
- `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/spc_cep_guideline_v1/guideline_spc_cep_master_burners_v1.md`
- `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/ssot_approved_tickers_448_k60_n3_window_20251030_w62_with_history_audit_v2/ssot_approved_tickers.parquet`
- `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/base_operacional_canonica_completa_v2_448_cdi_excess_v1/panel/base_operacional_canonica.parquet`
- `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/state/s007_ruleflags_global/20260223/s007_ruleflags.parquet`
- `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/s008_candidates_championship_slope45_v1/candidates/candidates_daily.parquet`
- `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/transfer_packages/20260224/ATTEMPT2_PRE_20260224_S001_S008/artifact_inventory.parquet`
- `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/transfer_packages/20260224/ATTEMPT2_PRE_20260224_S001_S008/manifest_sha256.json`
- `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/transfer_packages/20260224/ATTEMPT2_PRE_20260224_S001_S008/corpus_seed_manifest.json`
- `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/work/checklists/checklist_orientacoes_owner.md`
- `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/work/task_specs/TASK_CEP_BUNDLE_CORE_ATT2_S008_CANDIDATES_CHAMPIONSHIP_SLOPE45_V1.json`

### Entrypoints (strict)

- `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/work/tasks`
- `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/work/experimentos_on_flight/EXP_001_S008_TOP10S45_STRESSSELL_2019_20210630_V1/run_experiment.py`
- `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/work/experimentos_on_flight/EXP_002_SELL_POLICY_GATE_CEP_RL_V1/run_experiment.py`

## Governance Notes

- Owner define objetivo e valida gates com evidencia material.
- CTO entrega O QUE/POR QUE/COMO/RESULTADO ESPERADO em linguagem natural antes do JSON.
- Agente executa com disciplina de gates, manifests e hashes.
- Padrao combinado: texto para Owner + JSON para Agente.

## Execution Record

- Protocolo de governanca T001 reexecutado a partir de `00_Strategy/Task_History/T001_Legacy_Bootstrap.json`.
- Registry atualizado com ciclo completo: `IN_PROGRESS` -> `DONE`.
