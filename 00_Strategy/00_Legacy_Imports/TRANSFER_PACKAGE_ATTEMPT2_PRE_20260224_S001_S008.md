# TRANSFER_PACKAGE_ATTEMPT2_PRE_20260224_S001_S008

- generated_at_utc: `2026-02-24T21:17:13.905403+00:00`
- overall: `PARTIAL_PASS_TOKEN_PENDING`

## Snapshot PRE-2026-02-24
- determination: `git_before_cutoff`
- git_hash: `142c631ac8f0af65acff05b145da9e17161cb044` (2026-02-23T17:59:45-03:00)
- exclude_patterns_applied:
  - `/20260224/`
  - `20260224`
  - `CORP_ACTIONS_V2`
  - `policy_fix_vivt3`
  - `CORPACTION_BRAPI_V1`
  - `ACTIVE_S006_POINTER.json`

## Gates
- S1_RESOLVE_SNAPSHOT_PRE_20260224: `PASS`
- S2_INDEX_ALL_ACTIVE_STATES_S001_S008_IN_ATTEMPT2: `PASS`
- S3_EXTRACT_RULES_AND_EVIDENCE_PER_STATE: `PASS`
- S4_EXTRACT_PROGRESS_LOGIC_S001_TO_S008: `PASS`
- S5_EXTRACT_GOVERNANCE_ROLE_RULES: `PASS`
- S6_BUILD_BRAPl_SECRETS_INSTRUCTIONS_REDACTED: `FAIL`
- S6A_CAPTURE_BRAPl_TOKEN_VALUE_REDACTED: `FAIL`
- S6B_WRITE_TOKEN_FILE_AND_VALIDATE_NONEMPTY: `FAIL`
- S7_COPY_CORPUS_LL_SEED_AND_HASH: `PASS`
- S8_BUILD_ARTIFACT_INVENTORY_AND_HASH_MANIFEST: `PASS`
- S9_WRITE_TRANSFER_PACKAGE_MD_AND_JSON: `PASS`

## Catálogo de regras por estado (S001..S008)
### S001
- definição: Universo promovido e auditoria de cobertura/funnel de ativos.
- inputs efetivos:
- outputs principais:
  - `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/ssot_audit_v1/manifest.json` :: `b28d9734f2eeaeaa3f9bb5dfdb64b4bdf7905f1703fa482039d644d14a78416c`
  - `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/ssot_audit_v1/report.md` :: `79c89c2eff1dd3c46ce7f8559fd2a058899362c1d9f4f26f57df7abe2cbbef57`
- task_specs/runs:
- evidências:
  - `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/ssot_audit_v1/evidence/funnel_counts.csv` :: `60a2c1191454064918ee76d83f598f22483d1522f49a643b1e45dde9622abdaa`
  - `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/ssot_audit_v1/evidence/gap_decomposition_1689_to_597.csv` :: `de6d37db17989d404f1f0485cf9d87e9e62278c3647cf7ffafa13ff98648e821`
- regras extraídas (resumo):

### S002
- definição: Séries de referência canônicas (CDI e SP500).
- inputs efetivos:
- outputs principais:
  - `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/reference_series_v1/manifest.json` :: `af46630f127041536e05aa606a1f6aedc4ac48aff0da6d8105a58e31c80a2609`
  - `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/reference_series_v1/cdi_daily.parquet` :: `bee97e79e0654ed79f8846558ffab359087080bd84e70d502dd219fee4eab5da`
  - `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/reference_series_v1/sp500_daily.parquet` :: `cb8a6979d8e11c7c92c045053d7f159c9e0fd8750f8f2f99bef89ffd96e84785`
- task_specs/runs:
- evidências:
  - `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/reference_series_v1/evidence/discovery_candidates.json` :: `29cb5e29cf86051acbe71f639fa8cc60970d0dbb227cce14bf973ea895e6c51b`
- regras extraídas (resumo):

### S003
- definição: Refresh SSOT referência (Ações/BDRs/BVSP/CDI/SP500).
- inputs efetivos:
- outputs principais:
  - `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/ssot_reference_refresh_v1/manifest.json` :: `0f49dea989d0ba3a4dba3164197b4d11bebfd00d6383bd9e1b71e857740b2fb9`
  - `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/ssot_reference_refresh_v1/ssot_ref_acoes.parquet` :: `40668fb4d58a5ab242dd982a394a41b51dae95892f11706dc768521869930b1f`
  - `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/ssot_reference_refresh_v1/ssot_ref_bdrs.parquet` :: `d0c3415574560d5d9ebb22767f7775c378a52c50f1169a076652458c1078cfeb`
