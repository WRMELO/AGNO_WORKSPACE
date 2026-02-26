--- FILE: docs/00_constituicao/CEP_NA_BOLSA_CONSTITUICAO_V1.md ---


## Documento de Abertura e Diretrizes Operacionais

### 1. Propósito do Projeto

O projeto **CEP_NA_BOLSA** tem como objetivo desenvolver um sistema de gestão e operação de ativos financeiros baseado **exclusivamente em Controle Estatístico de Processo (CEP)**, aplicando princípios clássicos de engenharia de processos (Western Electric / Nelson Rules) ao mercado de ações e BDRs.

O foco do projeto **não é previsão**, **não é narrativa de mercado** e **não é otimização prematura**, mas sim:

- operar **somente quando o processo estiver sob controle**;
    
- bloquear risco quando houver evidência estatística de causa especial;
    
- selecionar ativos com base em **estabilidade + resultado**, sempre condicionados ao CEP;
    
- manter **auditabilidade total** das decisões.
    

O projeto é **pessoal**, **experimental** e **engenheirado**, sem compromissos com práticas comerciais de mercado.

---

### 2. Filosofia Central

- O mercado é tratado como **processo estocástico com rupturas**, não como sistema causal previsível.
    
- O CEP é a **camada primária de decisão**, acima de qualquer modelo ou ranking.
    
- Nenhuma decisão operacional é tomada fora das regras CEP formalmente definidas.
    
- Toda sofisticação futura (ML, fatores, etc.) só pode existir **dentro de um regime estatisticamente sob controle**.
    

Frase-guia do projeto:

> _“Não operar processos fora de controle.”_

---

### 3. Arquitetura de Papéis (Obrigatória)

O projeto adota explicitamente a seguinte separação de responsabilidades:

- **Owner (Você)**  
    Responsável por objetivos, validações finais, decisões estratégicas e aceitação dos artefatos.
    
- **Planejador (ChatGPT – este papel)**  
    Responsável por:
    
    - definir constituições, regras e planos de trabalho;
        
    - manter coerência metodológica;
        
    - evitar improvisação;
        
    - escrever documentos estruturantes;
        
    - nunca “pular etapas”.
        
- **Orquestrador (Agno)**  
    Responsável por:
    
    - organizar tarefas em etapas claras;
        
    - garantir rastreabilidade;
        
    - executar planos aprovados;
        
    - registrar logs e resultados.
        
- **Agente (Cursor + modelo de código)**  
    Responsável por:
    
    - implementação técnica (código);
        
    - execução fiel das tarefas definidas;
        
    - não tomar decisões conceituais.
        

⚠️ **Regra de ouro**:  
O Planejador **não codifica**, o Agente **não decide**, o Orquestrador **não interpreta**.

---

### 4. Ferramentas Oficiais do Projeto

Estas ferramentas fazem parte **formal** do projeto e devem continuar sendo usadas:

- **Agno**
    
    - Organização do trabalho em tarefas.
        
    - Execução ordenada e rastreável.
        
    - Registro de resultados intermediários.
        
- **Cursor**
    
    - Implementação técnica.
        
    - Execução de código.
        
    - Interface prática com o Agno.
        
- **Obsidian**
    
    - Registro histórico.
        
    - Decisões importantes.
        
    - Versões conceituais da constituição.
        
    - Diário do projeto.
        
- **Mermaid** (Obsidian ou online)
    
    - Fluxos operacionais.
        
    - Sequência de decisão CEP.
        
    - Estados do Master e dos Queimadores.
        
- **Miro**
    
    - Mapas mentais.
        
    - Exploração conceitual.
        
    - Organização de ideias antes de formalização.
        

Nenhuma ferramenta substitui outra. Cada uma tem papel distinto.

---

### 5. Estrutura Conceitual do Sistema

O sistema é dividido em **duas camadas principais**, ambas regidas por CEP clássico:

#### 5.1 Master (Gate Master)

- Representa o **regime agregado do mercado**.
    
- Decide:
    
    - se compras são permitidas;
        
    - se o sistema entra em modo de preservação.
        
- Não seleciona ativos.
    
- Usa cartas CEP (Xbarra–R, I, MR) sobre **log-retorno**.
    

#### 5.2 Queimadores (Ativos Individuais)

- Cada ativo é tratado como um **processo independente**.
    
- Decide:
    
    - manter;
        
    - reduzir;
        
    - zerar;
        
    - tornar-se elegível novamente.
        
- Não há quarentena fixa arbitrária.
    
- Reentrada ocorre **quando o processo volta a estar sob controle estatístico**.
    

⚠️ Apenas regras CEP clássicas são permitidas para declarar “fora de controle”.

---

### 6. Dados e Variável Fundamental

- Fonte de preços: **yfinance**.
    
- Universo: ações e BDRs disponíveis (com saneamento mínimo).
    
