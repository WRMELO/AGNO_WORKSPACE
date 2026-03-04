#!/home/wilson/AGNO_WORKSPACE/.venv/bin/python
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if not ("agno_env" in sys.prefix or ".venv" in sys.prefix):
    raise RuntimeError("FATAL: Not in agno_env/.venv")

TASK_ID = "T110"
RUN_ID = "T110-PHASE8-LESSONS-LEARNED-V1"
ROOT = Path("/home/wilson/AGNO_WORKSPACE")
CHANGELOG_PATH = ROOT / "00_Strategy/changelog.md"
TRACEABILITY_LINE = (
    "- 2026-03-04T13:00:00Z | DOCUMENTATION: T110 Phase 8 Lessons Learned "
    "(ciclo T101→T109, 16 licoes, winner C010_N15_CB10). "
    "Artefatos: scripts/t110_phase8_lessons_learned.py; "
    "02_Knowledge_Bank/docs/process/STATE3_PHASE8_LESSONS_LEARNED_T110.md; "
    "outputs/governanca/T110-PHASE8-LESSONS-LEARNED-V1_manifest.json"
)

OUT_DOC = ROOT / "02_Knowledge_Bank/docs/process/STATE3_PHASE8_LESSONS_LEARNED_T110.md"
OUT_REPORT = ROOT / "outputs/governanca/T110-PHASE8-LESSONS-LEARNED-V1_report.md"
OUT_MANIFEST = ROOT / "outputs/governanca/T110-PHASE8-LESSONS-LEARNED-V1_manifest.json"
OUT_EVID_DIR = ROOT / "outputs/governanca/T110-PHASE8-LESSONS-LEARNED-V1_evidence"
OUT_LESSONS_INDEX = OUT_EVID_DIR / "lessons_index.json"
OUT_SCRIPT = ROOT / "scripts/t110_phase8_lessons_learned.py"

NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def append_changelog_idempotent(line: str) -> bool:
    existing = CHANGELOG_PATH.read_text(encoding="utf-8") if CHANGELOG_PATH.exists() else ""
    if line in existing:
        return True
    text = existing if existing.endswith("\n") else existing + "\n"
    text += line.rstrip("\n") + "\n"
    CHANGELOG_PATH.write_text(text, encoding="utf-8")
    return line in CHANGELOG_PATH.read_text(encoding="utf-8")


