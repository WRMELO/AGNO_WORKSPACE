# STATE 3 Local Rule Capture Protocol (T043-CAPTURE-V2)

## Terminologia (Mandatoria)

Fonte de verdade: `02_Knowledge_Bank/docs/specs/GLOSSARY_OPERATIONAL.md`.

- **Master** = carteira/portfolio operacional (agregado de burners).
- **Mercado** = Ibovespa (`^BVSP`).

### Regra de bloqueio terminologico

- E proibido usar `Master` para se referir ao Ibovespa.
- Qualquer sinal derivado de `^BVSP` deve ser rotulado como `Mercado`.
- Toda regra deve declarar escopo: `Mercado` ou `Master`.
- Violacao desta regra invalida a captura (`G0_GLOSSARY_COMPLIANCE = FAIL`).

## Objetivo

Capturar regras locais fortes, deterministicas e auditaveis que operem apenas sob condicoes definidas, sem misturar politicas antagonicas bull/bear no mesmo estado.

Este protocolo e de controle operacional (CEP/SPC), nao de previsao de mercado.

## Principios operacionais

1. Somente informacao disponivel ate t (sem look-ahead).
2. Regras devem ser explicaveis e rastreaveis por evidencia.
3. Estados operacionais devem ser mutuamente exclusivos.
4. Histerese e permitida apenas para transicao entre estados.
5. Politica local so atua no estado onde foi validada.

## Processo de captura

### Etapa 1 - Definicao formal do problema de deriva

Fixar metricas de controle da deriva (ex.: pico->fim, end_drawdown, underwater_frac, days_since_peak, switches, blocked_buys, share defensivo).

### Etapa 2 - Condition Ledger

Construir ledger diario unificado com dois blocos independentes:

- Bloco `Mercado` (Ibovespa): sinais CEP/SPC + Nelson/WE sobre series do mercado.
- Bloco `Master` (Carteira): sinais e metricas agregadas da carteira.

Regras de captura devem consumir o ledger, nunca dados avulsos.

### Etapa 3 - Catalogo de episodios

Segmentar o historico em episodios por persistencia de sinais.
Para cada episodio, calcular comportamento de risco/retorno e custos operacionais.

### Etapa 4 - Decisor de estados

Especificar maquina de estados deterministica, com entrada/saida claras e estados mutuamente exclusivos.
Base primaria do decisor: condicoes de `Mercado` (Ibovespa), podendo usar confirmacao do bloco `Master` quando explicitado.

### Etapa 5 - Regras locais por estado

Cada estado recebe um conjunto proprio de regras locais.
Regra local deve declarar:

- escopo (`Mercado` ou `Master`);
- estado valido;
- gatilhos CEP/SPC/Nelson/WE;
- acao operacional;
- criterio de saida/invalidacao.

E proibido usar simultaneamente condicoes bull e bear dentro do mesmo estado.

### Etapa 6 - Robustez e promocao

Promover regra apenas se houver robustez por subperiodo e evidencia de reducao de deriva sem degradacao estrutural relevante.

## Gates obrigatorios

- `G0_GLOSSARY_COMPLIANCE`: Master!=Mercado e nomenclatura correta.
- `G1_CONDITION_LEDGER_PRESENT`: ledger diario gerado e documentado.
- `G2_EPISODE_CATALOG_PRESENT`: episodios catalogados com metricas.
- `G3_DECISOR_STATE_MACHINE_SPEC`: especificacao da maquina de estados.
- `G4_LOCAL_RULE_CANDIDATES`: regras locais candidatas documentadas.
- `G5_ROBUSTNESS_SUBPERIODS`: validacao por subperiodos concluida.

Qualquer gate em `FAIL` bloqueia promocao de regra para baseline.

## Fora de escopo nesta fase

- Nao introduzir RL/Q-learning antes de estabilizar o controlador deterministico local.
- Nao adicionar novas camadas de ativos remuneradores para substituir caixa nesta etapa.
