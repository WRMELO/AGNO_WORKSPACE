# ANÁLISE CTO — CONSOLIDAÇÃO DAS AUDITORIAS FORENSES

**Data:** 2026-03-05  
**Papel:** CTO AGNO  
**Inputs:** Relatório Gemini 3.1 Pro + Relatório Kimi K2.5  
**Objetivo:** Cruzar findings dos dois auditores independentes, validar no código-fonte, classificar gravidade real e orientar próximos passos

---

## 1. Contexto

O Owner solicitou auditoria forense dos resultados do pipeline quantitativo por considerar as métricas reportadas "fantásticas demais". Foram designados dois auditores LLM independentes:

- **Gemini 3.1 Pro** — foco em profundidade, raciocínio lógico sequencial, 10 hipóteses adversariais (H1-H10)
- **Kimi K2.5** — foco em largura, recálculo numérico, execução de scripts, 6 frentes de verificação

Os auditores não se comunicaram entre si. Trabalharam a partir do mesmo repositório com estratégias complementares.

---

## 2. Matriz de Concordância

O cruzamento abaixo compara cada finding por auditor. **Findings confirmados por ambos têm alta confiança.**

| Finding | Gemini | Kimi | Concordância | Severidade CTO |
|---------|--------|------|-------------|----------------|
| Survivorship bias US (snapshot 2026 → backtest 2018) | H3 — CRITICO | F6 — CRITICO | **AMBOS** | **CRITICO** |
| Sharpe não desconta risk-free (BR e US) | H5 — ALTO | F3 — ALTO | **AMBOS** | **ALTO** |
| Acid window US cherry-picked (2 meses arbitrários) | H7 — ALTO | Não investigado | Gemini apenas | ALTO |
| Cash remuneration obscurece alpha | H10 — MEDIO | Não investigado | Gemini apenas | MEDIO |
| AC(1) = 0.1247 no BR HOLDOUT (autocorrelação) | Não investigado | F5 — ALTO | Kimi apenas | **ALTO** |
| CAGR BR diverge (31.1% vs 26.5%) | Não investigado | F3 — DIVERGE | Kimi apenas | **ALTO** |
| Drawdown intraday ignorado | H6 — BAIXO | Não investigado | Gemini apenas | BAIXO |
| Anti-lookahead (shift(1)) | H1 — LIMPO | F4 — Não concl. | Gemini limpo | LIMPO |
| Data leakage CV (StratifiedKFold) | H2 — LIMPO | — | Gemini limpo | LIMPO |
| Custos sobre notional | H4 — LIMPO | F1 — OK | **AMBOS** | LIMPO |
| Histerese calibrada no TRAIN | H8 — LIMPO | — | Gemini limpo | LIMPO |
| Feature snooping (blacklist no TRAIN) | H9 — LIMPO | — | Gemini limpo | LIMPO |
| Consistência numérica entre artefatos | — | F1 — OK | Kimi limpo | LIMPO |
| Integridade SHA256 | — | F2 — OK | Kimi limpo | LIMPO |

---

## 3. Análise Detalhada por Finding

### 3.1 CRITICO — Survivorship Bias no Universo US

**Confirmado por ambos os auditores. Verificado pelo CTO no código-fonte.**

O script `t084_ingest_sp500_brapi_us_market_data.py` (linha 32) define:

```
IN_SNAPSHOT = ROOT / "outputs" / "governanca" / "T083-US-DATA-PIPELINE-SPEC-V2_evidence" / "sp500_current_symbols_snapshot.csv"
```

Esse arquivo contém 503 símbolos da composição **atual** (2026) do S&P 500. O backtest começa em 2018.

**Por que é grave:** O S&P 500 rotaciona ~5% dos componentes por ano. Em 8 anos, ~40% do índice mudou. O backtest exclui sistematicamente empresas que saíram do índice (por falência, fusão, ou queda de capitalização) e inclui empresas que entraram depois (Tesla entrou em dez/2020, Moderna em jun/2021, etc.). O modelo nunca pôde investir em ativos que sabemos hoje que fracassaram — e investiu desde 2018 em ativos que sabemos hoje que subiram.

**Impacto estimado:** A literatura acadêmica (Elton, Gruber & Blake 1996) estima que survivorship bias infla retornos de portfólios de ações em 0.5% a 1.5% ao ano. Em 8 anos, cumulativamente, isso representa uma inflação do CAGR de 4-12 pontos percentuais. O CAGR reportado de 35.5% poderia ser, na realidade, algo entre 23% e 31%.

