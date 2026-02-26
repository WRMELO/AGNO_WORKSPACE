# Legacy Diagnostic - T005

- task_id: `TASK-005-DEEP-DISCOVERY`
- generated_at_utc: `2026-02-25T18:37:08+00:00`
- fontes lidas integralmente:
  - `00_Strategy/00_Legacy_Imports/TRANSFER_PACKAGE_ATTEMPT2_PRE_20260224_S001_S008.json.processed`
  - `00_Strategy/00_Legacy_Imports/TRANSFER_PACKAGE_ATTEMPT2_PRE_20260224_S001_S008.md.processed`
  - `01_Architecture/System_Context.md`

## Historico de Falhas

### Falhas tecnicas recorrentes

1. **Gestao de segredo incompleta (bloqueio de entrega)**  
   - Evidencia: `overall = PARTIAL_PASS_TOKEN_PENDING` e falhas em `S6`, `S6A`, `S6B`.  
   - Causa provavel: dependencia de `BRAPI_TOKEN` sem trilha padrao de provisionamento validada no runtime final.

2. **Acoplamento forte a ambiente local legado**  
   - Evidencia: caminhos absolutos extensos em `/home/wilson/CEP_BUNDLE_CORE/...` e runtime antigo em `/home/wilson/PortfolioZero/.venv/bin/python`.  
   - Custo: baixa portabilidade, alto tempo de replicacao e risco de erro por path inexistente.

3. **Complexidade operacional alta por excesso de artefatos e gates**  
   - Evidencia: cadeia `S001..S008`, multiplos manifests, hashes, evidencias, task specs e variacoes de output roots.  
   - Custo: manutencao e verificacao manuais caras; alta chance de drift documental.

4. **Dependencia de snapshot congelado e exclusoes manuais**  
   - Evidencia: politica `PRE_2026_02_24` + `exclude_patterns_applied`.  
   - Risco: congelamento protege consistencia historica, mas pode esconder divergencias em dados recentes.

5. **Sinal de tentativa anterior abandonada por custo de estabilizacao**  
   - Evidencia indireta: pacote finaliza com `PARTIAL_PASS` apesar de `8 PASS`, por dependencia externa critica nao resolvida (token).

### O que NAO fazer (derivado do legado)

- Nao iniciar pipeline sem validar segredo obrigatorio (`BRAPI_TOKEN`) antes dos gates dependentes.
- Nao codificar paths absolutos de maquina como contrato principal de execucao.
- Nao misturar contexto de negocio e instrucoes de execucao sem separar "politica" de "operacao".
- Nao promover tarefa para "concluida" com status parcial mascarado por alto numero de `PASS`.
- Nao crescer o numero de artefatos de evidencia sem um indice operacional minimo e objetivo de consumo.

### Cruzamento com `System_Context.md` (contradicoes e redundancias)

#### Contradicoes

- O `System_Context.md` ainda aponta `Source MD/JSON` sem sufixo `.processed`, enquanto os arquivos foram marcados como processados no fluxo T003.
- Em `Execution Record`, o texto cita ciclo `IN_PROGRESS -> DONE`, mas o `TASK_REGISTRY.md` atual foi normalizado para registrar apenas `DONE` por politica de governanca.

#### Redundancias

- Regras de governanca Owner/CTO/Agente aparecem repetidas em secoes diferentes (`Governance Notes` e `Legacy Integration History`).
- Informacoes de gates e contexto tecnico foram duplicadas entre o bloco principal legado e a secao de integracao historica.

## Inventario de Regras Ativas

### Regras de negocio e governanca identificadas

- Progressao canonica obrigatoria: `S001 -> S002 -> S003 -> S004 -> S005 -> S006 -> S007 -> S008`.
- Criterio de integridade por gates e evidencias materiais.
- Politica de snapshot congelado (`PRE_2026_02_24`) com exclusoes explicitas.
- Regra de dados: `Parquet-first`; `CSV` apenas para leitura humana.
- Politica de seed: `corpus_seed` em modo somente leitura.
- Segredo obrigatorio: `BRAPI_TOKEN` para completar trilha S6/S6A/S6B.
- Governanca de papeis:
  - Owner valida objetivo e gates com evidencia.
  - CTO entrega O QUE/POR QUE/COMO/RESULTADO em linguagem natural antes de JSON.
  - Agente executa com disciplina de manifests/hashes/gates.
  - Padrao operacional combinado: texto para Owner + JSON para Agente.

### Regras tecnicas/operacionais explicitas

- Materializacao por convencoes de diretorio:
  - `outputs/<estado>_vN`
  - `outputs/state/s007_ruleflags_global/YYYYMMDD`
  - `outputs/experimentos/on_flight/YYYYMMDD`
- Orquestracao em `work/task_specs` e `planning/task_specs`.
- Hashes (`sha256`) como prova de rastreabilidade de artefatos.

## Proposta de Plano de Trabalho

### Fase 1 - Estabilizacao minima (curto prazo)

- Criar gate de preflight de secrets antes de qualquer processamento pesado.
- Padronizar runtime local oficial do AGNO (um unico ambiente virtual documentado).
- Substituir caminhos absolutos por variaveis de ambiente e caminhos relativos ao repo.

### Fase 2 - Reducao de complexidade (medio prazo)

- Consolidar artefatos de evidencia em um inventario unico com prioridade de consumo.
- Definir matriz minima de gates obrigatorios vs opcionais.
- Unificar seções duplicadas no `System_Context.md` para evitar drift.

### Fase 3 - Governanca e custo operacional (continuo)

- Separar claramente documento de politica (governanca) de documento de execucao (operacao).
- Adotar checklists curtos por estado com criterio binario de aceite.
- Medir custo por tentativa (tempo, arquivos gerados, bloqueios) para guiar simplificacao.
