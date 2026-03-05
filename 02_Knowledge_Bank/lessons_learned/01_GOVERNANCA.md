# Lessons Learned — Governança

> Consolidação temática de todas as lições sobre manifest, changelog, registry, auditoria e cadeia de comando.
> Fonte: phases 2, 3, 4, 6, 8, 9, 10. Originais em `archive/by_phase/`.

---

## 1. Manifest SHA256

**Regra**: todo artefato de execução deve ter `manifest.json` com SHA256 de inputs e outputs. O manifest **não pode conter self-hash** (hash de si mesmo), pois isso cria dependência circular.

- Primeira ocorrência: Phase 2 (LL-PH2-004, LL-PH2-012).
- Reforçada em Phase 3 (LL-PH3-012) e Phase 6 (LL-PH6-010).
- Evidência negativa: T079 EXEC #1 falhou por computar SHA256 do `report.md` antes de escrever a linha `OVERALL STATUS`, gerando hash obsoleto.
- **Sequência obrigatória de finalização**: `write_report_complete()` → `hash_all()` → `write_manifest()`. Nenhuma escrita de artefato pode ocorrer após a computação dos hashes.

## 2. Changelog

**Regra**: uma linha única no changelog por execução, formato ISO8601, sem placeholders.

- Primeira ocorrência: Phase 3 (LL-PH3-011).
- Evolução: Phase 8 introduziu `append_changelog_one_line_idempotent()` para evitar duplicatas por re-run (LL-PH8-013). Padrão adotado em todos os scripts a partir de T109.
- Evidência negativa: T108 tinha linha duplicada no changelog por re-run (finding INFO, sem impacto, mas motivou o fix).

## 3. JSON estrito (RFC 8259)

**Regra**: NaN e Infinity não são JSON válido. Devem ser convertidos para `null`.

- Phase 2 (LL-PH2-003). Regra nunca precisou de revisão — funciona desde a primeira formulação.

## 4. Dual-ledger

**Regra**: separar TASK_REGISTRY (produto, milestones) de OPS_LOG (manutenção, auditoria). IDs de séries diferentes (Txxx vs M-xxx, A-xxx, HOTFIX-xxx).

- Phase 2 (LL-PH2-010). Preserva rastreabilidade sem mistura de finalidade.
- Em uso contínuo e sem alteração desde a formulação.

## 5. Critério de desempate em ablações

**Regra**: quando candidatos têm métricas TRAIN idênticas, o desempate por `candidate_id` é arbitrário e pode eleger um winner inferior. Critério hierárquico obrigatório: (1) `switches_train` ASC, (2) `h_out` DESC, (3) `candidate_id` ASC como último recurso. Documentar no `selection_rule.json`.

- Phase 6 (LL-PH6-007). Motivação: C057 vs C060 — candidate_id menor elegeu C057, mas C060 era superior no HOLDOUT (+R$31k equity, -6.7pp MDD). T079 foi necessário para reverter.

## 6. Winner formal vs winner de produto

**Regra**: distinguir explicitamente o winner formal da ablação (selecionado em TRAIN-only) do winner de produto (decisão do Owner pós-validação out-of-sample). O winner formal preserva a integridade histórica do registro; o winner de produto é a decisão operacional.

- Phase 6 (LL-PH6-008). T078 permanece curado com C057 (winner TRAIN-only); C060 é o winner de produto por decisão do Owner via T079.

## 7. Declaração formal de winner

**Regra**: materializar o winner oficial em artefato JSON declarativo (`*_WINNER_DECLARATION.json`) antes de criar dashboards consolidados. Elimina ambiguidade operacional.

- Phase 10 (LL-PH10-004). T127 formalizou `T127_US_WINNER_DECLARATION.json` com `winner_task_id=T122` e `trigger_rejected={T126,abandoned}`.

## 8. Padrão V1 FAIL → V2 PASS

**Observação**: 4 tasks na Phase 8 (T083, T084, T086, T101) seguiram o padrão V1 FAIL → V2 PASS. A auditoria independente funciona como rede de segurança, mas o custo de retrabalho é alto.

- Phase 8 (LL-PH8-014). Ação preventiva: gates mais rigorosos no script antes de submeter à auditoria.

## 9. Feature guard como gate anti-contaminação

**Regra**: implementar `feature_guard.json` em toda task ML para impedir que colunas auxiliares (ex: `sp500_close`) contaminem o modelo. Resolveu findings recorrentes de T112/T113.

- Phase 9 (LL-PH9-008). Padrão adotado como obrigatório.

## 10. Registro de evidência negativa

**Regra**: registrar tasks como DONE mesmo quando o objetivo funcional não é atingido, preservando o artefato e a evidência negativa como conhecimento formal.

- Phase 4 (LL-PH4-012). T068 documentada como DONE apesar de rally protection não atingido — a prova negativa ("ajuste paramétrico não resolve diferença estrutural") é tão valiosa quanto um PASS.

## 11. Cadeia de comando obrigatória

**Regra**: manter ciclo Executor → Auditor → Curator para promoção de qualquer marco. Sem atalhos.

- Phase 10 (LL-PH10-013). Roteamento fixo de LLM por papel e gate obrigatório para evitar erro de processo (reforça LL-PH2-011).

## 12. Contrato de semântica de input

**Regra**: validar não apenas o path do arquivo de input, mas também o schema esperado (colunas, tipos). "Path certo" não basta sem validação de colunas.

- Phase 10 (LL-PH10-008, LL-PH10-009). T128 V1 falhou por usar arquivo errado como BR winner; V2 exigiu adaptação de schema (`equity_end_norm`, `ret_cdi`).

---

## Checklist operacional de governança

1. [ ] Manifest SHA256 sem self-hash, sequência write→hash→manifest
2. [ ] Changelog com linha única idempotente por execução
3. [ ] JSON RFC 8259 (NaN→null)
4. [ ] Dual-ledger: produto em TASK_REGISTRY, operação em OPS_LOG
5. [ ] Critério de desempate hierárquico documentado em `selection_rule.json`
6. [ ] Winner formal ≠ winner de produto (ambos documentados)
7. [ ] Winner declarado em JSON antes de dashboards
8. [ ] Feature guard obrigatório em toda task ML
9. [ ] Evidência negativa registrada formalmente
10. [ ] Cadeia Executor → Auditor → Curator sem atalhos
11. [ ] Contrato de semântica de input (path + schema)
