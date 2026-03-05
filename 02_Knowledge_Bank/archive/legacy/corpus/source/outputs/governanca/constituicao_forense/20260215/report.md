# Report - Localizacao e Extracao Forense da Constituicao

- task_id: `TASK_CEP_BUNDLE_CORE_F0_002A_LOCATE_AND_EXTRACT_CONSTITUICAO_REPORT_V1`
- generated_at_utc: `2026-02-15T18:07:44Z`
- bootstrap_git_head: `7e883fb3fcae95fc93760b525f132aab02490db4`
- bootstrap_git_branch: `wt/bootstrap`

## (a) Localizacao do report alvo (path real)

- report localizado em:
  - `/home/wilson/_wt/CEP_BUNDLE_CORE/bootstrap/outputs/governanca/constituicao/20260215/report.md`
- manifest localizado em:
  - `/home/wilson/_wt/CEP_BUNDLE_CORE/bootstrap/outputs/governanca/constituicao/20260215/manifest.json`

## (b) Hashes

- Hashes completos registrados em:
  - `outputs/governanca/constituicao_forense/20260215/evidence/hashes.txt`

## (c) Resumo dos trechos extraidos da Constituicao atual

- Fonte: `wt/bootstrap/docs/CONSTITUICAO.md`.
- Extracao detalhada em:
  - `outputs/governanca/constituicao_forense/20260215/extract_constituicao_trechos.md`
- Pontos principais:
  - Venv oficial PortfolioZero: presente.
  - Parquet como formato padrao: presente.
  - Politica de periodos: presente (`D/W/M`), sem termos literais `development/holdout`.
  - Politica de worktrees: presente.
  - Variante 2: presente e normativa.
  - Politica formal de emendas: presente e obrigatoria.

## (d) Mapa de aderencia com legados

- Comparativo consolidado:
  - `outputs/governanca/constituicao_forense/20260215/legacy_alignment_map.md`
- Sintese:
  - convergencia em Parquet/CSV e emendas;
  - convergencia parcial em venv oficial;
  - lacunas em `worktree` explicito, `Variante 2` explicita e `development`.

## (e) Evidencias geradas

- `outputs/governanca/constituicao_forense/20260215/evidence/found_paths.txt`
- `outputs/governanca/constituicao_forense/20260215/evidence/hashes.txt`
- `outputs/governanca/constituicao_forense/20260215/extract_constituicao_trechos.md`
- `outputs/governanca/constituicao_forense/20260215/legacy_alignment_map.md`

## Gates

- `S1_GATE_ALLOWLIST`: PASS
- `S2_LOCATE_TARGET_REPORT`: PASS
- `S3_VERIFY_TARGET_REPORT_NONEMPTY`: PASS
- `S4_EXTRACT_CONSTITUICAO_TOPICS`: PASS
- `S5_SEARCH_LEGACY_REPOS_TOPICS`: PASS
- `S6_VERIFY_EVIDENCE_AND_HASHES`: PASS
- `S7_WRITE_MANIFEST_HASHES`: PASS

## Criterios de aceite

- OVERALL: **PASS**
