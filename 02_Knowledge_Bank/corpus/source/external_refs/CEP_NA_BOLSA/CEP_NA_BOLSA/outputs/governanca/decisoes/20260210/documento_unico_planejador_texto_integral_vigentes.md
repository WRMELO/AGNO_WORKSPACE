# Documento Único — Texto Integral dos Documentos Vigentes

## 1) Constituição vigente
Fonte: `docs/00_constituicao/CEP_NA_BOLSA_CONSTITUICAO_V2_20260204.md`

---
# Constituição Operacional do Projeto CEP_NA_BOLSA — Versão 2 (Consolidada)

Data: 2026-02-04 (America/Sao_Paulo)  
Status: Vigente  
Substitui: CEP_NA_BOLSA_CONSTITUICAO_V1.md

## 0. Propósito desta Constituição

Este documento é a âncora conceitual e operacional do projeto CEP_NA_BOLSA. Ele define o que é permitido, o que é proibido e como o projeto deve evoluir com rastreabilidade, disciplina e auditabilidade. Qualquer mudança conceitual exige atualização formal desta Constituição antes de execução.

---

## 1. Propósito do Projeto

O projeto CEP_NA_BOLSA tem como objetivo desenvolver um sistema de gestão e operação de ativos financeiros baseado exclusivamente em Controle Estatístico de Processo (CEP), aplicando princípios clássicos de engenharia de processos (Western Electric / Nelson Rules) ao mercado de ações e BDRs.

O foco do projeto não é previsão, não é narrativa de mercado e não é otimização prematura, mas sim operar somente quando o processo estiver sob controle, bloquear risco quando houver evidência estatística de causa especial, selecionar ativos com base em estabilidade e resultado (sempre condicionado ao CEP) e manter auditabilidade total das decisões.

O projeto é pessoal, experimental e engenheirado, sem compromissos com práticas comerciais de mercado.

Frase-guia do projeto:

“Não operar processos fora de controle.”

---

## 2. Filosofia Central

O mercado é tratado como processo estocástico com rupturas, não como sistema causal previsível. O CEP é a camada primária de decisão, acima de qualquer modelo ou ranking. Nenhuma decisão operacional é tomada fora das regras CEP formalmente definidas. Toda sofisticação futura (ML, fatores, etc.) só pode existir dentro de um regime estatisticamente sob controle.

---

## 3. Arquitetura de Papéis (Obrigatória)

O projeto adota explicitamente a seguinte separação de responsabilidades:

- Owner (Você)  
  Responsável por objetivos, validações finais, decisões estratégicas e aceitação dos artefatos.

- Planejador (ChatGPT – este papel)  
  Responsável por definir constituições, regras e planos de trabalho; manter coerência metodológica; evitar improvisação; escrever documentos estruturantes; e nunca pular etapas.

- Orquestrador (Agno)  
  Responsável por organizar tarefas em etapas claras; garantir rastreabilidade; executar planos aprovados; registrar logs e resultados.

- Agente (Cursor + modelo de código)  
  Responsável por implementação técnica (código); execução fiel das tarefas definidas; não tomar decisões conceituais.

Regra de ouro: o Planejador não codifica; o Agente não decide; o Orquestrador não interpreta.

---

## 4. Ferramentas Oficiais do Projeto

Estas ferramentas fazem parte formal do projeto e devem continuar sendo usadas:

- Agno  
  Organização do trabalho em tasks; execução ordenada e rastreável; registro de resultados intermediários.

- Cursor  
  Implementação técnica; execução de código; interface prática com o Agno.

- Obsidian  
  Registro histórico; decisões importantes; versões conceituais; diário do projeto.

- Mermaid (Obsidian ou online)  
  Fluxos operacionais; sequência de decisão CEP; estados do Master e dos Queimadores.

- Miro  
  Mapas mentais; exploração conceitual; organização de ideias antes de formalização.

Regra de governança do Obsidian: o vault do Obsidian não entra no git. Porém, toda decisão relevante deve ser replicada em documentos versionados no repositório (por exemplo, em docs/), para rastreabilidade e governança.

---

## 5. Estrutura Conceitual do Sistema

O sistema é dividido em duas camadas principais, ambas regidas por CEP clássico.

### 5.1 Master (Gate Master)

O Master representa o regime agregado do mercado e decide se compras são permitidas e se o sistema entra em modo de preservação. O Master não seleciona ativos. Ele usa cartas CEP sobre a variável operacional definida nesta Constituição.

