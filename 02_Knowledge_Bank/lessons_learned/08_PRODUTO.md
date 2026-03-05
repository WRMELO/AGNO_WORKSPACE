# Lessons Learned — Produto

> Consolidação temática de todas as lições sobre decisões do Owner, winners, operação real e benchmarks.
> Fonte: phases 5, 8, 9, 10. Originais em `archive/by_phase/`.

---

## 1. Winners oficiais do projeto

| Fábrica | Winner | Config | Métricas HOLDOUT | Fase |
|---|---|---|---|---|
| **BR** | C060X | N=10, thr=0.22, h_in=3, h_out=2, universo BR+BDR | Sharpe 2.42, MDD -6.3%, CAGR 31.1%, equity R$698k | Phase 8 (recalibrado) |
| **US** | T122 | TopN=5, Cadence=10, custo 1bp, sem ML trigger | Sharpe 1.19, MDD -28.3%, CAGR 35.5% | Phase 10 |

## 2. Decisões do Owner consolidadas

### Fábricas independentes
BR e US operam com **capital próprio**, sem split, sem interdependência. Consolidação em BRL via PTAX é apenas visualização financeira, não decisão de alocação.
- Phase 9 (LL-PH9-009), Phase 10 (LL-PH10-012).

### CDI como tank BR
CDI mantido como remuneração de caixa da Fábrica BR. Tesouro IPCA+ descartado após análise CTO: NTN-B mark-to-market (MDD -9.3% a -22%) contradiz propósito do cash como porto seguro.
- Phase 8 (LL-PH8-015). T082 cancelada.

### Treasury como tank US
Fed funds rate como proxy de T-Bill para a Fábrica US.
- Phase 9 handoff.

### Trigger US abandonado para produção
T126 (trigger ML v2) mantido como baseline informativo. T122 (motor puro) é o winner operacional. Razão: complexidade 5x (modelo + 60 features + API FRED + 24 switches) para ganho marginal (+0.79pp CAGR) e Sharpe inferior.
- Phase 10 (LL-PH10-010, LL-PH10-011).

### Custo de fricção
- BR: 2.5 bps uniforme (ações BR e BDRs). Emenda constitucional ativa.
- US: ~1 bp.

## 3. Benchmark externo

No recorte 2021-2025, T072 original = +55.8% vs CHC Momentum Smart Beta = +186.9%. A versão "martelada" (oracle) = +189.8%, praticamente empatando com o melhor fundo quantitativo real do Brasil.

- Phase 5 (LL-PH5-008). Confirma que o gap não é de estratégia, é de timing.

## 4. BDR Bridge valida diversificação geográfica

Expansão para BDRs (446 B3 + 50 US_DIRECT) melhorou Sharpe HOLDOUT de 0.96 (C060 Phase 6) para 3.19 (Phase 8 winner). Melhoria de 3.3x em Sharpe.

- Phase 8 (LL-PH8-001). Hipótese de diversificação validada.

## 5. Motor US bate SP500 em CAGR mas não em Sharpe

T122 (stock selection US): CAGR 35.5% vs SP500 21.5% (+14pp), mas Sharpe 1.19 vs 1.37. O MDD (-28.3%) não atinge o hard constraint de -15%.

- Phase 10. Direção futura: melhorar proteção de drawdown sem sacrificar CAGR.

## 6. Simplicidade vencedora

**Princípio**: quando ganho técnico marginal vem com custo alto de complexidade e piora de risco/claridade operacional, a decisão correta é padronizar o baseline mais simples e rastreável.

- Phase 10 (LL-PH10-007). Lição estrutural do projeto inteiro.

---

## Estado do produto (março 2026)

```
FÁBRICA BR (BRL)                    FÁBRICA US (USD)
┌─────────────────────┐             ┌─────────────────────┐
│ Winner: C060X       │             │ Winner: T122        │
│ Motor: M3 + ML trig │             │ Motor: M3-US puro   │
│ Universo: BR+BDR    │             │ Universo: S&P 500   │
│ Tank: CDI           │             │ Tank: Fed Funds     │
│ Custo: 2.5 bps      │             │ Custo: ~1 bp        │
│ Sharpe: 2.42        │             │ Sharpe: 1.19        │
│ MDD: -6.3%          │             │ MDD: -28.3%         │
│ CAGR: 31.1%         │             │ CAGR: 35.5%         │
└─────────────────────┘             └─────────────────────┘
         Operação independente, capital próprio cada
         Consolidação em BRL via PTAX = visual apenas
```