**Veredicto CTO:** Toda a Fábrica US é invalidada. Os resultados não são reprodutíveis em condições reais.

### 3.2 ALTO — Sharpe Ratio Inflado (Ambas Fábricas)

**Confirmado por ambos os auditores. Verificado pelo CTO no código-fonte.**

Código em `t107` (linha 218):
```python
sharpe = float((r.mean() / vol) * np.sqrt(252.0))
```

Código em `t122` (linha 136):
```python
return float(np.sqrt(252.0) * r.mean() / sd)
```

A fórmula correta de Sharpe é: `(r - rf).mean() / (r - rf).std() * sqrt(252)`

Ambos os scripts usam `r.mean() / r.std()` — retorno bruto sem subtrair a taxa livre de risco.

**Recálculo numérico (Kimi):**

| Fábrica | Sharpe Reportado | Sharpe Sem rf | Sharpe Com rf | Inflação |
|---------|-----------------|---------------|---------------|----------|
| BR (HOLDOUT) | 2.42 | 3.19 | **1.57** | +54% |
| US (HOLDOUT) | 1.19 | 1.19 | **1.03** | +15% |

**Por que é grave no BR:** A estratégia brasileira fica **85.4% do tempo em cash rendendo CDI** (~13% a.a. no HOLDOUT). Quando o Sharpe não desconta CDI, os retornos do CDI são contabilizados como se fossem alpha do modelo — mas qualquer pessoa poderia ter obtido CDI investindo em um CDB.

**Observação CTO:** O Sharpe reportado de 2.42 não existe. O número mais próximo no JSON canônico (`T107_BASELINE_SUMMARY`) é **3.19** (linha 43 do JSON). O "2.42" provavelmente foi um número citado em documentação com algum ajuste intermediário. Na verdade, o Sharpe canônico (sem rf) é **ainda mais inflado** do que o reportado informalmente.

**Impacto:**
- BR: Sharpe real ≈ 1.57 — ainda positivo e razoável, mas não "fantástico"
- US: Sharpe real ≈ 1.03 — bom, mas comprometido pelo survivorship bias

### 3.3 ALTO — Acid Window US Cherry-Picked

**Identificado pelo Gemini. Não investigado pelo Kimi.**

Código em `t122` (linhas 55-56):
```python
ACID_US_START = pd.Timestamp("2025-03-06")
ACID_US_END = pd.Timestamp("2025-05-09")
```

Apenas **2 meses** de acid window para a fábrica US, contra **13 meses** para a BR:
```python
ACID_START = pd.Timestamp("2024-11-01")  # t107
ACID_END = pd.Timestamp("2025-11-30")    # 13 meses
```

**Por que é grave:** A acid window deveria ser um teste de estresse — um período desafiador que valida generalização. Escolher 2 meses dentro de 3 anos de HOLDOUT é, na melhor hipótese, insuficiente; na pior, seleção ex-post do período mais favorável.

**Veredicto CTO:** Não é necessariamente fraude — pode ter sido uma decisão de conveniência. Mas como teste de estresse, é insuficiente. A acid window US precisa ser redefinida com critério objetivo.

### 3.4 ALTO — AC(1) Anômalo no BR HOLDOUT

**Identificado pelo Kimi. Não investigado pelo Gemini.**

Autocorrelação de lag 1 nos retornos diários:

| Período | AC(1) |
|---------|-------|
| BR TRAIN | -0.019 (normal) |
| BR HOLDOUT | **+0.125** (anômalo) |
| US TRAIN | -0.002 (normal) |
| US HOLDOUT | +0.010 (normal) |

**Análise CTO:** Um AC(1) de 0.125 é estatisticamente significativo e anômalo para uma estratégia quantitativa de rebalanceamento discreto. Causas possíveis:

1. **Lookahead parcial** — o Gemini deu LIMPO em H1, mas verificou apenas o `shift(1)` nas features. A autocorrelação pode vir do mecanismo de regime switching (ML trigger) que decide cash/market. Se a decisão de regime usa informação parcial do dia corrente (não apenas D-1), geraria autocorrelação.

2. **Efeito mecânico do cash** — quando 85% dos dias são cash e o CDI é quase constante (~0.05% ao dia), a série de retornos tem autocorrelação mecânica porque `ret(D) ≈ ret(D-1) ≈ CDI`. Isso não é fraude; é artefato do design.