#### 5.1.1 Estados finais do Master (normativos)

Estados finais permitidos (únicos):

- RISK_ON  
- RISK_OFF  
- PRESERVAÇÃO_TOTAL

Precedência operacional: PRESERVAÇÃO_TOTAL > RISK_OFF > RISK_ON.

#### 5.1.2 Definições operacionais dos estados

- RISK_ON: compras permitidas conforme regras do sistema; recomposição e substituições permitidas conforme regra vigente.
- RISK_OFF: compras proibidas; reduções e substituições defensivas permitidas conforme regra vigente; preservação parcial.
- PRESERVAÇÃO_TOTAL: compras proibidas e preservação de capital com precedência máxima. Regra operacional obrigatória: venda total dos ativos (zeragem completa da carteira; 100% em caixa). Somente são permitidas ações defensivas necessárias para efetivar a zeragem.

#### 5.1.3 Regras que definem estados (Master)

Regras efetivamente usadas/assumidas para o Master:

- STRESS_I: Regra 1 (ponto além do LCL) na carta I aplicada a X_t.
- STRESS_AMP: amplitude fora de controle (MR/R > UCL).
- TREND_RUN7: 7 pontos consecutivos do mesmo lado da linha central (abaixo da CL) aplicada à leitura de tendência do Master (Xbarra em subgrupos).

O estado composto RISK_OFF é derivado da lógica vigente do Gate (stress e/ou tendência). PRESERVAÇÃO_TOTAL tem precedência máxima quando definido pelo Gate (ver 5.1.2).

#### 5.1.4 Tabela-verdade (precedência)

- Se PRESERVAÇÃO_TOTAL ativo: estado final = PRESERVAÇÃO_TOTAL.
- Senão, se RISK_OFF ativo: estado final = RISK_OFF.
- Senão: estado final = RISK_ON.

### 5.2 Queimadores (Ativos Individuais)

Cada ativo é tratado como um processo independente. O Queimador decide manter, reduzir, zerar e tornar-se elegível novamente. Não há quarentena fixa arbitrária. Reentrada ocorre quando o processo volta a estar sob controle estatístico.

#### 5.2.1 Regras e consequências operacionais (Queimadores)

- Stress do queimador: Regra 1 na carta I e/ou amplitude fora de controle (MR/R > UCL) — consequência operacional típica: zera (conforme regras já vigentes no CEP_NA_BOLSA).
- Tendência do queimador: Regra 2 na leitura de tendência (Xbarra em subgrupos) — consequência operacional típica: reduzir, podendo evoluir a zera conforme regra vigente e persistência (sem inventar percentuais).
- Regra 4 nos queimadores: diagnóstico para qualificar instabilidade e endurecer reentrada, mas sem gatilho único.

Apenas regras CEP clássicas são permitidas para declarar “fora de controle”.

---

## 6. Dados, SSOTs e Variável Fundamental

### 6.1 Princípio de Separação: Universo versus Dados de Mercado

O projeto separa, de forma mandatória, duas categorias de dados:

- Fonte de universo (SSOT): lista oficial e versionada dos ativos elegíveis por classe (Ações e BDRs), obtida de fontes institucionais.
- Fonte de dados de mercado: provedor de cotação e histórico utilizado para compor séries temporais e derivar a variável operacional.

É proibido usar provedor de dados de mercado como SSOT de universo.

### 6.2 SSOT de Universo (listagem oficial)

- Ações: SSOT institucional baseado em fonte oficial da B3 (artefato e método de extração definidos por task dedicada).
- BDRs: SSOT institucional baseado na B3 como fonte primária do universo negociável, com a CVM como validação/regulatório complementar em fase posterior.

Todo SSOT deve ser versionado, possuir manifesto (fonte, data, critérios, hash) e auditoria (contagens, duplicidades, chaves e campos críticos).

### 6.3 Fonte de Dados de Mercado (cotação e histórico)

Fonte de dados de mercado (cotação e histórico): BRAPI.

A BRAPI é utilizada exclusivamente como provedor de dados de mercado para ativos individuais, servindo ao enriquecimento de séries temporais necessárias ao cálculo da variável operacional. A BRAPI não é, em nenhuma hipótese, fonte de universo (SSOT) para ações ou BDRs.

### 6.4 SSOT de Preços Brutos e Base Operacional Unificada

Os dados de mercado serão organizados em duas camadas distintas e complementares:

- SSOTs de preços brutos (Close em valor nominal), mantidos separadamente por classe de ativo, com versionamento e manifesto: um SSOT para Ações e um SSOT para BDRs.
- Base operacional unificada do projeto, derivada exclusivamente dos SSOTs de preço bruto, contendo a série operacional para todas as classes de ativos em uma mesma base de análise, com regras de cálculo e auditoria rastreáveis.

A base operacional unificada é a única base autorizada para cartas CEP, regras Western Electric/Nelson e lógica de decisão do Master e dos Queimadores.

### 6.5 Variável Fundamental do Projeto (CEP)

O projeto adota como variável fundamental para Controle Estatístico de Processo a série de log-retorno diário:

X_t = log(Close_t / Close_{t-1})

O CEP do Master e dos Queimadores será construído, calibrado, aplicado e auditado exclusivamente sobre X_t. A utilização de preços em valor bruto (R$ ou índice) não é permitida como variável de controle.

Nenhuma outra variável substitui X_t para fins de controle.

---

## 7. Períodos Oficiais e Fases do Projeto

### 7.1 Período de Dados (cobertura do projeto)

O projeto manterá SSOT de séries (preços brutos) e base operacional (X_t) no intervalo de 01/01/2018 até o presente, com versionamento por data de geração e manifesto associado. Este período define cobertura histórica e não define calibração.

### 7.2 Período-base do CEP (calibração)

A Constituição exige a existência de um período-base contíguo de calibração do CEP, usado exclusivamente para estimar limites de controle, parâmetros e estabilidade do controlador.

O período-base de calibração será definido formalmente em momento posterior por decisão do Owner e registrado por task dedicada, com evidências, manifesto e auditoria. Não existe ano base fixo pré-declarado nesta versão.

### 7.2.1 Método de seleção do período-base do Master (Xbarra–R)

Definição de acerto por score de evento: D ou D+1 = 100; D+2 = 80; D+3 ou D+5 = 50; demais = 0. Para cada evento, usa-se o maior score observado; o score do período é a soma dos scores dos eventos.

Procedimento: usar carta Xbarra–R no Master variando N (subgrupo), começando em N=2; selecionar o melhor período por score; congelar o período; aumentar N (3, 4, ...) e avaliar se o score melhora.

Desempate: em empate de score total entre períodos candidatos, escolher o período com **menor número de sessões**.

Nota de governança: eventos sistêmicos são referência ex post para auditoria/seleção e não alteram a lógica CEP do monitoramento.

### 7.2.2 Parâmetros operacionais padrão da Fase de Teste (Master)

Parâmetros de candidatos de baseline: min_sessoes=60; max_sessoes=400; comprimentos_testados=[60,80,100,120,160,200,260,320,400]; estrategia=janela_deslizante; passo_sessoes=5.

Parâmetros do scan de N: N_max=10 (scan N=3..10, com baseline congelado selecionado em N=2).

Nota de governança: o snapshot deve registrar os valores usados e qualquer desvio desses parâmetros.

### 7.2.3 Baseline único do Master (congelado)
Baseline único: 2018-10-03 → 2019-01-04 (K=60 subgrupos), com N_master=3.
Limites congelados (EXP_029):
- Xbarra–R: CL=0.002264819106910559; LCL=-0.026588621725635364; UCL=0.03111825993945648; R_CL=0.028204731996623583; LCL_R=0.0; UCL_R=0.0725989801593091.
- I–MR: I_CL=0.0019680418505369475; LCL_I=-0.04404841000020794; UCL_I=0.04798449370128184; MR_CL=0.01730218589588008; LCL_MR=0.0; UCL_MR=0.05652624132184022.
Fonte: `outputs/experimentos/fase1_calibracao/exp/20260208/master_backtest_replica_bvsp_kn_scan/best_global.json`.
SSOT canônico: `docs/ssot/master_calibration.json`.
É proibido qualquer baseline alternativo no repositório.
Regra: toda task/runner deve registrar baseline_start/baseline_end/N_master usados (lidos do SSOT) em manifest/report.

### 7.2.4 Subgrupos para Xbarra/R (rolling sobreposto)

Modo: rolling_overlapping, stride=1, janela=N_master.
Exemplo: 1..4, 2..5, 3..6, ...
Eixo temporal: subgroup_end_date.

