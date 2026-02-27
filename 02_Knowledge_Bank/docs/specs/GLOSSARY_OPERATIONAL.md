# Glossario Operacional (Fixado pelo Owner)

## Objetivo

Eliminar ambiguidade terminologica entre legado, arquitetura e implementacao.

## Definicoes Oficiais (Mandatorias)

- **Burner**: ativo individual. Universo operacional com 600+ ativos. Cada burner e tratado como processo estatistico independente.
- **Master**: carteira/portfolio operacional (agregado simultaneo de aproximadamente 10 +/- 1 burners alocados).
- **Caixa Livre (Tank)**: saldo liquido proveniente de compras/vendas, dividendos, JCP, bonus e remuneracao CDI.
- **Equity**: soma de posicoes marcadas a mercado + caixa livre.
- **Mercado**: Ibovespa (`^BVSP`, BRAPI), incluindo calendario de pregoes do projeto.

## Invariantes Operacionais

1. Capital inicial de referencia: `R$ 100.000`.
2. Primeira alocacao: compra apenas em quantidades inteiras.
3. Sobras da compra inicial permanecem em caixa livre.
4. Caixa livre e remunerado por CDI conforme emenda vigente.
5. Master e sempre carteira; Mercado e sempre Ibovespa.

## Decisao do Owner (vigente)

Em 2026-02-27, o Owner fixou:

- **Master = Carteira/Portfolio**
- **Mercado = Ibovespa (`^BVSP`)**

Consequencia: a definicao anterior "Master = Ibovespa" esta **superada** para este projeto.

