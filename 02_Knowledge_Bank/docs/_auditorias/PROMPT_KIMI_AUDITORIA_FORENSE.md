# PROMPT PARA KIMI K2.5 — AUDITORIA FORENSE

> Copie tudo abaixo (da linha "---" até o final) e cole no Kimi K2.5.
> Ative Agent Swarm se disponível. Dê acesso ao repositório local.

---

## MISSÃO

Você é um **auditor forense adversarial independente**, especializado em **verificação numérica e consistência cruzada**. Seu objetivo é ENCONTRAR FALHAS num pipeline quantitativo de investimentos.

Os resultados reportados são excepcionais — e isso é motivo de **suspeita**, não de celebração. Você foi contratado especificamente porque o dono do projeto desconfia que os números podem estar inflados por erros metodológicos, data leakage, ou vieses ocultos.

**Sua força é diferente de outro auditor que já está trabalhando em paralelo** (ele foca em raciocínio lógico profundo e sequencial). A sua força é:
- **Recálculo numérico independente** — escreva e execute scripts Python para recalcular métricas do zero
- **Consistência cruzada** — cruze números entre todos os artefatos que os citam
- **Execução paralela** — decomponha a auditoria em frentes simultâneas
- **Análise estatística de distribuição** — detecte anomalias nos retornos

## REGRAS FUNDAMENTAIS

1. A ausência de evidência de erro **NÃO** é evidência de ausência de erro.
2. Números precisam **BATER** entre todos os artefatos que os citam. Divergência > 0.01 = finding.
3. Toda métrica reportada deve ser **RECALCULÁVEL** a partir dos dados brutos. Se não for, é finding.
4. Você tem **ACESSO TOTAL** ao repositório. Navegue livremente.
5. Pode e **DEVE EXECUTAR scripts Python** para validar cálculos. Não confie apenas em inspeção visual.

## O REPOSITÓRIO

Path local: `/home/wilson/AGNO_WORKSPACE`

Estrutura de diretórios:

```
AGNO_WORKSPACE/
├── 00_Strategy/          ← roadmap, task registry, OPS_LOG, changelog
├── 01_Architecture/      ← System_Context.md
├── 02_Knowledge_Bank/    ← base de conhecimento do projeto
│   ├── lessons_learned/  ← 8 documentos temáticos (regras declaradas)
│   ├── docs/             ← constituição, emendas, specs, handoffs
│   └── archive/          ← originais por fase, supersedidos, legado
├── scripts/              ← 97 scripts Python (o CORE da auditoria)
├── src/                  ← módulos Python (data engine, adapters)
│   └── data_engine/
│       ├── ssot/         ← SSOTs canônicos (parquets)
│       ├── features/     ← features, predictions, datasets (parquets)
│       ├── models/       ← modelos JSON com hiperparâmetros
│       └── portfolio/    ← equity curves, ledgers, configs (parquets + JSON)
├── data/                 ← 700+ parquets de market data bruto
└── outputs/              ← 70+ diretórios de evidência por task
    └── governanca/       ← reports, manifests, evidence dirs
```

## O QUE O PROJETO AFIRMA

O projeto construiu duas "fábricas" independentes de investimento:

### Fábrica BR (BRL) — Winner: C060X
- Motor M3 + ML trigger (XGBoost classificador de regime cash/market)
- Universo: 1.174 tickers (663 BR + 446 BDRs + 50 US_DIRECT)
- **Métricas HOLDOUT reportadas**: Sharpe 2.42, MDD -6.3%, CAGR 31.1%
- Equity: R$300k → R$698k no HOLDOUT
- Custo: 2.5 bps sobre notional. Tank: CDI diário
- TRAIN: 2018-07-02 → 2022-12-30 | HOLDOUT: 2023-01-02 → 2026-02-26
- **85% do tempo em cash (rendendo CDI)**

### Fábrica US (USD) — Winner: T122
- Motor M3-US puro (stock selection, sem ML trigger)
- Universo: 496 tickers S&P 500
- **Métricas HOLDOUT reportadas**: Sharpe 1.19, MDD -28.3%, CAGR 35.5%
- Custo: ~1 bp. Tank: Fed Funds rate
- Mesma janela TRAIN/HOLDOUT

### Proteções que o projeto declara
O Knowledge Bank (`02_Knowledge_Bank/lessons_learned/`) lista proteções. **Cada uma deve ser verificada numericamente, não apenas no código:**

1. Anti-lookahead: `shift(1)` em toda feature
2. Walk-forward estrito: winner selecionado 100% no TRAIN
3. StratifiedKFold(5, shuffle) no CV
4. Feature guard impedindo contaminação
5. Custo sobre notional em toda operação
6. Manifest SHA256 em todo artefato

## COMO PROCEDER

### Passo 1 — Reconhecimento (navegue livremente)

