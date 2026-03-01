# STATE 3 Phase 3 - Lessons Learned (T065)

## 1) Contexto do ciclo
- Escopo: consolidacao do ciclo T058 -> T059 -> T060 -> A060 -> A061 -> T063(V2) -> T064.
- Evidencia de fechamento visual da correcao: `/home/wilson/AGNO_WORKSPACE/outputs/governanca/T064-PHASE3D-PLOTLY-COMPARATIVE-V1_report.md`.
- Referencias de governanca: `/home/wilson/AGNO_WORKSPACE/00_Strategy/ROADMAP.md`, `/home/wilson/AGNO_WORKSPACE/00_Strategy/TASK_REGISTRY.md`, `/home/wilson/AGNO_WORKSPACE/00_Strategy/OPS_LOG.md`.

## 2) O que deu certo
- **LL-PH3-001**: O comportamento CDI-only observado em T044 nao depende do ponto de inicio (2018 vs 2023). [evidencia: `T058` | `/home/wilson/AGNO_WORKSPACE/outputs/governanca/T058-START2023-PLOTLY-V1_report.md`]
- **LL-PH3-002**: Sem constraints explicitas, a selecao pode favorecer solucoes de baixa participacao mesmo com bom risco aparente. [evidencia: `T059` | `/home/wilson/AGNO_WORKSPACE/outputs/governanca/T059-PARTICIPATION-OBJECTIVE-V2_report.md`]
- **LL-PH3-003**: Selecao lexicografica deterministica aumenta rastreabilidade da escolha final. [evidencia: `T059` | `/home/wilson/AGNO_WORKSPACE/outputs/governanca/T059-PARTICIPATION-OBJECTIVE-V2_report.md`]
- **LL-PH3-006**: Migrar o decisor para sinal de mercado (market slope) removeu a dependencia circular da carteira. [evidencia: `T063` | `/home/wilson/AGNO_WORKSPACE/outputs/governanca/T063-MARKET-SLOPE-REENTRY-ABLATION-V2_report.md`]
- **LL-PH3-007**: Calibracao de histerese por grade e obrigatoria para equilibrar estabilidade e responsividade de regime. [evidencia: `T063` | `/home/wilson/AGNO_WORKSPACE/outputs/governanca/T063-MARKET-SLOPE-REENTRY-ABLATION-V2_report.md`]
- **LL-PH3-008**: Reentrada sem cap de compra pode violar limite de turnover total; buy_turnover_cap_ratio foi decisivo. [evidencia: `T063` | `/home/wilson/AGNO_WORKSPACE/outputs/governanca/T063-MARKET-SLOPE-REENTRY-ABLATION-V2_report.md`]
- **LL-PH3-009**: Veredicto visual final em Plotly e mandatorio para consolidar conclusoes de participacao e risco. [evidencia: `T060` | `/home/wilson/AGNO_WORKSPACE/outputs/governanca/T060-PHASE3-PLOTLY-FINAL-V1_report.md`]
- **LL-PH3-010**: Comparativo T064 confirmou T063 como correcao operacional da armadilha do defensivo. [evidencia: `T064` | `/home/wilson/AGNO_WORKSPACE/outputs/governanca/T064-PHASE3D-PLOTLY-COMPARATIVE-V1_report.md`]

## 3) O que nao deu certo
- **LL-PH3-004**: No T044, regime defensivo virou estado absorvente quando a carteira ficou sem posicoes. [evidencia: `A060` | `/home/wilson/AGNO_WORKSPACE/outputs/governanca/A060-RANKING-VS-REGIME-DIAGNOSTIC-V1_report.md`]

## 4) Por que aconteceu (mecanismos)
- **LL-PH3-005**: Analise de logica invertida (A061) acelerou a identificacao da condicao necessaria para reentrada. [evidencia: `A061` | `/home/wilson/AGNO_WORKSPACE/outputs/governanca/A061-REVERSE-DECISION-2024-10-15_report.md`]

## 5) Decisoes de governanca que mudaram o resultado
- **LL-PH3-011**: Linha unica no changelog por execucao e essencial para rastreabilidade temporal auditavel. [evidencia: `T064` | `/home/wilson/AGNO_WORKSPACE/00_Strategy/changelog.md`]
- **LL-PH3-012**: Manifest SHA256 com cobertura de inputs/outputs e sem self-hash segue como gate de concluibilidade. [evidencia: `T064` | `/home/wilson/AGNO_WORKSPACE/outputs/governanca/T064-PHASE3D-PLOTLY-COMPARATIVE-V1_manifest.json`]

## 6) Regras operacionais (Do/Don't) para o proximo ciclo
- **DO**: manter constraints de participacao + risco como hard constraints em ablação.
- **DO**: validar reentrada com sinal exogeno de mercado quando houver risco de estado absorvente.
- **DO**: exigir comparativo visual final (equity + drawdown + tabela) antes de promover.
- **DON'T**: reintroduzir decisor de regime dependente de serie que zera em caixa total.
- **DON'T**: promover task sem manifest consistente e linha de changelog correspondente.

## 7) Checklist anti-regressao
- [ ] Inputs canônicos presentes para todo comparativo.
- [ ] Hard constraints explicitadas no report e na regra de selecao.
- [ ] Reentrada validada em subperiodo alvo (sem estado absorvente).
- [ ] Dashboard final publicado com assinaturas esperadas de traces.
- [ ] Manifest SHA256 sem self-hash e com cobertura de inputs/outputs.
- [ ] Changelog atualizado com 1 linha por execucao.
- [ ] Promocao no dual-ledger somente apos PASS do Auditor.