- task_specs/runs:
- evidências:
  - `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/ssot_reference_refresh_v1/evidence/discovery_inputs.json` :: `469ba10b9d4c1ba994770a5b6936edb3aa76f263ca2bccb1a0fc9a0e65be9d06`
  - `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/ssot_reference_refresh_v1/evidence/acoes_bdrs_alignment_counts.csv` :: `585194cfdaa5ad6fd391d7a77b9aa680a1ef69b84ed3d1b123231ea4e73c72dd`
- regras extraídas (resumo):

### S004
- definição: Guideline SPC/CEP master para política operacional.
- inputs efetivos:
- outputs principais:
  - `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/spc_cep_guideline_v1/manifest.json` :: `29c6ee1acf081dd8ee509e29473ad46dddf4de4622c23cb800a11b471b0e5be5`
  - `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/spc_cep_guideline_v1/guideline_spc_cep_master_burners_v1.md` :: `696435337a3614a84b7c1052e01960804ece7e98975bd76defc6900de7cb8e35`
- task_specs/runs:
- evidências:
  - `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/spc_cep_guideline_v1/evidence/snapshot_unchanged_check.txt` :: `a95fad48f0e3f401dadcdd246f17125ec09fa5921b5210784d8a3ae367efa191`
- regras extraídas (resumo):

### S005
- definição: SSOT tickers aprovados 448 com auditoria histórica.
- inputs efetivos:
- outputs principais:
  - `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/ssot_approved_tickers_448_k60_n3_window_20251030_w62_with_history_audit_v2/manifest.json` :: `85cb49e0670ef2f53cf4cedfc8bb9ea8de6f020d67a71f348d32c9d6fac85a48`
  - `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/ssot_approved_tickers_448_k60_n3_window_20251030_w62_with_history_audit_v2/ssot_approved_tickers.parquet` :: `8da5be2ceea79c877fddbbec6529c504c58dd09b48c7d62120d7ec3d8f764f55`
- task_specs/runs:
- evidências:
  - `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/ssot_approved_tickers_448_k60_n3_window_20251030_w62_with_history_audit_v2/evidence/history_audit_per_ticker.csv` :: `b9d5fe6b8e4c57b7fe2766dabf550ad4905f01bb6344064e00aa06a4b14553b0`
- regras extraídas (resumo):
  - from `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/ssot_approved_tickers_448_k60_n3_window_20251030_w62_with_history_audit_v2/manifest.json` key `required_files`
  - from `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/ssot_approved_tickers_448_k60_n3_window_20251030_w62_with_history_audit_v2/manifest.json` key `gates`

### S006
- definição: Base operacional canônica completa (448) com excess CDI (pré-corp-actions-v2).
- inputs efetivos:
  - `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/ssot_approved_tickers_448_k60_n3_window_20251030_w62_with_history_audit_v2/ssot_approved_tickers.parquet` (inferred_from_state_chain)
  - `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/ssot_reference_refresh_v1/ssot_ref_acoes.parquet` (inferred_from_state_chain)
  - `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/ssot_reference_refresh_v1/ssot_ref_bdrs.parquet` (inferred_from_state_chain)
  - `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/ssot_reference_refresh_v1/cdi_daily.parquet` (inferred_from_state_chain)
- outputs principais:
  - `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/base_operacional_canonica_completa_v2_448_cdi_excess_v1/manifest.json` :: `db7985b6041669ae336a7369676b3f48f307e34f8f2e5de3dd54bdacc31d52a2`
  - `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/base_operacional_canonica_completa_v2_448_cdi_excess_v1/panel/base_operacional_canonica.parquet` :: `49a3987f8c2811b97facde234076f3ac7cc333f66d58cae9325257fbc7a20fb8`
- task_specs/runs:
  - `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/work/task_specs/TASK_CEP_BUNDLE_CORE_ATT2_BUILD_BASE_OPERACIONAL_CANONICA_COMPLETA_V2_448_CDI_EXCESS_V1.json` :: `cb66374d450c2e8a945446ac43a9a5191c73c98f5ee511cac14490499545295a`
