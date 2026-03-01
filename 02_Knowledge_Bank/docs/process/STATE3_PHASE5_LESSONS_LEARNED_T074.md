# STATE 3 Phase 5 - Lessons Learned (T074)

## 1) Contexto do ciclo
- Escopo: consolidação do ciclo T071 → T072 → T073 + diagnóstico de viabilidade e decisão de pivô.
- Objetivo-mestre: produzir estratégia que supere T037 no rali E T044 no trecho CDI-bloqueado, simultaneamente, via comutação endógena entre dois modos de operação do forno.
- Resultado: T072 atingiu R$407k (+307%) no período completo (2018-2026), superando T044 (R$381k) e T067 (R$352k). Porém, no recorte 2021-2025, entregou apenas +55.8% — abaixo do CDI (+67.5%) e muito abaixo de benchmarks reais (CHC Momentum Smart Beta +186.9%).
- Evidência de fechamento visual: `outputs/plots/T073_STATE3_PHASE5C_COMPARATIVE.html`, `outputs/plots/T072_RATIO_CDI_IBOV.html`, `outputs/plots/T072_HAMMER_CDI_PERIODS.html`.
- Referências de governança: `00_Strategy/ROADMAP.md`, `00_Strategy/TASK_REGISTRY.md`, `00_Strategy/OPS_LOG.md`.

## 2) O que deu certo

- **LL-PH5-001**: O conceito de dual-mode (T037/T067) é válido. O motor funciona e a comutação endógena produz resultado superior ao de qualquer estratégia individual no período completo. O T072 é o melhor resultado absoluto do projeto (R$407k). [evidência: `T072` | `outputs/governanca/T072-DUAL-MODE-ENGINE-ABLATION-V1_report.md`]

- **LL-PH5-002**: A especificação formal do termostato (SPEC-007, T071) com glossário operacional, regras de transição, anti-lookahead e desenho mínimo da ablação permitiu execução limpa do T072 na primeira tentativa. O ciclo Spec→Engine→Plotly funcionou bem. [evidência: `T071` | `02_Knowledge_Bank/docs/specs/SPEC-007_THERMOSTAT_FORNO_DUAL_MODE_T071.md`]

- **LL-PH5-003**: Walk-forward com split TRAIN/HOLDOUT explícito (2018-2022 / 2023-2026) e seleção exclusivamente no TRAIN é a forma correta de validar. O winner passou nos gates do HOLDOUT sem ajuste. [evidência: `T072` | `outputs/governanca/T072-DUAL-MODE-ENGINE-ABLATION-V1_evidence/feasibility_snapshot.json`]

- **LL-PH5-004**: Diagnóstico de ablação embutido no Plotly (T073) — mostrar feasibility por variante de sinal, top-N de candidatos inviáveis e margens do winner vs constraints — acelerou a tomada de decisão do Owner. [evidência: `T073` | `outputs/governanca/T073-PHASE5-PLOTLY-COMPARATIVE-V1_evidence/ablation_diagnostics.json`]

## 3) O que não deu certo

- **LL-PH5-005 (CRÍTICO)**: SINAL-1 (produtividade dos burners = `positions_value_end`) produziu **zero candidatos feasíveis** (0/162). O sinal baseado apenas no valor das posições é estruturalmente lento para detectar mudança de regime — ele só reage depois que as posições já perderam valor, quando o dano está feito. [evidência: `T073` | `ablation_diagnostics.json` → `sinal1_train_feasible_count=0`]

- **LL-PH5-006 (CRÍTICO)**: SINAL-2 (net excess = `equity_end` vs CDI) produziu apenas **2 candidatos feasíveis de 162** (1.2%). O winner opera na fronteira dos constraints (MDD_train = -29.78% vs limite -30.00%, margem de 0.22pp). Isso indica que o espaço de busca determinístico (rolling window + threshold + histerese) está **esgotado** para este problema. [evidência: `T073` | `ablation_diagnostics.json` → `winner_margins_vs_train_thresholds`]

- **LL-PH5-007 (CRÍTICO)**: A deriva continua acontecendo em dois períodos específicos: ago/2021–mar/2023 e nov/2024–nov/2025. O termostato endógeno do T072 não detecta esses períodos com velocidade suficiente. A "martelada" (forçar caixa a CDI nesses dois períodos) eleva o equity de R$407k para R$757k (+657%), provando que o problema é **detecção**, não conceito. [evidência: `outputs/plots/T072_HAMMER_CDI_PERIODS.html`]

- **LL-PH5-008**: No recorte 2021-2025 (mesmo período do benchmark CHC Momentum Smart Beta), o T072 original entrega +55.8% vs +186.9% do CHC. A versão "martelada" entrega +189.8% — praticamente empatando com o melhor fundo quantitativo real do Brasil. Isso confirma que o gap não é de estratégia, é de **timing de comutação**. [evidência: análise CTO em chat]

## 4) Diagnóstico: por que o determinístico esgotou

### Histórico de 7 tentativas determinísticas (T039 → T072)

