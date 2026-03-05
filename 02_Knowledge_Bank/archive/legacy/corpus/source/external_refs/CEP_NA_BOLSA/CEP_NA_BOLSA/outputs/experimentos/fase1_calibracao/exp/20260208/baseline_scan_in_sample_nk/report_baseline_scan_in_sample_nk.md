# Baseline scan in-sample por (N,K)

## Método
- Subgrupos sobrepostos (rolling), stride=1.
- In-sample: limites estimados e avaliados nos mesmos K subgrupos.

## Regras usadas
- rules_used: ['XBAR_RULE1', 'R_RULE1', 'XBAR_RUN7_RULE2', 'I_RULE1_OPTIONAL', 'MR_RULE1_OPTIONAL']

## Constantes SPC
- A2/D3/D4 por N: {3: (1.023, 0.0, 2.574), 4: (0.729, 0.0, 2.282), 5: (0.577, 0.0, 2.114)}

## Resultado
- best_global: 2018-01-05 → 2018-01-18 | N=3 | K=10 | weighted_violations=0 | total_violations=0

## Nota técnica SPC
- Método in-sample pode favorecer K pequeno; risco registrado sem alterar critério.

## Progresso
- progress_mode: tqdm
