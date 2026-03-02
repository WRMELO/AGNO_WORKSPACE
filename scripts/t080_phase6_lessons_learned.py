"""
T080 — Phase 6 Lessons Learned
STATE 3 Phase 6D — Consolidação e Governança

Gera documento canônico 14 lições + manifest SHA256.
"""
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

TASK_ID = "T080"
TIMESTAMP = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
WORKSPACE = Path(__file__).resolve().parent.parent

# ── Paths ─────────────────────────────────────────────────────────────────────
DOCS_DIR = WORKSPACE / "02_Knowledge_Bank/docs/process"
GOV_DIR = WORKSPACE / "outputs/governanca"
EVIDENCE_DIR = GOV_DIR / "T080-PHASE6-LESSONS-LEARNED-V1_evidence"
LESSONS_DOC = DOCS_DIR / "STATE3_PHASE6_LESSONS_LEARNED_T080.md"
REPORT_PATH = GOV_DIR / "T080-PHASE6-LESSONS-LEARNED-V1_report.md"
MANIFEST_PATH = GOV_DIR / "T080-PHASE6-LESSONS-LEARNED-V1_manifest.json"
LESSONS_INDEX = EVIDENCE_DIR / "lessons_index.json"
CHANGELOG = WORKSPACE / "00_Strategy/changelog.md"

REF = {
    "t077_model": WORKSPACE / "src/data_engine/models/T077_V3_XGB_SELECTED_MODEL.json",
    "t078_config": WORKSPACE / "src/data_engine/portfolio/T078_ML_TRIGGER_BACKTEST_SELECTED_CONFIG.json",
    "t078_summary": WORKSPACE / "src/data_engine/portfolio/T078_BASELINE_SUMMARY_ML_TRIGGER.json",
    "t079_metrics": WORKSPACE / "outputs/governanca/T079-PHASE6-PLOTLY-COMPARATIVE-V1_evidence/c057_vs_c060_metrics.json",
    "t079_manifest": WORKSPACE / "outputs/governanca/T079-PHASE6-PLOTLY-COMPARATIVE-V1_manifest.json",
    "template": WORKSPACE / "02_Knowledge_Bank/docs/process/STATE3_PHASE5_LESSONS_LEARNED_T074.md",
}

TRACEABILITY_LINE = (
    "- 2026-03-02T19:30:00Z | LESSONS_LEARNED: T080 Phase 6 Lessons Learned "
    "(14 lições estruturadas, ciclo T076→T079, winner C060 formalizado). "
    "Artefatos: scripts/t080_phase6_lessons_learned.py; "
    "02_Knowledge_Bank/docs/process/STATE3_PHASE6_LESSONS_LEARNED_T080.md; "
    "outputs/governanca/T080-PHASE6-LESSONS-LEARNED-V1_manifest.json"
)

# ── Helpers ───────────────────────────────────────────────────────────────────
def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def gate(name: str, ok: bool, msg: str = "") -> str:
    status = "PASS" if ok else "FAIL"
    line = f"  {name}: [{status}]{' — ' + msg if msg else ''}"
    print(line)
    return status


gates: dict[str, str] = {}
retry_log: list[str] = []

print(f"\n{'='*70}")
print(f"HEADER: {TASK_ID} — Phase 6 Lessons Learned")
print(f"Timestamp: {TIMESTAMP}")
print(f"{'='*70}\n")

# ── G0: Verificar arquivos de referência ──────────────────────────────────────
print("STEP GATES:")
missing = [k for k, p in REF.items() if not p.exists()]
gates["G0_REF_FILES"] = gate("G0_REF_FILES", not missing,
                              f"ausentes: {missing}" if missing else "6/6 presentes")
if missing:
    print(f"\nOVERALL STATUS: [[ FAIL ]] — G0 falhou: {missing}")
    sys.exit(1)

# ── Carregar dados de referência ──────────────────────────────────────────────
with open(REF["t079_metrics"]) as f:
    t079 = json.load(f)

with open(REF["t078_config"]) as f:
    t078_cfg = json.load(f)

with open(REF["t077_model"]) as f:
    t077 = json.load(f)

with open(REF["t078_summary"]) as f:
    t078_sum = json.load(f)

C057 = t079["C057"]
C060 = t079["C060"]

# walk-forward dates
wf_dates = t078_cfg.get("walk_forward", {})
train_end = wf_dates.get("train_end", "2022-12-30")
holdout_start = wf_dates.get("holdout_start", "2023-01-02")
acid_start = wf_dates.get("acid_start", "2024-11-01")
acid_end = wf_dates.get("acid_end", "2025-11-28")

# T077 model params
t077_params = t077.get("params", {})
n_est = t077_params.get("n_estimators", 120)
max_depth = t077_params.get("max_depth", 4)
lr = t077_params.get("learning_rate", 0.06)
thr_model = t077.get("threshold", 0.05)
n_features = len(t077.get("feature_names", [t077_params.get("n_features", 14)]))

