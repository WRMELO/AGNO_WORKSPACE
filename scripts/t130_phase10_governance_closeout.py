#!/home/wilson/AGNO_WORKSPACE/.venv/bin/python
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any


if ".venv" not in sys.executable:
    raise RuntimeError("FATAL: Execute with /home/wilson/AGNO_WORKSPACE/.venv/bin/python")

TASK_ID = "T130"
RUN_ID = "T130-PHASE10-GOVERNANCE-CLOSEOUT-V1"
ROOT = Path("/home/wilson/AGNO_WORKSPACE")

ROADMAP = ROOT / "00_Strategy/ROADMAP.md"
TASK_REGISTRY = ROOT / "00_Strategy/TASK_REGISTRY.md"
OPS_LOG = ROOT / "00_Strategy/OPS_LOG.md"
CHANGELOG = ROOT / "00_Strategy/changelog.md"
DECL_T127 = ROOT / "src/data_engine/portfolio/T127_US_WINNER_DECLARATION.json"
LL_T129 = ROOT / "02_Knowledge_Bank/docs/process/STATE3_PHASE10_LESSONS_LEARNED_T129.md"

TRACEABILITY_LINE = (
    "- 2026-03-04T21:51:46Z | GOVERNANCE: T130 Phase 10 Governance Closeout. "
    "STATE3 Phase 10 formalmente encerrada. Artefatos: scripts/t130_phase10_governance_closeout.py; "
    "outputs/governanca/T130-PHASE10-GOVERNANCE-CLOSEOUT-V1_report.md; "
    "outputs/governanca/T130-PHASE10-GOVERNANCE-CLOSEOUT-V1_manifest.json"
)

OUT_DIR = ROOT / "outputs/governanca"
OUT_REPORT = OUT_DIR / f"{RUN_ID}_report.md"
OUT_MANIFEST = OUT_DIR / f"{RUN_ID}_manifest.json"
OUT_EVID_DIR = OUT_DIR / f"{RUN_ID}_evidence"
OUT_REGISTRY = OUT_EVID_DIR / "registry_snapshot.json"
OUT_CHANGELOG = OUT_EVID_DIR / "changelog_snapshot.json"
OUT_MANIFEST_CHECK = OUT_EVID_DIR / "manifest_integrity_check.json"
OUT_WINNER = OUT_EVID_DIR / "phase10_winner_snapshot.json"
OUT_MANIFEST_SELF_CHECK = OUT_EVID_DIR / "manifest_integrity_self_check.json"
SCRIPT_PATH = ROOT / "scripts/t130_phase10_governance_closeout.py"

PHASE10_TASKS = ["T119", "T120", "T121", "T122", "T123", "T124", "T125", "T126", "T127", "T128", "T129"]
PHASE10_MANIFESTS = [
    ROOT / "outputs/governanca/T119-SSOT-US-CANONICAL-V1_manifest.json",
    ROOT / "outputs/governanca/T120-M3-US-SCORES-V1_manifest.json",
    ROOT / "outputs/governanca/T121-US-ENGINE-BACKTEST-V1_manifest.json",
    ROOT / "outputs/governanca/T122-US-ENGINE-ABLATION-NPOS-CADENCE-V1_manifest.json",
    ROOT / "outputs/governanca/T123-US-FEATURES-V2-V1_manifest.json",
    ROOT / "outputs/governanca/T124-US-XGBOOST-V2-V1_manifest.json",
    ROOT / "outputs/governanca/T125-US-TRIGGER-V2-THR-HYST-V1_manifest.json",
    ROOT / "outputs/governanca/T126-US-ENGINE-V2-TRIGGER-BACKTEST-V1_manifest.json",
    ROOT / "outputs/governanca/T127-US-WINNER-COMPARATIVE-V1_manifest.json",
    ROOT / "outputs/governanca/T128-BR-US-BRL-DASHBOARD-V1_manifest.json",
    ROOT / "outputs/governanca/T128-BR-US-BRL-DASHBOARD-V2_manifest.json",
]

