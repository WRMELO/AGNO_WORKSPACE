# STATE 3 Condition Ledger Schema (T043-CAPTURE-V2)

## Objetivo

Definir schema minimo do ledger diario para captura de condicoes e regras locais sem ambiguidade terminologica.

## Regra terminologica obrigatoria

- Colunas do Ibovespa pertencem ao bloco `Mercado`.
- E proibido rotular series/colunas do Ibovespa como `Master`.
- `Master` refere-se exclusivamente a carteira/portfolio agregado.

## Chave e granularidade

- Granularidade: diaria (pregao).
- Chave primaria: `date`.
- Politica temporal: apenas dados disponiveis ate `date` (sem look-ahead).

## Bloco A - Mercado (Ibovespa)

Campos minimos sugeridos:

- `date` (datetime)
- `market_close` (float)
- `market_logret_1d` (float)
- `market_drawdown` (float)
- `market_vol_w` (float)
- `market_spc_i_value` (float, quando aplicavel)
- `market_spc_i_ucl` (float, quando aplicavel)
- `market_spc_i_lcl` (float, quando aplicavel)
- `market_nelson_flags` (json/string)
- `market_we_flags` (json/string)
- `market_special_cause_flag` (bool)
- `market_signal_persistence` (int)

## Bloco B - Master (Carteira)

Campos minimos sugeridos:

- `portfolio_equity` (float)
- `portfolio_logret_1d` (float)
- `portfolio_drawdown` (float)
- `portfolio_exposure_risk` (float)
- `portfolio_cash_weight` (float)
- `portfolio_regime_defensivo` (bool)
- `portfolio_switch_flag` (bool)
- `portfolio_blocked_buy_flag` (bool)
- `portfolio_spc_flags` (json/string, quando aplicavel)
- `portfolio_nelson_flags` (json/string, quando aplicavel)
- `portfolio_we_flags` (json/string, quando aplicavel)

## Bloco C - Estado operacional (decisor)

Campos minimos sugeridos:

- `state_id` (string enum; mutuamente exclusivo)
- `state_entry_flag` (bool)
- `state_exit_flag` (bool)
- `state_transition_reason` (string)
- `state_hysteresis_counter` (int)

## Bloco D - Acao e resultado local

Campos minimos sugeridos:

- `local_rule_id` (string)
- `local_rule_scope` (enum: `Mercado` | `Master`)
- `local_rule_fired` (bool)
- `action_type` (string)
- `action_size` (float, quando aplicavel)
- `post_action_pnl_1d` (float)
- `post_action_dd_delta` (float)

## Regras de qualidade do ledger

1. `G0_GLOSSARY_COMPLIANCE`: nenhum campo de Ibovespa pode usar prefixo `master_` ou `portfolio_`.
2. Campos booleanos devem ser normalizados (`true`/`false`).
3. Campos de flags compostas devem ser serializados de forma deterministica.
4. Toda versao do ledger deve publicar `manifest.json` com `sha256`.
5. Toda alteracao de schema deve ser versionada e documentada.
