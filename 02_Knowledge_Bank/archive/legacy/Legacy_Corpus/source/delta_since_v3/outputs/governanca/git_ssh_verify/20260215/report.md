# Report - Verify GitHub SSH Auth Post Register

- task_id: `TASK_CEP_BUNDLE_CORE_F0_001G_VERIFY_GITHUB_SSH_AUTH_POST_REGISTER_V1`
- generated_at_utc: `2026-02-15T15:07:48Z`
- repo_root: `[LEGACY_ROOT]`
- github_host: `github.com`
- sync_task_rerun_reference: `TASK_CEP_BUNDLE_CORE_F0_001E_GIT_SYNC_REMOTE_CREDENTIALS_V1`

## Resultado

OVERALL: **PASS**

## Verificacao SSH

- Comando: `ssh -T git@github.com`
- Resultado: **PASS**
- Mensagem: `Hi WRMELO! You've successfully authenticated, but GitHub does not provide shell access.`
- Conclusao objetiva: nao houve `Permission denied (publickey)`.

## Reexecucao do sync Git (equivalente ao F0_001E)

- `git ls-remote --heads origin`: **PASS**
- `git fetch origin`: **PASS**
- `git branch --set-upstream-to=origin/main main`: **PASS**
- `git pull --ff-only`: **PASS** (`Already up to date.`)
- `git push --dry-run origin main`: **PASS**
- `git push origin main`: **PASS** (`[new branch] main -> main`)
- `git status --porcelain` final: **PASS** (vazio)

## Gates

- `S1_GATE_ALLOWLIST`: PASS
- `S2_VERIFY_SSH_AUTH_OK`: PASS
- `S3_VERIFY_SYNC_COMPLETED`: PASS
- `S4_WRITE_MANIFEST_HASHES`: PASS

## Evidencias principais

- `outputs/governanca/git_ssh_verify/20260215/evidence/ssh_T_test_after_register.txt`
- `outputs/governanca/git_ssh_verify/20260215/evidence/remote_v.txt`
- `outputs/governanca/git_ssh_verify/20260215/evidence/ls_remote.txt`
- `outputs/governanca/git_ssh_verify/20260215/evidence/fetch.txt`
- `outputs/governanca/git_ssh_verify/20260215/evidence/set_upstream.txt`
- `outputs/governanca/git_ssh_verify/20260215/evidence/pull_ff_only.txt`
- `outputs/governanca/git_ssh_verify/20260215/evidence/push_dry_run.txt`
- `outputs/governanca/git_ssh_verify/20260215/evidence/push.txt`