ALLOWED_GOV_DRIFT = {
    ROOT / "00_Strategy/ROADMAP.md",
    ROOT / "00_Strategy/TASK_REGISTRY.md",
    ROOT / "00_Strategy/OPS_LOG.md",
    ROOT / "00_Strategy/changelog.md",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def parse_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"), parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))


def line_with_done(text: str, tid: str) -> bool:
    for line in text.splitlines():
        if f"| {tid} |" in line and "| DONE |" in line:
            return True
    return False


def count_changelog_entries(text: str, tid: str) -> int:
    return sum(1 for line in text.splitlines() if tid in line)


def append_changelog_idempotent(line: str) -> bool:
    before = CHANGELOG.read_text(encoding="utf-8") if CHANGELOG.exists() else ""
    if line in before:
        return True
    body = before if before.endswith("\n") or before == "" else before + "\n"
    body += line + "\n"
    CHANGELOG.write_text(body, encoding="utf-8")
    after = CHANGELOG.read_text(encoding="utf-8")
    return after.count(line) == 1


def check_manifest(path: Path) -> dict[str, Any]:
    result = {
        "manifest_path": str(path.relative_to(ROOT)),
        "exists": path.exists(),
        "json_parse_ok": False,
        "entries_total": 0,
        "hard_mismatches": 0,
        "allowed_governance_drift": 0,
        "missing_paths": 0,
        "details": [],
    }
    if not path.exists():
        return result

    obj = parse_json(path)
    result["json_parse_ok"] = True
    hashes = obj.get("hashes_sha256", {})
    result["entries_total"] = len(hashes)

    for rel_path, expected in hashes.items():
        p = Path(rel_path)
        p = p if p.is_absolute() else ROOT / p
        if not p.exists():
            result["missing_paths"] += 1
            result["details"].append({"path": rel_path, "status": "MISSING"})
            continue
        got = sha256_file(p)
        if got == expected:
            continue
        if p in ALLOWED_GOV_DRIFT:
            result["allowed_governance_drift"] += 1
            result["details"].append({"path": rel_path, "status": "ALLOWED_DRIFT"})
        else:
            result["hard_mismatches"] += 1
            result["details"].append({"path": rel_path, "status": "MISMATCH", "expected": expected, "actual": got})
    return result


def build_report(gates: list[dict[str, Any]], manifest_totals: dict[str, int]) -> str:
    lines = [
        f"# {RUN_ID} Report",
        "",
        "## 1) Resumo executivo",
        "- Closeout de governança da STATE3-P10E (Phase 10) com validação de consistência documental e integridade de manifests.",
        "- Escopo: T119..T129, changelog, manifests de execução da fase e declaração oficial de winner.",
        "",
        "## 2) STEP GATES",
    ]
    for g in gates:
        status = "PASS" if g["pass"] else "FAIL"
        lines.append(f"- {g['name']}: {status} — {g['detail']}")
    lines.extend(
        [
            "",
            "## 3) Integridade de manifests (Phase 10)",
            f"- manifests_checked: {manifest_totals['manifests_checked']}",
            f"- total_entries: {manifest_totals['total_entries']}",
            f"- hard_mismatches: {manifest_totals['hard_mismatches']}",
            f"- allowed_governance_drift: {manifest_totals['allowed_governance_drift']}",
            f"- missing_paths: {manifest_totals['missing_paths']}",
            f"- parse_fail: {manifest_totals['parse_fail']}",
            "",
            "## 4) Artefatos de fechamento",
            f"- {OUT_REGISTRY.relative_to(ROOT)}",
            f"- {OUT_CHANGELOG.relative_to(ROOT)}",
            f"- {OUT_MANIFEST_CHECK.relative_to(ROOT)}",
            f"- {OUT_WINNER.relative_to(ROOT)}",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    gates: list[dict[str, Any]] = []
    retry_log: list[str] = []

    required = [ROADMAP, TASK_REGISTRY, OPS_LOG, CHANGELOG, DECL_T127, LL_T129, *PHASE10_MANIFESTS]
    missing = [str(p.relative_to(ROOT)) for p in required if not p.exists()]
    g0_pass = len(missing) == 0
    gates.append({"name": "G0_INPUTS_PRESENT", "pass": g0_pass, "detail": f"missing={len(missing)}"})
    if not g0_pass:
        print(f"HEADER: {TASK_ID}")
        print("STEP GATES:")
        print(f"- G0_INPUTS_PRESENT: FAIL (missing={missing})")
        print("RETRY LOG:")
        print("- Nenhum retry executado.")
        print("ARTIFACT LINKS:")
        print("- N/A")
        print("OVERALL STATUS: [[ FAIL ]]")
        return 1

    OUT_EVID_DIR.mkdir(parents=True, exist_ok=True)

    roadmap_txt = ROADMAP.read_text(encoding="utf-8")
    registry_txt = TASK_REGISTRY.read_text(encoding="utf-8")
    changelog_txt = CHANGELOG.read_text(encoding="utf-8")

    reg_snap: dict[str, Any] = {}
    for tid in PHASE10_TASKS:
        reg_snap[tid] = {
            "roadmap_done": line_with_done(roadmap_txt, tid),
            "task_registry_done": line_with_done(registry_txt, tid),
        }
    g1_pass = all(v["roadmap_done"] and v["task_registry_done"] for v in reg_snap.values())
    gates.append(
        {
            "name": "G1_REGISTRY_CONSISTENCY",
            "pass": g1_pass,
            "detail": f"{sum(1 for v in reg_snap.values() if v['roadmap_done'] and v['task_registry_done'])}/{len(PHASE10_TASKS)} DONE in ROADMAP+TASK_REGISTRY",
        }
    )
    write_json(OUT_REGISTRY, reg_snap)

    chlog_snap = {tid: count_changelog_entries(changelog_txt, tid) for tid in PHASE10_TASKS}
    g2_pass = all(c >= 1 for c in chlog_snap.values())
    gates.append(
        {
            "name": "G2_CHANGELOG_COUNTS",
            "pass": g2_pass,
            "detail": f"{sum(1 for c in chlog_snap.values() if c >= 1)}/{len(PHASE10_TASKS)} tasks with >=1 changelog line",
        }
    )
    write_json(OUT_CHANGELOG, chlog_snap)

    manifest_checks = []
    totals = {
        "manifests_checked": len(PHASE10_MANIFESTS),
        "total_entries": 0,
        "hard_mismatches": 0,
        "allowed_governance_drift": 0,
        "missing_paths": 0,
        "parse_fail": 0,
    }
    for mp in PHASE10_MANIFESTS:
        ck = check_manifest(mp)
        manifest_checks.append(ck)
        if not ck["exists"] or not ck["json_parse_ok"]:
            totals["parse_fail"] += 1
        totals["total_entries"] += ck["entries_total"]
        totals["hard_mismatches"] += ck["hard_mismatches"]
        totals["allowed_governance_drift"] += ck["allowed_governance_drift"]
        totals["missing_paths"] += ck["missing_paths"]

    g3_pass = totals["hard_mismatches"] == 0 and totals["missing_paths"] == 0 and totals["parse_fail"] == 0
    gates.append(
        {
            "name": "G3_MANIFESTS_INTEGRITY",
            "pass": g3_pass,
            "detail": (
                f"manifests={totals['manifests_checked']}, entries={totals['total_entries']}, "
                f"hard_mismatches={totals['hard_mismatches']}, allowed_drift={totals['allowed_governance_drift']}, "
                f"missing={totals['missing_paths']}, parse_fail={totals['parse_fail']}"
            ),
        }
    )
    write_json(OUT_MANIFEST_CHECK, {"totals": totals, "details": manifest_checks})

    decl = parse_json(DECL_T127)
    winner_snap = {
        "phase": "STATE3-P10E",
        "winner_us": {
            "task_id": decl.get("winner_task_id"),
            "label": decl.get("winner_label"),
            "config": decl.get("winner_config", {}),
        },
        "trigger_rejected": decl.get("trigger_rejected", {}),
        "winner_br_baseline": {
            "task_id": "C060X",
            "curve_path": "src/data_engine/portfolio/CTO_C060_EXPANDED_ABLATION_WINNER_CURVE.parquet",
        },
        "lessons_document": str(LL_T129.relative_to(ROOT)),
    }
    g4_pass = winner_snap["winner_us"]["task_id"] == "T122" and winner_snap["trigger_rejected"].get("task_id") == "T126"
    gates.append(
        {
            "name": "G4_WINNER_DECLARATION_SNAPSHOT",
            "pass": g4_pass,
            "detail": f"winner_us={winner_snap['winner_us']['task_id']}, trigger_rejected={winner_snap['trigger_rejected'].get('task_id')}",
        }
    )
    write_json(OUT_WINNER, winner_snap)

    g_chlog = append_changelog_idempotent(TRACEABILITY_LINE)
    gates.append({"name": "G_CHLOG_UPDATED", "pass": g_chlog, "detail": f"line_present={g_chlog}"})

    OUT_REPORT.write_text(build_report(gates, totals), encoding="utf-8")

    outputs_produced = [
        str(SCRIPT_PATH.relative_to(ROOT)),
        str(OUT_REPORT.relative_to(ROOT)),
        str(OUT_MANIFEST.relative_to(ROOT)),
        str(OUT_REGISTRY.relative_to(ROOT)),
        str(OUT_CHANGELOG.relative_to(ROOT)),
        str(OUT_MANIFEST_CHECK.relative_to(ROOT)),
        str(OUT_WINNER.relative_to(ROOT)),
        str(OUT_MANIFEST_SELF_CHECK.relative_to(ROOT)),
    ]
    inputs_consumed = [
        str(ROADMAP.relative_to(ROOT)),
        str(TASK_REGISTRY.relative_to(ROOT)),
        str(OPS_LOG.relative_to(ROOT)),
        str(CHANGELOG.relative_to(ROOT)),
        str(DECL_T127.relative_to(ROOT)),
        str(LL_T129.relative_to(ROOT)),
        *[str(p.relative_to(ROOT)) for p in PHASE10_MANIFESTS],
    ]

    hashes = {p: sha256_file(ROOT / p) for p in outputs_produced if (ROOT / p).exists()}
    manifest_payload = {
        "task_id": TASK_ID,
        "run_id": RUN_ID,
        "policy": "no_self_hash",
        "inputs_consumed": inputs_consumed,
        "outputs_produced": outputs_produced,
        "hashes_sha256": hashes,
    }
    write_json(OUT_MANIFEST, manifest_payload)

    self_check = {"checked": len(hashes), "mismatches": 0, "details": []}
    for rel, expected in hashes.items():
        got = sha256_file(ROOT / rel)
        if got != expected:
            self_check["mismatches"] += 1
            self_check["details"].append({"path": rel, "expected": expected, "actual": got})
    write_json(OUT_MANIFEST_SELF_CHECK, self_check)
    g_hash_manifest = self_check["mismatches"] == 0 and OUT_MANIFEST.exists()
    gates.append(
        {
            "name": "Gx_HASH_MANIFEST_PRESENT",
            "pass": g_hash_manifest,
            "detail": f"manifest_exists={OUT_MANIFEST.exists()}, checked={self_check['checked']}, mismatches={self_check['mismatches']}",
        }
    )

    overall = all(g["pass"] for g in gates)
    if not retry_log:
        retry_log.append("Nenhum retry necessário.")

    print(f"HEADER: {TASK_ID}")
    print("STEP GATES:")
    for g in gates:
        print(f"- {g['name']}: {'PASS' if g['pass'] else 'FAIL'} ({g['detail']})")
    print("RETRY LOG:")
    for r in retry_log:
        print(f"- {r}")
    print("ARTIFACT LINKS:")
    print(f"- {OUT_REPORT.relative_to(ROOT)}")
    print(f"- {OUT_MANIFEST.relative_to(ROOT)}")
    print(f"- {OUT_REGISTRY.relative_to(ROOT)}")
    print(f"- {OUT_CHANGELOG.relative_to(ROOT)}")
    print(f"- {OUT_MANIFEST_CHECK.relative_to(ROOT)}")
    print(f"- {OUT_WINNER.relative_to(ROOT)}")
    print(f"- {OUT_MANIFEST_SELF_CHECK.relative_to(ROOT)}")
    print(f"OVERALL STATUS: [[ {'PASS' if overall else 'FAIL'} ]]")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
