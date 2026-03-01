# STATE 3 Phase 4 - Lessons Learned (T069)

## 1) Contexto do ciclo
- Escopo: consolidacao do ciclo T067 -> T068 + diagnostico de engenharia de processos.
- Objetivo-mestre: superar T044 winner no trecho CDI-bloqueado (~2023+) com compras efetivas de acao.
- Resultado: T067 atingiu o objetivo no trecho 2023+ (+68.4pp vs T044). T068 provou que ajuste parametrico nao resolve a perda de rali jun/20-jul/21. Diagnostico de processo revelou causa-raiz estrutural.
- Evidencia de fechamento visual: `outputs/plots/T067_STATE3_PHASE4A_COMPARATIVE.html`, `outputs/plots/T068_STATE3_PHASE4B_COMPARATIVE.html`.
- Referencias de governanca: `00_Strategy/ROADMAP.md`, `00_Strategy/TASK_REGISTRY.md`, `00_Strategy/OPS_LOG.md`.

## 2) O que deu certo
- **LL-PH4-001**: Abordagem "de cima para baixo" (partir do maximo e reduzir) foi mais eficiente que a abordagem incremental usada em fases anteriores. T067 encontrou winner com cadence=10 pregoes e sem cap, resolvendo o trecho 2023+ na primeira ablacao. [evidencia: `T067` | `outputs/governanca/T067-AGGRESSIVE-ALLOCATION-ABLATION-V1_report.md`]
- **LL-PH4-002**: Plotly embutido no script de ablacao (regra de fase) acelerou a avaliacao visual e eliminou a necessidade de task separada para visualizacao durante a ablacao. [evidencia: `T067` | `outputs/plots/T067_STATE3_PHASE4A_COMPARATIVE.html`]
- **LL-PH4-003**: Ranking lexicografico com excess_return_2023plus_vs_t044 como primeiro criterio focou a selecao no objetivo-mestre da fase, evitando que metricas globais mascarassem o desempenho no trecho-alvo. [evidencia: `T067` | `src/data_engine/portfolio/T067_AGGRESSIVE_SELECTED_CONFIG.json`]
- **LL-PH4-004**: Hard constraint unico (MDD>=-0.30) manteve simplicidade sem restringir excessivamente o espaco de busca (feasible=10/25 no T067). [evidencia: `T067` | `outputs/governanca/T067-AGGRESSIVE-ALLOCATION-ABLATION-V1_report.md`]

## 3) O que nao deu certo
- **LL-PH4-005**: T068 (rally protection) nao conseguiu recuperar o rali jun/20-jul/21. Ablacao de 36 candidatos (histerese assimetrica + filtro hibrido de tendencia) produziu winner identico ao T067. Ajuste parametrico dentro do mesmo processo nao resolve diferenca estrutural entre estrategias. [evidencia: `T068` | `outputs/governanca/T068-RALLY-PROTECTION-ABLATION-V1_report.md`]
- **LL-PH4-006**: MODE_B (HYBRID_TREND) nao produziu nenhum candidato feasible sob as constraints definidas, indicando que o filtro de tendencia com os parametros testados era excessivamente restritivo ou incompativel com o regime market-slope. [evidencia: `T068` | `outputs/governanca/T068-RALLY-PROTECTION-ABLATION-V1_report.md`]

## 4) Diagnostico de engenharia de processos (mecanismos)

### Glossario operacional (fixado pelo Owner)
- **Burner**: ativo individual (600+ no universo elegivel). Processo SPC independente.
- **Master**: carteira/portfolio (conjunto de ~10+/-1 burners operando simultaneamente).
- **Tank**: caixa livre (resultado liquido de compras/vendas/dividendos/JCP/bonus + remuneracao CDI).
- **Equity**: posicoes marcadas a mercado + tank. Comeca em R$100k.

### Dois modos de operacao do forno

**LL-PH4-007 (CRITICO)**: T037 e T067 operam como dois modos fundamentalmente diferentes do mesmo forno. A diferenca nao e parametrica — e estrutural.