- Variável única do projeto:
    
    [  
    X_t = \log\left(\frac{Close_t}{Close_{t-1}}\right)  
    ]
    

Nenhuma outra variável substitui esta para fins de controle.

---

### 7. Calibração e Fases do Projeto

O projeto segue rigorosamente a lógica CEP:

- **Fase I (Calibração)**
    
    - Ano base: **2022**.
        
    - Objetivo:
        
        - definir (n_{burner}), (n_{master}) e persistências (k);
            
        - estimar limites de controle;
            
        - avaliar estabilidade do controlador (não performance financeira).
            
- **Fase II (Aplicação)**
    
    - Período: **2023 até janeiro/2026**.
        
    - Objetivo:
        
        - observar comportamento do sistema;
            
        - validar decisões do Gate Master;
            
        - analisar entradas e saídas dos queimadores.
            

Nenhum parâmetro é ajustado em Fase II sem revisão formal da constituição.

---

### 8. Seleção de Ativos para Compra (Condicionada ao CEP)

Quando o Gate Master permitir compras, a seleção segue este princípio:

- Universo elegível = ativos **em controle estatístico**.
    
- Avaliação periódica (semanal):
    
    - média de log-retorno em janela (t);
        
    - medida de estabilidade (amplitude ou desvio-padrão).
        
- Classificação em quadrantes teóricos:
    
    - alta média + baixa dispersão = prioridade.
        
- Alocação de capital:
    
    - respeitando limites de carteira (ex.: máx. 20% por ativo);
        
    - respeitando diversidade de mercado.
        

⚠️ Métricas de ranking **não substituem** CEP.  
CEP define _se_ pode operar; ranking define _como_ operar.

---

### 9. Princípios de Qualidade e Disciplina

- Nenhuma regra implícita.
    
- Nenhuma decisão sem log.
    
- Nenhum “jeitinho” fora da constituição.
    
- Nenhuma sofisticação antes de controle estável.
    
- Toda mudança conceitual exige atualização formal deste documento.
    

---

### 10. Instrução ao Próximo Chat (Explícita)

> **Este chat inicia o projeto CEP_NA_BOLSA.**
> 
> O Planejador deve:
> 
> - respeitar integralmente esta constituição;
>     
> - começar pelo plano técnico de execução da Fase I;
>     
> - organizar o trabalho via Agno;
>     
> - não antecipar ML, previsão ou otimizações;
>     
> - priorizar clareza, rastreabilidade e controle estatístico.
>     

---

### Encerramento

Este documento é a **âncora conceitual** do projeto CEP_NA_BOLSA.  
Tudo o que vier depois deve ser compatível com ele — ou explicitamente revisado.

---



--- FILE: docs/00_constituicao/CEP_NA_BOLSA_CONSTITUICAO_V2_20260204.md ---
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


--- FILE: docs/00_constituicao/RETOMADA_PLANO_VS_EXECUCAO.md ---
# Retomada — Plano vs Execução (CEP_NA_BOLSA)

Este documento relaciona o **plano geral (Constituição)** com o que já foi **implementado/validado** no repositório, indicando **onde estão os artefatos**, o que **foi feito certo** e o que **foi feito errado ou falhou** até aqui.

Base de referência do plano:  
`docs/00_constituicao/CEP_NA_BOLSA_CONSTITUICAO_V1.md`

---

## 1) Propósito do Projeto (Constituição §1)

**Plano:**  
Sistema de gestão baseado em **CEP**, sem previsão, com operação condicionada a controle estatístico e auditabilidade total.

**Status na execução:**  
- **Certo:** A estrutura de execução com rastreabilidade (Agno + outputs + audits) foi implantada.  
- **Errado/Falta:** Ainda não há implementação de cartas CEP, nem regras Western/Nelson.

**Onde está o que fizemos:**
- Execução rastreável: `scripts/agno_runner.py`
- Registros de execução: `planning/runs/*/report.json`
- Auditorias: `outputs/*/AUDIT*.md`

---

## 2) Filosofia Central (Constituição §2)

**Plano:**  
CEP como camada primária de decisão; nada fora de controle estatístico.

**Status na execução:**  
- **Certo:** Ainda não implementamos nada que viole essa regra (nenhuma decisão operacional foi criada).  
- **Falta:** Nenhuma lógica CEP implementada ainda.

**Onde está o que fizemos:**
- Estrutura pronta para rodar tasks CEP (sem lógica ainda): `planning/task_specs/*`

---

## 3) Arquitetura de Papéis (Constituição §3)

**Plano:**  
Owner decide, Planejador planeja, Orquestrador executa, Agente implementa.

**Status na execução:**  
- **Certo:** Modelo respeitado: tasks executadas via Agno, alterações via Cursor.  
- **Falta:** Nenhum mecanismo automático para garantir validações do Owner além dos reports.

