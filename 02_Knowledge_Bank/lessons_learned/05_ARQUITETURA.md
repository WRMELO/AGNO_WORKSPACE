# Lessons Learned — Arquitetura

> Consolidação temática de todas as lições sobre decisões estruturais: motor, forno dual-mode, fábricas, sinais de regime.
> Fonte: phases 2, 3, 4, 5, 6, 10. Originais em `archive/by_phase/`.

---

## 1. Dois modos de forno (T037 vs T067)

**Descoberta fundamental**: T037 ("plena carga") e T067 ("controle de regime") são dois modos estruturalmente diferentes do mesmo motor. A diferença não é paramétrica — é de processo.

| Dimensão | Modo T037 (plena carga) | Modo T067 (controle de regime) |
|---|---|---|
| Disjuntor | Binário (CEP/SPC) | Gradual (market slope) |
| Cadência | Rápida (~13d) | Lenta (~10 pregões) |
| Reentrada | Sem bloqueio | Via histerese |
| Tank (caixa) | Seco (~5% cash) | Gordo (~19% cash) |
| Regime defensivo | Sem | Com (72% do tempo) |

- Phase 4 (LL-PH4-007). Evidência: decomposição por período (base 100) mostra separação dramática — T037 +186.7% vs +70.9% no P1; T067 +101.9% vs -35.4% no P2 (LL-PH4-010).

## 2. Sinal endógeno, não exógeno

**Regra**: o sinal para comutar entre modos não vem do mercado (MA200, volatilidade, slope do Ibovespa). Todos dão ~49% vs 51% na decomposição dia a dia. O sinal vem de dentro do próprio forno: retorno rolling dos burners ativos vs CDI.

- Phase 4 (LL-PH4-009). Burners > CDI → modo T037. Burners < CDI → modo T067.

## 3. Três variáveis de processo do forno

A vantagem de cada modo depende da interação entre: (1) **produtividade dos burners**, (2) **velocidade de reposição**, (3) **custo de oportunidade do tank**.

- Phase 4 (LL-PH4-008). Framework de engenharia de processos que orienta todas as decisões de arquitetura.

## 4. Conceito dual-mode validado (T072)

O motor dual-mode com termostato endógeno (SPEC-007) funciona. T072 = R$407k, melhor resultado absoluto do projeto à época. A comutação endógena produz resultado superior ao de qualquer estratégia individual.

- Phase 5 (LL-PH5-001). Conceito validado. Limitação: termostato determinístico esgotou (feasibility 0.6%).

## 5. Sinal SINAL-1 vs SINAL-2

- **SINAL-1** (positions_value_end): 0/162 candidatos feasíveis. Estruturalmente lento — só reage depois que posições já perderam valor (LL-PH5-005).
- **SINAL-2** (net excess equity vs CDI): 2/162 feasíveis, winner na fronteira (LL-PH5-006).

## 6. Migrar decisor para sinal exógeno remove dependência circular

Quando o decisor usa dados da própria carteira (portfolio_logret), `n_positions=0` cria estado absorvente. Migrar para market slope (sinal do Ibovespa) remove a dependência.

- Phase 3 (LL-PH3-006). Solução definitiva para o problema da armadilha do defensivo.

## 7. Complexidade incremental pode destruir valor

**Princípio**: aumento de complexidade pode degradar retorno sem melhorar risco.

- Phase 2 (LL-PH2-005). Princípio fundacional.
- Phase 10 (LL-PH10-007). Trigger ML v2 adicionou alto custo (60 features + modelo + API FRED + tuning) para ganho marginal (+0.79pp CAGR) e Sharpe inferior ao motor puro T122.

## 8. Fábricas BR e US independentes

**Decisão arquitetural**: as duas fábricas operam com capital próprio, sem split, sem interdependência operacional. Consolidação em BRL via PTAX é apenas visualização financeira.

- Phase 9 (LL-PH9-009), Phase 10 (LL-PH10-003, LL-PH10-012).
- Justificativa: split ótimo (20% US) produz ganho marginal de Sharpe (+0.06) com perda de 3.2pp CAGR (LL-PH9-005).

## 9. Especificação formal antes de execução

O ciclo Spec → Engine → Plotly funciona. A SPEC-007 (termostato) com glossário, regras de transição e desenho mínimo da ablação permitiu execução limpa na primeira tentativa.

- Phase 5 (LL-PH5-002). Padrão adotado para tasks complexas.

---

## Princípios arquiteturais consolidados

1. O motor tem dois modos estruturais (não paramétricos)
2. Sinal de comutação é endógeno (produtividade vs CDI), não exógeno (mercado)
3. Dependência circular no decisor → estado absorvente → usar sinal exógeno
4. Complexidade deve ser justificada por ganho mensurável
5. Fábricas independentes com moeda própria
6. Especificar formalmente antes de executar
