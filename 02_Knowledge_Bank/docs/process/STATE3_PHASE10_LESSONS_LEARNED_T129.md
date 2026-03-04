# STATE 3 Phase 10 - Lessons Learned (T129)

**Gerado em**: 2026-03-04T21:42:26Z  
**Task**: T129  
**Ciclo coberto**: T119 -> T120 -> T121 -> T122 -> T123 -> T124 -> T125 -> T126 -> T127 -> T128  
**Winner Fabrica BR (inalterada)**: C060X canonic (Sharpe ~2.42, MDD ~-6.3%)  
**Winner Fabrica US (declarado em T127)**: T122 pure engine (TopN=5, cadence=10, cost=1bp)

## 1) Contexto do ciclo

- **Escopo**: construir e consolidar o motor US de selecao de acoes para benchmark contra SP500 buy-hold, mantendo BR e US como fabricas independentes (decisao do Owner).
- **Objetivo-mestre**: elevar qualidade do motor US com selecao de ativos (nao apenas timing de indice), com governanca forte (walk-forward, anti-lookahead, manifest, changelog, auditoria).
- **Fases cobertas**:
  - 10A: base US canonica e score diario (T119-T120)
  - 10B: backtest do motor US e ablacao N/cadencia (T121-T122)
  - 10C: trilha ML trigger v2 (features, modelo, tuning: T123-T125)
  - 10D: integrado + declaracao de winner US (T126-T127)
  - 10E: painel BR+US em BRL (T128 V2)
- **Resultado final de produto**:
  - Winner US oficial: **T122** (simplicidade + robustez de processo)
  - Trigger T126: **abandonado para producao**, mantido como baseline informativo
  - Painel BR+US em BRL: **visualizacao apenas**, sem split e sem interdependencia operacional

## 2) O que deu certo

- **LL-PH10-001 (PROCESSO)**: a trilha em blocos (SSOT -> score -> motor -> trigger -> integracao -> declaracao -> dashboard) manteve rastreabilidade ponta-a-ponta com evidencias auditaveis.
- **LL-PH10-002 (GOVERNANCA)**: anti-lookahead e walk-forward foram mantidos de forma consistente no ciclo inteiro, reduzindo risco de leakage.
- **LL-PH10-003 (ARQUITETURA)**: separacao BR/US com capital proprio simplificou decisao de produto e evitou sobre-otimizacao de split historico.
- **LL-PH10-004 (DECISAO TECNICA)**: declaracao formal do winner em `T127_US_WINNER_DECLARATION.json` eliminou ambiguidade operacional para ciclos seguintes.
- **LL-PH10-005 (RECUPERACAO DE QUALIDADE)**: o replanejamento T128 V2 corrigiu com sucesso o erro semantico do V1 (BR winner errado), preservando governanca e coerencia de negocio.

## 3) O que não deu certo

- **LL-PH10-006 (PRODUTO)**: o hard constraint de risco **MDD HOLDOUT >= -0.15** nao foi atingido no integrado T126 (`mdd_holdout_integrated=-0.2468`), apesar de melhora relativa vs T122.
- **LL-PH10-007 (COMPLEXIDADE)**: o trigger ML v2 adicionou alto custo de manutencao (feature stack + modelo + tuning + histerese) para ganho marginal, com Sharpe HOLDOUT inferior ao T122.
- **LL-PH10-008 (SEMANTICA DE DADOS)**: T128 V1 falhou por usar arquivo incorreto como BR winner (`T108...`) em vez do canonic C060X; reforca necessidade de contracto de semantica de input.
- **LL-PH10-009 (SCHEMA COMPATIBILITY)**: a divergencia de schema entre curvas BR exigiu adaptacao explicita no V2 (`equity_end_norm` e `ret_cdi`), mostrando que "path certo" nao basta sem validacao de colunas.

## 4) Decisões do Owner

- **LL-PH10-010 (WINNER US)**: adotar **T122** como winner US oficial para operacao.
- **LL-PH10-011 (TRIGGER)**: abandonar trigger T126 para producao e manter como baseline informativo para rastreabilidade historica.
- **LL-PH10-012 (OPERACAO BR+US)**: BR e US seguem **independentes**, com capital proprio; consolidacao em BRL e apenas visual/financeira.
- **LL-PH10-013 (GOVERNANCA)**: manter ciclo obrigatorio Executor -> Auditor -> Curator para promocao de qualquer marco.

## 5) Checklist anti-regressão

1. Manter anti-lookahead estrito (`shift(1)`) em score/feature/execucao.
2. Preservar split temporal canonical (TRAIN/HOLDOUT) e isolamento de selecao em TRAIN.
3. Quando houver hard constraint de produto (ex.: MDD), registrar explicitamente no summary e gate de verificacao.
4. Formalizar winner em artefato declarativo JSON antes de dashboards consolidados.
5. Validar semantica de input (arquivo canonical) e schema minimo esperado antes de gerar visualizacoes.
6. Em comparativos BR+US, manter a regra: visualizacao em BRL nao implica politica de alocacao.
7. Manter `manifest.json` coerente com `ARTIFACT LINKS` e changelog com linha unica por execucao.

## 6) Artefatos de referência

| Artefato | Path |
| --- | --- |
| SSOT US canonic | `src/data_engine/ssot/SSOT_CANONICAL_BASE_US.parquet` |
| Score diario M3-US | `src/data_engine/features/T120_M3_US_SCORES_DAILY.parquet` |
| Curva winner US (T122) | `src/data_engine/portfolio/T122_US_ENGINE_WINNER_CURVE_DAILY.parquet` |
| Summary integrado trigger (T126) | `src/data_engine/portfolio/T126_US_ENGINE_V2_TRIGGER_SUMMARY.json` |
| Declaracao winner US | `src/data_engine/portfolio/T127_US_WINNER_DECLARATION.json` |
| Curva winner BR canonic (C060X) | `src/data_engine/portfolio/CTO_C060_EXPANDED_ABLATION_WINNER_CURVE.parquet` |
| FX PTAX USD/BRL | `src/data_engine/ssot/SSOT_FX_PTAX_USDBRL.parquet` |
| Dashboard BR+US BRL (V2) | `outputs/plots/T128_STATE3_PHASE10E_BR_US_BRL_DASHBOARD_V2.html` |
| Evidencia T128 metrics | `outputs/governanca/T128-BR-US-BRL-DASHBOARD-V2_evidence/metrics_table.json` |

## 7) Fechamento executivo da fase

- A fase 10 entregou motor US operacional e governanca robusta.
- Em decisao de engenharia de processo, o sistema convergiu para **simplicidade vencedora** (T122) em vez de complexidade incremental (T126).
- A principal licao estrutural: quando ganho tecnico marginal vem com custo alto de complexidade e piora de risco/claridade operacional, a decisao correta e padronizar o baseline mais simples e rastreavel.
