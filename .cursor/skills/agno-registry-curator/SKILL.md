---
name: agno-registry-curator
description: Aplicar o dual-ledger AGNO para atualizar TASK_REGISTRY e OPS_LOG com consistencia de IDs, status e artefatos. Use quando uma task concluir e houver necessidade de registro documental.
---

# AGNO Registry Curator

## Missao

Manter rastreabilidade documental sem misturar evolucao de produto com manutencao.

## Cadeia de comando

- So atualizar registros apos `OVERALL STATUS: [[ PASS ]]` confirmado pelo Auditor.
- Se o Auditor emitir `FAIL`, nao registrar como concluido; aguardar novo ciclo.
- O OWNER pode solicitar registro manual de tarefas canceladas ou reclassificadas.

## Politica dual-ledger

- `00_Strategy/TASK_REGISTRY.md`: apenas evolucao funcional e milestones (`Txxx`).
- `00_Strategy/OPS_LOG.md`: manutencao, auditoria, hotfix, refatoracao e suporte.

## Regras de escrita

1. Atualizar registros somente com status final claro.
2. Usar sempre a tabela:
`| ID | Task Name | Phase | Status | Key Artifacts / Logs | Timestamp |`
3. Preservar historico: sem apagar linhas antigas para "limpar" estado.

## Gate de conclusao

Somente promover para registro de produto apos evidenciar `OVERALL STATUS: [[ PASS ]]`.
