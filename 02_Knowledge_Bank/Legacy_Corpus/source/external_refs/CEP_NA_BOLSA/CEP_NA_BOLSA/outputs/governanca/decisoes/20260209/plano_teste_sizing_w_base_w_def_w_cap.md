# Plano de Testes (Fase I) — Sizing w_base / w_def / w_cap

## Contexto e objetivo
Definir, de forma governada, parâmetros de sizing para Queimadores,
produzindo evidências numéricas (tabelas/relatórios) para decisão do Owner,
sem fixar valores finais nesta fase.

## Definições operacionais
- w_base: peso alvo em regime normal (RISK_ON), por ativo elegível.
- w_def: patamar defensivo mínimo após redução, por ativo (RISK_OFF).
- w_cap: teto máximo por ativo (limite de concentração).

## Regras e restrições
- Fase I (calibração): foco em estabilidade do controlador, não em previsão.
- Compras apenas na janela semanal e somente quando permitido pelo Master.
- Em RISK_OFF: compras proibidas; redução defensiva permitida.
- Em PRESERVAÇÃO_TOTAL: zeragem total e 100% caixa.
- Não criar regras CEP novas; apenas testar parâmetros de sizing e persistência.

## Parâmetros de persistência a testar
- Persistência para reduzir -> zerar em RISK_ON.
- Persistência para reduzir -> zerar em RISK_OFF.

## Grid inicial sugerido (candidatos)
- w_base: 0.08, 0.10, 0.12
- w_def: 0.03, 0.05, 0.07
- w_cap: 0.15, 0.20, 0.25
- persist_reduce_to_zero (RISK_ON): 1, 2, 3
- persist_reduce_to_zero (RISK_OFF): 1, 2

## Métricas de avaliação (outputs)
- % tempo em caixa
- nº de reduções
- nº de zeragens
- tempo médio para reentrada
- nº de operações / turnover
- violações de limites de carteira (ex.: máximo por ativo)
- indicadores de estabilidade do portfólio (carta/violação, se aplicável)

## Critérios de seleção final (decisão do Owner)
- Priorizar estabilidade CEP do portfólio e disciplina de risco.
- Desempatar por menor churn/turnover e menor número de zeragens, se aplicável.
- Registrar explicitamente as razões da escolha no decision package.

## Outputs esperados por task
- Dataset/estado de simulação (governado via Agno).
- Resultados do grid (tabelas consolidadas).
- Decision package com recomendações não vinculantes.

## Em caso de erro na resposta (não no código)
- Qual janela semanal de compra deve ser usada (1º pregão, último pregão ou parametrizável)?
- O limite máximo por ativo (w_cap) será fixo ou também varrido?
- As métricas devem priorizar estabilidade CEP ou incluir métricas financeiras como secundárias?

Gerado em: 2026-02-09T14:54:48Z
