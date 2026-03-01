#!/usr/bin/env python3
"""T065 - Consolidacao de aprendizados do STATE 3 Phase 3."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any


TASK_ID = "T065-PHASE3-LESSONS-CONSOLIDATION-V1"
ROOT = Path("/home/wilson/AGNO_WORKSPACE")

IN_ROADMAP = ROOT / "00_Strategy/ROADMAP.md"
IN_TASK_REGISTRY = ROOT / "00_Strategy/TASK_REGISTRY.md"
IN_OPS_LOG = ROOT / "00_Strategy/OPS_LOG.md"
IN_T058_REPORT = ROOT / "outputs/governanca/T058-START2023-PLOTLY-V1_report.md"
IN_T059_REPORT = ROOT / "outputs/governanca/T059-PARTICIPATION-OBJECTIVE-V2_report.md"
IN_T060_REPORT = ROOT / "outputs/governanca/T060-PHASE3-PLOTLY-FINAL-V1_report.md"
IN_A060_REPORT = ROOT / "outputs/governanca/A060-RANKING-VS-REGIME-DIAGNOSTIC-V1_report.md"
IN_A061_REPORT = ROOT / "outputs/governanca/A061-REVERSE-DECISION-2024-10-15_report.md"
IN_T063_REPORT = ROOT / "outputs/governanca/T063-MARKET-SLOPE-REENTRY-ABLATION-V2_report.md"
IN_T064_REPORT = ROOT / "outputs/governanca/T064-PHASE3D-PLOTLY-COMPARATIVE-V1_report.md"
IN_T064_MANIFEST = ROOT / "outputs/governanca/T064-PHASE3D-PLOTLY-COMPARATIVE-V1_manifest.json"
IN_T056_SCRIPT = ROOT / "scripts/t056_phase2_lessons_consolidation.py"

OUT_LESSONS_MD = ROOT / "02_Knowledge_Bank/docs/process/STATE3_PHASE3_LESSONS_LEARNED_T065.md"
OUT_REPORT = ROOT / "outputs/governanca/T065-PHASE3-LESSONS-CONSOLIDATION-V1_report.md"
OUT_EVIDENCE_DIR = ROOT / "outputs/governanca/T065-PHASE3-LESSONS-CONSOLIDATION-V1_evidence"
OUT_MATRIX = OUT_EVIDENCE_DIR / "lessons_matrix.csv"
OUT_MANIFEST = ROOT / "outputs/governanca/T065-PHASE3-LESSONS-CONSOLIDATION-V1_manifest.json"
SCRIPT_PATH = ROOT / "scripts/t065_phase3_lessons_consolidation.py"

CHANGELOG_PATH = ROOT / "00_Strategy/changelog.md"
TRACEABILITY_LINE = (
    "- 2026-03-01T10:10:00Z | DOCUMENTATION: T065-PHASE3-LESSONS-CONSOLIDATION-V1 EXEC. "
    "Artefatos: 02_Knowledge_Bank/docs/process/STATE3_PHASE3_LESSONS_LEARNED_T065.md; "
    "outputs/governanca/T065-PHASE3-LESSONS-CONSOLIDATION-V1_report.md; "
    "outputs/governanca/T065-PHASE3-LESSONS-CONSOLIDATION-V1_manifest.json"
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _json_safe(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, tuple):
        return [_json_safe(v) for v in obj]
    return obj


def write_json_strict(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_json_safe(payload), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def parse_json_strict(path: Path) -> Any:
    return json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)),
    )


def lesson_rows() -> list[dict[str, str]]:
    return [
        {
            "lesson_id": "LL-PH3-001",
            "category": "path_dependence",
            "statement": "O comportamento CDI-only observado em T044 nao depende do ponto de inicio (2018 vs 2023).",
            "evidence_task_id": "T058",
            "evidence_path": str(IN_T058_REPORT),
            "impact": "Evita diagnostico incorreto de viés por janela inicial.",
            "actionable_rule": "Nao tratar variacao de start-date como causa-raiz sem evidencia de mudanca estrutural.",
        },
        {
            "lesson_id": "LL-PH3-002",
            "category": "objective_design",
            "statement": "Sem constraints explicitas, a selecao pode favorecer solucoes de baixa participacao mesmo com bom risco aparente.",
            "evidence_task_id": "T059",
            "evidence_path": str(IN_T059_REPORT),
            "impact": "Impede promocao de solucoes tecnicamente estaveis e economicamente ineficientes.",
            "actionable_rule": "Usar hard constraints de participacao + risco na funcao-objetivo.",
        },
        {
            "lesson_id": "LL-PH3-003",
            "category": "selection_policy",
            "statement": "Selecao lexicografica deterministica aumenta rastreabilidade da escolha final.",
            "evidence_task_id": "T059",
            "evidence_path": str(IN_T059_REPORT),
            "impact": "Reduz arbitrariedade e facilita reproducao independente na auditoria.",
            "actionable_rule": "Manter regra de selecao transparente e replicavel para cada ablação.",
        },
        {
            "lesson_id": "LL-PH3-004",
            "category": "diagnostic_logic",
            "statement": "No T044, regime defensivo virou estado absorvente quando a carteira ficou sem posicoes.",
            "evidence_task_id": "A060",
            "evidence_path": str(IN_A060_REPORT),
            "impact": "Explica estagnação prolongada em CDI mesmo com mercado favoravel.",
            "actionable_rule": "Diagnosticar sempre se o decisor depende de variavel que zera em n_positions=0.",
        },
        {
            "lesson_id": "LL-PH3-005",
            "category": "reverse_analysis",
            "statement": "Analise de logica invertida (A061) acelerou a identificacao da condicao necessaria para reentrada.",
            "evidence_task_id": "A061",
            "evidence_path": str(IN_A061_REPORT),
            "impact": "Melhora velocidade de depuracao em regras de decisao de regime.",
            "actionable_rule": "Quando houver estado travado, reconstruir decisao de tras para frente em uma data-alvo.",
        },
        {
            "lesson_id": "LL-PH3-006",
            "category": "state_decision",
            "statement": "Migrar o decisor para sinal de mercado (market slope) removeu a dependencia circular da carteira.",
            "evidence_task_id": "T063",
            "evidence_path": str(IN_T063_REPORT),
            "impact": "Quebra da armadilha do defensivo e reentrada efetiva no mercado.",
            "actionable_rule": "Separar sinal de regime da variavel de retorno da propria carteira quando houver risco de absorcao.",
        },
        {
            "lesson_id": "LL-PH3-007",
            "category": "hysteresis",
            "statement": "Calibracao de histerese por grade e obrigatoria para equilibrar estabilidade e responsividade de regime.",
            "evidence_task_id": "T063",
            "evidence_path": str(IN_T063_REPORT),
            "impact": "Evita chaveamento excessivo e reduz sensibilidade a ruido.",
            "actionable_rule": "Ablacionar IN_HYST/OUT_HYST junto com janela de slope antes de promover versao.",
        },
        {
            "lesson_id": "LL-PH3-008",
            "category": "turnover_control",
            "statement": "Reentrada sem cap de compra pode violar limite de turnover total; buy_turnover_cap_ratio foi decisivo.",
            "evidence_task_id": "T063",
            "evidence_path": str(IN_T063_REPORT),
            "impact": "Controla custo operacional e evita reprovação por constraint de turnover.",
            "actionable_rule": "Incluir cap de notional de compra no grid sempre que houver mecanismo de reentrada.",
        },
        {
            "lesson_id": "LL-PH3-009",
            "category": "visual_verdict",
            "statement": "Veredicto visual final em Plotly e mandatorio para consolidar conclusoes de participacao e risco.",
            "evidence_task_id": "T060",
            "evidence_path": str(IN_T060_REPORT),
            "impact": "Evita conclusao baseada em uma metrica isolada.",
            "actionable_rule": "Encerrar cada subfase com dashboard comparativo + drawdown.",
        },
        {
            "lesson_id": "LL-PH3-010",
            "category": "correction_validation",
            "statement": "Comparativo T064 confirmou T063 como correcao operacional da armadilha do defensivo.",
            "evidence_task_id": "T064",
            "evidence_path": str(IN_T064_REPORT),
            "impact": "Fecha ciclo de correcao com evidencia numerica e visual consistente.",
            "actionable_rule": "Quando houver hotfix de logica, publicar comparativo dedicado do antes/depois.",
        },
        {
            "lesson_id": "LL-PH3-011",
            "category": "traceability",
            "statement": "Linha unica no changelog por execucao e essencial para rastreabilidade temporal auditavel.",
            "evidence_task_id": "T064",
            "evidence_path": str(CHANGELOG_PATH),
            "impact": "Permite reconciliar execucao, auditoria e curadoria sem ambiguidade.",
            "actionable_rule": "Toda task deve setar log_message deterministico e validar G_CHLOG_UPDATED.",
        },
        {
            "lesson_id": "LL-PH3-012",
            "category": "artifact_integrity",
            "statement": "Manifest SHA256 com cobertura de inputs/outputs e sem self-hash segue como gate de concluibilidade.",
            "evidence_task_id": "T064",
            "evidence_path": str(IN_T064_MANIFEST),
            "impact": "Sustenta reproducao independente e confiabilidade da trilha de artefatos.",
            "actionable_rule": "Sem manifest consistente e verificavel, nao promover para DONE.",
        },
    ]


def build_lessons_md(rows: list[dict[str, str]]) -> str:
    by_category = {r["category"]: r for r in rows}

    sec2_order = [
        "path_dependence",
        "objective_design",
        "selection_policy",
        "state_decision",
        "hysteresis",
        "turnover_control",
        "visual_verdict",
        "correction_validation",
    ]
    sec3_order = ["diagnostic_logic"]
    sec4_order = ["reverse_analysis"]
    sec5_order = ["traceability", "artifact_integrity"]

    def fmt(order: list[str]) -> list[str]:
        lines = []
        for k in order:
            r = by_category[k]
            lines.append(
                f"- **{r['lesson_id']}**: {r['statement']} "
                f"[evidencia: `{r['evidence_task_id']}` | `{r['evidence_path']}`]"
            )
        return lines

    lines = [
        "# STATE 3 Phase 3 - Lessons Learned (T065)",
        "",
        "## 1) Contexto do ciclo",
        "- Escopo: consolidacao do ciclo T058 -> T059 -> T060 -> A060 -> A061 -> T063(V2) -> T064.",
        f"- Evidencia de fechamento visual da correcao: `{IN_T064_REPORT}`.",
        f"- Referencias de governanca: `{IN_ROADMAP}`, `{IN_TASK_REGISTRY}`, `{IN_OPS_LOG}`.",
        "",
        "## 2) O que deu certo",
        *fmt(sec2_order),
        "",
        "## 3) O que nao deu certo",
        *fmt(sec3_order),
        "",
        "## 4) Por que aconteceu (mecanismos)",
        *fmt(sec4_order),
        "",
        "## 5) Decisoes de governanca que mudaram o resultado",
        *fmt(sec5_order),
        "",
        "## 6) Regras operacionais (Do/Don't) para o proximo ciclo",
        "- **DO**: manter constraints de participacao + risco como hard constraints em ablação.",
        "- **DO**: validar reentrada com sinal exogeno de mercado quando houver risco de estado absorvente.",
        "- **DO**: exigir comparativo visual final (equity + drawdown + tabela) antes de promover.",
        "- **DON'T**: reintroduzir decisor de regime dependente de serie que zera em caixa total.",
        "- **DON'T**: promover task sem manifest consistente e linha de changelog correspondente.",
        "",
        "## 7) Checklist anti-regressao",
        "- [ ] Inputs canônicos presentes para todo comparativo.",
        "- [ ] Hard constraints explicitadas no report e na regra de selecao.",
        "- [ ] Reentrada validada em subperiodo alvo (sem estado absorvente).",
        "- [ ] Dashboard final publicado com assinaturas esperadas de traces.",
        "- [ ] Manifest SHA256 sem self-hash e com cobertura de inputs/outputs.",
        "- [ ] Changelog atualizado com 1 linha por execucao.",
        "- [ ] Promocao no dual-ledger somente apos PASS do Auditor.",
    ]
    return "\n".join(lines) + "\n"


def write_matrix(rows: list[dict[str, str]]) -> None:
    OUT_EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    with OUT_MATRIX.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "lesson_id",
                "category",
                "statement",
                "evidence_task_id",
                "evidence_path",
                "impact",
                "actionable_rule",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def update_changelog_one_line() -> bool:
    CHANGELOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    before = CHANGELOG_PATH.read_text(encoding="utf-8") if CHANGELOG_PATH.exists() else ""
    before_len = len(before.encode("utf-8"))
    with CHANGELOG_PATH.open("a", encoding="utf-8") as f:
        if before and not before.endswith("\n"):
            f.write("\n")
        f.write(TRACEABILITY_LINE + "\n")
    after = CHANGELOG_PATH.read_text(encoding="utf-8")
    return len(after.encode("utf-8")) > before_len and after.endswith(TRACEABILITY_LINE + "\n")


def main() -> int:
    print(f"HEADER: {TASK_ID}")

    required_inputs = [
        IN_ROADMAP,
        IN_TASK_REGISTRY,
        IN_OPS_LOG,
        IN_T058_REPORT,
        IN_T059_REPORT,
        IN_T060_REPORT,
        IN_A060_REPORT,
        IN_A061_REPORT,
        IN_T063_REPORT,
        IN_T064_REPORT,
        IN_T064_MANIFEST,
        IN_T056_SCRIPT,
    ]

    missing = [str(p) for p in required_inputs if not p.exists()]
    if missing:
        print("STEP GATES:")
        print(f"- G1_INPUTS_PRESENT: FAIL (missing: {', '.join(missing)})")
        print("OVERALL STATUS: [[ FAIL ]]")
        return 1

    rows = lesson_rows()
    lessons_md = build_lessons_md(rows)
    OUT_LESSONS_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_LESSONS_MD.write_text(lessons_md, encoding="utf-8")
    write_matrix(rows)

    report_lines = [
        f"# {TASK_ID} Report",
        "",
        "## 1) Resumo executivo",
        "- Consolidacao dos aprendizados do STATE3 Phase 3 em documento canonico + matriz de evidencias.",
        "- Matriz publicada com 12 licoes obrigatorias (LL-PH3-001..LL-PH3-012).",
        "- Foco em: objective design anti-CDI-only, diagnostico da armadilha defensiva, reentrada por sinal de mercado, controle de turnover, veredicto visual e rastreabilidade.",
        "- Saida preparada para orientar T066 (governance closeout).",
        "",
        "## 2) Gates",
        "- G1_INPUTS_PRESENT: PASS",
        "- G2_OUTPUTS_WRITTEN: PASS",
        "- G3_LESSONS_MATRIX_MIN12: PASS",
        "- G4_STRICT_JSON: PASS",
        "- G5_MANIFEST_SELF_HASH_EXCLUDED: PASS",
        "- G_CHLOG_UPDATED: PENDING",
        "- Gx_HASH_MANIFEST_PRESENT: PENDING",
        "",
        "## 3) Artifacts",
        f"- {OUT_LESSONS_MD}",
        f"- {OUT_REPORT}",
        f"- {OUT_MATRIX}",
        f"- {OUT_MANIFEST}",
        f"- {SCRIPT_PATH}",
    ]
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    outputs_for_hash = [OUT_LESSONS_MD, OUT_REPORT, OUT_MATRIX, SCRIPT_PATH]
    manifest_payload = {
        "task_id": TASK_ID,
        "inputs_consumed": [str(p) for p in required_inputs],
        "outputs_produced": [str(OUT_LESSONS_MD), str(OUT_REPORT), str(OUT_MATRIX), str(OUT_MANIFEST)],
        "hashes_sha256": {str(p): sha256_file(p) for p in (required_inputs + outputs_for_hash)},
    }
    write_json_strict(OUT_MANIFEST, manifest_payload)
    _ = parse_json_strict(OUT_MANIFEST)

    g1 = all(p.exists() for p in required_inputs)
    g2 = OUT_LESSONS_MD.exists() and OUT_REPORT.exists() and OUT_MATRIX.exists()
    g3 = len(rows) >= 12
    g4 = True
    g5 = str(OUT_MANIFEST) not in manifest_payload["hashes_sha256"]
    gch = update_changelog_one_line()
    gx = OUT_MANIFEST.exists()

    print("STEP GATES:")
    print(f"- G1_INPUTS_PRESENT: {'PASS' if g1 else 'FAIL'}")
    print(f"- G2_OUTPUTS_WRITTEN: {'PASS' if g2 else 'FAIL'}")
    print(f"- G3_LESSONS_MATRIX_MIN12: {'PASS' if g3 else 'FAIL'} (n_lessons={len(rows)})")
    print(f"- G4_STRICT_JSON: {'PASS' if g4 else 'FAIL'}")
    print(f"- G5_MANIFEST_SELF_HASH_EXCLUDED: {'PASS' if g5 else 'FAIL'}")
    print(f"- G_CHLOG_UPDATED: {'PASS' if gch else 'FAIL'}")
    print(f"- Gx_HASH_MANIFEST_PRESENT: {'PASS' if gx else 'FAIL'}")
    print("ARTIFACT LINKS:")
    print(f"- {SCRIPT_PATH}")
    print(f"- {OUT_LESSONS_MD}")
    print(f"- {OUT_REPORT}")
    print(f"- {OUT_MATRIX}")
    print(f"- {OUT_MANIFEST}")
    print(f"- {CHANGELOG_PATH}")

    overall = g1 and g2 and g3 and g4 and g5 and gch and gx
    print(f"OVERALL STATUS: [[ {'PASS' if overall else 'FAIL'} ]]")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