**Onde está o que fizemos:**
- Tarefas e execução: `planning/task_specs/` e `planning/runs/`

---

## 4) Ferramentas Oficiais (Constituição §4)

**Plano:**  
Agno, Cursor, Obsidian, Mermaid, Miro.

**Status na execução:**  
- **Certo:** Agno e Cursor em uso; Obsidian ignorado no git.  
- **Falta:** Mermaid/Miro ainda não usados.

**Onde está o que fizemos:**
- Agno runner: `scripts/agno_runner.py`
- Exclusão Obsidian: `.gitignore` (inclui `.obsidian/`)

---

## 5) Estrutura Conceitual (Constituição §5)

**Plano:**  
Master (mercado) e Queimadores (ativos) com cartas CEP.

**Status na execução:**  
- **Falta total:** nenhuma carta CEP, nenhum cálculo de X_t, nenhuma lógica Master/Queimadores.

**Onde está o que fizemos:**
- Dados base para o futuro Master (falhou no fluxo antigo com Yahoo; ver §6)
- Dados base para universo de ativos (parcialmente prontos)

---

## 6) Dados e Variável Fundamental (Constituição §6)

**Plano:**  
Fonte de preços: yfinance. Variável: log-retorno.

**Status na execução:**  
- **Errado/Conflito:** O projeto passou a usar **brapi.dev** por limitação do Yahoo, contrariando o plano original.  
  Isso foi necessário para viabilizar continuidade, mas está **em conflito com a constituição**.
- **Falta:** Nenhum cálculo de X_t realizado.

**Onde está o que fizemos:**
- Tentativa Yahoo: `outputs/fase1/f1_002/*` (FAIL por rate-limit)
- Probe BRAPI (SDK e API): `outputs/fase1/f1_probe_sdk/*`
- Prova de BDRs via quote direto (BRAPI): `outputs/fase1/f1_bdr_direct_probe/*`

---

## 7) Fase I (Calibração 2022) (Constituição §7)

**Plano:**  
Usar 2022 para calibrar limites e estabilidade.

**Status na execução:**  
### 7.1 Master (^BVSP 2022)
- **Errado/Falhou:** Yahoo rate-limit impediu validação do Master no fluxo inicial.  
- **Falta:** Nenhum cálculo de limites ou estabilidade.

### 7.2 Universo de ativos
**Certo (parcial):**
1) **Universo NM + N2 (ações)**  
   - **Encontrado:** 210 tickers  
   - **Origem:** API B3 (listados)  
   - **Artefatos:**  
     `outputs/fase1/f1_003/universe_nm_n2_tickers.txt`  
     `outputs/fase1/f1_003/universe_nm_n2_audit.json`

2) **Universo BDR P2/P3 (32/33)**  
   - **Listagem via BRAPI (type=bdr):** **FAIL**, vazia  
   - **Heurística via universo geral + validação quote:** **PASS**  
   - **Artefatos:**  
     `outputs/fase1/f1_bdr_universe_heuristic/validated_bdr_p2_p3_tickers.txt`

3) **SSOT BDR oficial (B3 XLSX)**  
   - **PASS** com versionamento + hash  
   - **Artefatos:**  
     `outputs/ssot/bdr/b3/20260204/ssot_bdr_b3.csv`  
     `outputs/ssot/bdr/b3/20260204/manifest.json`

---

## 8) Seleção de Ativos (Constituição §8)

**Plano:**  
Somente ativos em controle estatístico, ranking secundário.

**Status na execução:**  
 - **Falta total:** Nenhuma regra de seleção implementada.

---

## 9) Qualidade e Disciplina (Constituição §9)

**Plano:**  
Nenhuma decisão sem log, nenhuma regra implícita, auditabilidade total.

**Status na execução:**  
 - **Certo:** Todas as tasks executadas via Agno têm report e evidências.  
 - **Falta:** Não há ainda um “log operacional” contínuo.

**Onde está o que fizemos:**
- Logs e reports: `planning/runs/*`
- Auditorias: `outputs/*/AUDIT*.md`

---

## 10) Instrução ao Próximo Chat (Constituição §10)

**Plano:**  
Planejador deve iniciar pela Fase I e usar Agno.

**Status na execução:**  
 - **Certo:** Workflows estruturados com Agno, execução de tasks com rastreabilidade.

---

## Inventário de Tasks e Resultado Real