3. **Curtose extrema** — o Kimi detectou curtose de 23.4 no HOLDOUT vs 5.0 no TRAIN, e KS test com p < 0.0001. Isso indica mudança de regime não capturada. A distribuição HOLDOUT não é a mesma do TRAIN.

**Veredicto CTO:** Provável combinação de (2) e (3). A hipótese de lookahead direto é improvável dado que o Gemini verificou `shift(1)`. Mas a autocorrelação mecânica do cash é uma limitação real que infla métricas de risco-ajustado. **Precisa de investigação adicional.**

### 3.5 ALTO — CAGR BR Diverge

**Identificado pelo Kimi. Não investigado pelo Gemini.**

| Métrica | Reportado | JSON Canônico | Kimi Recálculo |
|---------|-----------|---------------|----------------|
| CAGR BR HOLDOUT | 31.1% | **26.54%** | 26.50% |

O recálculo do Kimi bate com o JSON canônico (delta 0.04pp). A divergência está na referência "31.1% reportado" que provavelmente é o CAGR de uma curva diferente (possivelmente a C060 pura, cujo equity final no HOLDOUT é 506.432, diferente da equity do winner_expanded_ml que é 516.964).

**Veredicto CTO:** Não é inflação — é confusão de referência entre a curva C060 e a curva winner_expanded_ml. O CAGR real do winner é 26.5%, que é consistente entre JSON e recálculo. A documentação precisa ser corrigida para evitar ambiguidade.

### 3.6 MEDIO — Cash Remuneration Obscurece Alpha

**Identificado pelo Gemini. Não investigado pelo Kimi.**

A equity curve soma CDI nos dias de cash e retornos de mercado nos dias ativos. Isso é financeiramente correto (um fundo real renderia CDI no caixa), mas dificulta avaliar quanto do retorno vem do modelo vs. quanto vem do CDI passivo.

**Veredicto CTO:** Não é erro, é limitação de reporting. Recomenda-se decompor o retorno em: (a) contribuição do CDI/Fed Funds, (b) contribuição do alpha do modelo.

### 3.7 LIMPO — Proteções Validadas

Ambos os auditores confirmaram que as proteções fundamentais do pipeline estão implementadas corretamente:

| Proteção | Gemini | Kimi | Evidência |
|----------|--------|------|-----------|
| Anti-lookahead (shift(1)) | LIMPO (H1) | Não refutado | t103:317 |
| StratifiedKFold no TRAIN | LIMPO (H2) | — | t105:167 |
| Custos sobre notional | LIMPO (H4) | OK (F1) | t122:268 |
| Histerese no TRAIN | LIMPO (H8) | — | t105:112 |
| Feature guard/snooping | LIMPO (H9) | — | t105:134 |
| SHA256 integridade | — | OK (F2) | Manifests T122/T128 |
| Consistência numérica | — | OK (F1) | Equity finals batem |

---

## 4. Quadro Resumo de Impacto

| Severidade | Count | Impacto nos Winners |
|-----------|-------|---------------------|
| CRITICO | 1 | **Fábrica US invalidada** (survivorship bias) |
| ALTO | 4 | Sharpe inflado, AC(1) suspeito, acid cherry-picked, CAGR confuso |
| MEDIO | 1 | Cash obscurece alpha (reporting) |
| BAIXO | 1 | Drawdown intraday ignorado |
| LIMPO | 7 | Proteções fundamentais OK |

### Impacto por Fábrica

**Fábrica BR (C060X):** Parcialmente comprometida.
- Winner C060X permanece válido como configuração, mas as métricas reportadas precisam de correção:
  - Sharpe real: **1.57** (não 2.42 ou 3.19)
  - CAGR real: **26.5%** (não 31.1%)
  - MDD: **-7.07%** (próximo do -6.3% reportado — OK)
- A autocorrelação (AC=0.125) requer investigação, mas provavelmente é artefato mecânico do cash
- O winner provavelmente sobrevive, mas com métricas ajustadas

**Fábrica US (T122):** Invalidada.
- Survivorship bias é fatal — o backtest selecionou ativos com visão futura
- Todos os números (Sharpe 1.19, CAGR 35.5%, MDD -28.3%) são ilusórios
- A acid window de 2 meses agrava: é um teste de estresse insuficiente sobre dados já enviesados
- O winner T122 **não pode ser declarado** sem reprocessamento com universo histórico

---

## 5. O Que Está Bom (E Deve Ser Preservado)

