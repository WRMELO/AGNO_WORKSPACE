# KNOWLEDGE BASE

## TECHNICAL SPECIFICATIONS - DATA ENGINE

### 1) SPC Constants for N=4
Constantes oficiais adotadas no pipeline canônico:
- `A2 = 0.729` (limites da carta XBar),
- `D4 = 2.282` (limite superior da carta R),
- `E2 = 2.66` (limites da carta I).

### 2) The VIVT3 Heuristic Algorithm
Para cada data marcada por evento corporativo, calcular o impacto em retorno logaritmico absoluto para tres candidatos de serie:
- `Raw` (preco sem transformacao),
- `Factor * P` (aplicacao direta do fator),
- `P / Factor` (aplicacao inversa do fator).

Selecionar o candidato vencedor por regra de menor distorcao:
- `winner = argmin(Abs(LogRet))`.

Politica de decisao: *winner takes all* no ponto de evento (com propagacao conforme implementacao operacional da serie `close_operational`).

### 3) Real Return Calculation
Retorno real diario descontado de CDI:

`X_real = ln(P_t / P_{t-1}) - ln(1 + CDI_daily)`.

Essa formula separa variacao de preco do componente de carrego monetario, permitindo leitura economica mais fiel do retorno.

### 4) Data Topology
Topologia consolidada da fase de dados:

`S001 (Legacy) -> Operational (697) -> Canonical (SPC Enriched)`.

- `S001 (Legacy)`: universo legado inicial e regras de sanidade.
- `Operational (697)`: universo operacional apos blacklist/pruning de falhas de provedor.
- `Canonical (SPC Enriched)`: base final com precos operacionais, macro alinhado e campos para controle estatistico (SPC).
