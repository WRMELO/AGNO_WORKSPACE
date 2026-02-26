# LESSONS LEARNED

## PHASE 1: DATA ENGINE & PHYSICS (Feb 2026)

### 1) The Double Adjustment Trap
Durante a auditoria forense do T023, ficou comprovado que a coluna `close` do provedor ja vinha suavizada para eventos de split em casos relevantes (ex.: VIVT3). Quando um ajuste externo adicional de split e aplicado sobre uma serie que ja estava ajustada, ocorre destruicao de escala e distorcao severa de retornos. Regra operacional: nunca aplicar fator corporativo cegamente sem validar comportamento observado na serie de preco.

### 2) Burner Physics (Dividends vs Splits)
A politica de fisica de mercado foi consolidada em dois comportamentos distintos:
- Dividendos: representam extracao de caixa do ativo, portanto queda de preco no ex-date e esperada (`Price Drop = True`).
- Splits/Inplits: representam transformacao geometrica de unidade, portanto nao devem criar queda economica real (`Price Drop = False`).
Essa separacao evita mascarar sinal real (dividendos) e evita criar descontinuidades artificiais (splits).

### 3) Calendar Authority
`SSOT_UNIVERSE` define *quem* pode ser operado, mas nao define *quando* existe pregao valido. A autoridade temporal da malha diaria deve ser o `^BVSP` via BRAPI, pois ele representa o calendario efetivo de negociacao B3 para alinhamento macro/micro.

### 4) Heuristic Auto-Correction
Metadado de evento corporativo pode ser inconsistente em direcao e fator efetivo. A estrategia robusta e testar candidatos de ajuste no proprio dia do evento e escolher o que minimiza distorcao de retorno logaritmico:
- `Raw` (sem ajuste),
- `Factor * P`,
- `P / Factor`.
O criterio de minimizacao de `abs(logret)` no entorno do evento reduz falsos ajustes e preserva continuidade operacional.
