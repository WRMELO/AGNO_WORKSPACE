# Report - Git SSH Credentials Diagnose and Fix

- task_id: `TASK_CEP_BUNDLE_CORE_F0_001F_GIT_SSH_CREDENTIALS_DIAG_AND_FIX_V1`
- generated_at_utc: `2026-02-15T14:56:44Z`
- repo_root: `/home/wilson/CEP_BUNDLE_CORE`
- github_host: `github.com`
- expected_remote: `git@github.com:WRMELO/CEP_BUNDLE_CORE.git`

## Causa raiz

A autenticacao SSH falhou por **chave nao registrada no GitHub** para a conta/entidade que acessa o repositorio.  
Mesmo apos configurar chave local + `ssh-agent` + `~/.ssh/config`, o teste retornou:

- `git@github.com: Permission denied (publickey).`

## Estado antes/depois

- Antes:
  - `~/.ssh` sem `id_ed25519`
  - `ssh-agent` ativo, sem identidades
- Depois:
  - chave `~/.ssh/id_ed25519` criada (ed25519, comment `CEP_BUNDLE_CORE_AGENT`)
  - identidade carregada no `ssh-agent`
  - `~/.ssh/config` com `Host github.com`, `IdentityFile ~/.ssh/id_ed25519`, `IdentitiesOnly yes`

## Fingerprint detectada

- `SHA256:X146aZGYEHeSLsbco7gOtimFOIYzsrcQgS8I6MtTyjE` (ED25519)

## O que registrar no GitHub

Registrar a chave publica em:

- arquivo local: `outputs/governanca/git_ssh_fix/20260215/evidence/public_key_to_register.pub`
- destino recomendado: **GitHub Account SSH keys** (Settings -> SSH and GPG keys -> New SSH key)
- alternativa: **Deploy key** no repositorio `WRMELO/CEP_BUNDLE_CORE` (com write, se necessitar push do agente)

## Criterio objetivo de sucesso

- Sucesso quando `ssh -T git@github.com` **nao** retorna `Permission denied (publickey)`.

## Resultado do teste atual

- `ssh -T git@github.com`: **FAIL**
- mensagem exata: `git@github.com: Permission denied (publickey).`

## Evidencias

- `outputs/governanca/git_ssh_fix/20260215/evidence/remote_v.txt`
- `outputs/governanca/git_ssh_fix/20260215/evidence/ssh_dir_list.txt`
- `outputs/governanca/git_ssh_fix/20260215/evidence/ssh_key_fingerprints.txt`
- `outputs/governanca/git_ssh_fix/20260215/evidence/ssh_agent_identities.txt`
- `outputs/governanca/git_ssh_fix/20260215/evidence/ssh_config_effective.txt`
- `outputs/governanca/git_ssh_fix/20260215/evidence/ssh_T_test.txt`
- `outputs/governanca/git_ssh_fix/20260215/evidence/public_key_to_register.pub`