**Emenda única (Burners):** Para cada Queimador (ativo individual), fixar K=60 subgrupos e N_burner=3. A construção de subgrupos para Xbarra–R deve usar rolling_overlapping (stride=1, janela=N_burner), análogo ao Master. O período-base (baseline) do Queimador é definido e registrado por ticker (SSOT por ticker) e não precisa coincidir com o baseline do Master. Limites e estatísticas do Queimador devem ser estimados exclusivamente a partir do baseline do próprio ticker. Qualquer revisão de baseline (Master ou Queimadores) somente pode ocorrer na Fase III, por decisão explícita do Owner, via task dedicada, preservando rastreabilidade do antes/depois.

### 7.2.5 Templates e runner oficiais (padrão do projeto)

Runner oficial: `src/cep/runners/runner_xbarr_r_plotly_v1.py`.
Templates oficiais: `docs/templates/runner_xbarr_r_plotly_v1.config.json` e `docs/templates/runner_xbarr_r_plotly_v1.usage.md`.
Política plotly: dependency-gated; não instalar automaticamente.
Artefatos gerados devem incluir manifest.json com hashes.

### 7.2.5 Regras CEP autorizadas (Western Electric/Nelson) e uso operacional

Variável base: log-retorno diário (X_t = log(Close_t/Close_{t-1})) como insumo comum.

Cartas autorizadas: Xbarra–R para leitura de tendência/regime; Individuais (I) para eventos; Amplitude (MR ou R, conforme já adotado no projeto) para stress/instabilidade.

Conjunto autorizado de regras (único):

- Regra 1: 1 ponto além do limite de controle (abaixo do LCL / acima do UCL). Gatilho.
- Regra 2: 7 pontos consecutivos do mesmo lado da linha central (acima/abaixo). Gatilho.
- Regra 3: 6 pontos consecutivos em tendência monotônica (subindo/caindo). Auxiliar/opcional (não deve ser gatilho único se não estiver explicitamente ativada).
- Regra 4: 14 pontos alternando acima/abaixo. Diagnóstica (não aciona sozinha mudança de estado).

Uso no Master (Gate):

- Stress do Master: acionado por Regra 1 na carta I (evento extremo negativo) e/ou por amplitude fora de controle na carta de amplitude (MR/R > UCL), conforme a implementação vigente do Master.
- Tendência/regime do Master: Regra 2 aplicada à leitura de tendência (Xbarra em subgrupos). Regra 3 apenas como reforço se explicitamente habilitada. Regra 4 apenas diagnóstico.

Uso nos Queimadores:

- Stress do queimador: Regra 1 na carta I e/ou amplitude fora de controle (MR/R > UCL) — consequência operacional típica: zera (conforme regras já vigentes no CEP_NA_BOLSA).
- Tendência do queimador: Regra 2 na leitura de tendência (Xbarra em subgrupos) — consequência operacional típica: reduzir, podendo evoluir a zera conforme regra vigente e persistência (sem inventar percentuais).
- Regra 4 nos queimadores: diagnóstico para qualificar instabilidade e endurecer reentrada, mas sem gatilho único.

Proibição explícita: quaisquer regras fora deste conjunto (ex.: 2-de-3 além de 2σ, 4-de-5 além de 1σ, 15 dentro de 1σ etc.) não podem acionar ações sem emenda formal da Constituição.

Parâmetros em teste: N/tamanho do subgrupo e k/persistência/histerese (e quaisquer equivalentes já usados nas tasks) permanecem **EM TESTE** e serão definidos/fechados via tasks e evidências do Master; esta subseção não fixa valores numéricos fora do baseline vigente.

### 7.2.6 Evidências auditadas do Gate Master

Relatórios e tabelas auditadas:

- `outputs/master_gate_applicability/20260206/report_master_gate_applicability.md`
- `outputs/master_gate_applicability/20260206/summary_by_rule.csv`
- `outputs/master_gate_applicability/20260206/summary_by_state.csv`

### 7.2.6 Evidências auditadas do Gate Master

Relatórios e tabelas auditadas:

- `outputs/master_gate_applicability/20260206/report_master_gate_applicability.md`
- `outputs/master_gate_applicability/20260206/summary_by_rule.csv`
- `outputs/master_gate_applicability/20260206/summary_by_state.csv`
### 7.3 Fase I (Calibração)

Objetivo: definir parâmetros do controlador (Master e Queimadores), estimar limites de controle e avaliar estabilidade do controlador (não performance financeira), utilizando exclusivamente o período-base definido em 7.2.