| Mecanismo | T037 ("plena carga") | T067 ("controle de regime") |
|---|---|---|
| Disjuntor de venda | Binario (BURNER_STRESS_CEP: 0% ou 100%) | Gradual (CEP_SEVERITY: 25%/50%/100%) |
| Cadencia de compra | 3 pregoes, 17% dos dias com compra (P1) | 5 pregoes + regime, 2.8% dos dias (P1) |
| Reentrada apos venda | 39% com reentrada, mediana 10d (P1) | 10% com reentrada, mediana 29d (P1) |
| Tank (cash fraction) | 5% (seco) | 16-19% (gordo) |
| Regime defensivo | Nenhum (0%) | 50% do tempo |
| CDI no caixa | Irrelevante (0.5% da variacao P1) | Significativo (13.4% da variacao P2) |

### Performance por periodo (base 100)

| Periodo | T037 | T067 | T044 | Vencedor |
|---|---|---|---|---|
| P1 (inicio-jul/21) | +186.7% | +70.9% | +153.8% | T037 |
| P2 (ago/21-fim) | -35.4% | +101.9% | +49.9% | T067 |

### Tres variaveis de processo que explicam a diferenca

**LL-PH4-008**: A vantagem de cada modo depende da interacao entre:

1. **Produtividade dos burners** — quando ativos selecionados produzem retorno acima do CDI, o modo T037 (reposicao rapida, tank seco) captura mais upside. Quando produzem abaixo do CDI, o modo T067 (tank gordo remunerado) preserva capital.

2. **Velocidade de reposicao** — T037 compra 6x mais frequentemente que T067. No P1, isso reacende burners rapido apos vendas. No P2, isso reacende burners que vao apagar de novo (queima de combustivel).

3. **Custo de oportunidade do tank** — com CDI a 2-4% (P1), tank gordo = dinheiro parado. Com CDI a 10-13% (P2), tank gordo = burner passivo de alta performance.

### Sinal de comutacao endogeno

**LL-PH4-009**: O sinal para comutar entre modos nao vem do mercado (MA200, volatilidade, slope do Ibovespa nao separam os dois modos com clareza — todos dao ~49% vs 51% dia a dia). O sinal vem de **dentro do proprio forno**: retorno rolling dos burners ativos vs CDI. Quando burners produzem acima do CDI -> modo T037. Quando produzem abaixo -> modo T067.

### Evidencia quantitativa

**LL-PH4-010**: Decomposicao por cenario de mercado (Ibov acima/abaixo MA200, slope positivo/negativo, volatilidade alta/baixa) mostrou separacao fraca (~49% vs 51%) entre os modos. Porem, decomposicao por periodo (base 100) mostrou separacao dramatica: +186.7% vs +70.9% (P1) e -35.4% vs +101.9% (P2). A diferenca e de processo, nao de mercado.

## 5) Decisoes de governanca que mudaram o resultado
- **LL-PH4-011**: Regra de fase "Plotly embutido em toda ablacao" reduziu ciclo de feedback e eliminou tasks intermediarias de visualizacao.
- **LL-PH4-012**: Registro de T068 como DONE apesar de objetivo funcional nao atingido preservou o artefato e a evidencia negativa como conhecimento formal.

## 6) Regras operacionais (Do/Don't) para o proximo ciclo
- **DO**: usar diagnostico de engenharia de processos (burners/master/tank) como framework de analise antes de propor solucoes.
- **DO**: testar comutacao entre modos de operacao usando sinal endogeno (produtividade dos burners vs CDI).
- **DO**: manter Plotly embutido em scripts de ablacao.
- **DO**: registrar resultados negativos como evidencia formal (eliminacao de caminhos).
- **DON'T**: tentar resolver diferencas estruturais entre estrategias com ajuste parametrico.
- **DON'T**: usar indicadores de mercado (MA200, vol, slope Ibov) como unico sinal de comutacao — a separacao dia-a-dia e fraca.
- **DON'T**: assumir que o modo de operacao otimo e constante ao longo do tempo.

## 7) Checklist anti-regressao
- [ ] Motor dual-mode deve suportar comutacao entre dois conjuntos completos de parametros (disjuntor, cadencia, regime, tank).
- [ ] Sinal de comutacao deve ser endogeno (baseado em telemetria do forno, nao em indicadores de mercado).
- [ ] Ablacao de comutacao deve usar walk-forward para evitar look-ahead no sinal endogeno.
- [ ] Comparativo final deve incluir T037, T044, T067 e a nova estrategia dual-mode.
- [ ] Hard constraints de MDD e excess_return por subperiodo devem ser mantidos.
- [ ] Manifest SHA256 sem self-hash e changelog atualizado.
- [ ] Promocao somente apos PASS do Auditor.
