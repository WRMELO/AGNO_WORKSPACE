# ROADMAP Oficial - Pos T006

## Objetivo

Executar a evolucao do ambiente AGNO com foco em portabilidade, reducao de complexidade operacional e governanca orientada a `Overall PASS`.

## Fase 1 - Estabilizacao Minima

### TASK-007-PREFLIGHT-SECRETS

1. Implementar preflight obrigatorio de segredos antes de qualquer pipeline.
2. Validar `BRAPI_TOKEN` (presenca, nao vazio, nao whitespace) no inicio da execucao.
3. Bloquear execucao de gates dependentes quando o segredo estiver invalido.
4. Publicar evidencias de validacao em artefato unico de status.

### TASK-008-RUNTIME-PADRONIZACAO

1. Definir um unico runtime oficial para o AGNO.
2. Documentar bootstrap do ambiente com comandos reprodutiveis.
3. Remover referencias a runtimes antigos fora do padrao oficial.
4. Atualizar documentacao de execucao para reduzir divergencia entre maquinas.

### TASK-009-PATHS-PORTAVEIS

1. Substituir paths absolutos por variaveis de ambiente e caminhos relativos ao repo.
2. Criar mapa de paths canonicos por contexto (dados, evidencias, saidas).
3. Validar operacao em ambiente limpo sem dependencia de estrutura local legada.
4. Registrar riscos remanescentes de portabilidade.

## Fase 2 - Reducao de Complexidade

### TASK-010-EVIDENCE-CONSOLIDATION

1. Consolidar evidencias em inventario unico priorizado por consumo.
2. Eliminar duplicacoes de manifests e referencias redundantes.
3. Definir padrao minimo de evidencias por estado.
4. Medir ganho de custo operacional apos consolidacao.

### TASK-011-GATE-MATRIX

1. Classificar gates em obrigatorios e opcionais.
2. Definir criterio de bloqueio hard vs soft por gate.
3. Publicar matriz de decisao de aprovacao com exemplos reais.
4. Integrar matriz ao fluxo de registro de tarefas.

### TASK-012-DOC-SANITIZATION

1. Unificar secoes duplicadas em documentos de arquitetura.
2. Separar claramente documento de politica e documento de execucao.
3. Criar checklist de consistencia documental por release.
4. Auditar referencias quebradas e remover texto obsoleto.

## Fase 3 - Governanca e Custo Operacional

### TASK-013-GOVERNANCE-POLICY-ENFORCEMENT

1. Formalizar no processo que apenas `Overall PASS` gera `DONE` no registry.
2. Definir mecanismo de excecao com aprovacao explicita do Owner.
3. Integrar rastreabilidade entre `Task_History`, `TASK_REGISTRY` e `changelog`.
4. Publicar rotina de auditoria periodica da governanca.

### TASK-014-COST-OBSERVABILITY

1. Medir custo por tentativa (tempo, arquivos, bloqueios, retrabalho).
2. Definir indicadores de eficiencia por fase e por task.
3. Criar relatorio recorrente de tendencia de custos.
4. Retroalimentar backlog com base em evidencias de custo.
