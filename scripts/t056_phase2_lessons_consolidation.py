#!/usr/bin/env python3
"""T056 - Consolidacao de aprendizados do STATE3 Phase 2."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any


TASK_ID = "T056-PHASE2-LESSONS-CONSOLIDATION-V1"
ROOT = Path("/home/wilson/AGNO_WORKSPACE")

IN_TASK_REGISTRY = ROOT / "00_Strategy/TASK_REGISTRY.md"
IN_OPS_LOG = ROOT / "00_Strategy/OPS_LOG.md"
IN_T044_REPORT = ROOT / "outputs/governanca/T044-ANTI-DRIFT-GUARDRAILS-V2_report.md"
IN_T044_MANIFEST = ROOT / "outputs/governanca/T044-ANTI-DRIFT-GUARDRAILS-V2_manifest.json"
IN_T044_SELECTED = ROOT / "src/data_engine/portfolio/T044_GUARDRAILS_SELECTED_CONFIG.json"
IN_T055_REPORT = ROOT / "outputs/governanca/T055-PHASE2-PLOTLY-FINAL-V1_report.md"
IN_T055_MANIFEST = ROOT / "outputs/governanca/T055-PHASE2-PLOTLY-FINAL-V1_manifest.json"
IN_T055_PLOT = ROOT / "outputs/plots/T055_STATE3_PHASE2_FINAL_COMPARATIVE.html"
IN_T053_REPORT = ROOT / "outputs/governanca/T053-CEP-SLOPE-STATE-TESTS-V1_report.md"
IN_T053_MANIFEST = ROOT / "outputs/governanca/T053-CEP-SLOPE-STATE-TESTS-V1_manifest.json"
IN_T051_REPORT = ROOT / "outputs/governanca/T051-LOCAL-RULE-CANDIDATES-V1_report.md"
IN_T052_REPORT = ROOT / "outputs/governanca/T052-ROBUSTNESS-SUBPERIODS-V1_report.md"
IN_T040_SUBPERIODS = ROOT / "src/data_engine/portfolio/T040_METRICS_BY_SUBPERIOD.csv"
IN_ROUTING_RULE = ROOT / ".cursor/rules/agno-llm-routing-fixed.mdc"
IN_CTO_RULE = ROOT / ".cursor/rules/agno-cto-resposta-io-v4.mdc"

OUT_LESSONS_MD = ROOT / "02_Knowledge_Bank/docs/process/STATE3_PHASE2_LESSONS_LEARNED_T056.md"
OUT_REPORT = ROOT / "outputs/governanca/T056-PHASE2-LESSONS-CONSOLIDATION-V1_report.md"
OUT_EVIDENCE_DIR = ROOT / "outputs/governanca/T056-PHASE2-LESSONS-CONSOLIDATION-V1_evidence"
OUT_MATRIX = OUT_EVIDENCE_DIR / "lessons_matrix.csv"
OUT_MANIFEST = ROOT / "outputs/governanca/T056-PHASE2-LESSONS-CONSOLIDATION-V1_manifest.json"
SCRIPT_PATH = ROOT / "scripts/t056_phase2_lessons_consolidation.py"


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
    path.write_text(json.dumps(_json_safe(payload), indent=2, sort_keys=True, allow_nan=False), encoding="utf-8")


def parse_json_strict(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"), parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))


def lesson_rows() -> list[dict[str, str]]:
    return [
        {
            "lesson_id": "LL-PH2-001",
            "category": "state_modeling",
            "statement": "CEP em logret captura choques agudos, mas pode falhar na deriva lenta; CEP+SLOPE melhora granularidade do decisor.",
            "evidence_task_id": "T053",
            "evidence_path": str(IN_T053_REPORT),
            "impact": "Aumenta sensibilidade a tendencias persistentes.",
            "actionable_rule": "Combinar indicador de causa especial com slope derivado de X_t em novos decisores.",
        },
        {
            "lesson_id": "LL-PH2-002",
            "category": "parameter_selection",
            "statement": "Parametros 'por exemplo' devem ser evitados; selecao precisa ser data-driven via ablação deterministica.",
            "evidence_task_id": "T044",
            "evidence_path": str(IN_T044_REPORT),
            "impact": "Reduz arbitrariedade e aumenta reprodutibilidade.",
            "actionable_rule": "Toda calibracao de guardrail deve usar grade de candidatos e regra objetiva de escolha.",
        },
        {
            "lesson_id": "LL-PH2-003",
            "category": "data_integrity",
            "statement": "JSON estrito (RFC8259) e obrigatorio; NaN/Infinity devem virar null.",
            "evidence_task_id": "T044",
            "evidence_path": str(IN_T044_MANIFEST),
            "impact": "Evita quebra de interoperabilidade e auditoria.",
            "actionable_rule": "Usar serializacao strict JSON em todos os artefatos de governanca.",
        },
        {
            "lesson_id": "LL-PH2-004",
            "category": "manifest_integrity",
            "statement": "Manifest nao pode incluir self-hash.",
            "evidence_task_id": "T044",
            "evidence_path": str(IN_T044_MANIFEST),
            "impact": "Permite verificacao de integridade consistente.",
            "actionable_rule": "Excluir o proprio manifest do bloco hashes_sha256.",
        },
        {
            "lesson_id": "LL-PH2-005",
            "category": "strategy_complexity",
            "statement": "Aumento de complexidade pode degradar retorno sem melhorar risco.",
            "evidence_task_id": "T055",
            "evidence_path": str(IN_T055_REPORT),
            "impact": "Complexidade excessiva pode destruir performance.",
            "actionable_rule": "Comparar sempre contra baseline simples antes de promover novas camadas.",
        },
        {
            "lesson_id": "LL-PH2-006",
            "category": "guardrails",
            "statement": "Cadencia de compra foi o guardrail dominante no vencedor C021.",
            "evidence_task_id": "T044",
            "evidence_path": str(IN_T044_SELECTED),
            "impact": "Controla drift e turnover sem cap adicional.",
            "actionable_rule": "Priorizar cadencia como alavanca primaria e testar cap como opcional.",
        },
        {
            "lesson_id": "LL-PH2-007",
            "category": "visual_audit",
            "statement": "Dashboards Plotly sao evidencia operacional obrigatoria para leitura de comportamento temporal.",
            "evidence_task_id": "T055",
            "evidence_path": str(IN_T055_PLOT),
            "impact": "Aumenta capacidade de diagnostico de regime e drawdown.",
            "actionable_rule": "Toda fase deve ter artefato visual comparativo final.",
        },
        {
            "lesson_id": "LL-PH2-008",
            "category": "benchmarking",
            "statement": "A solucao precisa bater simultaneamente T037 (meta) e T039 (baseline).",
            "evidence_task_id": "T055",
            "evidence_path": str(IN_T055_REPORT),
            "impact": "Evita promocao de melhorias parciais.",
            "actionable_rule": "Adicionar check de dominancia em equity/CAGR/MDD/Sharpe em tasks comparativas.",
        },
        {
            "lesson_id": "LL-PH2-009",
            "category": "robustness",
            "statement": "Robustez por subperiodos canonicos evita overfitting temporal.",
            "evidence_task_id": "T052",
            "evidence_path": str(IN_T052_REPORT),
            "impact": "Aumenta confianca na generalizacao dos candidatos.",
            "actionable_rule": "Sempre incluir cobertura por subperiodos antes de promover regras.",
        },
        {
            "lesson_id": "LL-PH2-010",
            "category": "governance",
            "statement": "Dual-ledger (produto vs operacao) preserva rastreabilidade sem mistura de finalidade.",
            "evidence_task_id": "M-017",
            "evidence_path": str(IN_OPS_LOG),
            "impact": "Historico fica claro e auditavel.",
            "actionable_rule": "Registrar evolucao funcional no TASK_REGISTRY e manutencao no OPS_LOG.",
        },
        {
            "lesson_id": "LL-PH2-011",
            "category": "model_routing",
            "statement": "Roteamento fixo de LLM por papel e gate obrigatorio para evitar erro de processo.",
            "evidence_task_id": "M-017",
            "evidence_path": str(IN_ROUTING_RULE),
            "impact": "Reduz falhas de governanca por modelo incorreto.",
            "actionable_rule": "Bloquear execucao/arquitetura/auditoria/curadoria em caso de mismatch de modelo.",
        },
        {
            "lesson_id": "LL-PH2-012",
            "category": "hash_policy",
            "statement": "Policy de manifest SHA256 com cobertura de inputs/outputs e requisito canonico de concluibilidade.",
            "evidence_task_id": "M-015",
            "evidence_path": str(IN_CTO_RULE),
            "impact": "Assegura trilha de auditoria confiavel.",
            "actionable_rule": "Sem manifest consistente, task nao pode ser promovida para DONE.",
        },
    ]


def build_lessons_md(rows: list[dict[str, str]]) -> str:
    def fmt_items(category: str) -> list[str]:
        out = []
        for r in rows:
            if r["category"] == category:
                out.append(
                    f"- **{r['lesson_id']}**: {r['statement']} "
                    f"[evidencia: `{r['evidence_task_id']}` | `{r['evidence_path']}`]"
                )
        return out

    sec2 = fmt_items("state_modeling") + fmt_items("parameter_selection") + fmt_items("guardrails") + fmt_items("visual_audit") + fmt_items("robustness")
    sec3 = fmt_items("strategy_complexity") + fmt_items("data_integrity") + fmt_items("manifest_integrity")
    sec4 = fmt_items("benchmarking")
    sec5 = fmt_items("governance") + fmt_items("model_routing") + fmt_items("hash_policy")

    lines = [
        "# STATE 3 Phase 2 - Lessons Learned (T056)",
        "",
        "## 1) Contexto do ciclo",
        "- Escopo: consolidacao do ciclo T050 -> T053 -> T051 -> T052 -> T044 (R2) -> T055.",
        f"- Baseline/meta de referencia: T039 (baseline) e T037 (meta) [evidencia: `T055` | `{IN_T055_REPORT}`].",
        f"- Solucao promovida no ciclo: guardrails anti-drift T044 [evidencia: `T044` | `{IN_T044_REPORT}`].",
        "",
        "## 2) O que deu certo",
        *sec2,
        "",
        "## 3) O que nao deu certo",
        *sec3,
        "",
        "## 4) Por que aconteceu (mecanismos)",
        *sec4,
        "- A combinacao de evidencias numericas e visuais reduziu risco de conclusao apressada por metrica isolada.",
        "",
        "## 5) Decisoes de governanca que mudaram o resultado",
        *sec5,
        "",
        "## 6) Regras operacionais (Do/Don't) para o proximo ciclo",
        "- **DO**: usar ablação data-driven para qualquer calibracao de parametro operacional.",
        "- **DO**: exigir report + manifest + evidencia visual antes de promover para DONE.",
        "- **DO**: validar robustez por subperiodos canonicos antes de rollout de regras.",
        "- **DON'T**: usar parametro arbitrario ('por exemplo') sem experimento comparativo.",
        "- **DON'T**: aceitar manifest com self-hash ou JSON nao estrito.",
        "- **DON'T**: continuar quando houver mismatch de modelo por papel.",
        "",
        "## 7) Checklist anti-regressao",
        "- [ ] Inputs obrigatorios presentes e versionados.",
        "- [ ] Gates G1..Gx explicitados no report.",
        "- [ ] JSON estrito validado sem NaN/Infinity.",
        "- [ ] Manifest SHA256 consistente, sem self-hash.",
        "- [ ] Comparativo final vs T037 e T039 publicado.",
        "- [ ] Atualizacao dual-ledger somente apos PASS do Auditor.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    print(f"HEADER: {TASK_ID}")
    print("STEP GATES:")

    required_inputs = [
        IN_TASK_REGISTRY,
        IN_OPS_LOG,
        IN_T044_REPORT,
        IN_T044_MANIFEST,
        IN_T044_SELECTED,
        IN_T055_REPORT,
        IN_T055_MANIFEST,
        IN_T055_PLOT,
        IN_T053_REPORT,
        IN_T053_MANIFEST,
        IN_T051_REPORT,
        IN_T052_REPORT,
        IN_T040_SUBPERIODS,
        IN_ROUTING_RULE,
        IN_CTO_RULE,
    ]

    missing = [str(p) for p in required_inputs if not p.exists()]
    g1 = len(missing) == 0
    print(f"- G1_INPUTS_PRESENT: {'PASS' if g1 else 'FAIL'}")
    if not g1:
        print(f"  missing_inputs={missing}")
        print("RETRY LOG: NONE")
        print("OVERALL STATUS: [[ FAIL ]]")
        return 1

    OUT_LESSONS_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)

    rows = lesson_rows()
    fieldnames = ["lesson_id", "category", "statement", "evidence_task_id", "evidence_path", "impact", "actionable_rule"]
    with OUT_MATRIX.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    OUT_LESSONS_MD.write_text(build_lessons_md(rows), encoding="utf-8")
    g2 = OUT_LESSONS_MD.exists() and OUT_MATRIX.exists()
    print(f"- G2_OUTPUTS_WRITTEN: {'PASS' if g2 else 'FAIL'}")

    required_ids = {f"LL-PH2-{i:03d}" for i in range(1, 13)}
    found_ids = {r["lesson_id"] for r in rows}
    g3 = len(rows) >= 12 and required_ids.issubset(found_ids)
    print(f"- G3_LESSONS_MATRIX_MIN12: {'PASS' if g3 else 'FAIL'} (rows={len(rows)})")

    report_lines = [
        f"# {TASK_ID} Report",
        "",
        "## 1) Resumo executivo",
        "- Consolidacao dos aprendizados do STATE3 Phase 2 em documento canonico + matriz de evidencias.",
        "- Matriz publicada com 12 licoes obrigatorias (LL-PH2-001..LL-PH2-012).",
        "- Foco em: modelagem de estado, calibracao data-driven, integridade JSON/manifest e governanca de roteamento de modelo.",
        "- Evidencias cruzadas por task_id e path para evitar narrativa sem rastreabilidade.",
        "- Saida preparada para orientar T047 e proximos ciclos de melhoria.",
        "",
        "## 2) Gates",
        f"- G1_INPUTS_PRESENT: {'PASS' if g1 else 'FAIL'}",
        f"- G2_OUTPUTS_WRITTEN: {'PASS' if g2 else 'FAIL'}",
        f"- G3_LESSONS_MATRIX_MIN12: {'PASS' if g3 else 'FAIL'}",
        "- G4_STRICT_JSON: PENDING",
        "- G5_MANIFEST_SELF_HASH_EXCLUDED: PENDING",
        "- Gx_HASH_MANIFEST_PRESENT: PENDING",
        "",
        "## 3) Artifacts",
        f"- {OUT_LESSONS_MD}",
        f"- {OUT_MATRIX}",
    ]
    OUT_REPORT.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    outputs = [OUT_LESSONS_MD, OUT_REPORT, OUT_MATRIX, OUT_MANIFEST, SCRIPT_PATH]
    manifest = {
        "task_id": TASK_ID,
        "inputs_consumed": [str(p) for p in required_inputs],
        "outputs_produced": [str(p) for p in outputs],
        "hashes_sha256": {
            **{str(p): sha256_file(p) for p in required_inputs},
            **{str(p): sha256_file(p) for p in outputs if p.exists() and p != OUT_MANIFEST},
        },
    }
    write_json_strict(OUT_MANIFEST, manifest)

    g4 = True
    for p in [OUT_MANIFEST]:
        try:
            parse_json_strict(p)
        except Exception:
            g4 = False
            break
    g5 = str(OUT_MANIFEST) not in manifest.get("hashes_sha256", {})
    gx = OUT_MANIFEST.exists()

    report_lines = [
        f"# {TASK_ID} Report",
        "",
        "## 1) Resumo executivo",
        "- Consolidacao dos aprendizados do STATE3 Phase 2 em documento canonico + matriz de evidencias.",
        "- Matriz publicada com 12 licoes obrigatorias (LL-PH2-001..LL-PH2-012).",
        "- Foco em: modelagem de estado, calibracao data-driven, integridade JSON/manifest e governanca de roteamento de modelo.",
        "- Evidencias cruzadas por task_id e path para evitar narrativa sem rastreabilidade.",
        "- Saida preparada para orientar T047 e proximos ciclos de melhoria.",
        "",
        "## 2) Gates",
        f"- G1_INPUTS_PRESENT: {'PASS' if g1 else 'FAIL'}",
        f"- G2_OUTPUTS_WRITTEN: {'PASS' if g2 else 'FAIL'}",
        f"- G3_LESSONS_MATRIX_MIN12: {'PASS' if g3 else 'FAIL'}",
        f"- G4_STRICT_JSON: {'PASS' if g4 else 'FAIL'}",
        f"- G5_MANIFEST_SELF_HASH_EXCLUDED: {'PASS' if g5 else 'FAIL'}",
        f"- Gx_HASH_MANIFEST_PRESENT: {'PASS' if gx else 'FAIL'}",
        "",
        "## 3) Artifacts",
        f"- {OUT_LESSONS_MD}",
        f"- {OUT_REPORT}",
        f"- {OUT_MATRIX}",
        f"- {OUT_MANIFEST}",
        f"- {SCRIPT_PATH}",
    ]
    OUT_REPORT.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    manifest["hashes_sha256"][str(OUT_REPORT)] = sha256_file(OUT_REPORT)
    write_json_strict(OUT_MANIFEST, manifest)
    g5 = str(OUT_MANIFEST) not in manifest.get("hashes_sha256", {})

    print(f"- G4_STRICT_JSON: {'PASS' if g4 else 'FAIL'}")
    print(f"- G5_MANIFEST_SELF_HASH_EXCLUDED: {'PASS' if g5 else 'FAIL'}")
    print(f"- Gx_HASH_MANIFEST_PRESENT: {'PASS' if gx else 'FAIL'}")
    print("RETRY LOG: NONE")
    print("ARTIFACT LINKS:")
    print(f"- {OUT_LESSONS_MD}")
    print(f"- {OUT_REPORT}")
    print(f"- {OUT_MATRIX}")
    print(f"- {OUT_MANIFEST}")

    ok = all([g1, g2, g3, g4, g5, gx])
    print(f"OVERALL STATUS: [[ {'PASS' if ok else 'FAIL'} ]]")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