# ── Definição das 14 lições ────────────────────────────────────────────────────
LESSONS = [
    {
        "id": "LL-PH6-001",
        "category": "ESTRATEGIA",
        "impact": "POSITIVO",
        "statement": (
            "O pivô para ML foi validado empiricamente. O modelo C060 entrega HOLDOUT R$506k "
            f"vs T072 R$407k (+24.4%), com MDD HOLDOUT={C060['holdout']['mdd']*100:.1f}% "
            f"vs T072 MDD≈-19.5%. A hipótese central da Phase 6 — que o gap é de detecção, "
            "não de conceito — foi confirmada out-of-sample."
        ),
        "evidence_task_id": "T079",
        "evidence_path": "outputs/governanca/T079-PHASE6-PLOTLY-COMPARATIVE-V1_evidence/c057_vs_c060_metrics.json",
        "actionable_rule": (
            "Em próximos ciclos ML, usar o mesmo protocolo: label binário derivado de períodos "
            "conhecidos de deriva + walk-forward + acid window. O conceito do termostato ML é "
            "a arquitetura padrão do projeto a partir da Phase 6."
        ),
    },
    {
        "id": "LL-PH6-002",
        "category": "VALIDACAO",
        "impact": "POSITIVO",
        "statement": (
            "Anti-lookahead via shift(1) global foi aplicado desde T076 e mantido em todo o "
            "pipeline. Nenhuma feature usa dado do dia D na decisão do dia D. A decisão no dia D "
            "usa informação até D-1. Esse controle foi validado como gate de aceitação em T076 "
            "e confirmado na auditoria de cada task subsequente."
        ),
        "evidence_task_id": "T076",
        "evidence_path": "outputs/governanca/T076-EDA-FEATURE-ENGINEERING-V1_manifest.json",
        "actionable_rule": (
            "Qualquer nova feature adicionada ao pipeline DEVE ter gate explícito de anti-lookahead "
            "antes de entrar em ablação. Features sem esse controle são causa de contaminação de "
            "todo o pipeline e devem ser bloqueadas na porta de entrada."
        ),
    },
    {
        "id": "LL-PH6-003",
        "category": "FEATURE_ENG",
        "impact": "NEGATIVO_CORRIGIDO",
        "statement": (
            "T077-V2 falhou por overfitting severo causado por features instáveis: "
            "recall_cv=1.000 vs recall_holdout=0.145, gap=0.855. Features como spc_close_std, "
            "cdi_simple_1d e spc_close_mean apresentaram inversão de sinal entre TRAIN e HOLDOUT. "
            "T077-V3 corrigiu com ALLOWLIST_CORE_V3 (14 features estáveis) e gate de generalização "
            "G_GENERALIZATION_GAP_RECALL (gap < 0.15). Gap final V3: 0.012."
        ),
        "evidence_task_id": "T077",
        "evidence_path": "outputs/governanca/T077-V3-XGBOOST-ABLATION-V1_manifest.json",
        "actionable_rule": (
            "NUNCA submeter feature a ablação sem verificação prévia de estabilidade cross-split "
            "(comparar distribuição TRAIN vs HOLDOUT, sinal de correlação TRAIN vs HOLDOUT). "
            "Feature com inversão de sinal ou KS-stat > threshold deve ir para blacklist antes "
            "de qualquer grid search."
        ),
    },
    {
        "id": "LL-PH6-004",
        "category": "MODEL_TUNING",
        "impact": "NEGATIVO_CORRIGIDO",
        "statement": (
            "T077-V1 falhou logicamente com feasible_count=0/48 e recall=0.000 na acid window. "
            "A causa foi o uso de expanding-window CV com folds temporais iniciais que não "
            "continham a classe positiva ('caixa'), zerando o recall sistematicamente. "
            "StratifiedKFold(5, shuffle) em V2/V3 corrigiu o problema garantindo representação "
            "balanceada da classe minoritária em cada fold."
        ),
        "evidence_task_id": "T077",
        "evidence_path": "00_Strategy/OPS_LOG.md",
        "actionable_rule": (
            "Em problemas com classes raras (< 40% de prevalência) e séries temporais de comprimento "
            "moderado (< 5.000 amostras), usar sempre StratifiedKFold com shuffle. Expanding-window "
            "CV é inadequado quando a classe positiva se concentra em períodos específicos do TRAIN."
        ),
    },
    {
        "id": "LL-PH6-005",
        "category": "MODEL_TUNING",
        "impact": "POSITIVO",
        "statement": (
            f"O threshold ótimo de recall do modelo (thr={thr_model}) não é o threshold ótimo "
            "financeiro. T077-V3 usou thr=0.05 para maximizar recall (0.988 HOLDOUT), mas o "
            "backtest financeiro em T078 mostrou que thr=0.25 (C057/C060) entrega melhor equity "
            "por reduzir falsos positivos que geram trocas desnecessárias. Os dois thresholds "
            "têm funções distintas e devem ser calibrados em etapas separadas."
        ),
        "evidence_task_id": "T078",
        "evidence_path": "src/data_engine/portfolio/T078_ML_TRIGGER_BACKTEST_SELECTED_CONFIG.json",
        "actionable_rule": (
            "Separar pipeline em duas etapas: (1) calibração de threshold de classificação no TRAIN-CV "
            "para maximizar recall; (2) calibração de threshold operacional no backtest financeiro "
            "TRAIN para maximizar equity/Sharpe com constraints de MDD e switches. Nunca usar o "
            "threshold de recall diretamente como threshold operacional."
        ),
    },
    {
        "id": "LL-PH6-006",
        "category": "BACKTEST",
        "impact": "POSITIVO",
        "statement": (
            f"h_out (histerese de saída do modo cash) é o parâmetro com maior impacto no churn "
            f"operacional. C057 (h_out=2) gerou {C057['holdout']['switches']} switches no HOLDOUT; "
            f"C060 (h_out=5) gerou {C060['holdout']['switches']} switches — redução de "
            f"{(1 - C060['holdout']['switches']/C057['holdout']['switches'])*100:.0f}%. "
            "Maior h_out também melhorou equity (R$506k vs R$475k) e MDD (-18.7% vs -25.4%) "
            "porque evita reentradas prematuras no mercado durante períodos de deriva."
        ),
        "evidence_task_id": "T079",
        "evidence_path": "outputs/governanca/T079-PHASE6-PLOTLY-COMPARATIVE-V1_evidence/c057_vs_c060_metrics.json",
        "actionable_rule": (
            "Incluir h_out no range [2, 3, 4, 5, 6, 7] como dimensão obrigatória no grid de histerese. "
            "Preferir h_out assimétrico (h_out > h_in) por design: reação rápida para entrar em cash "
            "(h_in pequeno), saída conservadora do cash (h_out grande). Usar switches_holdout como "
            "métrica de custo operacional ao lado de equity e MDD."
        ),
    },
    {
        "id": "LL-PH6-007",
        "category": "GOVERNANCA",
        "impact": "NEGATIVO_CORRIGIDO",
        "statement": (
            "O tie-break por candidate_id (menor ID) elegeu C057 sobre C060 em T078 de forma "
            "arbitrária. C057 e C060 tinham TRAIN idêntico (equity, MDD, switches=1); a diferença "
            "era apenas h_out (2 vs 5). C057 tinha candidate_id menor e foi escolhido. C060, com "
            "h_out=5, entregou HOLDOUT R$506k vs R$475k de C057 e MDD -18.7% vs -25.4%. "
            "T079 foi necessário para reverter a decisão com evidência auditada."
        ),
        "evidence_task_id": "T079",
        "evidence_path": "outputs/governanca/T079-PHASE6-PLOTLY-COMPARATIVE-V1_evidence/c057_vs_c060_metrics.json",
        "actionable_rule": (
            "Critério de desempate hierárquico obrigatório quando equity_train e MDD_train são "
            "idênticos: (1) switches_train ASC; (2) h_out DESC (preferir menos churn); "
            "(3) candidate_id ASC como último recurso. Documentar critério de desempate no "
            "selection_rule.json de cada ablação."
        ),
    },
    {
        "id": "LL-PH6-008",
        "category": "GOVERNANCA",
        "impact": "POSITIVO",
        "statement": (
            "A distinção entre winner formal de ablação (C057, selecionado em TRAIN-only em T078) "
            "e winner de produto (C060, decisão Owner pós-validação em T079) foi um aprendizado "
            "importante de governança. T078 permanece curado com C057 como seu resultado formal "
            "de ablação — a integridade histórica do registro está preservada. C060 é o winner "
            "de produto da Phase 6 por decisão do Owner com evidência auditada."
        ),
        "evidence_task_id": "T079",
        "evidence_path": "outputs/governanca/T079-PHASE6-PLOTLY-COMPARATIVE-V1_manifest.json",
        "actionable_rule": (
            "Em futuros ciclos: (1) registrar winner formal da ablação como resultado da task de "
            "backtest (TRAIN-only); (2) se evidência out-of-sample posterior sugerir alternativa "
            "superior, criar task de comparação (como T079) antes de sobrescrever; (3) documentar "
            "explicitamente no TASK_REGISTRY e OPS_LOG a distinção entre winner formal e winner "
            "de produto, com referência cruzada entre as duas tasks."
        ),
    },
    {
        "id": "LL-PH6-009",
        "category": "VALIDACAO",
        "impact": "POSITIVO",
        "statement": (
            f"A acid window (nov/2024–nov/2025), completamente fora do TRAIN, é o teste de "
            "generalização mais exigente. C060 entregou nesse período: equity=R$445k, "
            f"MDD={C060['acid']['mdd']*100:.1f}%, {C060['acid']['switches']} switches, "
            "Sharpe≈2.75. O T072 original tinha MDD=-19.2% nesse mesmo período. A redução de "
            "MDD de -19.2% para -5.4% no período mais difícil é a evidência mais forte de "
            "que o modelo generalizou e não decorou o TRAIN."
        ),
        "evidence_task_id": "T079",
        "evidence_path": "outputs/governanca/T079-PHASE6-PLOTLY-COMPARATIVE-V1_evidence/c057_vs_c060_metrics.json",
        "actionable_rule": (
            "Definir acid window explicitamente no início de cada phase como o período mais recente "
            "e mais difícil do HOLDOUT. Se o modelo não passar na acid window, considerar FAIL "
            "independente de métricas agregadas do HOLDOUT. Incluir acid_mdd e acid_sharpe como "
            "métricas obrigatórias no selection_rule.json de backtests futuros."
        ),
    },
    {
        "id": "LL-PH6-010",
        "category": "GOVERNANCA",
        "impact": "NEGATIVO_CORRIGIDO",
        "statement": (
            "T079 EXEC #1 falhou auditoria por hash inconsistente no manifest: o script computava "
            "o SHA256 do report.md ANTES de escrever a linha final 'OVERALL STATUS', resultando "
            "em hash obsoleto no manifest. T079 EXEC #2 corrigiu com a sequência obrigatória: "
            "write_report_complete() → hash_all() → write_manifest(). Nenhuma escrita de artefato "
            "pode ocorrer após a computação dos hashes."
        ),
        "evidence_task_id": "T079",
        "evidence_path": "outputs/governanca/T079-PHASE6-PLOTLY-COMPARATIVE-V1_manifest.json",
        "actionable_rule": (
            "Ordem obrigatória de finalização em todos os scripts de task: "
            "(1) Escrever TODOS os artefatos; "
            "(2) Escrever report.md COMPLETO (incluindo OVERALL STATUS); "
            "(3) Computar SHA256 de todos os artefatos + report; "
            "(4) Escrever manifest.json com os hashes; "
            "(5) NÃO escrever nada mais depois do manifest. "
            "Qualquer desvio desta ordem invalida a integridade do manifest."
        ),
    },
    {
        "id": "LL-PH6-011",
        "category": "ESTRATEGIA",
        "impact": "POSITIVO",
        "statement": (
            "A curva oracle (martelada perfeita — forçar cash nos dois períodos de deriva "
            "conhecidos) entrega ~R$716k no período completo. C060 no HOLDOUT entrega R$506k "
            "vs T072 R$407k. C060 captura ~38% do gap entre T072 e o oracle no HOLDOUT. "
            "Esse percentual de captura do gap é a métrica de eficiência do termostato ML "
            "e serve como referência para Phase 7 e ciclos futuros."
        ),
        "evidence_task_id": "T078",
        "evidence_path": "src/data_engine/portfolio/T078_PORTFOLIO_CURVE_MARTELADA_ORACLE.parquet",
        "actionable_rule": (
            "Sempre manter a curva oracle como benchmark de teto. Reportar 'gap_capture_rate = "
            "(ML_equity - T072_equity) / (oracle_equity - T072_equity)' como KPI de evolução "
            "do termostato entre phases. Meta para Phase 7: gap_capture_rate > 50%."
        ),
    },
    {
        "id": "LL-PH6-012",
        "category": "ESTRATEGIA",
        "impact": "POSITIVO",
        "statement": (
            "Reinforcement Learning (RL) e abordagem híbrida ML+determinístico foram avaliados "
            "pelo CTO e descartados conscientemente. Razões: (a) volume de dados insuficiente "
            "para RL estável (~1.900 pregões); (b) recompensa esparsa (poucos períodos de regime "
            "real); (c) a natureza do problema é de classificação supervisionada, não decisão "
            "sequencial com recompensa acumulada; (d) híbrido adicionaria complexidade sem "
            "evidência de ganho marginal sobre XGBoost puro com features bem validadas."
        ),
        "evidence_task_id": "T077",
        "evidence_path": "00_Strategy/OPS_LOG.md",
        "actionable_rule": (
            "Não reabrir a discussão de RL ou híbrido sem nova evidência concreta: "
            "(a) pelo menos 5.000 pregões disponíveis; ou "
            "(b) demonstração de ganho > 20% de gap_capture_rate sobre o XGBoost puro em "
            "validação out-of-sample. Qualquer proposta sem essas condições deve ser bloqueada "
            "na fase de gate check do Architect."
        ),
    },
    {
        "id": "LL-PH6-013",
        "category": "FEATURE_ENG",
        "impact": "POSITIVO",
        "statement": (
            "ALLOWLIST_CORE_V3 (14 features estáveis validadas pelo CTO) é o conjunto de "
            "features canônico do termostato ML a partir da Phase 6. Blacklist consolidada: "
            "m3_n_tickers e spc_n_tickers (proxies temporais — correlação > 0.9 com tempo). "
            "36 features candidatas descartadas por instabilidade cross-split. "
            "Gap recall CV→HOLDOUT com ALLOWLIST_CORE_V3: 0.012 (< 0.15 — gate PASS)."
        ),
        "evidence_task_id": "T077",
        "evidence_path": "src/data_engine/models/T077_V3_XGB_SELECTED_MODEL.json",
        "actionable_rule": (
            "ALLOWLIST_CORE_V3 deve ser o ponto de partida para Phase 7. Novas features "
            "precisam passar pelo gate de estabilidade (KS-stat, sinal de correlação, "
            "G_GENERALIZATION_GAP_RECALL < 0.15) antes de serem adicionadas à allowlist. "
            "m3_n_tickers e spc_n_tickers permanecem na blacklist permanente até revisão "
            "fundamentada."
        ),
    },
    {
        "id": "LL-PH6-014",
        "category": "BACKTEST",
        "impact": "POSITIVO",
        "statement": (
            "Histerese assimétrica (h_in < h_out) é a configuração ótima por design: "
            "h_in=3 (reação moderada para entrar em cash) + h_out=5 (saída conservadora do "
            "cash) minimiza falsos alarmes de retorno ao mercado durante deriva prolongada. "
            "A configuração h_in=h_out ou h_out < h_in aumenta o churn sem ganho de equity. "
            "Grid com h_out simétrico (h_out=h_in) produziu candidatos com switches_holdout "
            "> 20, causando custos operacionais elevados."
        ),
        "evidence_task_id": "T078",
        "evidence_path": "src/data_engine/portfolio/T078_ML_TRIGGER_BACKTEST_SELECTED_CONFIG.json",
        "actionable_rule": (
            "Grid de histerese em backtests futuros deve usar h_out ≥ h_in como restrição "
            "hard. Candidatos com h_out < h_in devem ser descartados antes da avaliação de "
            "métricas financeiras. Incluir switches_holdout ≤ 20 como constraint adicional "
            "de feasibility nos próximos ciclos (além de equity, MDD, switches_train)."
        ),
    },
]