Comece por onde quiser. Sugestões de entrada:
- `02_Knowledge_Bank/INDEX.md` → mapa do conhecimento
- `02_Knowledge_Bank/lessons_learned/` → o que o projeto AFIRMA
- `src/data_engine/portfolio/` → equity curves e configs (dados numéricos)
- `outputs/governanca/` → reports e manifests de cada task

### Passo 2 — Decomponha em frentes paralelas

Use Agent Swarm para atacar **simultaneamente** pelo menos estas 6 frentes:

#### FRENTE 1 — Consistência numérica cruzada
Cruzar métricas entre artefatos. Os **mesmos números** devem bater em:
- `report.md` de cada task (outputs/governanca/)
- `manifest.json` de cada task
- `selection_rule.json` e `winner_declaration.json`
- `*_SELECTED_CONFIG.json` em src/data_engine/portfolio/
- `*_BASELINE_SUMMARY*.json`
- `OPS_LOG.md` em 00_Strategy/

**Testes obrigatórios:**
1. Sharpe do winner BR: cruzar T107 summary vs T109 dashboard vs T128 consolidado
2. MDD do winner US: cruzar T122 selected config vs T127 declaration vs T128 consolidado
3. Equity final: cruzar último dia da equity curve (.parquet) vs report (.md)
4. Número de switches de regime: cruzar transition_diagnostics.json vs report

**Critério**: divergência > 0.01 em qualquer métrica = FINDING

#### FRENTE 2 — Integridade SHA256
Para **cada** task com manifest.json em outputs/governanca/:
1. Computar SHA256 de cada arquivo listado no manifest
2. Comparar com o hash declarado
3. Verificar que TODOS os outputs estão no manifest (sem artefato fantasma)
4. Verificar que TODOS os inputs estão no manifest (sem input não rastreado)
5. Verificar se o manifest foi escrito DEPOIS do report completo

**Escreva um script Python** que automatize essa verificação para todos os manifests.

**Critério**: qualquer hash divergente = FINDING CRITICO

#### FRENTE 3 — Reprodutibilidade aritmética (CRUCIAL)
**Escreva e execute scripts Python** que recalculem do zero:

```python
# RECÁLCULOS OBRIGATÓRIOS:

# 1. Sharpe do winner BR (C060X) no HOLDOUT
#    Ler: src/data_engine/portfolio/T107_PORTFOLIO_CURVE_DUAL_MODE_EXPANDED_ML_TRIGGER.parquet
#    Calcular: mean(r - rf) / std(r - rf) * sqrt(252)
#    Onde rf = CDI diário (de SSOT_MACRO_EXPANDED.parquet, coluna cdi_log_daily)
#    COMPARAR com 2.42 reportado

# 2. Sharpe do winner US (T122) no HOLDOUT
#    Ler: src/data_engine/portfolio/T122_US_ENGINE_WINNER_CURVE_DAILY.parquet
#    Calcular: mean(r - rf) / std(r - rf) * sqrt(252)
#    Onde rf = Fed Funds rate diário (cash_log_daily_us)
#    COMPARAR com 1.19 reportado

# 3. MDD do winner BR no HOLDOUT
#    Ler mesma equity curve
#    Calcular: max peak-to-trough
#    COMPARAR com -6.3% reportado

# 4. MDD do winner US no HOLDOUT
#    COMPARAR com -28.3% reportado

# 5. CAGR de ambos
#    Calcular: (equity_final / equity_inicial) ^ (252/n_days) - 1

# 6. Switches de regime (BR)
#    Contar transições cash→market e market→cash na série

# 7. % do tempo em cash (BR)
#    Fração de dias com state_cash == 1
```

**ATENÇÃO ESPECIAL**: verificar se o Sharpe reportado DESCONTA a taxa livre de risco no numerador. Se o código calcula `mean(r) / std(r)` em vez de `mean(r - rf) / std(r - rf)`, isso é um **FINDING ALTO** porque infla o Sharpe quando a estratégia fica muito tempo em cash rendendo CDI/Fed Funds.

**Tolerância**: |delta| < 0.005 para Sharpe, < 0.1pp para MDD e CAGR.

#### FRENTE 4 — Anti-lookahead end-to-end
Selecionar **3 datas aleatórias** no HOLDOUT e, para cada uma:
1. Carregar o parquet de features daquele dia
2. Verificar que TODAS as features são do dia anterior (shift(1))
3. Verificar que o label oracle usa janela futura (correto por design, mas ISOLADO)
4. Verificar que a decisão cash/market no dia D usa apenas dados até D-1
5. Verificar que o rebalanceamento acontece no CLOSE de D

**Escreva um script** que faça esse trace para as 3 datas escolhidas.

#### FRENTE 5 — Análise de distribuição e anomalias
Carregar as equity curves e:
1. Calcular autocorrelação AC(1) dos retornos diários
   - AC(1) > |0.05| significativo = FINDING ALTO (sugere lookahead)
2. Comparar distribuição TRAIN vs HOLDOUT (KS test ou similar)
   - Divergência extrema sugere overfitting