- evidências:
  - `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/base_operacional_canonica_completa_v2_448_cdi_excess_v1/evidence/domain_checks_summary.csv` :: `68bd77e056e4f249b151f6b4a45da11a7f3634ac2e5710297078ea1abed184b5`
  - `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/base_operacional_canonica_completa_v2_448_cdi_excess_v1/metadata/dataset_metadata.json` :: `1f89394fa3bfb344cb32a2050a2fba613f7a81029c04fa8fe9b5ae4d4c08e143`
- regras extraídas (resumo):
  - from `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/base_operacional_canonica_completa_v2_448_cdi_excess_v1/manifest.json` key `required_files`
  - from `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/base_operacional_canonica_completa_v2_448_cdi_excess_v1/manifest.json` key `gates`
  - from `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/work/task_specs/TASK_CEP_BUNDLE_CORE_ATT2_BUILD_BASE_OPERACIONAL_CANONICA_COMPLETA_V2_448_CDI_EXCESS_V1.json` key `task_spec_excerpt`

### S007
- definição: Ruleflags globais ativos pré-2026-02-24.
- inputs efetivos:
  - `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/base_operacional_canonica_completa_v2_448_cdi_excess_v1/panel/base_operacional_canonica.parquet` (explicit_checklist_chain)
- outputs principais:
  - `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/state/s007_ruleflags_global/20260223/manifest.json` :: `db973ff4fc4ae8a25e2d05f5e599ec69b435028cec378c2d14dfc5625877d755`
  - `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/state/s007_ruleflags_global/20260223/s007_ruleflags.parquet` :: `4822009b46f1334c97fa1a1f09fa59e8f4af08f08c29d777273eae1346ad9b61`
- task_specs/runs:
  - `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/work/task_specs/TASK_CEP_BUNDLE_CORE_ATT2_BURNERS_RANKING_OEE_LP_CP_DAILY_V2_WARMUP_BUFFER.json` :: `45446fc093f9db5cf882304504364f5adb7b3cdde133709baa7bd3cea77d8fb6`
- evidências:
  - `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/state/s007_ruleflags_global/20260223/evidence/domain_counts.txt` :: `2dbc20f813eec406383feaba59618d3b8c812a7a9445a2304a79c2b9d1075d10`
  - `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/governanca/audits/20260223/s007_ruleflags_fulldomain_equivalence/report.md` :: `953a25ba3c31f2debcd3738fe80598167fa8119c9dd9197818794ffd1c205cd0`
- regras extraídas (resumo):
  - from `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/state/s007_ruleflags_global/20260223/manifest.json` key `required_files`
  - from `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/work/task_specs/TASK_CEP_BUNDLE_CORE_ATT2_BURNERS_RANKING_OEE_LP_CP_DAILY_V2_WARMUP_BUFFER.json` key `task_spec_excerpt`

### S008
- definição: Candidatos diários por campeonato F1 + slope_45 (filtro slope_60>0).
- inputs efetivos:
  - `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/state/s007_ruleflags_global/20260223/s007_ruleflags.parquet` (explicit_checklist_chain_pre_20260224)
- outputs principais:
  - `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/s008_candidates_championship_slope45_v1/manifest.json` :: `49de83c5febb5a4b18a561c582e01a0faca3ace65afc37adb6ddf01668a22655`
  - `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/s008_candidates_championship_slope45_v1/candidates/candidates_daily.parquet` :: `744406e634b2d01bd0aae9ba97a36f5717168c99351e2b2b1c1dba00d9575cb6`
- task_specs/runs:
  - `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/work/task_specs/TASK_CEP_BUNDLE_CORE_ATT2_S008_CANDIDATES_CHAMPIONSHIP_SLOPE45_V1.json` :: `bd44bea2d9bdf23aa6c3bd7cad56fdbb5a29ded650fbcaf4a5a8f41270a9e8a5`
- evidências:
  - `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/s008_candidates_championship_slope45_v1/evidence/sample_first_selection_day.csv` :: `146242a17ebb2d05714b052b370831711c33669ae9377f7610699270a0ee24b5`
  - `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/s008_candidates_championship_slope45_v1/metadata/dataset_metadata.json` :: `ee25b064986e1c71326d0ddfb3bbc361ec5b9b8288c5a62d66be8458ed9a76bd`