| Task | Sinal/Mecanismo | Resultado | Por que não resolveu |
|---|---|---|---|
| T039 | Slope portfolio_logret W=4 | MDD=-44.9%, 72% defensivo | Sinal do portfolio é circular (cai quando vende) |
| T044 | Cadence=81d, sem cap | MDD=-17%, CDI-only 2023+ | Absorção defensiva irreversível |
| T059 | Constraints de participação | MDD=-9.6%, equity≈CDI | Constraints forçaram participação mas não retorno |
| T063 | Slope Ibov W=30, hyst 4/4 | MDD=-4.5%, equity=R$260k | Bom para reentrada, insuficiente para rali |
| T067 | Cadence=10, market-slope | MDD=-20.3%, equity=R$352k | Perde rali jun/20-jul/21 |
| T068 | Hyst assimétrica + trend | Idêntico a T067 | Ajuste paramétrico não resolve diferença estrutural |
| T072 | Termostato endógeno SINAL-2 | MDD=-29.8%, equity=R$407k | Feasibility 0.6%, deriva persiste |

### Limitação fundamental

Todas as tentativas usam a mesma arquitetura: **1 sinal escalar → threshold → histerese → decisão binária**. Essa arquitetura captura relações lineares/monotônicas entre 1 variável e o estado do forno. Mas a "produtividade do forno" é uma função de **múltiplas variáveis interagindo de forma não-linear**: dispersão dos scores, fração de tickers em alerta SPC, velocidade de deterioração dos retornos, custo de oportunidade do CDI, etc. Um threshold sobre 1 sinal não captura essas interações.

## 5) Decisão do Owner: pivô para Machine Learning

**Decisão tomada**: abandonar a linha determinística (rendimentos decrescentes após 7 tentativas) e pivotar para classificação supervisionada com ML (XGBoost + walk-forward).

**Formulação correta do problema** (fixada pelo Owner):
- **NÃO É**: "o forno está produtivo hoje?" (lookahead)
- **É**: "o forno **esteve** produtivo **até ontem**?" (shift(1) — só dados passados)
- Todas as features devem ser calculadas com dados até D-1. A decisão no dia D usa informação até D-1.
- Perder 1 dia de reação é aceitável para salvar uma jornada inteira de deriva.

**Requisitos hard para Phase 6**:
1. Anti-lookahead estrito: features calculadas com `shift(1)` ou equivalente
2. Walk-forward: treinar no TRAIN (2018-2022), validar no HOLDOUT (2023-2026)
3. O segundo período de caixa (nov/24-nov/25) está **inteiramente no HOLDOUT** — se o modelo acertar sem tê-lo visto, é evidência forte de generalização
4. Transparência não é requisito; confiança via validação out-of-sample é
5. Label binário: "caixa" vs "mercado", baseado nos dois períodos identificados pela martelada

**Inventário de dados disponíveis para ML**:
- Feature matrix: 17+ features × 1.964 pregões
- SSOT_CANONICAL: 631.944 ticker-days × 21 colunas (SPC charts)
- M3_SCORES: 866.863 ticker-days × 10 colunas
- SSOT_MACRO: 2.025 pregões × 6 colunas
- Label equilibrado: 32% caixa / 68% mercado (tanto no TRAIN quanto no HOLDOUT)
- Expansível para 50-100 features via rolling windows, lags, ratios cruzados

## 6) Checklist anti-regressão para Phase 6

- [ ] Nunca usar features com informação do dia D ou posterior (shift(1) obrigatório)
- [ ] Nunca selecionar features ou hiperparâmetros usando dados do HOLDOUT
- [ ] Validar que o modelo não está simplesmente "ficando no estado atual" (medir transições previstas vs reais)
- [ ] Comparar backtest financeiro do modelo vs T072 original vs martelada vs CDI vs Ibov
- [ ] Manter manifest SHA256 e changelog para toda task
- [ ] Se o modelo não acertar o segundo período de caixa (nov/24-nov/25) no HOLDOUT, considerar FAIL

## 7) Artefatos da Phase 5

| Artefato | Task | Tipo |
|---|---|---|
| `SPEC-007_THERMOSTAT_FORNO_DUAL_MODE_T071.md` | T071 | Especificação |
| `T072_DUAL_MODE_SELECTED_CONFIG.json` | T072 | Configuração do winner |
| `T072_PORTFOLIO_CURVE_DUAL_MODE.parquet` | T072 | Curva do portfolio |
| `T072_DUAL_MODE_ABLATION_RESULTS.parquet` | T072 | Resultados da ablação |
| `T072_STATE3_PHASE5B_COMPARATIVE.html` | T072 | Plotly comparativo |
| `T073_STATE3_PHASE5C_COMPARATIVE.html` | T073 | Plotly diagnóstico |
| `T072_RATIO_CDI_IBOV.html` | CTO | Ratio T072/CDI e T072/Ibov |
| `T072_HAMMER_CDI_PERIODS.html` | CTO | Martelada (prova de conceito) |
| `STATE3_PHASE5_LESSONS_LEARNED_T074.md` | T074 | Este documento |
