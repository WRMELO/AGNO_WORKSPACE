# Baseline scan por estabilidade (EXP)

## Método
- Subgrupos sobrepostos (rolling) com stride=1.
- Limites Xbarra–R estimados por holdout interno (70% train / 30% test) quando viável.
- Estabilidade medida por violações das regras autorizadas (Xbar/R/Run7; I/MR opcional).

## Parâmetros
- lengths_sessions: [60, 80, 100, 120, 160, 200, 260, 320, 400]
- step_sessions: 5
- N_grid: [2, 3, 4, 5, 6, 7, 8, 9, 10]
- min_effective_subgroups: 25
- use_imr: True

## Notas SPC
- Holdout interno aplicado conforme especificação.

## Recomendação técnica
- Melhor global: 2023-11-16 → 2024-04-11 | N=2 | weighted_violations=0