Regras: nenhuma execução de cartas CEP do Master é considerada válida sem a task específica de definição e geração da série do Master (fonte, artefato, auditoria e fallback) e sem a definição formal do período-base.

### 7.4 Fase II (Aplicação e Validação)

Objetivo: aplicar o controlador calibrado e observar comportamento no tempo, validando decisões do Gate Master e analisando entradas e saídas dos Queimadores.

A aplicação e validação deve cobrir:
- Período pré-base: 01/01/2018 até o início do período-base.
- Período pós-base: fim do período-base até o presente.

Produto obrigatório: relatório de validação registrando violações CEP, segmentos fora de controle e métricas de comportamento do controlador, sem alteração de parâmetros durante esta fase.

### 7.5 Eventos Externos (anotação ex post)

Justificativas por “eventos externos reconhecidos” são permitidas apenas como anotação ex post para auditoria e entendimento do comportamento do processo nos pontos fora de controle. Essas anotações não alteram o resultado CEP nem mudam parâmetros automaticamente. O registro deve ser versionado e rastreável.

### 7.6 Fase III (Revisão e Re-baseline)

A calibração estatística do CEP (definição de limites e parâmetros) é congelada durante a Fase II e não pode ser recalibrada por critérios automáticos, por variações aparentes de volatilidade ou por “folga” entre limites e observações.

Qualquer revisão de baseline (re-baseline) só pode ocorrer em uma fase separada de Revisão, e somente mediante decisão manual e explícita do Owner, aplicável tanto ao Master quanto aos Queimadores.

Toda revisão, quando autorizada pelo Owner, deve ser registrada como evento de governança e executada por task dedicada, preservando rastreabilidade completa do antes e do depois (baseline anterior e baseline revisado), sem apagamento de histórico.

---

## 8. Seleção de Ativos para Compra (Condicionada ao CEP)

Quando o Gate Master permitir compras, a seleção segue este princípio:

- Universo elegível: ativos em controle estatístico.
- Avaliação periódica: média de log-retorno em janela e medida de estabilidade.
- Classificação: alta média e baixa dispersão tem prioridade.
- Alocação de capital: respeitando limites de carteira e diversidade.

Métricas de ranking não substituem CEP. CEP define se pode operar; ranking define como operar, sempre dentro do universo e da base operacional definidos nesta Constituição.

---

## 9. Princípios de Qualidade e Disciplina

Nenhuma regra implícita. Nenhuma decisão sem log. Nenhum “jeitinho” fora da Constituição. Nenhuma sofisticação antes de controle estável. Toda mudança conceitual exige atualização formal deste documento.

### 9.1 Proibição de artefatos manuais de estado

Todo artefato de estado do projeto (universo, SSOTs, base operacional, relatórios de calibração/validação/revisão) deve ser produzido por task Agno, com report e evidências. É proibido manter “scripts manuais” como fonte definitiva de estado.

Quando existir legado manual (por exemplo, listas geradas fora de task), ele deve ser substituído por task equivalente antes de ser considerado parte do estado governado do projeto.

### 9.2 Convenção de nomenclatura de tasks

As tasks devem seguir convenção de naming, com prefixos que indiquem a natureza do trabalho e garantam rastreabilidade:

- TASK_CEP_F1_xxx: fase de calibração e consolidação (Fase I).
- TASK_CEP_F2_xxx: fase de aplicação e validação (Fase II).
- TASK_CEP_REV_xxx: fase de revisão e re-baseline (Fase III).
- TASK_CEP_DISC_xxx: tarefas de descoberta/diagnóstico/probe de fontes.
- TASK_CEP_SSOT_xxx: tarefas de construção e versionamento de SSOTs.

É obrigatório que todo artefato “de estado” seja produzido por task e referenciado em report, manifesto e evidências.

### 9.3 Em caso de erro na resposta (não no código)

Quando houver erro na resposta (texto/decisão/planejamento) o agente deve interromper e formular perguntas objetivas ao Owner/Estrategista para identificar causa, evidências necessárias e próximo passo único antes de prosseguir. O objetivo é evitar improviso e garantir correção governada.

---

## 10. Instrução ao Próximo Chat

Este documento inicia e governa o projeto CEP_NA_BOLSA. O Planejador deve respeitar integralmente esta Constituição, começar pelo plano técnico de execução da Fase I e organizar o trabalho via Agno, priorizando clareza, rastreabilidade e controle estatístico.

