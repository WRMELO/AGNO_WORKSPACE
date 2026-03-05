# Lessons Learned — Processo

> Consolidação temática de todas as lições sobre workflow, evidência visual, ciclo de execução e cadeia de comando.
> Fonte: phases 2, 3, 4, 5, 8, 9, 10. Originais em `archive/by_phase/`.

---

## 1. Plotly como evidência operacional obrigatória

**Regra**: dashboards Plotly interativos são evidência mandatória para leitura de comportamento temporal. Reports de visualização devem incluir métricas quantitativas, não apenas referências textuais.

- Phase 2 (LL-PH2-007). Princípio fundacional.
- Phase 3 (LL-PH3-009). Veredicto visual em Plotly mandatório para consolidar conclusões.
- Phase 4 (LL-PH4-002, LL-PH4-011). Plotly embutido no script de ablação reduziu ciclo de feedback e eliminou tasks intermediárias.
- Phase 5 (LL-PH5-004). Diagnóstico de ablação embutido no Plotly (feasibility, margens) acelerou decisão do Owner.
- Phase 8 (LL-PH8-016). Dashboard T109 com tabelas quantitativas (HOLDOUT/ACID).

## 2. Seleção lexicográfica determinística

**Regra**: toda seleção de winner deve usar critério lexicográfico documentado em `selection_rule.json`, com ordem explícita de métricas e direção (ASC/DESC).

- Phase 3 (LL-PH3-003). Aumenta rastreabilidade.
- Phase 4 (LL-PH4-003). Primeiro critério = métrica do objetivo-mestre da fase.

## 3. Análise de lógica invertida para diagnóstico

**Técnica**: quando o sistema tem comportamento inesperado, inverter a lógica de decisão para uma data/estado específico acelera o diagnóstico da causa raiz.

- Phase 3 (LL-PH3-005). A061 (reverse decision analysis 2024-10-15) identificou o estado absorvente em T044.

## 4. Ciclo Spec → Engine → Plotly

**Padrão**: especificação formal → execução com ablação → visualização comparativa. Funciona para tasks complexas.

- Phase 5 (LL-PH5-002). SPEC-007 permitiu execução limpa do T072 na primeira tentativa.

## 5. Pipeline ML portátil cross-market

**Evidência**: o ciclo de 4 etapas (labels → features → XGBoost → backtest) é portátil. Transpor da Fábrica BR para US levou 4 tasks (T112-T115) com zero regressão no pipeline BR.

- Phase 9 (LL-PH9-001).

## 6. Trilha em blocos com rastreabilidade ponta-a-ponta

**Padrão**: SSOT → score → motor → trigger → integração → declaração → dashboard. Cada bloco com manifest e changelog.

- Phase 10 (LL-PH10-001). Manteve rastreabilidade ponta-a-ponta com evidências auditáveis.

## 7. Roteamento fixo de LLM por papel

**Regra**: cada papel (CTO, Architect, Executor, Auditor, Curator) usa a LLM designada, com gate obrigatório de verificação.

- Phase 2 (LL-PH2-011). Evita erros de processo por mistura de papéis.

## 8. Recuperação de qualidade (V1 FAIL → V2 PASS)

**Padrão observado**: replanejamento formal quando V1 falha, com correção documentada e V2 auditada.

- Phase 10 (LL-PH10-005). T128 V2 corrigiu erro semântico do V1 preservando governança.

---

## Princípios de processo consolidados

1. Plotly é evidência, não decoração — embutir em scripts de ablação
2. Seleção sempre lexicográfica e documentada
3. Inverter lógica para diagnosticar estados inesperados
4. Spec → Engine → Plotly para tasks complexas
5. Pipeline ML portátil entre mercados
6. Blocos com rastreabilidade ponta-a-ponta
7. LLM por papel, sem mistura