3. Verificar se melhores dias coincidem com dias de rebalanceamento
   - Se sim, suspeita de timing bias
4. Calcular curtose e skew — verificar se plausível
5. Calcular information ratio por ano — outlier extremo deve ser investigado

#### FRENTE 6 — Validação de universo e seleção
1. **BR**: verificar se os 663 tickers incluem empresas deslistadas entre 2018-2026
   - Carregar `src/data_engine/ssot/SSOT_CANONICAL_BASE.parquet` e verificar
2. **US**: verificar se os 496 tickers são a composição do S&P 500 de **2018** ou de **2026**
   - Composição muda ~5%/ano. Se for a de 2026, = survivorship bias CRITICO
   - Buscar `sp500_current_symbols_snapshot.csv` em outputs/ para ver a data do snapshot
3. Verificar se o filtro SPC usa dados futuros para excluir tickers

### Passo 3 — Consolidação

Após as 6 frentes, produza o relatório final:

```
# RELATÓRIO DE AUDITORIA FORENSE — KIMI K2.5

## Resumo executivo
[1 parágrafo: pipeline limpo ou comprometido?]

## Findings por frente
### Frente 1 — Consistência numérica: [n findings]
### Frente 2 — Integridade SHA256: [n findings]
### Frente 3 — Reprodutibilidade: [n findings]
### Frente 4 — Anti-lookahead: [n findings]
### Frente 5 — Distribuição: [n findings]
### Frente 6 — Universo: [n findings]

## Tabela de findings
| # | Frente | Severidade | Descrição | Evidência |
|---|--------|-----------|-----------|-----------|
| 1 | ...    | CRITICO   | ...       | ...       |

## Métricas recalculadas vs reportadas
| Métrica | Reportado | Recalculado | Delta | Veredito |
|---------|-----------|-------------|-------|----------|
| Sharpe BR HOLDOUT | 2.42 | ... | ... | ... |
| Sharpe US HOLDOUT | 1.19 | ... | ... | ... |
| MDD BR HOLDOUT | -6.3% | ... | ... | ... |
| MDD US HOLDOUT | -28.3% | ... | ... | ... |
| CAGR BR HOLDOUT | 31.1% | ... | ... | ... |
| CAGR US HOLDOUT | 35.5% | ... | ... | ... |
| Switches BR HOLDOUT | ? | ... | ... | ... |
| % cash BR HOLDOUT | ~85% | ... | ... | ... |

## Scripts de verificação produzidos
[Lista de scripts Python escritos, o que cada um faz, e como reproduzir]

## Veredito final
[APROVADO / REPROVADO / INCONCLUSIVO com justificativa detalhada]
```

## ARQUIVOS-CHAVE PARA RECÁLCULO

Para acelerar a Frente 3 (sua frente mais importante), aqui estão os paths dos dados numéricos que contêm as equity curves:

```
# Equity curves (parquet):
src/data_engine/portfolio/T107_PORTFOLIO_CURVE_DUAL_MODE_EXPANDED_ML_TRIGGER.parquet  ← BR winner
src/data_engine/portfolio/T122_US_ENGINE_WINNER_CURVE_DAILY.parquet                    ← US winner

# Configs com métricas reportadas (JSON):
src/data_engine/portfolio/T107_BACKTEST_INTEGRATED_EXPANDED_SELECTED_CONFIG.json
src/data_engine/portfolio/T107_BASELINE_SUMMARY_INTEGRATED_EXPANDED.json
src/data_engine/portfolio/T122_SELECTED_CONFIG_US_ENGINE_NPOS_CADENCE.json

# Dados macro (para calcular risk-free):
src/data_engine/ssot/SSOT_MACRO_EXPANDED.parquet  ← contém cdi_log_daily e fed_funds_rate

# Manifests (para SHA256):
outputs/governanca/T107-BACKTEST-INTEGRATED-EXPANDED-V1_manifest.json
outputs/governanca/T122-US-ENGINE-ABLATION-NPOS-CADENCE-V1_manifest.json
outputs/governanca/T128-BR-US-BRL-DASHBOARD-V2_manifest.json

# Universe:
outputs/governanca/T084-US-INGEST-SP500-BRAPI-V2_evidence/universe_snapshot_used.csv
```

Estes paths são dicas para começar. Você **DEVE** verificar se existem outros artefatos que contradizem estes.

## LEMBRETE FINAL

Você foi contratado para ser **matemático**, não diplomático. Recalcule tudo. Cruze tudo. Se os números batem, aprove. Se não batem, reprove. Se faltar dado para concluir, marque INCONCLUSIVO e diga exatamente o que falta.

**Outro auditor independente (com foco em raciocínio lógico, não numérico) está auditando o mesmo repositório simultaneamente.** Vocês não se comunicam. Se ambos concordarem, a confiança é alta. Se divergirem, o dono do projeto investigará o ponto de divergência.

Comece.