Antes de implementar cartas CEP do Master, devem existir (por tasks) os seguintes blocos de base:

- SSOT de universo de Ações (B3) versionado e auditado.
- SSOT de universo de BDRs (B3) versionado e auditado.
- SSOTs de preços brutos (Ações e BDRs) no período 01/01/2018 até o presente.
- Base operacional unificada (X_t) derivada dos SSOTs de preços brutos.
- Task formal definindo a série do Master/Gate de Mercado (fonte, fallback e auditoria). 
- Task formal definindo baseline do Master e N do Xbarra–R, com evidências e manifestação do Owner.

Se algum item acima não estiver disponível em artefatos governados, registrar: [INFORMAÇÃO AUSENTE – PRECISAR PREENCHER].

---

## 2) Emenda vigente
Fonte: `outputs/governanca/emendas/20260210/EMENDA_VOLATILIDADE_EXCECAO_UPSIDE_V1/emenda.md`

---
# Emenda — Volatilidade com exceção de upside

## Regra
- R/MR acima do UCL dispara defesa **apenas se** não houver upside extremo (Xbar>UCL ou I>UCL).
- Upside extremo **não** dispara defesa por volatilidade; segue regras normais.
- Regras de downside (Xbar<LCL ou I<LCL) permanecem soberanas.

## Limites CEP
- Nenhum limite foi recalculado; uso dos limites existentes permanece.

## Artefatos
- decision_table.csv: `outputs/governanca/emendas/20260210/EMENDA_VOLATILIDADE_EXCECAO_UPSIDE_V1/decision_table.csv`
- emenda.json: `outputs/governanca/emendas/20260210/EMENDA_VOLATILIDADE_EXCECAO_UPSIDE_V1/emenda.json`

---

## 3) Definição do baseline do Master
Fonte: `outputs/governanca/decisoes/20260208/master_baseline_definition.md`

---
# Definição do Baseline do Master (^BVSP)

## Contexto
Documento de governança que consolida a trajetória de definição do baseline do Master,
com rastreabilidade dos artefatos e a decisão final aprovada.

## Linha do tempo (tasks e evidências)
- TASK_CEP_DISC_010_MEMORIAL_ESTADO_REPO_20260206
  - report: `planning/runs/TASK_CEP_DISC_010_MEMORIAL_ESTADO_REPO_20260206/report.json`
  - outputs: `outputs/governanca/estado_real/20260206/`
- TASK_CEP_F1_EXP_020_MASTER_BASELINE_SCAN_STABILITY_ROLLINGN_V1
  - report: `planning/runs/TASK_CEP_F1_EXP_020_MASTER_BASELINE_SCAN_STABILITY_ROLLINGN_V1/report.json`
  - outputs: `outputs/fase1_calibracao/exp/20260208/baseline_scan_stability/`
- TASK_CEP_F1_CAL_021_PREPARAR_DECISAO_BASELINE_MASTER_V1
  - report: `planning/runs/TASK_CEP_F1_CAL_021_PREPARAR_DECISAO_BASELINE_MASTER_V1/report.json`
  - outputs: `outputs/fase1_calibracao/cal/20260208/decision_baseline_master/`
- TASK_CEP_F1_CAL_022_SANITY_CHECK_BASELINE_SCAN_N345_V1
  - report: `planning/runs/TASK_CEP_F1_CAL_022_SANITY_CHECK_BASELINE_SCAN_N345_V1/report.json`
  - outputs: `outputs/fase1_calibracao/cal/20260208/sanity_check_n345/`
- TASK_CEP_F1_EXP_029_MASTER_BACKTEST_REPLICA_BVSP_KN_SCAN_V1
  - report: `planning/runs/TASK_CEP_F1_EXP_029_MASTER_BACKTEST_REPLICA_BVSP_KN_SCAN_V1/report.json`
  - outputs: `outputs/experimentos/fase1_calibracao/exp/20260208/master_backtest_replica_bvsp_kn_scan/`
- TASK_CEP_F1_CAL_030_DECISION_PACKAGE_MASTER_BACKTEST_REPLICA_BVSP_KN_V1
  - report: `planning/runs/TASK_CEP_F1_CAL_030_DECISION_PACKAGE_MASTER_BACKTEST_REPLICA_BVSP_KN_V1/report.json`
  - outputs: `outputs/experimentos/fase1_calibracao/cal/20260208/decision_master_backtest_replica_bvsp_kn/`
