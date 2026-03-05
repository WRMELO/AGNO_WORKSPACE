# Lessons Learned — Backtest e Simulação Financeira

> Consolidação temática de todas as lições sobre ablação, histerese, custos, constraints e motor de seleção.
> Fonte: phases 2, 3, 4, 5, 6, 8, 9, 10. Originais em `archive/by_phase/`.

---

## 1. Ablação data-driven, nunca "por exemplo"

**Regra**: parâmetros devem ser selecionados por ablação determinística sobre um grid explícito, nunca por intuição ou valores "de exemplo".

- Phase 2 (LL-PH2-002). Princípio fundacional.
- Phase 4 (LL-PH4-001). Abordagem "de cima para baixo" (partir do máximo e reduzir) mais eficiente que incremental.

## 2. Seleção lexicográfica determinística

**Regra**: ranking de candidatos deve usar critério lexicográfico documentado (ex: CAGR DESC → Sharpe DESC → turnover ASC). Evita escolhas arbitrárias.

- Phase 3 (LL-PH3-003). Rastreabilidade da escolha final.
- Phase 4 (LL-PH4-003). Colocar a métrica do objetivo-mestre como primeiro critério foca a seleção.

## 3. Hard constraints e feasibility

**Regra**: definir constraints hard explícitas (MDD, turnover, participação). Um constraint único (MDD >= -0.30) é suficiente — muitos constraints restringem excessivamente o espaço.

- Phase 4 (LL-PH4-004). feasible=10/25 com constraint único.
- Phase 3 (LL-PH3-002). Sem constraints, a seleção pode premiar CDI-only (T057 falhou por isso).
- Phase 10 (LL-PH10-006). Hard constraint MDD >= -0.15 não atingido no T126 (-24.68%).

## 4. Histerese assimétrica (h_in < h_out)

**Regra**: h_in (para entrar em cash) deve ser menor que h_out (para sair de cash). Isso minimiza reentradas prematuras durante deriva prolongada.

- Phase 6 (LL-PH6-014). C060: h_in=3, h_out=5. Grid com h_out=h_in produziu switches > 20 com custo elevado.
- Phase 6 (LL-PH6-006). h_out é o parâmetro com maior impacto no churn: C057 (h_out=2) = 25 switches; C060 (h_out=5) = 13 switches. Redução de 48%.

## 5. Estado absorvente e reentrada

**Problema**: no T044, o regime defensivo virou estado absorvente quando `n_positions=0` — `portfolio_logret=0.0` impede `slope_daily` de mudar, tornando `regime_defensivo` irreversível.

- Phase 3 (LL-PH3-004, LL-PH3-005). Análise de lógica invertida (A061) acelerou diagnóstico.
- Phase 3 (LL-PH3-006). Solução: migrar o decisor para sinal exógeno (market slope), removendo a dependência circular.

## 6. Cadência e turnover

- Phase 2 (LL-PH2-006). Cadência de compra foi o guardrail dominante no vencedor C021.
- Phase 3 (LL-PH3-008). Reentrada sem cap pode violar turnover total; `buy_turnover_cap_ratio` foi decisivo.
- Phase 8 (LL-PH8-011). n_positions=15 + cadence=10 é o ponto ótimo no universo expandido.

## 7. Robustez por subperíodos

**Regra**: validar em subperíodos canônicos para evitar overfitting temporal.

- Phase 2 (LL-PH2-009). Princípio mantido em todo o projeto.
- Phase 8 (LL-PH8-012). Winner C010 underperforma em 2019H2-2020 (-33.67% vs C060) mas domina no agregado. Trade-off documentado.

## 8. Consolidação de fábricas com Sharpe assimétrico

**Regra**: quando uma fábrica tem Sharpe muito superior à outra, consolidar dilui retorno sem compensar em risco. Correlação baixa (0.13 BR vs US) não garante ganho.

- Phase 9 (LL-PH9-005, LL-PH9-006). Ponto ótimo 20% US: +0.06 Sharpe, -3.2pp CAGR. Não justifica complexidade.
- Phase 9 (LL-PH9-007). PTAX como fator de risco real: -3.8% câmbio no HOLDOUT.

## 9. Comparativo obrigatório vs meta e baseline

**Regra**: a solução deve bater simultaneamente a meta (benchmark superior) e o baseline (último winner).

- Phase 2 (LL-PH2-008). Princípio mantido.
- Phase 3 (LL-PH3-010). Comparativo visual T064 confirmou T063 como correção operacional.

## 10. Gap capture rate como métrica de eficiência

**Métrica**: % do gap entre o determinístico e o oracle capturado pelo ML trigger.

- Phase 6 (LL-PH6-011). C060 captura ~38% do gap T072→oracle no HOLDOUT. Referência para ciclos futuros.

## 11. Ajuste paramétrico não resolve diferença estrutural

**Evidência**: T068 (36 candidatos de rally protection) produziu winner idêntico ao T067. Quando a diferença entre estratégias é estrutural (dois modos de forno), ajustar parâmetros dentro do mesmo processo não funciona.

- Phase 4 (LL-PH4-005). Motivou o conceito de dual-mode e depois o pivô para ML.

---

## Checklist anti-regressão backtest

1. [ ] Ablação sobre grid explícito, nunca "por exemplo"
2. [ ] Seleção lexicográfica com critério documentado
3. [ ] Hard constraints explícitas no grid
4. [ ] Histerese assimétrica (h_in < h_out)
5. [ ] Validação por subperíodos canônicos
6. [ ] Comparativo vs meta + baseline
7. [ ] Gap capture rate registrado