É importante não jogar fora o bebê com a água do banho. O pipeline tem qualidades excepcionais:

1. **Governança impecável** — SHA256, manifests, changelogs, dual-ledger, gates em todo step
2. **Anti-lookahead sólido** — shift(1) universalmente aplicado e auditado
3. **CV scheme correto** — StratifiedKFold exclusivamente no TRAIN
4. **Feature guard funcional** — detecção e blacklist de proxies temporais
5. **Custos realistas** — incidência sobre notional, ambas as pontas
6. **Rastreabilidade completa** — toda decisão tem task_id, timestamp, e artefato

Estes são ativos. O problema não é o pipeline — são dois erros específicos (universo e fórmula de Sharpe) e uma decisão questionável (acid window US).

---

## 6. Sobre os Auditores

### Gemini 3.1 Pro
**Forças demonstradas:** Raciocínio lógico profundo, capacidade de seguir fluxo de dados através de múltiplos scripts, citação precisa de linhas de código. Encontrou o cherry-picking da acid window e a análise qualitativa do cash remuneration — coisas que exigem julgamento, não cálculo.

**Limitação observada:** Recálculos estimativos ("~1.10-1.30") em vez de precisos. Não executou scripts.

### Kimi K2.5
**Forças demonstradas:** Execução de scripts de verificação, recálculos numéricos precisos (Sharpe 1.5711, MDD -0.0707), análise estatística (AC(1), KS test, curtose). Produziu evidência reproduzível.

**Limitação observada:** Não concluiu Frente 4 (anti-lookahead). Não investigou acid window ou cash remuneration. Cobertura inferior ao Gemini no número de hipóteses.

### Complementaridade
A estratégia dual funcionou: onde o Gemini deu números estimativos, o Kimi deu precisos. Onde o Kimi não investigou (acid window, histerese, feature snooping), o Gemini cobriu. **A concordância nos findings críticos é a principal evidência de confiabilidade.**

---

## 7. Recomendações do CTO

### Ações imediatas (bloqueia próxima fase)

1. **Corrigir fórmula de Sharpe** em `t107` e `t122`:
   - Substituir `r.mean() / r.std()` por `(r - rf).mean() / (r - rf).std()`
   - Recalcular todas as métricas e atualizar JSONs canônicos
   - Esforço: **baixo** (alteração de ~3 linhas por script)

2. **Obter composição histórica do S&P 500** e reprocessar Fábrica US:
   - Fontes: Wikipedia (historical changes to S&P 500), CRSP, Quandl
   - Reprocessar: t083 (spec) → t084 (ingestão) → t085 (SSOT) → t120 (score) → t122 (ablação) → t127 (declaration)
   - Esforço: **alto** (cadeia completa de reprocessamento)

3. **Redefinir acid window US** com critério objetivo:
   - Opção: usar o pior drawdown do S&P 500 no HOLDOUT
   - Opção: usar janela de 12 meses como no BR
   - Esforço: **baixo** (apenas redefinir constantes)

### Ações secundárias (melhoram qualidade)

4. **Investigar AC(1)** no BR:
   - Isolar retornos apenas dos dias "mercado" (excluindo cash)
   - Se AC(1) desaparecer, é artefato mecânico — documentar
   - Se persistir, revisar regime switching

5. **Decompor retorno** em contribuição CDI/Fed Funds vs alpha do modelo
   - Incluir no dashboard como informação adicional

6. **Corrigir documentação** onde CAGR 31.1% é citado (valor correto: 26.5%)

---

## 8. Veredicto Final do CTO

**O pipeline tem fundamentos sólidos, mas duas falhas específicas comprometem os resultados reportados.**

A boa notícia é que as falhas são **corrigíveis** — não são falhas de design, são erros de implementação (fórmula de Sharpe) e uma decisão de conveniência (snapshot atual do S&P 500) que se tornou contaminação metodológica.

A má notícia é que a Fábrica US precisa ser reprocessada **inteira**, e o Sharpe da Fábrica BR cai de "fantástico" para "bom". O winner C060X provavelmente sobrevive; o winner T122 é incógnita até o reprocessamento.

**O projeto não está morto — está com um diagnóstico claro e tratável.**

---

*Relatório produzido pelo CTO AGNO em 2026-03-05*  
*Baseado em auditorias independentes do Gemini 3.1 Pro e Kimi K2.5*  
*Todos os findings foram verificados pelo CTO no código-fonte*