- TASK_CEP_F1_EXP_031_BASELINE_LIMITS_VIOLATIONS_FULL_V1
  - report: `planning/runs/TASK_CEP_F1_EXP_031_BASELINE_LIMITS_VIOLATIONS_FULL_V1/report.json`
  - outputs: `outputs/experimentos/plots/20260208/baseline_limits/`
- TASK_CEP_F1_EXP_032_BACKTEST_FIXED_LIMITS_EXP031_V1
  - report: `planning/runs/TASK_CEP_F1_EXP_032_BACKTEST_FIXED_LIMITS_EXP031_V1/report.json`
  - outputs: `outputs/experimentos/fase1_calibracao/exp/20260208/backtest_fixed_limits_exp031/`
- TASK_CEP_F1_CAL_033_EXTRACT_LIMITS_FROM_EXP_029_V1
  - report: `None`
  - nota: Mesmo que não tenha gerado arquivos, usar os valores consolidados do best_global (N=3,K=60) abaixo como bloco final aprovado.

## Comparação de alternativas
- EXP_020: scan de estabilidade por N.
- CAL_022: sanity check N=3/4/5 (test_subgroups insuficiente).
- EXP_029: backtest KN scan (melhor desempenho operacional).
- EXP_031/EXP_032: limites fixos do baseline alternativo e backtest comparativo.

## Decisão final
Critério final: melhor desempenho operacional (equity_final) no backtest KN scan,
com desempate por menor K e menor N.

### Limites finais aprovados (para congelamento)

- N=3 | K=60
- Xbarra–R:
  - Xbar_CL=0.002264819106910559; LCL_Xbar=-0.026588621725635364; UCL_Xbar=0.03111825993945648
  - R_CL=0.028204731996623583; LCL_R=0.0; UCL_R=0.0725989801593091
  - Constantes: A2=1.023; D3=0.0; D4=2.574
- I–MR:
  - I_CL=0.0019680418505369475; LCL_I=-0.04404841000020794; UCL_I=0.04798449370128184
  - MR_CL=0.01730218589588008; LCL_MR=0.0; UCL_MR=0.05652624132184022

## Evidências principais
- `planning/runs/TASK_CEP_DISC_010_MEMORIAL_ESTADO_REPO_20260206/report.json`
- `planning/runs/TASK_CEP_F1_EXP_020_MASTER_BASELINE_SCAN_STABILITY_ROLLINGN_V1/report.json`
- `planning/runs/TASK_CEP_F1_CAL_021_PREPARAR_DECISAO_BASELINE_MASTER_V1/report.json`
- `planning/runs/TASK_CEP_F1_CAL_022_SANITY_CHECK_BASELINE_SCAN_N345_V1/report.json`
- `planning/runs/TASK_CEP_F1_EXP_029_MASTER_BACKTEST_REPLICA_BVSP_KN_SCAN_V1/report.json`
- `planning/runs/TASK_CEP_F1_CAL_030_DECISION_PACKAGE_MASTER_BACKTEST_REPLICA_BVSP_KN_V1/report.json`
- `planning/runs/TASK_CEP_F1_EXP_031_BASELINE_LIMITS_VIOLATIONS_FULL_V1/report.json`
- `planning/runs/TASK_CEP_F1_EXP_032_BACKTEST_FIXED_LIMITS_EXP031_V1/report.json`

Gerado em: 2026-02-08T21:37:06Z

---

## 4) Resumo SSOTs e base operacional
Fonte: `outputs/governanca/decisoes/20260208/ssot_base_summary.md`

---
# Resumo de SSOTs e base operacional

## SSOTs (localização)
- Ações (B3): `/home/wilson/CEP_NA_BOLSA/outputs/ssot/acoes/b3/20260204/ssot_acoes_b3.csv`
- BDRs (B3): `/home/wilson/CEP_NA_BOLSA/outputs/ssot/bdr/b3/20260204/ssot_bdr_b3.csv`
- Master (calibração): `/home/wilson/CEP_NA_BOLSA/docs/ssot/master_calibration.json`

## Base operacional derivada
- Arquivo atual: `/home/wilson/CEP_NA_BOLSA/outputs/base_operacional/xt_unificada_com_ibov/20260204/base_operacional_xt.csv`

## Contagens
- Ações: 854 tickers
- BDRs: 835 tickers
- Master: 1 ticker (^BVSP)
- Sessões (Master em base operacional): 2010
- Linhas totais (base operacional): 1619149