LESSONS = [
    {
        "id": "LL-PH8-001",
        "category": "ESTRATEGIA",
        "impact": "POSITIVO",
        "statement": (
            "A expansão do universo para BDR Bridge (446 BDRs B3 + 50 US_DIRECT com "
            "penalidade FX+IOF embutida) validou a hipótese de que mais diversificação "
            "geográfica melhora o Sharpe. Phase 8 winner (C010_N15_CB10) entrega "
            "Sharpe HOLDOUT=3.19 vs C060 Phase 6 Sharpe=0.96 — melhoria de 3.3x."
        ),
        "evidence_task_id": "T107/T108/T109",
        "evidence_path": "outputs/governanca/T109-PHASE8-PLOTLY-COMPARATIVE-V1_evidence/metrics_snapshot.json",
        "actionable_rule": (
            "Em ciclos futuros de expansão de universo, manter a abordagem BDR Bridge: "
            "sintetizar preços em BRL via PTAX, embutir custos de fricção no preço "
            "(não como custo pós-trade), e usar o mesmo pipeline de feature engineering."
        ),
    },
    {
        "id": "LL-PH8-002",
        "category": "ESTRATEGIA",
        "impact": "POSITIVO",
        "statement": (
            "O winner Phase 8 (HOLDOUT equity=R$516.964) supera C060 Phase 6 "
            "(R$506.432) em +2.08% no HOLDOUT, com MDD drasticamente menor "
            "(-7.1% vs -18.7%) e 15 switches vs 13. O trade-off é aceitável: "
            "+2 switches por -11.6pp de MDD."
        ),
        "evidence_task_id": "T109",
        "evidence_path": "outputs/governanca/T109-PHASE8-PLOTLY-COMPARATIVE-V1_evidence/metrics_snapshot.json",
        "actionable_rule": (
            "MDD é a métrica de qualidade de vida operacional. Priorizar MDD sobre "
            "equity marginal quando a diferença de equity é <5%."
        ),
    },
    {
        "id": "LL-PH8-003",
        "category": "ESTRATEGIA",
        "impact": "NEGATIVO_DOCUMENTADO",
        "statement": (
            "Na janela ACID (nov/24-nov/25), C060 (R$445.357) supera Phase 8 winner "
            "(R$383.680) em -13.85%. A Phase 8 winner fica mais tempo em cash (94% vs "
            "C060) nesse subperíodo. Isso ocorre porque o threshold agressivo (thr=0.05) "
            "combinado com features macro expandidas detecta mais sinais de risco."
        ),
        "evidence_task_id": "T109",
        "evidence_path": "outputs/governanca/T109-PHASE8-PLOTLY-COMPARATIVE-V1_evidence/metrics_snapshot.json",
        "actionable_rule": (
            "Monitorar performance ACID vs HOLDOUT agregado. Se ACID underperformance "
            "> 15% relativo a C060, considerar threshold recalibration em próximo ciclo."
        ),
    },
    {
        "id": "LL-PH8-004",
        "category": "FEATURE_ENG",
        "impact": "POSITIVO",
        "statement": (
            "Features macro expandidas (VIX, DXY, Treasury spread, USDBRL, Fed Funds) "
            "adicionaram valor detectável: variante CORE_PLUS_MACRO_EXPANDED_FX venceu "
            "a variante CORE pura na ablação T105/T106 com equity HOLDOUT R$475k vs "
            "R$413k (+15%). As 38 features combinadas passaram no gate de estabilidade."
        ),
        "evidence_task_id": "T105/T106",
        "evidence_path": "outputs/governanca/T105-V1-XGBOOST-RETRAIN-EXPANDED-V1_evidence/variant_comparison.json",
        "actionable_rule": (
            "Manter CORE_PLUS_MACRO_EXPANDED_FX como variante canônica. Novas features "
            "macro devem passar por gate de estabilidade cross-split (KS-stat, sinal) "
            "antes de entrar na allowlist."
        ),
    },
    {
        "id": "LL-PH8-005",
        "category": "FEATURE_ENG",
        "impact": "POSITIVO",
        "statement": (
            "O pipeline de feature engineering expandido (T103+T104) manteve anti-lookahead "
            "estrito: shift(1) global, first_row_all_nan=True, max_abs_diff=0.0. "
            "76 features no dataset final (vs 52 da Phase 6), todas validadas."
        ),
        "evidence_task_id": "T104",
        "evidence_path": "outputs/governanca/T104-EDA-FEATURE-ENGINEERING-EXPANDED-V1_evidence/anti_lookahead_checks.json",
        "actionable_rule": (
            "Manter o gate anti-lookahead como obrigatório em todo pipeline de features. "
            "Qualquer nova feature sem shift(1) demonstrado deve ser bloqueada."
        ),
    },
    {
        "id": "LL-PH8-006",
        "category": "DATA_PIPELINE",
        "impact": "POSITIVO",
        "statement": (
            "O pipeline de dados US (T083→T086) foi construído em 4 tasks com governança "
            "estrita: SPEC (T083), ingestão S&P 500 (T084), qualidade+blacklist (T085), "
            "SSOT unificado (T086). Cada task com manifest SHA256. 496 tickers US "
            "operacionais (3 blacklistados: DAY/HUBB/MMC por violação OHLC). "
            "Cobertura 2018-01-02 a 2026-02-26 alinhada com SSOT BR."
        ),
        "evidence_task_id": "T083/T084/T085/T086",
        "evidence_path": "outputs/governanca/T086-SSOT-BR-US-UNIFIED-V2_manifest.json",
        "actionable_rule": (
            "Para futuras expansões de mercado, seguir o mesmo pipeline de 4 etapas: "
            "SPEC → Ingestão → Qualidade → SSOT unificado. Alinhamento temporal com "
            "SSOT BR é obrigatório desde a ingestão."
        ),
    },
    {
        "id": "LL-PH8-007",
        "category": "DATA_PIPELINE",
        "impact": "NEGATIVO_CORRIGIDO",
        "statement": (
            "T084-V1 iniciou com start_date=2018-07-02, desalinhando 6 meses do SSOT BR "
            "(que começa em 2018-01-02). O warm-up de rolling windows (62d) precisa dos "
            "dados anteriores. Finding do Owner pós-auditoria V1 levou à correção em V2."
        ),
        "evidence_task_id": "T084",
        "evidence_path": "outputs/governanca/T084-US-INGEST-SP500-BRAPI-V2_manifest.json",
        "actionable_rule": (
            "Em toda ingestão de dados de novo mercado, alinhar start_date com o mínimo "
            "existente no SSOT primário. Gate de alinhamento temporal obrigatório na auditoria."
        ),
    },
    {
        "id": "LL-PH8-008",
        "category": "ESTRATEGIA",
        "impact": "NEGATIVO_CORRIGIDO",
        "statement": (
            "T101-V1 excluiu 50 tickers S&P 500 sem BDR negociável na B3 (G_BDR_COUNT=446 < 490). "
            "Decisão Owner: incluí-los como US_DIRECT com penalidade de fricção cross-border "
            "(1 - 0.0078) embutida no preço sintético. V2 resultou em 496 = 446 B3 + 50 US_DIRECT."
        ),
        "evidence_task_id": "T101",
        "evidence_path": "outputs/governanca/T101-PTAX-BDR-SYNTH-V2_manifest.json",
        "actionable_rule": (
            "Ao expandir universo via BDRs, sempre incluir tickers sem BDR como US_DIRECT "
            "com penalidade de fricção embutida. Não excluir por falta de instrumento local — "
            "o Owner opera manualmente todos os ativos."
        ),
    },
    {
        "id": "LL-PH8-009",
        "category": "MODEL_TUNING",
        "impact": "POSITIVO",
        "statement": (
            "O retreino do XGBoost com features expandidas (T105) mostrou que a variante "
            "CORE pura tem recall HOLDOUT superior (0.988 vs 0.940) mas equity financeira "
            "inferior. A decisão do Owner foi manter CORE_PLUS_MACRO_EXPANDED_FX e testar "
            "na T106 com ablação financeira, onde a superioridade se confirmou."
        ),
        "evidence_task_id": "T105",
        "evidence_path": "outputs/governanca/T105-V1-XGBOOST-RETRAIN-EXPANDED-V1_evidence/variant_comparison.json",
        "actionable_rule": (
            "Recall de classificação e performance financeira podem divergir. Decisões "
            "devem ser tomadas na etapa de backtest financeiro, não na ablação de modelo."
        ),
    },
    {
        "id": "LL-PH8-010",
        "category": "MODEL_TUNING",
        "impact": "NEGATIVO_DOCUMENTADO",
        "statement": (
            "Threshold agressivo (thr=0.05) foi selecionado como winner no T106. Isso "
            "maximiza proteção (time_in_cash HOLDOUT=85%) mas pode gerar underperformance "
            "em bull markets prolongados, como evidenciado na ACID window. "
            "Finding do Auditor T077-V3 F-001 sobre threshold agressivo se materializou."
        ),
        "evidence_task_id": "T106",
        "evidence_path": "outputs/governanca/T106-ML-TRIGGER-TUNING-EXPANDED-V1_evidence/selection_rule.json",
        "actionable_rule": (
            "Em próximos ciclos, considerar múltiplos thresholds finais (conservador e "
            "moderado) como alternativas para o Owner decidir conforme apetite de risco."
        ),
    },
    {
        "id": "LL-PH8-011",
        "category": "BACKTEST",
        "impact": "POSITIVO",
        "statement": (
            "A ablação de n_positions [10,12,15,18,20] + cadence [5,10,15,20] no T108 "
            "demonstrou que n_positions=15 com cadence=10 é o ponto ótimo: 3 de 20 "
            "candidatos passaram o gate equity_holdout>=C060. Desempate por Sharpe "
            "HOLDOUT DESC elegeu C010_N15_CB10 com Sharpe=3.192."
        ),
        "evidence_task_id": "T108",
        "evidence_path": "outputs/governanca/T108-ABLATION-NPOS-CADENCE-EXPANDED-V1_evidence/selection_rule.json",
        "actionable_rule": (
            "Manter grid de n_positions e cadence como dimensões obrigatórias em ablações "
            "de portfólio. O gate equity_holdout>=C060 (benchmark da fase anterior) é "
            "eficaz como filtro de qualidade mínima."
        ),
    },
    {
        "id": "LL-PH8-012",
        "category": "BACKTEST",
        "impact": "POSITIVO",
        "statement": (
            "A seleção HOLDOUT_PRIMARY_WITH_C060_GATE (T108) usou subperíodo 2019H2-2020 "
            "como tie-breaker adicional. Winner C010 teve rel_return_vs_c060=-33.67% nesse "
            "subperíodo — inferior a C060. Isso é aceitável porque a vantagem está no "
            "HOLDOUT agregado e na ACID window (MDD=-2.5% vs C060 MDD=-5.4%)."
        ),
        "evidence_task_id": "T108",
        "evidence_path": "outputs/governanca/T108-ABLATION-NPOS-CADENCE-EXPANDED-V1_evidence/subperiods_definition.json",
        "actionable_rule": (
            "Documentar trade-offs de subperíodos no selection_rule. Não descartar winner "
            "por underperformance em um subperíodo se dominar no agregado e na ACID window."
        ),
    },
    {
        "id": "LL-PH8-013",
        "category": "GOVERNANCA",
        "impact": "POSITIVO",
        "statement": (
            "Changelog idempotente (append_changelog_one_line_idempotent) foi introduzido "
            "no T109 para evitar duplicatas por re-run. Corrigiu finding F-001 INFO da T108 "
            "(linha duplicada no changelog). Padrão adotado em todos os scripts futuros."
        ),
        "evidence_task_id": "T109",
        "evidence_path": "scripts/t109_plotly_phase8_comparative.py",
        "actionable_rule": (
            "Todo script de task deve usar append_changelog_one_line_idempotent. "
            "Verificar idempotência antes do gate G_CHLOG_UPDATED."
        ),
    },
    {
        "id": "LL-PH8-014",
        "category": "GOVERNANCA",
        "impact": "NEGATIVO_CORRIGIDO",
        "statement": (
            "Múltiplas tasks exigiram remediação pós-auditoria: T083 (V1→V2 por hash mismatch), "
            "T084 (V1→V2 por alinhamento de período), T086 (V1→V2 por gates faltantes no report), "
            "T101 (V1→V2 por BDR count). O padrão de V1 FAIL → V2 PASS demonstra que a auditoria "
            "independente funciona como rede de segurança, mas o custo de retrabalho é alto."
        ),
        "evidence_task_id": "T083/T084/T086/T101",
        "evidence_path": "00_Strategy/OPS_LOG.md",
        "actionable_rule": (
            "Antes de executar, o Executor deve revisar o checklist anti-regressão da phase "
            "anterior. Gates de integridade (SHA256, report completo, changelog) devem ser "
            "verificados internamente antes de reportar PASS."
        ),
    },
    {
        "id": "LL-PH8-015",
        "category": "GOVERNANCA",
        "impact": "POSITIVO",
        "statement": (
            "A decisão do Owner de cancelar T082 (Cash upgrade CDI→IPCA+) após análise CTO "
            "com dados reais do Tesouro Transparente evitou complexidade desnecessária. "
            "NTN-B mark-to-market (MDD=-9.3% a -22%) contradiz o propósito do cash como "
            "porto seguro no ML trigger."
        ),
        "evidence_task_id": "T082",
        "evidence_path": "00_Strategy/ROADMAP.md",
        "actionable_rule": (
            "Manter CDI como ativo de caixa. Não substituir por instrumentos com volatilidade "
            "de mark-to-market sem demonstrar benefício líquido no backtest completo."
        ),
    },
    {
        "id": "LL-PH8-016",
        "category": "VISUALIZACAO",
        "impact": "POSITIVO",
        "statement": (
            "O dashboard comparativo T109 (4 painéis, 12 traces, janela ACID destacada) "
            "consolidou o veredicto visual da Phase 8. Report enriquecido pós-fix do Auditor "
            "inclui tabelas de métricas HOLDOUT/ACID, relativo vs C060 e cobertura de dados. "
            "Padrão adotado: reports de visualização devem incluir métricas quantitativas, "
            "não apenas referências textuais."
        ),
        "evidence_task_id": "T109",
        "evidence_path": "outputs/governanca/T109-PHASE8-PLOTLY-COMPARATIVE-V1_report.md",
        "actionable_rule": (
            "Reports de tasks de visualização devem incluir tabelas de métricas com "
            "equity_final, CAGR, MDD, Sharpe, switches para cada curva/split."
        ),
    },
]

