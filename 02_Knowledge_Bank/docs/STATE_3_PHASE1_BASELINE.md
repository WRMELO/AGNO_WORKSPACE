# STATE 3 Phase 1 — Baseline (AGNO_WORKSPACE)

## Objetivo

Documentar a baseline **estável** do motor de estratégia canônico (STATE 3) para servir de referência na fase de aprimoramento, mantendo rastreabilidade por artefatos e métricas.

Baseline visual (encerramento da fase): `outputs/plots/T041_STATE3_PHASE1_COMPARATIVE.html`.

## Glossário operacional (fixado pelo Owner)

- **Burner**: ativo individual (processo SPC por ticker).
- **Master**: **carteira/portfólio** (agregado ~10±1 burners).
- **Mercado**: **Ibovespa** `^BVSP` (calendário B3 via BRAPI).
- Fonte: `02_Knowledge_Bank/docs/specs/GLOSSARY_OPERATIONAL.md`.

## Componentes do STATE 3 (camadas)

1. **Ranking de compra (M3 canônico)**  
   \(M3 = z(score\_m0) + z(ret\_{62}) - z(vol\_{62})\)  
   Artefato de scores: `src/data_engine/features/T037_M3_SCORES_DAILY.parquet`.

2. **Master Gate (regime da carteira)**  
   Slope de `portfolio_logret` com histerese assimétrica (2-in / 3-out).  
   Especificação: `02_Knowledge_Bank/docs/specs/SPEC-002_MASTER_GATE_REGIME.md`.

3. **Severity Score + Partial Sells (D+1)**  
   Score multi-fator (downside band + persistência + evidência Nelson/WE proxy) e vendas parciais 25/50/100%.  
   Especificações:  
   - `02_Knowledge_Bank/docs/specs/SPEC-001_SEVERITY_SCORE.md`  
   - `02_Knowledge_Bank/docs/specs/SPEC-003_PARTIAL_SELLS.md`  
   - `02_Knowledge_Bank/docs/specs/SPEC-004_NELSON_RULES_INTEGRATION.md`

4. **Metrics Suite (SPEC-005)**  
   Materialização das métricas (17) e segmentações (regime/subperíodo).  
   Spec: `02_Knowledge_Bank/docs/specs/SPEC-005_METRICS_SUITE.md`  
   Artefatos: `src/data_engine/portfolio/T040_*`.

5. **Plotly comparativo (encerramento)**  
   5 curvas (T037/T038/T039/CDI/Ibov), shading do regime defensivo e tabela de métricas T040.  
   Artefato: `outputs/plots/T041_STATE3_PHASE1_COMPARATIVE.html`.

## Fonte de dados e semântica do CDI (correta)

- SSOT Macro: `src/data_engine/ssot/SSOT_MACRO.parquet`
- Campo canônico: `cdi_log_daily`
- Interpretação correta (BCB série 12 = taxa **diária** em %):  
  - `cdi_log_daily = log1p(cdi_rate_daily_pct / 100)`  
  - `cdi_daily = exp(cdi_log_daily) - 1`
- Sanity gate implementado nos scripts de simulação compara:
  - `prod(1 + cdi_daily)` vs `exp(sum(cdi_log_daily))`
  - erro relativo esperado: ~0.

## Artefatos oficiais (Phase 1)

### SSOT

- `src/data_engine/ssot/SSOT_CANONICAL_BASE.parquet`
- `src/data_engine/ssot/SSOT_MACRO.parquet`
- `src/data_engine/ssot/SSOT_QUALITY_BLACKLIST_A001.json`

### Curvas / Ledgers / Summaries

- `src/data_engine/portfolio/T037_PORTFOLIO_CURVE.parquet`
- `src/data_engine/portfolio/T038_PORTFOLIO_CURVE.parquet`
- `src/data_engine/portfolio/T039_PORTFOLIO_CURVE.parquet`
- `src/data_engine/portfolio/T037_BASELINE_SUMMARY.json`
- `src/data_engine/portfolio/T038_BASELINE_SUMMARY.json`
- `src/data_engine/portfolio/T039_BASELINE_SUMMARY.json`

### Métricas e Plot

- `src/data_engine/portfolio/T040_METRICS_COMPARATIVE.json`
- `src/data_engine/portfolio/T040_METRICS_BY_REGIME.csv`
- `src/data_engine/portfolio/T040_METRICS_BY_SUBPERIOD.csv`
- `outputs/plots/T041_STATE3_PHASE1_COMPARATIVE.html`

## Resultados (baseline atual)

Período: 2018-07-02 .. 2026-02-26 (1902 pregões).

| Variante | Equity final (R$) | CAGR | MDD | Sharpe | CDI final (R$) | Ibov final (R$) |
|---|---:|---:|---:|---:|---:|---:|
| T037 (M3 puro) | 188.809 | 8,79% | -45,04% | 0,56 | 191.639 | 262.225 |
| T038 (M3 + Gate) | 123.163 | 2,80% | -47,89% | 0,25 | 191.639 | 262.225 |
| T039 (M3 + Gate + Severity) | 124.704 | 2,97% | -44,94% | 0,25 | 191.639 | 262.225 |

Baseline visual oficial: T041.

## Reexecução (reprodutibilidade)

Executar sempre via `.venv` do workspace:

- `/home/wilson/AGNO_WORKSPACE/.venv/bin/python scripts/t037_m3_canonical_engine.py`
- `/home/wilson/AGNO_WORKSPACE/.venv/bin/python scripts/t038_master_gate_regime.py`
- `/home/wilson/AGNO_WORKSPACE/.venv/bin/python scripts/t039_severity_partial_sells.py`
- `/home/wilson/AGNO_WORKSPACE/.venv/bin/python scripts/t040_metrics_suite.py`
- `/home/wilson/AGNO_WORKSPACE/.venv/bin/python scripts/t041_plotly_comparative.py`

## Próximos passos (fase de aprimoramento)

- Guardrails anti-deriva (turnover caps, etc.) e reavaliação de ablations.
- Métricas adicionais dependentes de oracle/ground truth (`missed_sell_rate`, `false_sell_rate`, `regret_3d`).
- Integração RL (quando priorizado).

