# PHASE 2 EXECUTION PLAN (Reality-Based)

## 1. Diagnóstico da Realidade (O que temos)

Aprendizados concretos da Tentativa 2 (extraídos do Critical_Intel):

### Principais falhas da Tentativa 2
- Definição operacional de sucesso (o que precisa ser verdade ao final do V2):
- 1. Robustez W2-like melhora contra o baseline M3 sob a mesma contabilidade (custo + caixa remunerado a CDI), com queda relevante no comportamento de deriva longa (tempo underwater e drawdown), e redução do turnover trap em estresse.
- 2. Capacidade de captura em regimes favoráveis é preservada, sem bloqueio operacional por regras excessivas.
- 3. A política SPC/CEP↔RL é auditável por execução: fica impossível produzir um run “NEW ≈ M3” sem evidência clara de que o envelope contínuo e os guardrails foram consumidos e aplicados.
- ### 3. Baseline do bundle: M3 (fixo)
- - tags: governance, imported_evidence=true, lessons, low_signal, needs_curation=true, rag

### Regras de sizing validadas (sinais práticos encontrados)
- Métricas de auditoria/forense:
- * trilha diária de regime (envelope) e seus limites ativos,
- * registros de disparo de fallback,
- * incidência de anti-reentry (quando bloqueou/penalizou reentrada),
- * decomposição de contribuição por ticker/setor.
- ### 8. Plano por fases (objetivos por fase, entregas e fundamentação prática)

### Dependências de dados externos (BRAPI e similares)
- "title": "Licao extraida #108",
- "context": "Extracao de docs/corpus/licoes_aprendidas.json",
- "problem": "5. A conclusão conceitual do ciclo: Master não deve ser apenas um gate binário de compra; ele deve classificar regime (BULL/BEAR/TRANSIÇÃO), e cada regime deve ter política de carteira (níveis de liberdade de BUY), mantendo queimadores como",
- "decision": "Registrar evidencias e criterios de governanca com rastreabilidade por path.",
- "impact": "Reduz friccao de retomada e melhora capacidade de diagnostico.",
- "corpus/source/external_refs/CEP_COMPRA/CEP_COMPRA/docs/0_Relatório de encerramento do ciclo M0…M6 (CEP_COMPRA v1).md"

### Módulos que funcionaram
- Governança e rastreabilidade de execução (manifest/report/evidence)

### Módulos que quebraram / risco elevado
- Dependência de provedores externos de mercado (BRAPI/API) sem isolamento robusto

## 2. Arquitetura Alvo (Módulos)

1. Módulo de Ingestão de Dados (prioridade máxima)
   - Conectores de fontes (BRAPI/alternativas) com fallback.
   - Cache local versionado e contratos de esquema.
2. Módulo de Normalização e Qualidade
   - Padronização OHLCV, timezone, calendário e checks de integridade.
3. Módulo de Feature Store e Sizing Inputs
   - Geração de sinais/sizing com versionamento e trilha de auditoria.
4. Módulo de Backtest/Execução Simulada
   - Motor determinístico + trilha forense de cada experimento.
5. Módulo de Trading Logic (somente após ingestão estável)
   - Estratégias e regras de decisão desacopladas do pipeline de dados.

## 3. Roadmap de Implementação (Passo a Passo)

1. Fechar contratos de dados da ingestão (schemas, validações, limites).
2. Implementar conectores com retry/fallback e observabilidade mínima.
3. Versionar snapshots de dados e publicar manifest por execução.
4. Revalidar sizing em cima de dados normalizados e congelados.
5. Só então reintroduzir lógica de trading e comparação de estratégias.
6. Definir gate de promoção: somente ciclos com `OVERALL STATUS: [[ PASS ]]`.