| Task | Objetivo | Status | Evidência |
|---|---|---|---|
| `TASK_CEP_F1_001` | Bootstrap Agno runtime | **PASS** | `planning/runs/TASK_CEP_F1_001/report.json` |
| `TASK_CEP_F1_002` (SSOT BDR B3) | SSOT oficial B3 (XLSX) | **PASS** | `planning/runs/TASK_CEP_F1_002/report.json` |
| `TASK_CEP_DISC_F1_003` | BDR P2/P3 via `quote/list?type=bdr` | **FAIL** | `planning/runs/TASK_CEP_DISC_F1_003/report.json` |
| `TASK_CEP_DISC_F1_PROBE_SDK_001` | Probe SDK brapi quote/list | **PASS** | `planning/runs/TASK_CEP_DISC_F1_PROBE_SDK_001/report.json` |
| `TASK_CEP_DISC_F1_BDR_DIRECT_PROBE_001` | Provar BDR via quote direto | **PASS** | `planning/runs/TASK_CEP_DISC_F1_BDR_DIRECT_PROBE_001/report.json` |
| `TASK_CEP_DISC_F1_BDR_P2P3_UNIVERSE_HEURISTIC_001` | Universo P2/P3 via heurística | **PASS** | `planning/runs/TASK_CEP_DISC_F1_BDR_P2P3_UNIVERSE_HEURISTIC_001/report.json` |

**Nota:** O universo **NM + N2 (210 tickers)** foi gerado por script manual, sem task Agno:
- Script: `scripts/fetch_universe_nm_n2_tickers.py`
- Outputs:  
  `outputs/fase1/f1_003/universe_nm_n2_tickers.txt`  
  `outputs/fase1/f1_003/universe_nm_n2_audit.json`

---

## O que foi feito certo (resumo)

- Runtime Agno instalado e funcionando.  
- SSOT oficial de BDRs via XLSX da B3 com hash e manifesto.  
- Provas de BDRs acessíveis via cotação direta (BRAPI).  
- Heurística funcional para universo P2/P3 (32/33) baseada em universo geral e validação por quote.  
- Auditorias e evidências arquivadas corretamente.

---

## O que foi feito errado / falhou / conflitante

- **Falha real** no endpoint `quote/list?type=bdr` (BRAPI): vazio.  
  Evidência: `outputs/fase1/f1_003/diagnostic_matrix.json`
- **Conflito com a Constituição**: uso de BRAPI como fonte de dados, enquanto o plano original define yfinance.  
  (Foi necessário por rate-limit do Yahoo, mas requer revisão formal da constituição.)
- **Master 2022 (Yahoo)**: falhou por rate-limit; não há master validado nem limites CEP.

---

## Próximos passos (para o planejador alinhar plano vs realidade)

1) **Decidir formalmente** se BRAPI será fonte oficial (atualizar constituição) ou se voltamos ao Yahoo com outra estratégia.  
2) **Criar task Agno** para o universo NM+N2 (se quiser rastreabilidade formal).  
3) **Implementar Fase I real**: cálculo de X_t, cartas CEP, Master/Queimadores.  
4) **Integrar SSOT BDR B3** ao pipeline final de universo.

---

## Onde está o plano geral

`docs/00_constituicao/CEP_NA_BOLSA_CONSTITUICAO_V1.md`



--- FILE: docs/01_orientacoes_agente/README_TASK_CEP_DISC_F1_003_BDR_P2_P3_UNIVERSE_BRAPI_V1.md ---
# TASK_CEP_DISC_F1_003_BDR_P2_P3_UNIVERSE_BRAPI_V1

Discovery do universo de BDRs Patrocinados Nível II e III usando brapi.dev.

## Objetivo

Gerar o SSOT (Single Source of Truth) de tickers BDR P2/P3:
- **Nível II (P2)**: tickers terminados em `32`
- **Nível III (P3)**: tickers terminados em `33`

## Pré-requisitos

1. Token do brapi PRO definido na variável de ambiente:
   ```bash
   export BRAPI_TOKEN="seu_token_aqui"
   ```

2. Dependência `requests` instalada no venv.

## Como executar

```bash
cd /home/wilson/CEP_NA_BOLSA
source .venv/bin/activate  # se necessário
export BRAPI_TOKEN="..."   # obrigatório
python scripts/agno_runner.py --task planning/task_specs/TASK_CEP_DISC_F1_003_BDR_P2_P3_UNIVERSE_BRAPI_V1.json
```

Ou diretamente:
```bash
python planning/runners/cep_disc_f1_003_bdr_p2_p3_universe_brapi_v1.py \
  --out outputs/fase1/f1_003 \
  --cache data/cache/brapi/quote_list_bdr
```

## Saídas esperadas

```
outputs/fase1/f1_003/
├── universe_bdr_p2_p3_tickers.txt       (SSOT: lista de tickers 32/33)
├── universe_bdr_p2_p3_audit.json        (auditoria estruturada)
└── AUDIT_F1_003_BDR_P2_P3_UNIVERSE_BRAPI.md (auditoria legível)

data/cache/brapi/quote_list_bdr/
├── metadata_quote_list_bdr.json
└── raw_pages/
    ├── page_0001.json
    ├── page_0002.json
    └── ...
```

## Gates para PASS

