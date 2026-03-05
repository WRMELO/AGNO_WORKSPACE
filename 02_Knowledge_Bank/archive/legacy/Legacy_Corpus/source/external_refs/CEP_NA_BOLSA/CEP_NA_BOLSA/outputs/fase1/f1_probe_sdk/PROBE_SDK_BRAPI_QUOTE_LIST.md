# PROBE SDK BRAPI QUOTE/LIST

Timestamp: 2026-02-02T21:14:01Z
SDK version: 1.2.0
SDK supports quote/list: True

## Comparativo

| Probe | http_status | stocks_length | totalCount |
|---|---:|---:|---:|
| P1_NO_TYPE | 200 | 10 | 2317 |
| P2_TYPE_BDR | 200 | 0 | 0 |

## Chaves presentes
- P1_NO_TYPE: availableSectors, availableStockTypes, currentPage, hasNextPage, indexes, itemsPerPage, stocks, totalCount, totalPages
- P2_TYPE_BDR: availableSectors, availableStockTypes, currentPage, hasNextPage, indexes, itemsPerPage, stocks, totalCount, totalPages

## Amostras
- P1_NO_TYPE first_3_stock_symbols: ['GOLL54', 'RAIZ4', 'PETR4']
- P2_TYPE_BDR first_3_stock_symbols: []

## Conclusão
SDK confirma comportamento vazio