# ── G1: Contagem de lições ────────────────────────────────────────────────────
gates["G1_LESSON_COUNT"] = gate("G1_LESSON_COUNT", len(LESSONS) >= 12,
                                 f"{len(LESSONS)} lições definidas (mínimo 12)")

# ── G2: Campos obrigatórios ───────────────────────────────────────────────────
REQUIRED_FIELDS = {"id", "category", "impact", "statement",
                   "evidence_task_id", "evidence_path", "actionable_rule"}
missing_fields = [
    f"{ll['id']} falta {REQUIRED_FIELDS - set(ll.keys())}"
    for ll in LESSONS if REQUIRED_FIELDS - set(ll.keys())
]
gates["G2_LESSON_FIELDS"] = gate("G2_LESSON_FIELDS", not missing_fields,
                                  "; ".join(missing_fields) if missing_fields else "todos os 7 campos presentes em 14 lições")

# ── G3: Paths de evidência existentes ────────────────────────────────────────
path_warnings = []
for ll in LESSONS:
    ep = WORKSPACE / ll["evidence_path"]
    if not ep.exists():
        path_warnings.append(f"{ll['id']}: {ll['evidence_path']}")

gates["G3_EVIDENCE_PATHS"] = gate(
    "G3_EVIDENCE_PATHS",
    len(path_warnings) == 0,
    f"WARNING paths ausentes: {path_warnings}" if path_warnings else f"todos os {len(LESSONS)} paths verificados"
)