- `BRAPI_TOKEN` presente no ambiente
- Smoke-test retorna HTTP 200
- SSOT contém pelo menos 1 ticker
- 100% dos tickers no SSOT batem com regex `^[A-Z0-9]{4}(32|33)$`

## Segurança

- O token NUNCA é gravado em arquivos ou impresso em logs
- Autenticação via header `Authorization: Bearer <token>`


--- FILE: docs/01_orientacoes_agente/README_TASK_CEP_F1_001_BOOTSTRAP_AGNO_RUNTIME_V1.md ---
# TASK_CEP_F1_001_BOOTSTRAP_AGNO_RUNTIME_V1

Este TASK faz o bootstrap do runtime Agno no repo CEP_NA_BOLSA.

## Objetivo
- Criar o runner padrao do Agno.
- Criar um smoke-test minimo que gere evidencias em `planning/runs`.
- Garantir `OVERALL: PASS` no report.

## Como executar
```bash
cd /home/wilson/CEP_NA_BOLSA
python scripts/agno_runner.py --task planning/task_specs/TASK_CEP_F1_001_BOOTSTRAP_AGNO_RUNTIME_V1.json
```

## Evidencias esperadas
- `planning/runs/TASK_CEP_F1_001/report.json`
- `planning/runs/TASK_CEP_F1_001/smoke_summary.json`
- `planning/runs/TASK_CEP_F1_001/SMOKE_OK.txt`


--- FILE: docs/01_orientacoes_agente/README_TASK_CEP_F1_002_MASTER_AND_UNIVERSE_DISCOVERY_V1.md ---
# TASK_CEP_F1_002_MASTER_AND_UNIVERSE_DISCOVERY_V1

Bootstrap da Fase I para materializar o Master (^BVSP) e construir o universo B3 filtrado por recuperabilidade no Yahoo.

## Dependencias
- `yfinance` (registrado em `requirements.txt`)

## Como executar
```bash
cd /home/wilson/CEP_NA_BOLSA
python scripts/agno_runner.py --task planning/task_specs/TASK_CEP_F1_002_MASTER_AND_UNIVERSE_DISCOVERY_V1.json
```

## Saidas esperadas
- `outputs/fase1/f1_002/master_bvsp_2022.parquet`
- `outputs/fase1/f1_002/universe_b3_raw.parquet`
- `outputs/fase1/f1_002/universe_yahoo_resolvable_2022.parquet`
- `outputs/fase1/f1_002/universe_failures_2022.csv`
- `outputs/fase1/f1_002/AUDIT_F1_002_MASTER_AND_UNIVERSE.md`
- `outputs/fase1/f1_002/audit_summary.csv`


--- FILE: docs/emendas/E-2026-02-06-baseline-unico-subgrupos-rolling-runner-templates.md ---
# Emenda — Baseline único, subgrupos rolling e runner/templates oficiais

Declarações normativas:
- Baseline único: 2024-02-29..2024-05-24, N_master=4; SSOT canônico: docs/ssot/master_calibration.json; proibir baseline alternativo.
- Subgrupos Xbarra/R: rolling_overlapping, stride=1, janela=N_master, eixo subgroup_end_date.
- Runner/templates oficiais: src/cep/runners/runner_xbarr_r_plotly_v1.py e docs/templates/runner_xbarr_r_plotly_v1.*;
  política plotly dependency-gated; manifest.json com hashes obrigatório.

Instalação: emenda aplicada na Constituição ativa.


--- FILE: docs/governanca/CEP_NA_BOLSA — Ponto de Situação (snapshot 2026-02-04).md ---
According to a document from (2026-02-04), o “Planejamento Fase I” registrava (i) **Gate de Mercado = IBOVESPA**, (ii) **Master = IBOVESPA**, (iii) universo vindo da B3 e filtro por “recuperáveis”, e (iv) a variável operacional já pensada em **log-retorno** (em vez de preço bruto). Nesse mesmo trecho, a versão antiga ainda citava **yfinance/Yahoo** como fonte de preços e um recorte fixo em **2022** como referência inicial. A partir daí, o projeto evoluiu para o estado real abaixo (snapshot governado 2026-02-04).

---

# CEP_NA_BOLSA — Ponto de Situação (snapshot 2026-02-04)

Este snapshot lista apenas artefatos gerados por tasks Agno.

## 1. Constituição e governança (vigente)

A Constituição V2 foi publicada e apontada como “constituição vigente” via task de governança, com instrução JSON arquivada e evidência de execução (PASS). O repositório passou a refletir que:

- **“Universo”** vem de fonte institucional (B3/CVM).
    
- **“Dados de mercado”** vêm de provedor (BRAPI), para cotação/histórico.
    
- Decisões relevantes precisam estar em docs versionados no repo (Obsidian fora do Git).
    

Entregáveis já governados:

- `docs/CEP_NA_BOLSA_CONSTITUICAO_V2_20260204.md`
    