DOCUMENT = f"""# STATE 3 Phase 8 — Lessons Learned (T110)

**Gerado em**: {NOW}
**Task**: T110
**Ciclo coberto**: T082-CANCEL → T083 → T084 → T085 → T086 → T101 → T102 → T103 → T104 → T105 → T106 → T107 → T108 → T109
**Winner produto Phase 8**: C010_N15_CB10 (top_n=15, cadence_mode_b=10, thr=0.05, h_in=3, h_out=2)
**Winner produto Phase 6 (referencia)**: C060 (thr=0.25, h_in=3, h_out=5)

## 1) Contexto do ciclo

- **Escopo**: STATE 3 Phase 8 — BDR Bridge: expansão do universo operacional para incluir ações americanas via BDRs e US_DIRECT, com retreino do ML trigger e ablação de portfólio.
- **Objetivo-mestre**: superar C060 (Phase 6 winner) em CAGR e Sharpe usando universo expandido (~1.174 tickers: 678 BR + 496 BDR/US_DIRECT).
- **Walk-forward**: TRAIN 2018-07-02 → 2022-12-29 (1.115 pregões) | HOLDOUT 2023-01-02 → 2026-02-26 (787 pregões).
- **Acid window**: 2024-11-01 → 2025-11-30 (268 pregões, 100% HOLDOUT).
- **Sub-fases**: 8A (dados PTAX+BDR+SSOT), 8B (features expandidas), 8C (ML retreino+tuning), 8D (backtest+ablação), 8E (consolidação+governança).
- **Resultado final**: Winner = **C010_N15_CB10** (top_n=15, cadence=10, thr=0.05, h_in=3, h_out=2).
  - HOLDOUT: equity=R$516.964, CAGR=26.5%, MDD=-7.1%, Sharpe=3.19, switches=15.
  - ACID: equity=R$383.680, CAGR=19.2%, MDD=-2.5%, Sharpe=3.37, switches=2.
  - vs C060 HOLDOUT: +2.08% equity, MDD -11.6pp melhor, Sharpe +2.23 melhor.
- **Evidência de fechamento visual**: `outputs/plots/T109_STATE3_PHASE8E_COMPARATIVE.html`.
- **Referências de governança**: `00_Strategy/ROADMAP.md`, `00_Strategy/TASK_REGISTRY.md`, `00_Strategy/OPS_LOG.md`.

## 2) O que deu certo

- **LL-PH8-001** (ESTRATEGIA): Expansão BDR Bridge validada — Sharpe HOLDOUT 3.19 vs C060 0.96 (+3.3x). [evidência: `T107/T108/T109` | `{LESSONS[0]["evidence_path"]}`]
- **LL-PH8-002** (ESTRATEGIA): Winner supera C060 em +2.08% equity com MDD -11.6pp menor. [evidência: `T109` | `{LESSONS[1]["evidence_path"]}`]
- **LL-PH8-004** (FEATURE_ENG): Features macro expandidas agregaram +15% equity HOLDOUT vs CORE pura. [evidência: `T105/T106` | `{LESSONS[3]["evidence_path"]}`]
- **LL-PH8-005** (FEATURE_ENG): Anti-lookahead estrito mantido em 76 features (shift(1), max_abs_diff=0.0). [evidência: `T104` | `{LESSONS[4]["evidence_path"]}`]
- **LL-PH8-006** (DATA_PIPELINE): Pipeline US em 4 etapas (SPEC→Ingestão→Qualidade→SSOT) com governança estrita. [evidência: `T083-T086` | `{LESSONS[5]["evidence_path"]}`]
- **LL-PH8-009** (MODEL_TUNING): CORE_PLUS_MACRO_EXPANDED_FX confirmada como variante superior no backtest financeiro. [evidência: `T105` | `{LESSONS[8]["evidence_path"]}`]
- **LL-PH8-011** (BACKTEST): Ablação n_positions×cadence identificou ótimo (15×10) com gate C060. [evidência: `T108` | `{LESSONS[10]["evidence_path"]}`]
- **LL-PH8-013** (GOVERNANCA): Changelog idempotente introduzido, eliminando duplicatas por re-run. [evidência: `T109` | `{LESSONS[12]["evidence_path"]}`]
- **LL-PH8-015** (GOVERNANCA): Cancelamento T082 (IPCA+) baseado em evidência CTO evitou complexidade. [evidência: `T082` | `{LESSONS[14]["evidence_path"]}`]
- **LL-PH8-016** (VISUALIZACAO): Report enriquecido com métricas quantitativas pós-fix Auditor T109. [evidência: `T109` | `{LESSONS[15]["evidence_path"]}`]

## 3) O que não deu certo — Erros corrigidos

### Histórico de remediações Phase 8

| Task | V1 Issue | V2 Fix | Causa Raiz |
|---|---|---|---|
| T083 | Hash mismatch por double-write | Refatorado para write_all→hash_all→write_manifest | Ordem de escrita não canônica |
| T084 | start_date=2018-07-02 (desalinhado) | start_date=2018-01-02 (alinhado com SSOT BR) | Warm-up de 6 meses ignorado |
| T086 | Gates Gx e G_SHA256 ausentes do report | Reordenação: draft manifest → report → manifest final | Report escrito antes dos gates finais |
| T101 | G_BDR_COUNT=446 < 490 (50 tickers excluídos) | 496 = 446 B3 + 50 US_DIRECT com penalidade fricção | Falta de categoria US_DIRECT |

- **LL-PH8-007** (DATA_PIPELINE): T084-V1 desalinhamento temporal. [evidência: `T084` | `{LESSONS[6]["evidence_path"]}`]
- **LL-PH8-008** (ESTRATEGIA): T101-V1 excluiu 50 tickers sem BDR. [evidência: `T101` | `{LESSONS[7]["evidence_path"]}`]
- **LL-PH8-014** (GOVERNANCA): Padrão V1 FAIL → V2 PASS em 4 tasks. [evidência: `T083/T084/T086/T101` | `{LESSONS[13]["evidence_path"]}`]

## 4) O que não deu certo — Trade-offs aceitos

- **LL-PH8-003** (ESTRATEGIA): Phase 8 winner underperforma C060 na ACID window em -13.85%. Aceito porque domina no HOLDOUT agregado e tem Sharpe/MDD superiores. [evidência: `T109` | `{LESSONS[2]["evidence_path"]}`]
- **LL-PH8-010** (MODEL_TUNING): Threshold agressivo (thr=0.05) maximiza proteção mas pode underperformar em bull prolongado. [evidência: `T106` | `{LESSONS[9]["evidence_path"]}`]
- **LL-PH8-012** (BACKTEST): Winner underperforma C060 no subperíodo 2019H2-2020 (-33.67%). Aceito pelo domínio agregado. [evidência: `T108` | `{LESSONS[11]["evidence_path"]}`]

## 5) Tabela comparativa Phase 8 vs Phase 6

| Métrica | Phase 8 Winner (C010_N15_CB10) | C060 (Phase 6) | CDI | Ibovespa | Observação |
|---|---|---|---|---|---|
| HOLDOUT Equity | R$516.964 | R$506.432 | R$191.686 | R$262.225 | Phase 8 +2.08% vs C060 |
| HOLDOUT CAGR | 26.5% | 13.1% | 12.9% | 20.6% | Phase 8 2x C060 |
| HOLDOUT MDD | -7.1% | -18.7% | 0.0% | -14.2% | Phase 8 -11.6pp melhor |
| HOLDOUT Sharpe | 3.19 | 0.96 | 126.7 | 1.30 | Phase 8 3.3x C060 |
| HOLDOUT Switches | 15 | 13 | 0 | 0 | +2 switches aceitável |
| ACID Equity | R$383.680 | R$445.357 | R$185.655 | R$218.386 | C060 domina ACID equity |
| ACID CAGR | 19.2% | 9.9% | 13.9% | 22.7% | Phase 8 CAGR > C060 |
| ACID MDD | -2.5% | -5.4% | 0.0% | -9.3% | Phase 8 -2.9pp melhor |
| ACID Sharpe | 3.37 | 2.75 | 147.2 | 1.42 | Phase 8 Sharpe > C060 |
| ACID Switches | 2 | 4 | 0 | 0 | Phase 8 mais estável |
| TRAIN Equity | R$247.958 | R$344.523 | R$131.327 | R$151.058 | C060 domina TRAIN |
| TRAIN CAGR | 22.8% | 32.3% | 6.4% | 9.8% | C060 TRAIN superior |
| TRAIN MDD | -24.0% | -29.8% | 0.0% | -46.8% | Phase 8 MDD TRAIN melhor |

## 6) Checklist anti-regressão para próximo ciclo

Derivado das `actionable_rule` das 16 lições:

- [ ] Manter abordagem BDR Bridge com penalidade FX+IOF embutida no preço (LL-PH8-001)
- [ ] Priorizar MDD sobre equity marginal quando diferença < 5% (LL-PH8-002)
- [ ] Monitorar ACID underperformance vs benchmark; se > 15%, recalibrar threshold (LL-PH8-003)
- [ ] Partir de CORE_PLUS_MACRO_EXPANDED_FX como variante canônica (LL-PH8-004)
- [ ] Gate anti-lookahead (shift(1), max_abs_diff=0.0) obrigatório em toda feature (LL-PH8-005)
- [ ] Pipeline de novo mercado em 4 etapas: SPEC→Ingestão→Qualidade→SSOT (LL-PH8-006)
- [ ] Alinhar start_date com SSOT primário desde a ingestão (LL-PH8-007)
- [ ] Incluir tickers sem instrumento local como XX_DIRECT com penalidade embutida (LL-PH8-008)
- [ ] Decisão recall vs financial deve ser tomada no backtest, não na ablação ML (LL-PH8-009)
- [ ] Considerar múltiplos thresholds finais para Owner decidir (LL-PH8-010)
- [ ] Grid n_positions×cadence obrigatório; gate equity_holdout>=fase_anterior (LL-PH8-011)
- [ ] Documentar trade-offs de subperíodos no selection_rule (LL-PH8-012)
- [ ] Usar append_changelog_one_line_idempotent em todo script (LL-PH8-013)
- [ ] Revisar checklist anti-regressão antes de executar qualquer task (LL-PH8-014)
- [ ] Manter CDI como ativo de caixa; não substituir sem evidência no backtest (LL-PH8-015)
- [ ] Reports de visualização devem incluir tabelas de métricas quantitativas (LL-PH8-016)

## 7) Artefatos da Phase 8

| Artefato | Task | Tipo |
|---|---|---|
| `scripts/t101_ingest_ptax_bdr_synth.py` | T101 | Ingestão PTAX+BDR |
| `src/data_engine/ssot/SSOT_FX_PTAX_USDBRL.parquet` | T101 | SSOT câmbio |
| `src/data_engine/ssot/SSOT_BDR_B3_UNIVERSE.parquet` | T101 | Universo BDR |
| `src/data_engine/ssot/SSOT_BDR_SYNTH_MARKET_DATA_RAW.parquet` | T101 | Market data BDR sintético |
| `scripts/t102_build_ssot_br_expanded_brl.py` | T102 | SSOT BR expandido |
| `src/data_engine/ssot/SSOT_CANONICAL_BASE_BR_EXPANDED.parquet` | T102 | SSOT canônico expandido |
| `src/data_engine/ssot/SSOT_UNIVERSE_OPERATIONAL_EXPANDED.parquet` | T102 | Universo operacional expandido |
| `scripts/t103_feature_engineering_expanded_universe.py` | T103 | Features macro expandidas |
| `src/data_engine/features/T103_MACRO_FEATURES_EXPANDED_DAILY.parquet` | T103 | Features macro |
| `src/data_engine/features/T103_BDR_TICKER_METADATA.parquet` | T103 | Metadata BDR |
| `scripts/t104_eda_feature_engineering_ml_trigger_expanded.py` | T104 | Feature matrix unificada |
| `src/data_engine/features/T104_FEATURE_MATRIX_DAILY.parquet` | T104 | Matrix 76 features |
| `src/data_engine/features/T104_DATASET_DAILY.parquet` | T104 | Dataset ML completo |
| `outputs/plots/T104_STATE3_PHASE8B_EDA.html` | T104 | EDA visual |
| `scripts/t105_xgboost_retrain_expanded_walkforward_v1.py` | T105 | XGBoost retreino |
| `src/data_engine/models/T105_V1_XGB_SELECTED_MODEL.json` | T105 | Modelo winner |
| `src/data_engine/features/T105_V1_PREDICTIONS.parquet` | T105 | Predições diárias |
| `scripts/t106_threshold_hysteresis_ablation_expanded_v1.py` | T106 | Ablação threshold+histerese |
| `src/data_engine/portfolio/T106_ML_TRIGGER_EXPANDED_SELECTED_CONFIG.json` | T106 | Config ML trigger |
| `scripts/t107_backtest_integrated_expanded_ml_trigger_v1.py` | T107 | Backtest integrado |
| `src/data_engine/portfolio/T107_PORTFOLIO_CURVE_DUAL_MODE_EXPANDED_ML_TRIGGER.parquet` | T107 | Curva dual-mode+ML |
| `scripts/t108_ablation_n_positions_cadence_expanded_v1.py` | T108 | Ablação n_positions×cadence |
| `src/data_engine/portfolio/T108_PORTFOLIO_CURVE_DUAL_MODE_EXPANDED_ML_TRIGGER_WINNER.parquet` | T108 | Curva winner Phase 8 |
| `src/data_engine/portfolio/T108_SELECTED_CONFIG_NPOS_CADENCE_EXPANDED.json` | T108 | Config winner |
| `scripts/t109_plotly_phase8_comparative.py` | T109 | Plotly comparativo |
| `outputs/plots/T109_STATE3_PHASE8E_COMPARATIVE.html` | T109 | Dashboard comparativo |
| `02_Knowledge_Bank/docs/process/STATE3_PHASE8_LESSONS_LEARNED_T110.md` | T110 | Este documento |

## 8) Lições detalhadas (todas as 16)

"""