- regras extraídas (resumo):
  - from `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/s008_candidates_championship_slope45_v1/manifest.json` key `required_files`
  - from `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/s008_candidates_championship_slope45_v1/manifest.json` key `gates`
  - from `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/work/task_specs/TASK_CEP_BUNDLE_CORE_ATT2_S008_CANDIDATES_CHAMPIONSHIP_SLOPE45_V1.json` key `task_spec_excerpt`

## Lógica de avanço S001 -> S008
- grafo: `S001 -> S002 -> S003 -> S004 -> S005 -> S006 -> S007 -> S008`
- S001 -> S002: Universo/gaps auditados para cobertura de referência.
- S002 -> S003: Séries referência validadas e refresh SSOT completo.
- S003 -> S004: Guideline SPC/CEP sobre dados normalizados.
- S004 -> S005: Seleção de universo aprovado com auditoria histórica.
- S005 -> S006: Construção da base operacional canônica 448 + excess CDI.
- S006 -> S007: Derivação de ruleflags globais diário ticker-data.
- S007 -> S008: Seleção de candidatos por slope/campeonato.
- decisões congeladas pré-2026-02-24:
  - S007 ativo pré-snapshot: outputs/state/s007_ruleflags_global/20260223/s007_ruleflags.parquet
  - S006 referência pré-snapshot: outputs/base_operacional_canonica_completa_v2_448_cdi_excess_v1/panel/base_operacional_canonica.parquet
  - S008 pré-snapshot: outputs/s008_candidates_championship_slope45_v1/candidates/candidates_daily.parquet

## Regras de relacionamento Owner/CTO/Agente/Agno
- Owner define objetivo e valida gates com evidência material.
- CTO deve entregar O QUE/POR QUE/COMO/RESULTADO ESPERADO em linguagem natural antes do JSON para Agente.
- Agente executa com disciplina de gates, manifests e hashes.
- Padrão combinado: texto para Owner + JSON para Agente.
- Parquet-first para tabulares; CSV apenas para leitura humana quando necessário.
- evidência principal: `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/work/checklists/checklist_orientacoes_owner.md`

## BRAPI_TOKEN
- token NÃO encontrado automaticamente (env/dotenv/fallback textual).
- caminho esperado no pacote: `secrets/BRAPI_TOKEN.txt` (pendente).
- para concluir S6A/S6B, informar path canônico do BRAPI_TOKEN no ambiente atual.

## Índice de artefatos
- artifact_inventory: `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/transfer_packages/20260224/ATTEMPT2_PRE_20260224_S001_S008/artifact_inventory.parquet`
- manifest_sha256: `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/transfer_packages/20260224/ATTEMPT2_PRE_20260224_S001_S008/manifest_sha256.json`
- evidence_paths_index: `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/transfer_packages/20260224/ATTEMPT2_PRE_20260224_S001_S008/evidence/evidence_paths_index.json`
- corpus_seed_manifest: `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/transfer_packages/20260224/ATTEMPT2_PRE_20260224_S001_S008/corpus_seed_manifest.json`

## Corpus/LL seed
- origem: `/home/wilson/CEP_BUNDLE_CORE/corpus`
- cópia física: `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/transfer_packages/20260224/ATTEMPT2_PRE_20260224_S001_S008/corpus_seed`
- política: seed somente leitura.

## Ambiente e execução
- python usado: `/home/wilson/PortfolioZero/.venv/bin/python`
- entrypoint: `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/work/tasks`
- entrypoint: `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/work/experimentos_on_flight/EXP_001_S008_TOP10S45_STRESSSELL_2019_20210630_V1/run_experiment.py`
- entrypoint: `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/work/experimentos_on_flight/EXP_002_SELL_POLICY_GATE_CEP_RL_V1/run_experiment.py`
- agno runner: `nao_encontrado_no_repo_root`

## Known issues pré-2026-02-24
- Spike abril/2025 (VIVT3 corporate action) observado antes da correção canônica v2 de 2026-02-24.
- evidência: `/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220/outputs/experimentos/on_flight/20260223/EXP_001_S008_TOP10S45_STRESSSELL_2019_20210630_V1/report.md`