# ── Criar diretórios ──────────────────────────────────────────────────────────
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
DOCS_DIR.mkdir(parents=True, exist_ok=True)

# ── G4: Winner C060 documentado ──────────────────────────────────────────────
c060_in_doc = any("C060" in ll["statement"] or "C060" in ll["actionable_rule"] for ll in LESSONS)
gates["G4_C060_WINNER_PRESENT"] = gate("G4_C060_WINNER_PRESENT", c060_in_doc,
                                        "C060 encontrado nas lições" if c060_in_doc else "C060 AUSENTE das lições")

# ── Renderizar documento principal ────────────────────────────────────────────
def render_document() -> str:
    lines = []
    lines.append(f"# STATE 3 Phase 6 — Lessons Learned (T080)\n")
    lines.append(f"**Gerado em**: {TIMESTAMP}  ")
    lines.append(f"**Task**: {TASK_ID}  ")
    lines.append(f"**Ciclo coberto**: T076 → T077-V3 → T078 → T079  ")
    lines.append(f"**Winner produto Phase 6**: C060 (thr=0.25, h_in=3, h_out=5)  \n")

    # ── Seção 1: Contexto ─────────────────────────────────────────────────────
    lines.append("## 1) Contexto do ciclo\n")
    lines.append("- **Escopo**: STATE 3 Phase 6 — ML Trigger para Forno Dual-Mode (T076→T079).")
    lines.append("- **Objetivo-mestre**: substituir o termostato determinístico (esgotado após 7 tentativas T039→T072) "
                 "por um classificador supervisionado XGBoost com walk-forward e anti-lookahead estrito.")
    lines.append(f"- **Walk-forward**: TRAIN 2018-07-02 → {train_end} | HOLDOUT {holdout_start} → 2026-02-26.")
    lines.append(f"- **Acid window**: {acid_start} → {acid_end} (completamente fora do TRAIN).")
    lines.append(f"- **Resultado final**: Winner de produto = **C060** (thr=0.25, h_in=3, h_out=5), "
                 f"HOLDOUT equity=R${C060['holdout']['equity_final']:,.0f}, "
                 f"MDD={C060['holdout']['mdd']*100:.1f}%, "
                 f"switches={C060['holdout']['switches']}. "
                 f"Acid: equity=R${C060['acid']['equity_final']:,.0f}, MDD={C060['acid']['mdd']*100:.1f}%.")
    lines.append("- **Evidência de fechamento visual**: `outputs/plots/T079_STATE3_PHASE6D_COMPARATIVE.html`.")
    lines.append("- **Referências de governança**: `00_Strategy/ROADMAP.md`, `00_Strategy/TASK_REGISTRY.md`, `00_Strategy/OPS_LOG.md`.\n")

    # ── Seção 2: O que deu certo ───────────────────────────────────────────────
    lines.append("## 2) O que deu certo\n")
    positivo = [ll for ll in LESSONS if ll["impact"] == "POSITIVO"]
    for ll in positivo:
        lines.append(f"- **{ll['id']}** ({ll['category']}): {ll['statement'].splitlines()[0][:160]}... "
                     f"[evidência: `{ll['evidence_task_id']}` | `{ll['evidence_path']}`]\n")

    # ── Seção 3: O que não deu certo / Erros corrigidos ────────────────────────
    lines.append("## 3) O que não deu certo — Erros corrigidos\n")
    lines.append("### Histórico de versões T077\n")
    lines.append("| Versão | CV Scheme | Resultado | Causa do Problema |")
    lines.append("|---|---|---|---|")
    lines.append("| T077-V1 | Expanding-window (4 folds) | FAIL lógico — recall=0.000, feasible=0/48 | Folds iniciais sem classe positiva → recall sistematicamente zero |")
    lines.append("| T077-V2 | StratifiedKFold(5, shuffle) | PASS técnico / FAIL produto — recall_cv=1.000, recall_holdout=0.145 | Features instáveis com inversão de sinal dominaram o modelo |")
    lines.append("| T077-V3 | StratifiedKFold(5, shuffle) + ALLOWLIST_CORE_V3 | PASS — gap_recall=0.012 | Feature stability gate + allowlist 14 features estáveis |")
    lines.append("")
    negativo = [ll for ll in LESSONS if ll["impact"] == "NEGATIVO_CORRIGIDO"]
    for ll in negativo:
        lines.append(f"- **{ll['id']}** ({ll['category']}): {ll['statement'].splitlines()[0][:200]}... "
                     f"[evidência: `{ll['evidence_task_id']}` | `{ll['evidence_path']}`]\n")

    # ── Seção 4: Decisões de governança ────────────────────────────────────────
    lines.append("## 4) Decisões de governança\n")
    gov = [ll for ll in LESSONS if ll["category"] == "GOVERNANCA"]
    for ll in gov:
        lines.append(f"### {ll['id']}\n")
        lines.append(f"**Categoria**: {ll['category']} | **Impacto**: {ll['impact']}\n")
        lines.append(f"**Statement**: {ll['statement']}\n")
        lines.append(f"**Evidência**: `{ll['evidence_task_id']}` — `{ll['evidence_path']}`\n")
        lines.append(f"**Regra acionável**: {ll['actionable_rule']}\n")

    # ── Seção 5: Tabela comparativa de candidatos Phase 6 ─────────────────────
    lines.append("## 5) Tabela comparativa de candidatos Phase 6\n")
    lines.append("| Candidato | Task | thr | h_in | h_out | TRAIN Equity | HOLDOUT Equity | HOLDOUT MDD | HOLDOUT Switches | Acid Equity | Acid MDD | Status |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    lines.append(f"| C045 (XGB winner) | T077-V3 | 0.05 | — | — | — | HOLDOUT recall=0.988 | — | — | Acid recall=0.985 | — | Winner ablação modelo |")
    lines.append(f"| C057 (backtest) | T078 | 0.25 | 3 | 2 | R${C057['train']['equity_final']:,.0f} | R${C057['holdout']['equity_final']:,.0f} | {C057['holdout']['mdd']*100:.1f}% | {C057['holdout']['switches']} | R${C057['acid']['equity_final']:,.0f} | {C057['acid']['mdd']*100:.1f}% | Winner formal T078 (TRAIN-only) |")
    lines.append(f"| C060 (produto) | T079 | 0.25 | 3 | 5 | R${C060['train']['equity_final']:,.0f} | R${C060['holdout']['equity_final']:,.0f} | {C060['holdout']['mdd']*100:.1f}% | {C060['holdout']['switches']} | R${C060['acid']['equity_final']:,.0f} | {C060['acid']['mdd']*100:.1f}% | **WINNER PRODUTO PHASE 6** (Owner T079) |")
    lines.append(f"| T072 (baseline) | T072 | — | — | — | R$244.630 | R$407.082 | -19.5% | — | ~R$320k | -19.2% | Baseline determinístico |")
    lines.append(f"| Oracle (teto) | T078 | — | — | — | — | ~R$716k | — | — | — | — | Teto máximo teórico |")
    lines.append("")

    # ── Seção 6: Checklist anti-regressão para Phase 7 ────────────────────────
    lines.append("## 6) Checklist anti-regressão para Phase 7\n")
    lines.append("Derivado das `actionable_rule` das 14 lições:\n")
    lines.append("- [ ] Aplicar shift(1) global em todas as features — gate explícito de anti-lookahead (LL-PH6-002)")
    lines.append("- [ ] Verificar estabilidade cross-split de cada feature antes de ablação (KS-stat, sinal correlação) (LL-PH6-003)")
    lines.append("- [ ] Usar StratifiedKFold com shuffle para qualquer problema com classe minoritária < 40% (LL-PH6-004)")
    lines.append("- [ ] Calibrar threshold de classificação (recall) e threshold operacional (financeiro) em etapas separadas (LL-PH6-005)")
    lines.append("- [ ] Incluir h_out ∈ [2,3,4,5,6,7] no grid, com h_out ≥ h_in como constraint hard (LL-PH6-006, LL-PH6-014)")
    lines.append("- [ ] Documentar critério de desempate hierárquico no selection_rule.json (switches_train ASC → h_out DESC → candidate_id) (LL-PH6-007)")
    lines.append("- [ ] Definir acid window explicitamente antes de iniciar o ciclo; incluir acid_mdd e acid_sharpe no selection_rule (LL-PH6-009)")
    lines.append("- [ ] Seguir a ordem: write_all_artifacts → write_report_complete → hash_all → write_manifest (LL-PH6-010)")
    lines.append("- [ ] Reportar gap_capture_rate = (ML_equity - T072_equity) / (oracle_equity - T072_equity); meta > 50% (LL-PH6-011)")
    lines.append("- [ ] Partir de ALLOWLIST_CORE_V3 (14 features); novas features precisam passar no gate G_GENERALIZATION_GAP_RECALL < 0.15 (LL-PH6-013)")
    lines.append("- [ ] Nunca reabrir discussão de RL sem ≥ 5.000 pregões ou ganho demonstrado > 20% de gap_capture_rate (LL-PH6-012)\n")

    # ── Seção 7: Artefatos da Phase 6 ─────────────────────────────────────────
    lines.append("## 7) Artefatos da Phase 6\n")
    lines.append("| Artefato | Task | Tipo |")
    lines.append("|---|---|---|")
    lines.append("| `scripts/t076_eda_feature_engineering_ml_trigger.py` | T076 | Script EDA + Feature Engineering |")
    lines.append("| `src/data_engine/features/T076_FEATURE_MATRIX.parquet` | T076 | Feature matrix (1.902 pregões × 50+ features) |")
    lines.append("| `outputs/governanca/T076-EDA-FEATURE-ENGINEERING-V1_manifest.json` | T076 | Manifest SHA256 |")
    lines.append("| `scripts/t077_xgboost_ablation_walkforward_v2.py` | T077-V3 | Script ablação XGBoost |")
    lines.append(f"| `src/data_engine/models/T077_V3_XGB_SELECTED_MODEL.json` | T077-V3 | Modelo vencedor (C045, {n_est} estimadores, thr={thr_model}) |")
    lines.append("| `src/data_engine/features/T077_V3_PREDICTIONS_DAILY.parquet` | T077-V3 | Predições diárias (TRAIN+HOLDOUT) |")
    lines.append("| `src/data_engine/features/T077_V3_ABLATION_RESULTS.parquet` | T077-V3 | Resultados ablação (96 candidatos) |")
    lines.append("| `outputs/plots/T077_V3_STATE3_PHASE6B_MODEL_DIAGNOSTICS.html` | T077-V3 | Diagnóstico visual do modelo |")
    lines.append("| `outputs/governanca/T077-V3-XGBOOST-ABLATION-V1_manifest.json` | T077-V3 | Manifest SHA256 (17 entradas) |")
    lines.append("| `scripts/t078_ml_trigger_backtest_dual_mode.py` | T078 | Script backtest financeiro |")
    lines.append("| `src/data_engine/portfolio/T078_ML_TRIGGER_BACKTEST_SELECTED_CONFIG.json` | T078 | Config winner C057 (formal) |")
    lines.append("| `src/data_engine/portfolio/T078_PORTFOLIO_CURVE_ML_TRIGGER.parquet` | T078 | Curva equity C057 |")
    lines.append("| `src/data_engine/portfolio/T078_PORTFOLIO_CURVE_MARTELADA_ORACLE.parquet` | T078 | Curva oracle (teto) |")
    lines.append("| `outputs/plots/T078_STATE3_PHASE6C_BACKTEST_COMPARATIVE.html` | T078 | Plotly backtest comparativo |")
    lines.append("| `outputs/governanca/T078-ML-TRIGGER-BACKTEST-V1_manifest.json` | T078 | Manifest SHA256 (12 entradas) |")
    lines.append("| `scripts/t079_plotly_phase6_comparative.py` | T079 | Script comparativo C057 vs C060 |")
    lines.append("| `outputs/plots/T079_STATE3_PHASE6D_COMPARATIVE.html` | T079 | Dashboard Plotly 4 painéis |")
    lines.append("| `outputs/governanca/T079-PHASE6-PLOTLY-COMPARATIVE-V1_evidence/c057_vs_c060_metrics.json` | T079 | Métricas comparativas auditadas |")
    lines.append("| `outputs/governanca/T079-PHASE6-PLOTLY-COMPARATIVE-V1_manifest.json` | T079 | Manifest SHA256 (7 entradas) |")
    lines.append("| `02_Knowledge_Bank/docs/process/STATE3_PHASE6_LESSONS_LEARNED_T080.md` | T080 | Este documento |")
    lines.append("")

    # ── Seção 8: Lições completas (todas as 14) ────────────────────────────────
    lines.append("## 8) Lições detalhadas (todas as 14)\n")
    for ll in LESSONS:
        lines.append(f"### {ll['id']} — {ll['category']} ({ll['impact']})\n")
        lines.append(f"**Statement**: {ll['statement']}\n")
        lines.append(f"**Evidência**: Task `{ll['evidence_task_id']}` — `{ll['evidence_path']}`\n")
        lines.append(f"**Regra acionável**: {ll['actionable_rule']}\n")

    return "\n".join(lines)


doc_content = render_document()

# ── G5: Contagem de linhas ────────────────────────────────────────────────────
line_count = len(doc_content.splitlines())
gates["G5_DOC_LINE_COUNT"] = gate("G5_DOC_LINE_COUNT", line_count >= 120,
                                   f"{line_count} linhas (mínimo 120)")

# Verificar se algum gate crítico falhou antes de escrever
critical_gates = ["G0_REF_FILES", "G1_LESSON_COUNT", "G2_LESSON_FIELDS",
                  "G4_C060_WINNER_PRESENT", "G5_DOC_LINE_COUNT"]
critical_fail = [k for k in critical_gates if gates.get(k) == "FAIL"]

if critical_fail:
    print(f"\nOVERALL STATUS: [[ FAIL ]] — Gates críticos: {critical_fail}")
    sys.exit(1)

# ── Escrever documento principal ──────────────────────────────────────────────
LESSONS_DOC.write_text(doc_content, encoding="utf-8")
print(f"\n  Documento escrito: {LESSONS_DOC} ({line_count} linhas)")

# ── Escrever lessons_index.json ───────────────────────────────────────────────
index = [
    {
        "id": ll["id"],
        "category": ll["category"],
        "impact": ll["impact"],
        "actionable_rule": ll["actionable_rule"][:120] + "...",
    }
    for ll in LESSONS
]
LESSONS_INDEX.write_text(json.dumps({"task_id": TASK_ID, "timestamp": TIMESTAMP,
                                      "total_lessons": len(LESSONS), "lessons": index},
                                     indent=2, ensure_ascii=False), encoding="utf-8")

# ── Renderizar report completo ────────────────────────────────────────────────
def render_report() -> str:
    r = []
    r.append(f"# T080 — Phase 6 Lessons Learned — Execution Report")
    r.append(f"**Timestamp**: {TIMESTAMP}")
    r.append(f"**Task**: {TASK_ID}")
    r.append("")
    r.append("## HEADER")
    r.append(f"task_id={TASK_ID} | timestamp={TIMESTAMP}")
    r.append("")
    r.append("## STEP GATES")
    for k, v in gates.items():
        r.append(f"- {k}: [{v}]")
    r.append("")
    r.append("## RETRY LOG")
    r.append("Nenhum retry necessário." if not retry_log else "\n".join(retry_log))
    r.append("")
    r.append("## ARTIFACT LINKS")
    r.append(f"- Documento: {LESSONS_DOC}")
    r.append(f"- Lessons index: {LESSONS_INDEX}")
    r.append(f"- Report: {REPORT_PATH}")
    r.append(f"- Manifest: {MANIFEST_PATH}")
    r.append("")
    all_pass = all(v == "PASS" for k, v in gates.items() if k in critical_gates)
    r.append(f"## OVERALL STATUS: [[ {'PASS' if all_pass else 'FAIL'} ]]")
    return "\n".join(r)


report_content = render_report()
REPORT_PATH.write_text(report_content, encoding="utf-8")

# ── Computar SHA256 APÓS escrita completa de todos os artefatos ───────────────
artifacts_to_hash = [LESSONS_DOC, LESSONS_INDEX, REPORT_PATH]
manifest_entries = {}
for path in artifacts_to_hash:
    manifest_entries[str(path.relative_to(WORKSPACE))] = sha256(path)

# ── G6: Recomputo de integridade ─────────────────────────────────────────────
recompute_ok = True
for path, expected_hash in manifest_entries.items():
    actual = sha256(WORKSPACE / path)
    if actual != expected_hash:
        recompute_ok = False
        print(f"  HASH MISMATCH: {path}")

gates["G6_HASH_MANIFEST"] = gate("G6_HASH_MANIFEST", recompute_ok,
                                  f"{len(manifest_entries)} artefatos verificados, 0 mismatches" if recompute_ok
                                  else "mismatches detectados — ver acima")

# ── Escrever manifest.json ────────────────────────────────────────────────────
manifest = {
    "task_id": TASK_ID,
    "timestamp": TIMESTAMP,
    "mismatch_count": 0 if recompute_ok else 1,
    "entries": manifest_entries,
}
MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

# ── Atualizar changelog ───────────────────────────────────────────────────────
with open(CHANGELOG, "a", encoding="utf-8") as f:
    f.write(f"\n{TRACEABILITY_LINE}")
gates["G_CHLOG_UPDATED"] = gate("G_CHLOG_UPDATED", True, f"linha anexada em {CHANGELOG}")

# ── OVERALL STATUS ────────────────────────────────────────────────────────────
all_critical_pass = all(gates.get(k) == "PASS" for k in critical_gates)
hash_pass = gates.get("G6_HASH_MANIFEST") == "PASS"
overall_pass = all_critical_pass and hash_pass

print("\n" + "="*70)
print("ARTIFACT LINKS:")
print(f"  - {LESSONS_DOC}")
print(f"  - {LESSONS_INDEX}")
print(f"  - {REPORT_PATH}")
print(f"  - {MANIFEST_PATH}")
print("="*70)
print(f"OVERALL STATUS: [[ {'PASS' if overall_pass else 'FAIL'} ]]")
print("="*70 + "\n")

if not overall_pass:
    sys.exit(1)