## Nome intuitivo sugerido
- `base_operacional_xt_unificada_com_master.csv`

Gerado em: 2026-02-09T12:52:25Z

---

## 5) Decisão de sizing default V2
Fonte: `outputs/governanca/decisoes/20260209/freeze_sizing_default_v2/decisao_freeze_sizing_default_v2.md`

---
# Decisão de Governança — SIZING_DEFAULT_V2

ID formal: DEC_SIZING_20260209_V2
Data de vigência: 2026-02-09

## Parâmetros congelados
- w_base: 0.08
- w_def: 0.03
- w_cap: 0.15
- persist_on: 3
- persist_off: 1

## Guardrail (regra operacional bloqueante)
- Definição: mdd_real = min_t(E_t / max_{s<=t}E_s - 1), negativo
- Escopo: história inteira, incluindo PRESERVACAO_TOTAL
- Threshold: -0.12
- Regra PASS/FAIL: mdd_real >= -0.12

## Evidências
- decision_package_md: `outputs/experimentos/fase1_calibracao/cal/20260209/decision_package_sizing_v2/decision_package.md`
- selected_config_json: `outputs/experimentos/fase1_calibracao/cal/20260209/decision_package_sizing_v2/selected_config.json`
- auditoria (dir): `outputs/experimentos/fase1_calibracao/aud/20260209/verify_mdd_guardrail_v2/`
  - arquivos: mdd_recalc_table.csv, guardrail_verdict.json, mdd_recalc_notes.md, manifest.json

## Regras de mudança
- Qualquer alteração futura exige novo grid + novo decision package + auditoria + nova decisão.
- Emenda na Constituição deve ser feita em passo separado.

## Em caso de erro na resposta (não no código)
- Revalidar escopo do MDD e regra operacional bloqueante antes de nova decisão.

Gerado em: 2026-02-09T18:47:07Z

---

## 6) Plano de teste sizing (Fase I)
Fonte: `outputs/governanca/decisoes/20260209/plano_teste_sizing_w_base_w_def_w_cap.md`

---
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

---

## 7) Manifesto operacional da rotina
Fonte: `outputs/governanca/operacao_rotina/20260209/ROTINA_GESTAO_CARTEIRA_001/manifesto_operacao_rotina.md`

---
# Manifesto Operacional — Rotina de Gestão da Carteira

## Ordem de uso (sequência)
- 010: 010_constituicao_v2.md — Regra suprema: estados do Master, regras CEP autorizadas, precedência e política de defesa/venda.
- 020: 020_ssot_base_summary.md — Mapa/índice do que é SSOT e onde está no repositório.
- 030: 030_ssot_base_summary_manifest.json — Manifesto do SSOT base para localizar paths canônicos a copiar.
- 040: 040_master_baseline_definition.md — Definição de baseline do Master e parâmetros associados (referência conceitual/operacional).
- 050: 050_decision_package_sizing_v2.md — Justificativa da escolha de sizing e critérios aplicados (inclui guardrail).
- 060: 060_selected_config_sizing_v2.json — Parâmetros operacionais vigentes: w_base/w_def/w_cap/persist_on/persist_off.
- 070: 070_guardrail_verdict_aud039.json — Evidência formal de PASS do guardrail de MDD (-12%).
- 080: 080_mdd_recalc_notes_aud039.md — Definições oficiais aplicadas (história inteira, inclui preservação_total; mdd negativo) e reconciliação.
- 090: 090_patch_summary_w_base.md — Mudança operacional: Opção A (M_target=10; w_base<=0.10; caixa explícito; sem renormalização).
- 100: 100_ssot_acoes_b3.csv — SSOT universo ações (csv).
- 110: 110_ssot_bdrs_b3.csv — SSOT universo BDRs (csv).
- 120: 120_master_calibration.json — SSOT master_calibration.json.

## Regra vigente de sizing
- w_base=0.08; w_def=0.03; w_cap=0.15; persist_on=3; persist_off=1.
- Guardrail MDD (operacional bloqueante): mdd_real >= -0.12; história inteira; inclui PRESERVACAO_TOTAL.

## Encadeamento lógico
- Constituição -> SSOT Master -> Sizing (selected_config) -> Auditoria guardrail (AUD_039).

## Em caso de erro na resposta (não no código)
- Revalidar fontes canônicas e hashes do manifesto antes de operar.

Gerado em: 2026-02-09T19:13:45Z
