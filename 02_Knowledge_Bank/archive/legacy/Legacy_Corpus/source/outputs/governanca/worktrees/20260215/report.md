# Report - Worktrees Layout CEP_BUNDLE_CORE

- task_id: `TASK_CEP_BUNDLE_CORE_F0_001C_CREATE_WORKTREES_LAYOUT_V1`
- generated_at_utc: `2026-02-15T14:29:45Z`
- repo_root: `[LEGACY_ROOT]`
- worktrees_root: `/home/wilson/_wt/CEP_BUNDLE_CORE`
- head_sha: `4c84a020fa947401f26f5fd98c551e5f4ae7d59c`
- active_branch: `master`

## Resultado

Estrutura padronizada de worktrees criada com sucesso para as fases `bootstrap`, `ssot` e `experiments`, mantendo `master` limpo no `repo_root`.

## Layout de worktrees

- `[LEGACY_ROOT]` -> `master`
- `/home/wilson/_wt/CEP_BUNDLE_CORE/bootstrap` -> `wt/bootstrap`
- `/home/wilson/_wt/CEP_BUNDLE_CORE/ssot` -> `wt/ssot`
- `/home/wilson/_wt/CEP_BUNDLE_CORE/experiments` -> `wt/experiments`

## Branches dedicados

- `wt/bootstrap`
- `wt/ssot`
- `wt/experiments`

## Evidencias capturadas

- `git worktree list` salvo em `outputs/governanca/worktrees/20260215/evidence/worktree_list.txt`
- `git branch --all` salvo em `outputs/governanca/worktrees/20260215/evidence/branch_list.txt`
- `git status --porcelain` (repo_root) salvo em `outputs/governanca/worktrees/20260215/evidence/status_repo_root.txt`
- validacao do Python oficial em `outputs/governanca/worktrees/20260215/evidence/python_official.txt`

## Instrucao operacional

Abrir no Cursor o worktree da fase ativa:

- Fase bootstrap: `/home/wilson/_wt/CEP_BUNDLE_CORE/bootstrap`
- Fase SSOT: `/home/wilson/_wt/CEP_BUNDLE_CORE/ssot`
- Fase experiments: `/home/wilson/_wt/CEP_BUNDLE_CORE/experiments`

Manter `[LEGACY_ROOT]` como raiz de governanca (master limpo).

## Gates

- `S1_GATE_ALLOWLIST`: PASS
- `S2_VERIFY_GIT_INITIALIZED`: PASS
- `S3_GATE_VENV_OFFICIAL_PYTHON`: PASS
- `S4_VERIFY_BRANCHES_EXIST`: PASS
- `S5_VERIFY_WORKTREES_CREATED`: PASS
- `S6_VERIFY_ROOT_WORKTREE_CLEAN`: PASS
- `S7_WRITE_MANIFEST_HASHES`: PASS

## Criterios objetivos de sucesso

- `git worktree list` mostra 3 worktrees adicionais sob `/home/wilson/_wt/CEP_BUNDLE_CORE/`: PASS
- branches `wt/bootstrap`, `wt/ssot`, `wt/experiments` existem: PASS
- `git status --porcelain` no `repo_root` vazio: PASS
- `report` e `manifest` gerados: PASS
- OVERALL: **PASS**
