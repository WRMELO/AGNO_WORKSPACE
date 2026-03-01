# ROADMAP Oficial - Pos T006

## Objetivo

Executar a evolucao do ambiente AGNO com foco em portabilidade, reducao de complexidade operacional e governanca orientada a `Overall PASS`.

---

## STATE 3 — Phase 3: participação sem reabrir deriva

**Objetivo do ciclo**: recuperar **participação no mercado acionário** (exposure / time-in-market) **sem** reabrir deriva/drawdown, com **seleção data-driven** (ablação + regra objetiva), evitando parâmetros arbitrários.

> Governança (original): este ROADMAP concentra **planejamento/backlog**. O `00_Strategy/TASK_REGISTRY.md` mantém apenas tarefas que definiram **estados estáveis** (DONE/COMPLETED/ARCHIVED).

### Fase 3A — Diagnóstico: dependência do período inicial (Start 2023)

**Objetivo**: testar **path-dependence** e reavaliar o comportamento a partir do 1º pregão de 2023 (rebasing R$100k), mantendo comparabilidade visual no estilo T055.

| ID | Task Name | Phase | Status | Key Artifacts / Logs | Timestamp |
|---|---|---|---|---|---|
| T058 | Start-2023 Plotly Comparative (T044/T039/T037 vs CDI/Ibov) | STATE3-P3A (Start 2023) | DONE | `outputs/plots/T058_STATE3_START2023_COMPARATIVE.html` + report + manifest | 2026-02-28 |

### Fase 3B — Solução: participação com constraints (sem “CDI-only”)

**Objetivo**: reprojetar a função-objetivo para impedir que a seleção premie “ficar no CDI”, usando **constraints determinísticas** (piso de participação + guardas de risco) e seleção lexicográfica transparente.

| ID | Task Name | Phase | Status | Key Artifacts / Logs | Timestamp |
|---|---|---|---|---|---|
| T059 | Participation Objective v2 (constraints + deterministic selection) | STATE3-P3B (Objective) | DONE | `selection_rule_v2.json` + `T059_PARTICIPATION_ABLATION_RESULTS_V2.parquet` + `T059_PARTICIPATION_SELECTED_CONFIG_V2.json` + manifest | 2026-02-28 |
| T060 | Phase 3 Comparative Plotly Final (solution vs T044/T039/T037) | STATE3-P3B (Closeout) | DONE | `outputs/plots/T060_STATE3_PHASE3_FINAL_COMPARATIVE.html` + report + manifest | 2026-02-28 |

### Fase 3C — Robustez e promoção (anti-overfit)

**Objetivo**: confirmar robustez por subperíodos e promover somente após PASS do Auditor.

| ID | Task Name | Phase | Status | Key Artifacts / Logs | Timestamp |
|---|---|---|---|---|---|
| T061 | Robustness (subperiods) for participation solution | STATE3-P3C (Robustness) | CANCELLED (MERGED) | Cobertura de robustez será incorporada no novo ciclo de correção de reentrada (armadilha do defensivo) com ablação + evidências por subperíodo. | 2026-02-28 |
| T062 | Governance closeout (Auditor PASS + Registry promotion) | STATE3-P3C (Governance) | DONE | Auditor PASS + promoção no dual-ledger concluídos (T060 registrado em `TASK_REGISTRY.md` e `OPS_LOG.md`). | 2026-02-28 |

### Fase 3D — Correção: “escape” da armadilha do defensivo (reentrada)

**Objetivo**: eliminar estado absorvente de caixa no T044 (defensivo não reverte quando `n_positions=0`), migrando o decisor de regime para sinal de **Mercado** (slope do Ibov) e calibrando **histerese** de entrada/saída via ablação.

| ID | Task Name | Phase | Status | Key Artifacts / Logs | Timestamp |
|---|---|---|---|---|---|
| T063 | Market-slope reentry fix + hysteresis ablation V2 | STATE3-P3D (Reentry) | DONE | `T063_REENTRY_SELECTED_CONFIG_V2.json` + `T063_BASELINE_SUMMARY_REENTRY_FIX_V2.json` + manifest. Audit PASS. | 2026-02-28 |

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
