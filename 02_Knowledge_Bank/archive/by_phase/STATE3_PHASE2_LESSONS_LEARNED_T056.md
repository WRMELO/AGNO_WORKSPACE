# STATE 3 Phase 2 - Lessons Learned (T056)

## 1) Contexto do ciclo
- Escopo: consolidacao do ciclo T050 -> T053 -> T051 -> T052 -> T044 (R2) -> T055.
- Baseline/meta de referencia: T039 (baseline) e T037 (meta) [evidencia: `T055` | `/home/wilson/AGNO_WORKSPACE/outputs/governanca/T055-PHASE2-PLOTLY-FINAL-V1_report.md`].
- Solucao promovida no ciclo: guardrails anti-drift T044 [evidencia: `T044` | `/home/wilson/AGNO_WORKSPACE/outputs/governanca/T044-ANTI-DRIFT-GUARDRAILS-V2_report.md`].

## 2) O que deu certo
- **LL-PH2-001**: CEP em logret captura choques agudos, mas pode falhar na deriva lenta; CEP+SLOPE melhora granularidade do decisor. [evidencia: `T053` | `/home/wilson/AGNO_WORKSPACE/outputs/governanca/T053-CEP-SLOPE-STATE-TESTS-V1_report.md`]
- **LL-PH2-002**: Parametros 'por exemplo' devem ser evitados; selecao precisa ser data-driven via ablação deterministica. [evidencia: `T044` | `/home/wilson/AGNO_WORKSPACE/outputs/governanca/T044-ANTI-DRIFT-GUARDRAILS-V2_report.md`]
- **LL-PH2-006**: Cadencia de compra foi o guardrail dominante no vencedor C021. [evidencia: `T044` | `/home/wilson/AGNO_WORKSPACE/src/data_engine/portfolio/T044_GUARDRAILS_SELECTED_CONFIG.json`]
- **LL-PH2-007**: Dashboards Plotly sao evidencia operacional obrigatoria para leitura de comportamento temporal. [evidencia: `T055` | `/home/wilson/AGNO_WORKSPACE/outputs/plots/T055_STATE3_PHASE2_FINAL_COMPARATIVE.html`]
- **LL-PH2-009**: Robustez por subperiodos canonicos evita overfitting temporal. [evidencia: `T052` | `/home/wilson/AGNO_WORKSPACE/outputs/governanca/T052-ROBUSTNESS-SUBPERIODS-V1_report.md`]

## 3) O que nao deu certo
- **LL-PH2-005**: Aumento de complexidade pode degradar retorno sem melhorar risco. [evidencia: `T055` | `/home/wilson/AGNO_WORKSPACE/outputs/governanca/T055-PHASE2-PLOTLY-FINAL-V1_report.md`]
- **LL-PH2-003**: JSON estrito (RFC8259) e obrigatorio; NaN/Infinity devem virar null. [evidencia: `T044` | `/home/wilson/AGNO_WORKSPACE/outputs/governanca/T044-ANTI-DRIFT-GUARDRAILS-V2_manifest.json`]
- **LL-PH2-004**: Manifest nao pode incluir self-hash. [evidencia: `T044` | `/home/wilson/AGNO_WORKSPACE/outputs/governanca/T044-ANTI-DRIFT-GUARDRAILS-V2_manifest.json`]

## 4) Por que aconteceu (mecanismos)
- **LL-PH2-008**: A solucao precisa bater simultaneamente T037 (meta) e T039 (baseline). [evidencia: `T055` | `/home/wilson/AGNO_WORKSPACE/outputs/governanca/T055-PHASE2-PLOTLY-FINAL-V1_report.md`]
- A combinacao de evidencias numericas e visuais reduziu risco de conclusao apressada por metrica isolada.

## 5) Decisoes de governanca que mudaram o resultado
- **LL-PH2-010**: Dual-ledger (produto vs operacao) preserva rastreabilidade sem mistura de finalidade. [evidencia: `M-017` | `/home/wilson/AGNO_WORKSPACE/00_Strategy/OPS_LOG.md`]
- **LL-PH2-011**: Roteamento fixo de LLM por papel e gate obrigatorio para evitar erro de processo. [evidencia: `M-017` | `/home/wilson/AGNO_WORKSPACE/.cursor/rules/agno-llm-routing-fixed.mdc`]
- **LL-PH2-012**: Policy de manifest SHA256 com cobertura de inputs/outputs e requisito canonico de concluibilidade. [evidencia: `M-015` | `/home/wilson/AGNO_WORKSPACE/.cursor/rules/agno-cto-resposta-io-v4.mdc`]

## 6) Regras operacionais (Do/Don't) para o proximo ciclo
- **DO**: usar ablação data-driven para qualquer calibracao de parametro operacional.
- **DO**: exigir report + manifest + evidencia visual antes de promover para DONE.
- **DO**: validar robustez por subperiodos canonicos antes de rollout de regras.
- **DON'T**: usar parametro arbitrario ('por exemplo') sem experimento comparativo.
- **DON'T**: aceitar manifest com self-hash ou JSON nao estrito.
- **DON'T**: continuar quando houver mismatch de modelo por papel.

## 7) Checklist anti-regressao
- [ ] Inputs obrigatorios presentes e versionados.
- [ ] Gates G1..Gx explicitados no report.
- [ ] JSON estrito validado sem NaN/Infinity.
- [ ] Manifest SHA256 consistente, sem self-hash.
- [ ] Comparativo final vs T037 e T039 publicado.
- [ ] Atualizacao dual-ledger somente apos PASS do Auditor.
