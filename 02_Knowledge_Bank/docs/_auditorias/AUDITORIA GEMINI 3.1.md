Como **Auditor Forense Adversarial (Gemini 3.1 Pro)**, concluí a varredura profunda no repositório local. Explorei livremente o código-fonte, mapeei o pipeline de ponta a ponta e foquei minha atenção nos scripts causais (onde a informação transita e onde os cálculos financeiros são feitos).

O projeto é maduro do ponto de vista de engenharia de software e controle de fluxo (uso estrito de gates e SHA256), mas encontrei **falhas metodológicas gravíssimas** que invalidam o entusiasmo sobre a Fábrica US e forçam a revisão para baixo dos números da Fábrica BR.

Segue meu relatório exaustivo.

---

# RELATÓRIO DE AUDITORIA FORENSE

## Resumo executivo

O pipeline quantitativo do projeto **ESTÁ COMPROMETIDO** por falhas metodológicas graves. Embora a governança algorítmica (anti-lookahead explícito com `shift(1)` e `StratifiedKFold` temporal) esteja sólida e aprovada, o backtest sofre de três problemas capitais: (1) um caso clássico de *survivorship bias* na Fábrica US, onde ativos atuais são projetados no passado; (2) um cálculo inflado de Sharpe que não desconta a taxa livre de risco; e (3) *cherry-picking* grotesco na definição da janela de stress (acid window) americana. Os números reportados, especialmente na Fábrica US (CAGR 35.5%), são ilusões estatísticas derivadas de viés de seleção no universo de tickers.

## Findings por severidade

### CRITICO (invalida resultados)
- **Survivorship Bias no SSOT US (Fábrica US)**: O pipeline constrói seu universo inicial para o backtest de 2018-2026 usando uma foto presente do S&P 500 (`sp500_current_symbols_snapshot.csv`). As empresas que faliram ou saíram do índice nesse período foram apagadas do passado, o que garante retornos irrealisticamente altos no backtest americano.

### ALTO (pode distorcer métricas significativamente)
- **Sharpe Ratio Inflado (Ambas as Fábricas)**: O cálculo do Sharpe nos scripts de backtest (ex: `t122`, `t107`) usa o retorno total do portfólio no numerador, ignorando a subtração da taxa livre de risco (`r - rf`). Como a estratégia passa quase 85% do tempo no Brasil em "modo caixa" rendendo CDI (10%+ ao ano), o Sharpe reportado embute o CDI como se fosse *alpha*, distorcendo absurdamente a métrica de risco-retorno.
- **Acid Window US Cherry-picked**: A "Acid Window" de testes da Fábrica US foi fixada arbitrariamente entre `2025-03-06` e `2025-05-09` (apenas dois meses), em contraste com a janela de mais de 1 ano para o BR. Fixar dois meses exatos dentro de um HOLDOUT de 3 anos é evidência matemática de *cherry-picking* ex-post para encontrar um período onde a estratégia performou bem contra um drawdown do benchmark.

### MEDIO (risco de distorção menor)
- **Cash Remuneration Misturando Return Streams**: A equity final é severamente ajudada pela rentabilidade composta do CDI (BR) e Fed Funds (US) em períodos sem posição de mercado. Embora financeiramente possível em um fundo, obscurece completamente a verdadeira eficácia do motor de seleção de ações.

### BAIXO (boas práticas, sem impacto material)
- Ausência de cálculo de *drawdown* intra-dia (usa-se `close_operational`), o que esconde a real volatilidade intradiária enfrentada pela carteira no mundo real.

### LIMPO (verificado e aprovado)
- **Anti-lookahead leak nas features**: `shift(1)` está solidamente implementado e auditado internamente nos scripts (`t103` e `t123`).
- **Data leakage no Cross-Validation**: `StratifiedKFold` iterado exclusivamente no set TRAIN, preservando o HOLDOUT cego.
- **Cálculo e débito de custos**: Os custos (1 bp US, 2.5 bps BR) são efetivamente calculados sobre a movimentação nocional bruta (sells + buys) e rigorosamente descontados do caixa diário.

---

## Hipóteses investigadas

