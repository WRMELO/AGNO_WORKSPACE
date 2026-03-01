#!/usr/bin/env python3
"""T066 - Governance closeout do STATE 3 Phase 3."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


TASK_ID = "T066-PHASE3-GOVERNANCE-CLOSEOUT-V2"
ROOT = Path("/home/wilson/AGNO_WORKSPACE")

IN_ROADMAP = ROOT / "00_Strategy/ROADMAP.md"
IN_TASK_REGISTRY = ROOT / "00_Strategy/TASK_REGISTRY.md"
IN_OPS_LOG = ROOT / "00_Strategy/OPS_LOG.md"
IN_CHANGELOG = ROOT / "00_Strategy/changelog.md"
IN_T063_MANIFEST = ROOT / "outputs/governanca/T063-MARKET-SLOPE-REENTRY-ABLATION-V2_manifest.json"
IN_T063_REPORT = ROOT / "outputs/governanca/T063-MARKET-SLOPE-REENTRY-ABLATION-V2_report.md"
IN_T064_MANIFEST = ROOT / "outputs/governanca/T064-PHASE3D-PLOTLY-COMPARATIVE-V1_manifest.json"
IN_T064_REPORT = ROOT / "outputs/governanca/T064-PHASE3D-PLOTLY-COMPARATIVE-V1_report.md"
IN_T065_MANIFEST = ROOT / "outputs/governanca/T065-PHASE3-LESSONS-CONSOLIDATION-V1_manifest.json"
IN_T065_REPORT = ROOT / "outputs/governanca/T065-PHASE3-LESSONS-CONSOLIDATION-V1_report.md"

OUTPUT_REPORT = ROOT / "outputs/governanca/T066-PHASE3-GOVERNANCE-CLOSEOUT-V1_report.md"
OUT_EVIDENCE_DIR = ROOT / "outputs/governanca/T066-PHASE3-GOVERNANCE-CLOSEOUT-V1_evidence"
OUT_REGISTRY_SNAPSHOT = OUT_EVIDENCE_DIR / "registry_snapshot.json"
OUT_CHANGELOG_SNAPSHOT = OUT_EVIDENCE_DIR / "changelog_snapshot.json"
OUT_MANIFEST_CHECK = OUT_EVIDENCE_DIR / "manifest_integrity_check.json"
OUTPUT_MANIFEST = ROOT / "outputs/governanca/T066-PHASE3-GOVERNANCE-CLOSEOUT-V1_manifest.json"
SCRIPT_PATH = ROOT / "scripts/t066_phase3_governance_closeout.py"

CHANGELOG_PATH = ROOT / "00_Strategy/changelog.md"
TRACEABILITY_LINE = (
    "- 2026-03-01T11:05:00Z | GOVERNANCE: T066-PHASE3-GOVERNANCE-CLOSEOUT-V2 EXEC. "
    "Artefatos: outputs/governanca/T066-PHASE3-GOVERNANCE-CLOSEOUT-V1_report.md; "
    "outputs/governanca/T066-PHASE3-GOVERNANCE-CLOSEOUT-V1_manifest.json"
)

ALLOWED_GOVERNANCE_DRIFT_PATHS = {
    str(ROOT / "00_Strategy/ROADMAP.md"),
    str(ROOT / "00_Strategy/TASK_REGISTRY.md"),
    str(ROOT / "00_Strategy/OPS_LOG.md"),
    str(ROOT / "00_Strategy/changelog.md"),
}


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
    return obj


def write_json_strict(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe(payload), indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def parse_json_strict(path: Path) -> Any:
    txt = path.read_text(encoding="utf-8")
    return json.loads(txt, parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))


def count_contains(text: str, token: str) -> int:
    return sum(1 for line in text.splitlines() if token in line)


def check_manifest(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "manifest_path": str(path),
        "exists": path.exists(),
        "json_parse_ok": False,
        "self_hash_present": None,
        "entries_total": 0,
        "missing_paths": [],
        "hard_mismatches": [],
        "allowed_governance_drift": [],
    }
    if not path.exists():
        return result

    obj = parse_json_strict(path)
    result["json_parse_ok"] = True
    hashes = obj.get("hashes_sha256", {})
    result["entries_total"] = len(hashes)
    result["self_hash_present"] = str(path) in hashes

    for fp, expected in hashes.items():
        f = Path(fp)
        if not f.exists():
            result["missing_paths"].append(fp)
            continue
        actual = sha256_file(f)
        if actual != expected:
            entry = {"path": fp, "expected": expected, "actual": actual}
            if str(f) in ALLOWED_GOVERNANCE_DRIFT_PATHS:
                result["allowed_governance_drift"].append(entry)
            else:
                result["hard_mismatches"].append(entry)
    return result


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
        IN_CHANGELOG,
        IN_T063_MANIFEST,
        IN_T063_REPORT,
        IN_T064_MANIFEST,
        IN_T064_REPORT,
        IN_T065_MANIFEST,
        IN_T065_REPORT,
    ]
    missing = [str(p) for p in required_inputs if not p.exists()]
    if missing:
        print("STEP GATES:")
        print(f"- G0_INPUTS_PRESENT: FAIL (missing: {', '.join(missing)})")
        print("OVERALL STATUS: [[ FAIL ]]")
        return 1

    OUT_EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)

    roadmap_txt = IN_ROADMAP.read_text(encoding="utf-8")
    reg_txt = IN_TASK_REGISTRY.read_text(encoding="utf-8")
    ops_txt = IN_OPS_LOG.read_text(encoding="utf-8")
    chlog_txt = IN_CHANGELOG.read_text(encoding="utf-8")

    registry_checks = {
        "roadmap_t064_done": "| T064 |" in roadmap_txt and "| DONE |" in roadmap_txt,
        "roadmap_t065_done": "| T065 |" in roadmap_txt and "| DONE |" in roadmap_txt,
        "roadmap_t066_pending": "| T066 |" in roadmap_txt and "| PENDING |" in roadmap_txt,
        "task_registry_stable_has_t063": "| T063 |" in reg_txt and "STABLE MILESTONES INDEX" in reg_txt,
        "task_registry_stable_has_t064": "| T064 |" in reg_txt and "STABLE MILESTONES INDEX" in reg_txt,
        "task_registry_stable_has_t065": "| T065 |" in reg_txt and "STABLE MILESTONES INDEX" in reg_txt,
        "ops_has_t063_v2": "| T063-V2 |" in ops_txt,
        "ops_has_t064": "| T064 |" in ops_txt,
        "ops_has_t065": "| T065 |" in ops_txt,
    }

    changelog_snapshot = {
        "t063_v2_count": count_contains(chlog_txt, "T063-MARKET-SLOPE-REENTRY-ABLATION-V2"),
        "t064_count": count_contains(chlog_txt, "T064-PHASE3D-PLOTLY-COMPARATIVE-V1"),
        "t065_count": count_contains(chlog_txt, "T065-PHASE3-LESSONS-CONSOLIDATION-V1"),
    }

    manifests = [IN_T063_MANIFEST, IN_T064_MANIFEST, IN_T065_MANIFEST]
    manifest_results = [check_manifest(p) for p in manifests]
    manifest_integrity = {
        "results": manifest_results,
        "totals": {
            "manifests_checked": len(manifest_results),
            "json_parse_fail_count": sum(0 if r["json_parse_ok"] else 1 for r in manifest_results),
            "self_hash_count": sum(1 if r.get("self_hash_present") else 0 for r in manifest_results),
            "missing_paths_count": sum(len(r["missing_paths"]) for r in manifest_results),
            "hard_mismatches_count": sum(len(r["hard_mismatches"]) for r in manifest_results),
            "allowed_governance_drift_count": sum(len(r["allowed_governance_drift"]) for r in manifest_results),
        },
    }

    write_json_strict(OUT_REGISTRY_SNAPSHOT, registry_checks)
    write_json_strict(OUT_CHANGELOG_SNAPSHOT, changelog_snapshot)
    write_json_strict(OUT_MANIFEST_CHECK, manifest_integrity)

    report_lines = [
        f"# {TASK_ID} Report",
        "",
        "## 1) Resumo executivo",
        "- Closeout de governanca da STATE 3 Phase 3 baseado em consistencia de registros e integridade de manifests.",
        "- Escopo: validacao de T063-V2, T064 e T065 em ROADMAP/TASK_REGISTRY/OPS_LOG/changelog.",
        "",
        "## 2) Checklist documental",
        f"- roadmap_t064_done: {registry_checks['roadmap_t064_done']}",
        f"- roadmap_t065_done: {registry_checks['roadmap_t065_done']}",
        f"- roadmap_t066_pending: {registry_checks['roadmap_t066_pending']}",
        f"- task_registry_stable_has_t063: {registry_checks['task_registry_stable_has_t063']}",
        f"- task_registry_stable_has_t064: {registry_checks['task_registry_stable_has_t064']}",
        f"- task_registry_stable_has_t065: {registry_checks['task_registry_stable_has_t065']}",
        f"- ops_has_t063_v2: {registry_checks['ops_has_t063_v2']}",
        f"- ops_has_t064: {registry_checks['ops_has_t064']}",
        f"- ops_has_t065: {registry_checks['ops_has_t065']}",
        "",
        "## 3) Changelog snapshot",
        f"- t063_v2_count: {changelog_snapshot['t063_v2_count']}",
        f"- t064_count: {changelog_snapshot['t064_count']}",
        f"- t065_count: {changelog_snapshot['t065_count']}",
        "",
        "## 4) Manifest integrity summary",
        f"- manifests_checked: {manifest_integrity['totals']['manifests_checked']}",
        f"- json_parse_fail_count: {manifest_integrity['totals']['json_parse_fail_count']}",
        f"- self_hash_count: {manifest_integrity['totals']['self_hash_count']}",
        f"- missing_paths_count: {manifest_integrity['totals']['missing_paths_count']}",
        f"- hard_mismatches_count: {manifest_integrity['totals']['hard_mismatches_count']}",
        f"- allowed_governance_drift_count: {manifest_integrity['totals']['allowed_governance_drift_count']}",
        "- Observacao: drift em `ROADMAP.md`, `TASK_REGISTRY.md`, `OPS_LOG.md` e `changelog.md` e esperado por serem ledgers mutaveis.",
        "",
        "## 5) Artifacts",
        f"- `{OUTPUT_REPORT}`",
        f"- `{OUT_REGISTRY_SNAPSHOT}`",
        f"- `{OUT_CHANGELOG_SNAPSHOT}`",
        f"- `{OUT_MANIFEST_CHECK}`",
        f"- `{OUTPUT_MANIFEST}`",
    ]
    OUTPUT_REPORT.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    outputs_for_hash = [
        OUTPUT_REPORT,
        OUT_REGISTRY_SNAPSHOT,
        OUT_CHANGELOG_SNAPSHOT,
        OUT_MANIFEST_CHECK,
        SCRIPT_PATH,
    ]
    manifest_payload = {
        "task_id": TASK_ID,
        "inputs_consumed": [str(p) for p in required_inputs],
        "outputs_produced": [
            str(OUTPUT_REPORT),
            str(OUT_REGISTRY_SNAPSHOT),
            str(OUT_CHANGELOG_SNAPSHOT),
            str(OUT_MANIFEST_CHECK),
            str(OUTPUT_MANIFEST),
        ],
        "hashes_sha256": {str(p): sha256_file(p) for p in (required_inputs + outputs_for_hash)},
    }
    write_json_strict(OUTPUT_MANIFEST, manifest_payload)

    g0 = all(p.exists() for p in required_inputs)
    g1 = all(registry_checks.values())
    g2 = changelog_snapshot["t063_v2_count"] >= 1 and changelog_snapshot["t064_count"] >= 1 and changelog_snapshot["t065_count"] >= 1
    g3 = manifest_integrity["totals"]["json_parse_fail_count"] == 0
    g4 = manifest_integrity["totals"]["self_hash_count"] == 0
    g5 = manifest_integrity["totals"]["missing_paths_count"] == 0
    g6 = manifest_integrity["totals"]["hard_mismatches_count"] == 0
    gch = update_changelog_one_line()
    gx = OUTPUT_MANIFEST.exists()

    print("STEP GATES:")
    print(f"- G0_INPUTS_PRESENT: {'PASS' if g0 else 'FAIL'}")
    print(f"- G1_REGISTRY_CONSISTENCY: {'PASS' if g1 else 'FAIL'}")
    print(f"- G2_CHANGELOG_CONSISTENCY: {'PASS' if g2 else 'FAIL'}")
    print(f"- G3_MANIFEST_JSON_PARSE: {'PASS' if g3 else 'FAIL'}")
    print(f"- G4_MANIFEST_NO_SELF_HASH: {'PASS' if g4 else 'FAIL'}")
    print(f"- G5_MANIFEST_PATHS_EXIST: {'PASS' if g5 else 'FAIL'}")
    print(f"- G6_MANIFEST_HASH_MATCH: {'PASS' if g6 else 'FAIL'} (hard_mismatches={manifest_integrity['totals']['hard_mismatches_count']}, allowed_governance_drift={manifest_integrity['totals']['allowed_governance_drift_count']})")
    print(f"- G_CHLOG_UPDATED: {'PASS' if gch else 'FAIL'}")
    print(f"- Gx_HASH_MANIFEST_PRESENT: {'PASS' if gx else 'FAIL'}")
    print("ARTIFACT LINKS:")
    print(f"- {SCRIPT_PATH}")
    print(f"- {OUTPUT_REPORT}")
    print(f"- {OUT_REGISTRY_SNAPSHOT}")
    print(f"- {OUT_CHANGELOG_SNAPSHOT}")
    print(f"- {OUT_MANIFEST_CHECK}")
    print(f"- {OUTPUT_MANIFEST}")
    print(f"- {CHANGELOG_PATH}")

    overall = g0 and g1 and g2 and g3 and g4 and g5 and g6 and gch and gx
    print(f"OVERALL STATUS: [[ {'PASS' if overall else 'FAIL'} ]]")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())