- `docs/governanca/constituição_vigente.md`
    
- `planning/agent_instructions/20260204/TASK_CEP_GOV_001_PUBLICAR_CONSTITUICAO_V2.instruction.json`
    

## 2. SSOTs institucionais de universo (B3) — concluídos

Foram concluídas (PASS) as tasks de SSOT de universo:

- **BDRs via B3** (XLSX raw + CSV/Parquet SSOT + manifesto + evidências).
    
- **Ações via B3** (JSON raw + CSV/Parquet SSOT + manifesto + evidências).
    

Isso fecha a separação arquitetural: **B3 = universo**; **BRAPI = mercado**.

## 3. SSOTs de dados de mercado (BRAPI) — preços brutos desde 2018-01-01

### 3.1 Ações (preços brutos)

Task concluída (PASS) coletando histórico bruto desde **2018-01-01**:

- Cobertura OK: **697 tickers**
    
- Falhas: **158 tickers** (classificadas depois; total 157 no classificador por deduplicação/normalização de chave)
    

Classificação de falhas (PASS):

- Total classificado: **157**
    
- `INVALID_TICKER`: **131**
    
- `DELISTED_OR_NO_HISTORY`: **26**
    
- Ação recomendada: `EXCLUDE_FROM_OPERATIONAL`
    

Um subconjunto crítico foi analisado: **NM/N2 ∩ falhas (40)** com dossiê e “root cause” (provedor não suporta ticker / instrumento não é ação à vista / mismatch de formato), deixando explícito o que faltava como metadado no SSOT (status negociável, etc.).

### 3.2 BDRs (preços brutos)

Task concluída (PASS) coletando histórico bruto desde **2018-01-01**:

- Cobertura OK: **650 tickers**
    
- Falhas: **188 tickers**
    

Classificação de falhas (PASS):

- Total: **188**
    
- Categoria dominante: `INVALID_TICKER (188)`
    
- Ação recomendada: `EXCLUDE_FROM_OPERATIONAL (188)`
    

Observação importante de consistência: pelos números reportados, o SSOT BDR total implícito é **838** (650 OK + 188 falhas). Para ações, o total implícito é **854** (697 OK + 157 excluídos).

## 4. Base operacional unificada (log-retorno) — concluída e auditada

Foi criada (PASS) a **base operacional XT unificada**, isto é, o banco operacional em **log-retorno** (ln(Close_t / Close_{t-1})) com governança e auditoria:

- Inputs: ações **1.205.324** linhas, BDR **1.017.225** linhas
    
- Tickers input: ações **697**, BDR **650**
    
- Excluídos: ações **157**, BDR **188**
    
- Resultado: **1.617.139** linhas, **1.242** tickers
    
- Janela final: **2018-01-03 até 2026-02-04**
    

## 5. Master / Gate de mercado: IBOVESPA (ticker ^BVSP) — SSOT separado e agregado

Atendendo ao combinado de “Master = IBOVESPA”, foi feita uma SSOT isolada do índice com BRAPI:

- Símbolo selecionado por probe: **^BVSP**
    
- Linhas preços: **2011**
    
- Linhas XT: **2010**
    
- Janela: **2018-01-02 até 2026-02-04**
    

Em seguida, o **XT do IBOV** foi agregado à base operacional:

- Linhas finais: **1.619.149**
    
- Tickers finais: **1.243**
    
- IBOV incluído como `asset_class=INDEX` e `ticker=^BVSP`
    

Até aqui, portanto, o “Gate de Mercado” (IBOV) está pronto para uso como **série Master**, sem criar um “Master artificial”: é o próprio índice.


---

# Lista inicial de eventos sistêmicos (marcadores primários) — datas de início

Objetivo destes marcadores: servir de “âncoras” externas reconhecidas, para avaliar se o CEP do Master (^BVSP em log-retorno) torna **visíveis** (i) choques de causa especial e (ii) possíveis mudanças sistêmicas. A partir deste snapshot, a definição de acerto passa a ser por **score de evento**, usando a melhor pontuação observada entre D, D+1, D+2, D+3 e D+5:

- D ou D+1: 100
- D+2: 80
- D+3 ou D+5: 50
- demais: 0

Score do evento = maior pontuação observada. Score do período = soma dos scores dos eventos.

Abaixo vai uma lista P0 (para já termos o conjunto-alvo). Ela será “governada” depois (task específica) com curadoria por bancos/corretoras/jornais e evidência cruzada.