for ll in LESSONS:
    DOCUMENT += f"""### {ll['id']} — {ll['category']} ({ll['impact']})

**Statement**: {ll['statement']}

**Evidência**: Task `{ll['evidence_task_id']}` — `{ll['evidence_path']}`

**Regra acionável**: {ll['actionable_rule']}

"""


def main() -> int:
    gates: list[dict] = []
    retry_log: list[str] = []

    try:
        for p in [OUT_DOC, OUT_REPORT, OUT_MANIFEST, OUT_LESSONS_INDEX]:
            p.parent.mkdir(parents=True, exist_ok=True)

        gates.append({"name": "G_ENV_VENV", "pass": True, "detail": f"python={sys.executable}"})

        OUT_DOC.write_text(DOCUMENT, encoding="utf-8")
        gates.append({"name": "G_DOC_WRITTEN", "pass": OUT_DOC.exists(), "detail": f"lines={len(DOCUMENT.splitlines())}"})

        write_json(OUT_LESSONS_INDEX, [
            {"id": ll["id"], "category": ll["category"], "impact": ll["impact"],
             "evidence_task_id": ll["evidence_task_id"]}
            for ll in LESSONS
        ])
        gates.append({"name": "G_LESSONS_INDEX_WRITTEN", "pass": OUT_LESSONS_INDEX.exists(), "detail": f"count={len(LESSONS)}"})

        ch_ok = append_changelog_idempotent(TRACEABILITY_LINE)
        gates.append({"name": "G_CHLOG_UPDATED", "pass": ch_ok, "detail": f"path={CHANGELOG_PATH}"})

        overall_pre = all(g["pass"] for g in gates)

        report_lines = [f"# HEADER: {TASK_ID}", "", "## STEP GATES"]
        for g in gates:
            report_lines.append(f"- {g['name']}: {'PASS' if g['pass'] else 'FAIL'} | {g['detail']}")
        report_lines += [
            "", "## RESUMO",
            f"- 16 lições estruturadas (LL-PH8-001..016) cobrindo ciclo T082-CANCEL→T109.",
            f"- Winner Phase 8: C010_N15_CB10 (HOLDOUT equity=R$516.964, Sharpe=3.19).",
            f"- Documento: `{OUT_DOC.relative_to(ROOT)}`",
            "", "## RETRY LOG",
            "- none" if not retry_log else "",
        ]
        for r in retry_log:
            report_lines.append(f"- {r}")
        report_lines += [
            "", "## ARTIFACT LINKS",
            f"- {OUT_DOC.relative_to(ROOT)}",
            f"- {OUT_REPORT.relative_to(ROOT)}",
            f"- {OUT_MANIFEST.relative_to(ROOT)}",
            f"- {OUT_LESSONS_INDEX.relative_to(ROOT)}",
            f"- {OUT_SCRIPT.relative_to(ROOT)}",
        ]

        OUT_REPORT.write_text("\n".join(report_lines + ["", f"## OVERALL STATUS: [[ {'PASS' if overall_pre else 'FAIL'} ]]", ""]), encoding="utf-8")

        outputs = [OUT_SCRIPT, OUT_DOC, OUT_REPORT, OUT_LESSONS_INDEX, CHANGELOG_PATH]
        hashes = {str(p.relative_to(ROOT)): sha256_file(p) for p in outputs}
        manifest = {
            "task_id": TASK_ID,
            "run_id": RUN_ID,
            "manifest_policy": "no_self_hash",
            "inputs_consumed": [],
            "outputs_produced": [str(p.relative_to(ROOT)) for p in [OUT_DOC, OUT_REPORT, OUT_MANIFEST, OUT_LESSONS_INDEX]],
            "hashes_sha256": hashes,
        }
        write_json(OUT_MANIFEST, manifest)
        gates.append({"name": "Gx_HASH_MANIFEST_PRESENT", "pass": OUT_MANIFEST.exists(), "detail": f"entries={len(hashes)}"})

        mismatches = [r for r, exp in hashes.items() if sha256_file(ROOT / r) != exp]
        gates.append({"name": "G_SHA256_INTEGRITY_SELF_CHECK", "pass": len(mismatches) == 0, "detail": f"mismatches={len(mismatches)}"})

        overall = all(g["pass"] for g in gates)
        report_lines_final = [f"# HEADER: {TASK_ID}", "", "## STEP GATES"]
        for g in gates:
            report_lines_final.append(f"- {g['name']}: {'PASS' if g['pass'] else 'FAIL'} | {g['detail']}")
        report_lines_final += [
            "", "## RESUMO",
            f"- 16 lições estruturadas (LL-PH8-001..016) cobrindo ciclo T082-CANCEL→T109.",
            f"- Winner Phase 8: C010_N15_CB10 (HOLDOUT equity=R$516.964, Sharpe=3.19).",
            f"- Documento: `{OUT_DOC.relative_to(ROOT)}`",
            "", "## RETRY LOG", "- none" if not retry_log else "",
        ]
        for r in retry_log:
            report_lines_final.append(f"- {r}")
        report_lines_final += [
            "", "## ARTIFACT LINKS",
            f"- {OUT_DOC.relative_to(ROOT)}",
            f"- {OUT_REPORT.relative_to(ROOT)}",
            f"- {OUT_MANIFEST.relative_to(ROOT)}",
            f"- {OUT_LESSONS_INDEX.relative_to(ROOT)}",
            f"- {OUT_SCRIPT.relative_to(ROOT)}",
            "", f"## OVERALL STATUS: [[ {'PASS' if overall else 'FAIL'} ]]", "",
        ]
        OUT_REPORT.write_text("\n".join(report_lines_final), encoding="utf-8")
        final_hashes = {str(p.relative_to(ROOT)): sha256_file(p) for p in outputs}
        manifest["hashes_sha256"] = final_hashes
        write_json(OUT_MANIFEST, manifest)

        print(f"HEADER: {TASK_ID}")
        print("STEP GATES:")
        for g in gates:
            print(f"- {g['name']}: {'PASS' if g['pass'] else 'FAIL'} | {g['detail']}")
        print("RETRY LOG:\n- none" if not retry_log else "\n".join(f"- {r}" for r in retry_log))
        print("ARTIFACT LINKS:")
        print(f"- {OUT_DOC}")
        print(f"- {OUT_REPORT}")
        print(f"- {OUT_MANIFEST}")
        print(f"- {OUT_LESSONS_INDEX}")
        print(f"OVERALL STATUS: [[ {'PASS' if overall else 'FAIL'} ]]")
        return 0 if overall else 2

    except Exception as exc:
        retry_log.append(f"FATAL: {type(exc).__name__}: {exc}")
        print(f"FATAL: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
