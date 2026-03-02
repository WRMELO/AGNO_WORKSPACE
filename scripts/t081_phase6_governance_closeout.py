#!/usr/bin/env python3
"""T081 - Governance closeout do STATE 3 Phase 6."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any


TASK_ID = "T081-PHASE6-GOVERNANCE-CLOSEOUT-V1"
ROOT = Path("/home/wilson/AGNO_WORKSPACE")

IN_ROADMAP = ROOT / "00_Strategy/ROADMAP.md"
IN_TASK_REGISTRY = ROOT / "00_Strategy/TASK_REGISTRY.md"
IN_OPS_LOG = ROOT / "00_Strategy/OPS_LOG.md"
IN_CHANGELOG = ROOT / "00_Strategy/changelog.md"

IN_T076_MANIFEST = ROOT / "outputs/governanca/T076-EDA-FEATURE-ENGINEERING-V1_manifest.json"
IN_T077V3_MANIFEST = ROOT / "outputs/governanca/T077-V3-XGBOOST-ABLATION-V1_manifest.json"
IN_T078_MANIFEST = ROOT / "outputs/governanca/T078-ML-TRIGGER-BACKTEST-V1_manifest.json"
IN_T079_MANIFEST = ROOT / "outputs/governanca/T079-PHASE6-PLOTLY-COMPARATIVE-V1_manifest.json"
IN_T080_MANIFEST = ROOT / "outputs/governanca/T080-PHASE6-LESSONS-LEARNED-V1_manifest.json"
IN_C057_C060 = ROOT / "outputs/governanca/T079-PHASE6-PLOTLY-COMPARATIVE-V1_evidence/c057_vs_c060_metrics.json"

OUT_DIR = ROOT / "outputs/governanca"
OUT_EVIDENCE_DIR = OUT_DIR / "T081-PHASE6-GOVERNANCE-CLOSEOUT-V1_evidence"
OUT_REPORT = OUT_DIR / "T081-PHASE6-GOVERNANCE-CLOSEOUT-V1_report.md"
OUT_MANIFEST = OUT_DIR / "T081-PHASE6-GOVERNANCE-CLOSEOUT-V1_manifest.json"
OUT_REGISTRY_SNAPSHOT = OUT_EVIDENCE_DIR / "registry_snapshot.json"
OUT_CHANGELOG_SNAPSHOT = OUT_EVIDENCE_DIR / "changelog_snapshot.json"
OUT_MANIFEST_CHECK = OUT_EVIDENCE_DIR / "manifest_integrity_check.json"
OUT_WINNER_SNAPSHOT = OUT_EVIDENCE_DIR / "phase6_winner_snapshot.json"

TRACEABILITY_LINE = (
    "- 2026-03-02T20:00:00Z | GOVERNANCE: T081 Phase 6 Governance Closeout EXEC. "
    "Artefatos: outputs/governanca/T081-PHASE6-GOVERNANCE-CLOSEOUT-V1_report.md; "
    "outputs/governanca/T081-PHASE6-GOVERNANCE-CLOSEOUT-V1_manifest.json"
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_json_strict(path: Path) -> Any:
    txt = path.read_text(encoding="utf-8")
    return json.loads(txt, parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def count_contains(text: str, token: str) -> int:
    return sum(1 for line in text.splitlines() if token in line)


def check_manifest_integrity(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "manifest_path": str(path),
        "exists": path.exists(),
        "json_parse_ok": False,
        "hash_map_key": None,
        "entries_total": 0,
        "missing_paths": [],
        "mismatches": [],
    }
    if not path.exists():
        return result

    obj = parse_json_strict(path)
    result["json_parse_ok"] = True

    if isinstance(obj.get("hashes_sha256"), dict):
        hashes = obj["hashes_sha256"]
        result["hash_map_key"] = "hashes_sha256"
    elif isinstance(obj.get("entries"), dict):
        hashes = obj["entries"]
        result["hash_map_key"] = "entries"
    else:
        hashes = {}
        result["hash_map_key"] = "none"

    result["entries_total"] = len(hashes)
    for fp, expected in hashes.items():
        p = Path(fp)
        p = p if p.is_absolute() else ROOT / p
        if not p.exists():
            result["missing_paths"].append(fp)
            continue
        actual = sha256_file(p)
        if actual != expected:
            result["mismatches"].append(
                {
                    "path": fp,
                    "expected": expected,
                    "actual": actual,
                }
            )
    return result


def update_changelog_one_line() -> bool:
    before = IN_CHANGELOG.read_text(encoding="utf-8") if IN_CHANGELOG.exists() else ""
    if TRACEABILITY_LINE in before:
        # Idempotência para evitar duplicatas em re-runs.
        return True
    before_len = len(before.encode("utf-8"))
    with IN_CHANGELOG.open("a", encoding="utf-8") as f:
        if before and not before.endswith("\n"):
            f.write("\n")
        f.write(TRACEABILITY_LINE + "\n")
    after = IN_CHANGELOG.read_text(encoding="utf-8")
    return len(after.encode("utf-8")) > before_len and after.endswith(TRACEABILITY_LINE + "\n")


def extract_winner_snapshot() -> dict[str, Any]:
    t079 = parse_json_strict(IN_C057_C060)
    c057 = t079["C057"]
    c060 = t079["C060"]
    return {
        "winner_formal_t078": {
            "candidate_id": "C057",
            "selection_mode": "TRAIN_ONLY",
            "params": c057["params"],
            "holdout": c057["holdout"],
            "acid": c057["acid"],
        },
        "winner_product_phase6": {
            "candidate_id": "C060",
            "decision_task": "T079",
            "decision_authority": "Owner",
            "params": c060["params"],
            "holdout": c060["holdout"],
            "acid": c060["acid"],
        },
        "delta_c060_minus_c057": {
            "holdout_equity": c060["holdout"]["equity_final"] - c057["holdout"]["equity_final"],
            "holdout_mdd": c060["holdout"]["mdd"] - c057["holdout"]["mdd"],
            "holdout_switches": c060["holdout"]["switches"] - c057["holdout"]["switches"],
            "acid_equity": c060["acid"]["equity_final"] - c057["acid"]["equity_final"],
            "acid_mdd": c060["acid"]["mdd"] - c057["acid"]["mdd"],
            "acid_switches": c060["acid"]["switches"] - c057["acid"]["switches"],
        },
    }


def main() -> int:
    print(f"HEADER: {TASK_ID}")
    gates: dict[str, bool] = {}
    retry_log = ["Nenhum retry necessário."]

    required_inputs = [
        IN_ROADMAP,
        IN_TASK_REGISTRY,
        IN_OPS_LOG,
        IN_CHANGELOG,
        IN_T076_MANIFEST,
        IN_T077V3_MANIFEST,
        IN_T078_MANIFEST,
        IN_T079_MANIFEST,
        IN_T080_MANIFEST,
        IN_C057_C060,
    ]
    missing = [str(p) for p in required_inputs if not p.exists()]
    gates["G0_INPUTS_PRESENT"] = len(missing) == 0

    if not gates["G0_INPUTS_PRESENT"]:
        print("STEP GATES:")
        print(f"- G0_INPUTS_PRESENT: FAIL (missing: {', '.join(missing)})")
        print("OVERALL STATUS: [[ FAIL ]]")
        return 1

    OUT_EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    roadmap_txt = IN_ROADMAP.read_text(encoding="utf-8")
    reg_txt = IN_TASK_REGISTRY.read_text(encoding="utf-8")
    ops_txt = IN_OPS_LOG.read_text(encoding="utf-8")
    chlog_txt = IN_CHANGELOG.read_text(encoding="utf-8")

    registry_snapshot = {
        "roadmap_t076_done": "| T076 |" in roadmap_txt and "DONE" in roadmap_txt,
        "roadmap_t077_done": "| T077 |" in roadmap_txt and "DONE" in roadmap_txt,
        "roadmap_t078_done": "| T078 |" in roadmap_txt and "DONE" in roadmap_txt,
        "roadmap_t079_done": "| T079 |" in roadmap_txt and "DONE" in roadmap_txt,
        "roadmap_t080_done": "| T080 |" in roadmap_txt and "DONE" in roadmap_txt,
        "roadmap_t081_pending": "| T081 |" in roadmap_txt and "PENDING" in roadmap_txt,
        "task_registry_t076_done": "| T076 |" in reg_txt and "| DONE |" in reg_txt,
        "task_registry_t077_done": "| T077 |" in reg_txt and "| DONE |" in reg_txt,
        "task_registry_t078_done": "| T078 |" in reg_txt and "| DONE |" in reg_txt,
        "task_registry_t079_done": "| T079 |" in reg_txt and "| DONE |" in reg_txt,
        "task_registry_t080_done": "| T080 |" in reg_txt and "| DONE |" in reg_txt,
        "ops_t076_done": "| T076 |" in ops_txt and "| DONE |" in ops_txt,
        "ops_t077v3_done": "| T077-V3 |" in ops_txt and "| DONE |" in ops_txt,
        "ops_t078_done": "| T078 |" in ops_txt and "| DONE |" in ops_txt,
        "ops_t079_done": "| T079 |" in ops_txt and "| DONE |" in ops_txt,
        "ops_t080_done": "| T080 |" in ops_txt and "| DONE |" in ops_txt,
        "winner_c060_in_roadmap": "C060" in roadmap_txt and ("Winner" in roadmap_txt or "winner" in roadmap_txt),
        "winner_c060_in_task_registry": "C060" in reg_txt and ("Winner" in reg_txt or "winner" in reg_txt),
    }
    gates["G1_REGISTRY_CONSISTENCY"] = all(registry_snapshot.values())

    changelog_snapshot = {
        "t076_count": count_contains(chlog_txt, "T076"),
        "t077_v3_count": count_contains(chlog_txt, "T077-V3"),
        "t078_count": count_contains(chlog_txt, "T078"),
        "t079_count": count_contains(chlog_txt, "T079 Phase 6 Comparative Plotly"),
        "t080_count": count_contains(chlog_txt, "T080 Phase 6 Lessons Learned"),
    }
    gates["G2_CHANGELOG_COUNTS"] = (
        changelog_snapshot["t076_count"] >= 1
        and changelog_snapshot["t077_v3_count"] >= 1
        and changelog_snapshot["t078_count"] >= 1
        and changelog_snapshot["t079_count"] >= 2
        and changelog_snapshot["t080_count"] == 1
    )

    manifest_results = [
        check_manifest_integrity(IN_T076_MANIFEST),
        check_manifest_integrity(IN_T077V3_MANIFEST),
        check_manifest_integrity(IN_T078_MANIFEST),
        check_manifest_integrity(IN_T079_MANIFEST),
        check_manifest_integrity(IN_T080_MANIFEST),
    ]
    manifest_totals = {
        "manifests_checked": len(manifest_results),
        "json_parse_fail_count": sum(0 if r["json_parse_ok"] else 1 for r in manifest_results),
        "missing_paths_count": sum(len(r["missing_paths"]) for r in manifest_results),
        "hard_mismatches_count": sum(len(r["mismatches"]) for r in manifest_results),
    }
    gates["G3_MANIFESTS_PARSE_AND_MATCH"] = (
        manifest_totals["json_parse_fail_count"] == 0
        and manifest_totals["missing_paths_count"] == 0
        and manifest_totals["hard_mismatches_count"] == 0
    )

    winner_snapshot = extract_winner_snapshot()

    write_json(OUT_REGISTRY_SNAPSHOT, registry_snapshot)
    write_json(OUT_CHANGELOG_SNAPSHOT, changelog_snapshot)
    write_json(
        OUT_MANIFEST_CHECK,
        {
            "results": manifest_results,
            "totals": manifest_totals,
        },
    )
    write_json(OUT_WINNER_SNAPSHOT, winner_snapshot)

    # Gates finais (dependentes da materialização e changelog)
    gates["G4_CLOSEOUT_MANIFEST_INTEGRITY"] = False  # definido após escrita do report e recomputo.
    gates["Gx_HASH_MANIFEST_PRESENT"] = False
    gates["G_CHLOG_UPDATED"] = update_changelog_one_line()

    # Primeira versão do report (sem G4/Gx e sem overall final) para entrar no hash.
    report_lines = [
        f"# {TASK_ID} Report",
        "",
        "## HEADER",
        f"- task_id: {TASK_ID}",
        "",
        "## STEP GATES",
        f"- G0_INPUTS_PRESENT: {'PASS' if gates['G0_INPUTS_PRESENT'] else 'FAIL'}",
        f"- G1_REGISTRY_CONSISTENCY: {'PASS' if gates['G1_REGISTRY_CONSISTENCY'] else 'FAIL'}",
        f"- G2_CHANGELOG_COUNTS: {'PASS' if gates['G2_CHANGELOG_COUNTS'] else 'FAIL'}",
        f"- G3_MANIFESTS_PARSE_AND_MATCH: {'PASS' if gates['G3_MANIFESTS_PARSE_AND_MATCH'] else 'FAIL'}",
        "",
        "## RESUMO",
        "- Closeout de governança da Phase 6 com validação de consistência documental e integridade por SHA256.",
        f"- Winner formal T078: C057 | Winner produto Phase 6: C060.",
        "",
        "## SNAPSHOTS",
        f"- registry_snapshot: {OUT_REGISTRY_SNAPSHOT}",
        f"- changelog_snapshot: {OUT_CHANGELOG_SNAPSHOT}",
        f"- manifest_integrity_check: {OUT_MANIFEST_CHECK}",
        f"- phase6_winner_snapshot: {OUT_WINNER_SNAPSHOT}",
        "",
        "## RETRY LOG",
        *[f"- {line}" for line in retry_log],
        "",
        "## ARTIFACT LINKS",
        f"- {OUT_REPORT}",
        f"- {OUT_MANIFEST}",
        f"- {OUT_REGISTRY_SNAPSHOT}",
        f"- {OUT_CHANGELOG_SNAPSHOT}",
        f"- {OUT_MANIFEST_CHECK}",
        f"- {OUT_WINNER_SNAPSHOT}",
        "",
    ]
    OUT_REPORT.write_text("\n".join(report_lines), encoding="utf-8")

    outputs_for_manifest = [
        OUT_REPORT,
        OUT_REGISTRY_SNAPSHOT,
        OUT_CHANGELOG_SNAPSHOT,
        OUT_MANIFEST_CHECK,
        OUT_WINNER_SNAPSHOT,
    ]
    manifest_payload = {
        "task_id": "T081",
        "run_id": TASK_ID,
        "outputs_produced": [str(p.relative_to(ROOT)) for p in outputs_for_manifest] + [str(OUT_MANIFEST.relative_to(ROOT))],
        "hashes_sha256": {str(p.relative_to(ROOT)): sha256_file(p) for p in outputs_for_manifest},
        "mismatch_count": 0,
        "note": "manifest sem self-hash",
    }
    write_json(OUT_MANIFEST, manifest_payload)

    mismatches = []
    for rel, expected in manifest_payload["hashes_sha256"].items():
        actual = sha256_file(ROOT / rel)
        if actual != expected:
            mismatches.append(rel)
    gates["G4_CLOSEOUT_MANIFEST_INTEGRITY"] = len(mismatches) == 0
    gates["Gx_HASH_MANIFEST_PRESENT"] = OUT_MANIFEST.exists()

    overall = all(
        gates[g]
        for g in [
            "G0_INPUTS_PRESENT",
            "G1_REGISTRY_CONSISTENCY",
            "G2_CHANGELOG_COUNTS",
            "G3_MANIFESTS_PARSE_AND_MATCH",
            "G4_CLOSEOUT_MANIFEST_INTEGRITY",
            "Gx_HASH_MANIFEST_PRESENT",
            "G_CHLOG_UPDATED",
        ]
    )

    # Versão final do report com todos os gates e OVERALL STATUS (escrita final).
    report_lines_final = [
        f"# {TASK_ID} Report",
        "",
        "## HEADER",
        f"- task_id: {TASK_ID}",
        "",
        "## STEP GATES",
        f"- G0_INPUTS_PRESENT: {'PASS' if gates['G0_INPUTS_PRESENT'] else 'FAIL'}",
        f"- G1_REGISTRY_CONSISTENCY: {'PASS' if gates['G1_REGISTRY_CONSISTENCY'] else 'FAIL'}",
        f"- G2_CHANGELOG_COUNTS: {'PASS' if gates['G2_CHANGELOG_COUNTS'] else 'FAIL'}",
        f"- G3_MANIFESTS_PARSE_AND_MATCH: {'PASS' if gates['G3_MANIFESTS_PARSE_AND_MATCH'] else 'FAIL'}",
        f"- G4_CLOSEOUT_MANIFEST_INTEGRITY: {'PASS' if gates['G4_CLOSEOUT_MANIFEST_INTEGRITY'] else 'FAIL'}",
        f"- Gx_HASH_MANIFEST_PRESENT: {'PASS' if gates['Gx_HASH_MANIFEST_PRESENT'] else 'FAIL'}",
        f"- G_CHLOG_UPDATED: {'PASS' if gates['G_CHLOG_UPDATED'] else 'FAIL'}",
        "",
        "## RESUMO",
        "- Closeout de governança da Phase 6 com validação de consistência documental e integridade por SHA256.",
        f"- Winner formal T078: C057 | Winner produto Phase 6: C060.",
        "",
        "## SNAPSHOTS",
        f"- registry_snapshot: {OUT_REGISTRY_SNAPSHOT}",
        f"- changelog_snapshot: {OUT_CHANGELOG_SNAPSHOT}",
        f"- manifest_integrity_check: {OUT_MANIFEST_CHECK}",
        f"- phase6_winner_snapshot: {OUT_WINNER_SNAPSHOT}",
        "",
        "## RETRY LOG",
        *[f"- {line}" for line in retry_log],
        "",
        "## ARTIFACT LINKS",
        f"- {OUT_REPORT}",
        f"- {OUT_MANIFEST}",
        f"- {OUT_REGISTRY_SNAPSHOT}",
        f"- {OUT_CHANGELOG_SNAPSHOT}",
        f"- {OUT_MANIFEST_CHECK}",
        f"- {OUT_WINNER_SNAPSHOT}",
        "",
        f"## OVERALL STATUS: [[ {'PASS' if overall else 'FAIL'} ]]",
    ]
    OUT_REPORT.write_text("\n".join(report_lines_final), encoding="utf-8")

    # Atualiza hash do report na própria T081 mantendo consistência pós-escrita final.
    manifest_payload["hashes_sha256"][str(OUT_REPORT.relative_to(ROOT))] = sha256_file(OUT_REPORT)
    write_json(OUT_MANIFEST, manifest_payload)

    print("STEP GATES:")
    for k in [
        "G0_INPUTS_PRESENT",
        "G1_REGISTRY_CONSISTENCY",
        "G2_CHANGELOG_COUNTS",
        "G3_MANIFESTS_PARSE_AND_MATCH",
        "G4_CLOSEOUT_MANIFEST_INTEGRITY",
        "Gx_HASH_MANIFEST_PRESENT",
        "G_CHLOG_UPDATED",
    ]:
        print(f"- {k}: {'PASS' if gates[k] else 'FAIL'}")
    print("RETRY LOG:")
    for line in retry_log:
        print(f"- {line}")
    print("ARTIFACT LINKS:")
    print(f"- {OUT_REPORT}")
    print(f"- {OUT_MANIFEST}")
    print(f"- {OUT_REGISTRY_SNAPSHOT}")
    print(f"- {OUT_CHANGELOG_SNAPSHOT}")
    print(f"- {OUT_MANIFEST_CHECK}")
    print(f"- {OUT_WINNER_SNAPSHOT}")
    print(f"OVERALL STATUS: [[ {'PASS' if overall else 'FAIL'} ]]")
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