1. 2018-05-21 — Início da paralisação/greve dos caminhoneiros (Brasil). ([Serviços e Informações do Brasil](https://www.gov.br/abin/pt-br/centrais-de-conteudo/noticias/retrospectiva-abin-25-anos-greve-dos-caminhoneiros-de-2018-aperfeicoou-o-acompanhamento-de-inteligencia-corrente?utm_source=chatgpt.com "Retrospectiva ABIN 25 anos: greve dos caminhoneiros de ..."))
    
2. 2020-03-09 — Primeiro circuit breaker do Ibovespa em 2020 (choque inicial de COVID/mercados). ([Reuters](https://www.reuters.com/article/world/americas/ibovespa-cai-10-e-aciona-circuit-breaker-com-nervosismo-global-petrobras-derre-idUSKBN20W26R/?utm_source=chatgpt.com "Ibovespa cai 10% e aciona circuit breaker com nervosismo ..."))
    
3. 2020-03-11 — OMS declara COVID-19 como pandemia (marco global). ([Organização Mundial da Saúde](https://www.who.int/news-room/speeches/item/who-director-general-s-opening-remarks-at-the-media-briefing-on-covid-19---11-march-2020 "WHO Director-General's opening remarks at the media briefing on COVID-19 - 11 March 2020"))
    
4. 2021-03-17 — Copom inicia ciclo de alta (Selic para 2,75% a.a.; 1ª alta em anos). ([Banco Central do Brasil](https://www.bcb.gov.br/detalhenoticia/17341/nota?utm_source=chatgpt.com "Copom eleva a taxa Selic para 2,75% a.a."))
    
5. 2022-02-24 — Início da invasão em larga escala da Ucrânia pela Rússia (marco geopolítico global). ([The United Nations Office at Geneva](https://www.ungeneva.org/en/news-media/news/2024/11/100447/un-underlines-solidarity-ukraine-1000-days-russian-invasion?utm_source=chatgpt.com "UN underlines solidarity with Ukraine 1,000 days into Russian ..."))
    
6. 2022-03-16 — FOMC eleva a meta dos Fed Funds (início do ciclo 2022 de alta nos EUA). ([Reserva Federal](https://www.federalreserve.gov/newsevents/pressreleases/monetary20220316a.htm?utm_source=chatgpt.com "Federal Reserve issues FOMC statement"))
    
7. 2022-10-30 — 2º turno das eleições presidenciais no Brasil (marco político doméstico). ([Justiça Eleitoral](https://www.tse.jus.br/comunicacao/noticias/2022/Outubro/lula-e-eleito-novamente-presidente-da-republica-do-brasil "Lula é eleito novamente presidente da República do Brasil — Tribunal Superior Eleitoral"))
    
8. 2023-01-08 — Ataques/invasões às sedes dos Três Poderes (marco institucional doméstico). ([Senado Federal](https://www12.senado.leg.br/noticias/materias/2024/01/05/ataques-de-8-de-janeiro-tiveram-reflexo-na-agenda-legislativa-em-2023?utm_source=chatgpt.com "Ataques de 8 de janeiro tiveram reflexo na agenda ..."))
    
9. 2023-03-10 — Fechamento do Silicon Valley Bank (stress bancário/risco sistêmico). ([FDIC](https://www.fdic.gov/news/press-releases/2023/pr23019.html?utm_source=chatgpt.com "FDIC Acts to Protect All Depositors of the former Silicon ..."))
    
10. 2023-03-19 — Anúncio do acordo UBS–Credit Suisse (stress bancário/Europa). ([United States of America](https://www.ubs.com/global/en/media/display-page-ndp/en-20230319-tree.html?utm_source=chatgpt.com "UBS to acquire Credit Suisse"))
    

(Se você quiser, ainda dentro de “marcadores primários”, dá para incluir também datas de 2018/2022 em dois níveis: “evento (pleito)” e “data de resultado oficial” — mas eu mantive aqui os marcos mais consensuais e diretamente datáveis.)

---

# Emenda proposta à Constituição (rascunho) — definição do período de referência do CEP do Master

Você pediu apenas que conste que o período de referência virá de **regras conhecidas**, aplicadas ao **Master (IBOV)**. Segue um texto pronto para entrar como emenda (sem alterar o restante):

**Emenda — Regra de definição do período de referência (baseline) do CEP do Master**  
O período de referência do CEP (baseline) será definido formalmente por regras determinísticas, aplicadas exclusivamente à série Master (IBOVESPA, em log-retorno). O baseline deve ser um intervalo contínuo de pregões, contido na janela de dados disponível (a partir de 2018-01-01), com tamanho mínimo pré-definido (em pregões) e com dados íntegros. A escolha do baseline será feita por um procedimento de seleção comparativa entre candidatos, usando (i) uma lista governada de eventos sistêmicos com datas de início e (ii) métricas objetivas de desempenho do CEP no Master.

Definição de acerto por score de evento: D ou D+1 = 100; D+2 = 80; D+3 ou D+5 = 50; demais = 0. Para cada evento, usa-se o maior score observado; o score do período é a soma dos scores dos eventos. Em caso de empate de score total entre períodos candidatos, escolher o período com **menor número de sessões**. A seleção do período não se ancora em convenções econômicas (ex.: 252 pregões), mas em número de sessões e critérios estatísticos do CEP.

Procedimento: usar carta Xbarra–R no Master variando N (subgrupo), começando em N=2; selecionar o melhor período por score; congelar o período; aumentar N (3, 4, ...) e verificar se melhora o score. Eventos sistêmicos são referência ex post para auditoria/seleção e não alteram a lógica CEP do monitoramento.

## Fase de Teste — Início

Método adotado: N=2 -> escolher período por score -> congelar período -> aumentar N e comparar score.

Parâmetros desta execução:

- baseline: min_sessoes=60; max_sessoes=400; comprimentos_testados=[60,80,100,120,160,200,260,320,400]; estrategia=janela_deslizante; passo_sessoes=5.
- scan N: N_max=10.

## Ponto de Situação — Pós-Teste

- Período vencedor: 2024-02-29 até 2024-05-24 (60 sessões)
- N vencedor: 4
- Score total: 340

### Score por evento

| event_date | score |
| --- | --- |
| 2018-05-21 | 0 |
| 2020-03-09 | 80 |
| 2020-03-11 | 100 |
| 2021-03-17 | 0 |
| 2022-02-24 | 0 |
| 2022-03-16 | 80 |
| 2022-10-30 | 0 |
| 2023-01-08 | 80 |
| 2023-03-10 | 0 |
| 2023-03-19 | 0 |

### Score por N (baseline congelado)

| n | score_total |
| --- | --- |
| 4 | 340 |
| 3 | 230 |
| 5 | 230 |
| 6 | 180 |
| 9 | 180 |
| 10 | 180 |
| 7 | 100 |
| 8 | 0 |

### Evidências e artefatos

- outputs/master_baseline_selection/20260204/baseline_candidates_manifest.json
- outputs/master_baseline_selection/20260204/results_N2.parquet
- outputs/master_baseline_selection/20260204/selected_baseline_N2.json
- outputs/master_baseline_selection/20260204/results_N_scan.parquet
- outputs/master_baseline_selection/20260204/selected_N_master.json

## Reaplicação do Teste (N fixo = 4, varredura de comprimentos 10..300 passo 10)

- Baseline vencedor: 2024-08-06 até 2024-08-19 (10 sessões)
- Score total: 570

### Score por comprimento (N=4)

| n_sessoes | score_total |
| --- | --- |
| 10 | 570 |
| 20 | 550 |
| 30 | 470 |
| 40 | 420 |
| 50 | 420 |
| 60 | 420 |
| 70 | 420 |
| 80 | 340 |
| 90 | 340 |
| 100 | 340 |
| 110 | 340 |
| 120 | 340 |
| 130 | 340 |
| 140 | 340 |
| 150 | 340 |
| 160 | 340 |
| 170 | 340 |
| 180 | 340 |
| 190 | 340 |
| 200 | 340 |
| 210 | 340 |
| 220 | 340 |
| 230 | 340 |
| 240 | 340 |
| 250 | 340 |
| 260 | 340 |
| 270 | 340 |
| 280 | 340 |
| 290 | 260 |
| 300 | 260 |

### Evidências e artefatos

- outputs/master_baseline_selection/20260204/baseline_candidates_len_scan_N4_manifest.json
- outputs/master_baseline_selection/20260204/results_len_scan_N4.parquet
- outputs/master_baseline_selection/20260204/selected_baseline_N4.json

## Decisão de Freeze do Master

- Calibração congelada: baseline 2024-02-29 → 2024-05-24 (60 sessões), N=4
- Fonte de decisão: `TASK_CEP_F1_006_MASTER_BASELINE_N_SELECTION_V1`
- SSOT: `docs/ssot/master_calibration.json`


--- FILE: docs/governanca/constituição_vigente.md ---
# Constituição vigente

Vigente: CEP_NA_BOLSA_CONSTITUICAO_V2_20260204.md
Data de vigência: 2026-02-04


--- FILE: docs/templates/runner_xbarr_r_plotly_v1.usage.md ---
# Runner Xbarra–R (Plotly) — Template de uso

Este runner gera Xbarra–R interativo (Plotly) com subgrupos rolling-overlapping (stride=1) e manifest.json com hashes.

## Pré-requisitos

- `plotly` instalado no `.venv` (PortfolioZero).
- Política do projeto: o runner **não** instala dependências automaticamente.

## Execução

```bash
python -m cep.runners.runner_xbarr_r_plotly_v1 --config docs/templates/runner_xbarr_r_plotly_v1.config.json
```

## Observações

- Este runner assume **rolling_overlapping** como modo padrão (experimental).  
- O `window_n` deve ser igual ao `N_master` do SSOT em `docs/ssot/master_calibration.json`.
- Se a base operacional tiver outros nomes de coluna, ajuste `column_mapping`.