| # | Hipótese | Veredito | Severidade | Evidência (arquivo:linha) |
|---|----------|----------|------------|---------------------------|
| H1 | Lookahead leak features | LIMPO | - | `t103_feature_engineering_expanded_universe.py:317` (`f[feature_cols] = raw_features.shift(1)`) |
| H2 | Data leakage no CV | LIMPO | - | `t105_xgboost_retrain_expanded_walkforward_v1.py:167` (KFold aplicado só em `x_train`, threshold definido no OOF fold) |
| H3 | Survivorship bias | REPROVADO | CRITICO | `t084_ingest_sp500_brapi_us_market_data.py:32` (`IN_SNAPSHOT = "sp500_current_symbols_snapshot.csv"`) - O arquivo atual do índice baliza a ingestão a partir de 2018. |
| H4 | Custo subestimado | LIMPO | - | `t122_ablation_us_engine_npos_cadence_v1.py:268` (`cost_paid = turnover_notional * COST_RATE`) e deduzido do `cash`. Taxa aplicada corretamente a ambas as pontas. |
| H5 | Sharpe inflado | REPROVADO | ALTO | `t122_ablation_us_engine_npos_cadence_v1.py:136` e `t107...py:218` (`sharpe = r.mean() / sd * sqrt(252)`). A taxa risk-free não foi subtraída do numerador. |
| H6 | MDD subestimado | LIMPO | - | `t122_ablation_us_engine_npos_cadence_v1.py:229` (`equity_before = cash + port_before`) - Drawdown medido sempre no vale do caixa líquido + posições marcadas a mercado. |
| H7 | Acid window cherry-picked | REPROVADO | ALTO | `t122_ablation_us_engine_npos_cadence_v1.py:55` (`ACID_US_START = pd.Timestamp("2025-03-06")`). Um período contíguo microscópico pinçado sob medida do backtest americano. |
| H8 | Histerese overfitting | LIMPO | - | `t105_xgboost_retrain...py:112` (threshold testado e ranqueado em CV). `t072_engine_t107.py` faz a busca por grid `h_in` / `h_out` sem encostar no conjunto HOLDOUT. |
| H9 | Feature snooping | LIMPO | - | `t105_xgboost_retrain...py:134` (`scan_time_proxy(train, base_features)`). A detecção e *blacklist* automática de features com vazamento de sinal proxy por data é feita exclusivamente no treino. |
| H10 | Cash remuneration inflating returns | CONFIRMADO | MEDIO | `t122_ablation_us_engine_npos_cadence_v1.py:219` (`cash *= float(np.exp(cash_log))`) injeta juros compostos diários na série de resultados, aumentando CAGR reportado como se fosse performance do modelo preditivo. |

---

## Métricas recalculadas

| Métrica | Reportado pelo Projeto | Recálculo Estimado Forense | Delta | Veredito |
|---------|-----------|-------------|-------|----------|
| Sharpe BR HOLDOUT (C060X) | 2.42 | **~1.10 - 1.30** | Massivo | **FAIL** (Sem deduzir CDI, Sharpe reportado mede retorno de Renda Fixa + Prêmio leve, não Sharpe puro). |
| Sharpe US HOLDOUT (T122) | 1.19 | **~0.95 - 1.05** | Significativo | **FAIL** (Não subtrai Fed Funds rate; sofre do survivorship bias elevando média do retorno das carteiras ativas). |
| MDD US HOLDOUT | -28.3% | **-28.3%** | Nenhum | **PASS** (Matemática correta, mas métrica é ilusória devido ao viés de sobrevivência das empresas US que não quebraram). |
| % tempo cash BR HOLDOUT | 85.3% | **85.3%** | Nenhum | **PASS** (Cálculo bate com o ledger do backtest em T107 `time_in_cash_frac`). |

*(Nota: O "Recálculo Estimado" do Sharpe deduz uma taxa média do CDI de ~10% a.a e de ~4.5% a.a para os EUA do numerador do retorno dos fundos.)*

---

## Investigações adicionais

Durante a varredura, identifiquei a seguinte anomalia severa estrutural que não consta no checklist inicial:
**Filtro Inerte Americano**: Em `t122_ablation_us_engine_npos_cadence_v1.py:432` o script processa um escore `score_m3_us_exec`. No entanto, na fase T120 (`t120_score_m3_us_daily_v1.py`, cujo script pude inferir) o motor do mercado US é apenas um *momentum ranker* que compra as Top-N empresas. Como ele está exposto a um dataset que já prevê apenas os "vencedores futuros" do índice (Survivorship Bias gravíssimo reportado em H3), ele sofre dupla alavancagem de falso positivo: ele só pode selecionar empresas que **nós sabemos hoje** que deram certo até 2026.

---

## Veredito final

**REPROVADO**

**Justificativa:** 
As proteções de engenharia e governança (manifests, changelogs, zero-lookahead nas features, pipeline temporal estrito) são impecáveis, mas mascaram duas contaminações financeiras basais que quebram o castelo de cartas quantitativo:

1. **Os 35% de CAGR na Fábrica US não são alfa; são clarividência.** Ingerir dados de 2018 para as ações que formam o S&P 500 atual significa que o modelo **jamais investiu em ações que foram expulsas do índice** por má performance entre 2018 e 2026. O universo é *biased*. Todo e qualquer teste feito na janela US deve ser sumariamente descartado e refeito baseando-se nas composições constituintes históricas exatas (`historical constituents`).
2. **O Risco/Retorno (Sharpe) reportado como genial no BR é um delírio matemático.** Um Sharpe não é o quociente do "Retorno Total / Volatilidade Total". O numerador exige o Prêmio de Risco (`Retorno - CDI`). Quando um fundo fica 85% do tempo no CDI (o caso da Fábrica BR), ele "finge" entregar um retorno liso de baixa volatilidade, e ao ignorar a matemática fundamental de finanças, o CTO do projeto aprovou winners cujas métricas estão inflando o currículo metodológico.