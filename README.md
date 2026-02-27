# AGNO_WORKSPACE

## Ambiente (reprodutibilidade)

- Python obrigatório: `.venv` local do workspace
- Interpretador: `/home/wilson/AGNO_WORKSPACE/.venv/bin/python`
- Instalação de dependências:

```bash
/home/wilson/AGNO_WORKSPACE/.venv/bin/pip install -r requirements.txt
```

## Execução do baseline STATE 3

```bash
/home/wilson/AGNO_WORKSPACE/.venv/bin/python scripts/t037_m3_canonical_engine.py
/home/wilson/AGNO_WORKSPACE/.venv/bin/python scripts/t038_master_gate_regime.py
/home/wilson/AGNO_WORKSPACE/.venv/bin/python scripts/t039_severity_partial_sells.py
/home/wilson/AGNO_WORKSPACE/.venv/bin/python scripts/t040_metrics_suite.py
/home/wilson/AGNO_WORKSPACE/.venv/bin/python scripts/t041_plotly_comparative.py
```

## Política de artefatos (governança)

- Baseline visual oficial: `outputs/plots/T041_STATE3_PHASE1_COMPARATIVE.html`
- Outputs voláteis em `outputs/` são ignorados por padrão.
- Summaries e métricas de baseline em `src/data_engine/portfolio/` são mantidos para rastreabilidade.

## Sanity check rápido

```bash
/home/wilson/AGNO_WORKSPACE/.venv/bin/python scripts/state3_sanity_check.py
```
