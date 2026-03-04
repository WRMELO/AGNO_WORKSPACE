#!/home/wilson/AGNO_WORKSPACE/.venv/bin/python
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

if not ("agno_env" in sys.prefix or ".venv" in sys.prefix):
    raise RuntimeError("FATAL: Not in agno_env/.venv")

TASK_ID = "T111"
RUN_ID = "T111-PHASE8-GOVERNANCE-CLOSEOUT-V1"
ROOT = Path("/home/wilson/AGNO_WORKSPACE")
CHANGELOG_PATH = ROOT / "00_Strategy/changelog.md"
TRACEABILITY_LINE = (
    "- 2026-03-04T14:00:00Z | GOVERNANCE: T111 Phase 8 Governance Closeout. "
    "STATE 3 Phase 8 formalmente encerrada. "
    "Artefatos: scripts/t111_phase8_governance_closeout.py; "
    "outputs/governanca/T111-PHASE8-GOVERNANCE-CLOSEOUT-V1_manifest.json"
)

OUT_REPORT = ROOT / "outputs/governanca/T111-PHASE8-GOVERNANCE-CLOSEOUT-V1_report.md"
OUT_MANIFEST = ROOT / "outputs/governanca/T111-PHASE8-GOVERNANCE-CLOSEOUT-V1_manifest.json"
OUT_EVID_DIR = ROOT / "outputs/governanca/T111-PHASE8-GOVERNANCE-CLOSEOUT-V1_evidence"
OUT_REG_SNAP = OUT_EVID_DIR / "registry_snapshot.json"
OUT_CHLOG_SNAP = OUT_EVID_DIR / "changelog_snapshot.json"
OUT_MANIFEST_CHECK = OUT_EVID_DIR / "manifest_integrity_check.json"
OUT_PHASE8_WINNER = OUT_EVID_DIR / "phase8_winner_snapshot.json"
OUT_SCRIPT = ROOT / "scripts/t111_phase8_governance_closeout.py"

PHASE8_TASKS = [
    "T101", "T102", "T103", "T104", "T105", "T106", "T107", "T108", "T109", "T110",
]

PHASE8_MANIFESTS = [
    "outputs/governanca/T101-PTAX-BDR-SYNTH-V2_manifest.json",
    "outputs/governanca/T102-SSOT-BR-EXPANDED-V1_manifest.json",
    "outputs/governanca/T103-FEATURES-EXPANDED-V1_manifest.json",
    "outputs/governanca/T104-EDA-FEATURE-ENGINEERING-EXPANDED-V1_manifest.json",
    "outputs/governanca/T105-V1-XGBOOST-RETRAIN-EXPANDED-V1_manifest.json",
    "outputs/governanca/T106-ML-TRIGGER-TUNING-EXPANDED-V1_manifest.json",
    "outputs/governanca/T107-BACKTEST-INTEGRATED-EXPANDED-V1_manifest.json",
    "outputs/governanca/T108-ABLATION-NPOS-CADENCE-EXPANDED-V1_manifest.json",
    "outputs/governanca/T109-PHASE8-PLOTLY-COMPARATIVE-V1_manifest.json",
    "outputs/governanca/T110-PHASE8-LESSONS-LEARNED-V1_manifest.json",
]

ALLOWED_GOVERNANCE_DRIFT_PATHS = {
    "00_Strategy/ROADMAP.md",
    "00_Strategy/TASK_REGISTRY.md",
    "00_Strategy/OPS_LOG.md",
    "00_Strategy/changelog.md",
}


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


def main() -> int:
    gates: list[dict] = []
    retry_log: list[str] = []

    try:
        for p in [OUT_REPORT, OUT_MANIFEST, OUT_REG_SNAP, OUT_CHLOG_SNAP, OUT_MANIFEST_CHECK, OUT_PHASE8_WINNER]:
            p.parent.mkdir(parents=True, exist_ok=True)

        gates.append({"name": "G_ENV_VENV", "pass": True, "detail": f"python={sys.executable}"})

        # G1: Registry consistency — all Phase 8 tasks DONE in ROADMAP + TASK_REGISTRY
        roadmap = (ROOT / "00_Strategy/ROADMAP.md").read_text("utf-8")
        registry = (ROOT / "00_Strategy/TASK_REGISTRY.md").read_text("utf-8")
        opslog = (ROOT / "00_Strategy/OPS_LOG.md").read_text("utf-8")

        reg_checks = {}
        for tid in PHASE8_TASKS:
            in_roadmap = f"| {tid} |" in roadmap and "DONE" in roadmap[roadmap.find(f"| {tid} |"):roadmap.find(f"| {tid} |") + 300]
            in_registry = f"| {tid} |" in registry and "DONE" in registry[registry.find(f"| {tid} |"):registry.find(f"| {tid} |") + 300]
            reg_checks[tid] = {"roadmap_done": in_roadmap, "registry_done": in_registry}

        all_reg_ok = all(v["roadmap_done"] and v["registry_done"] for v in reg_checks.values())
        gates.append({"name": "G1_REGISTRY_CONSISTENCY", "pass": all_reg_ok,
                       "detail": f"{sum(1 for v in reg_checks.values() if v['roadmap_done'] and v['registry_done'])}/{len(PHASE8_TASKS)} tasks DONE in both"})

        write_json(OUT_REG_SNAP, reg_checks)

        # G2: Changelog counts
        changelog = (ROOT / "00_Strategy/changelog.md").read_text("utf-8")
        chlog_counts = {}
        for tid in PHASE8_TASKS:
            count = sum(1 for line in changelog.splitlines() if tid in line)
            chlog_counts[tid] = count

        all_chlog_ok = all(v >= 1 for v in chlog_counts.values())
        gates.append({"name": "G2_CHANGELOG_COUNTS", "pass": all_chlog_ok,
                       "detail": f"{sum(1 for v in chlog_counts.values() if v >= 1)}/{len(PHASE8_TASKS)} tasks with >=1 changelog entry"})

        write_json(OUT_CHLOG_SNAP, chlog_counts)

        # G3: Manifest integrity
        manifest_results = []
        total_entries = 0
        hard_mismatches = 0
        allowed_drift = 0
        missing_paths = 0
        parse_fail = 0

        for mpath_rel in PHASE8_MANIFESTS:
            mpath = ROOT / mpath_rel
            if not mpath.exists():
                manifest_results.append({"manifest": mpath_rel, "status": "MISSING"})
                parse_fail += 1
                continue

            try:
                man = json.loads(mpath.read_text("utf-8"))
            except json.JSONDecodeError:
                manifest_results.append({"manifest": mpath_rel, "status": "PARSE_FAIL"})
                parse_fail += 1
                continue

            hashes = man.get("hashes_sha256", {})
            entries = len(hashes)
            total_entries += entries
            result = {"manifest": mpath_rel, "entries": entries, "hard_mismatches": 0, "allowed_drift": 0, "missing": 0}

            for rel, expected in hashes.items():
                fpath = ROOT / rel
                if not fpath.exists():
                    result["missing"] += 1
                    missing_paths += 1
                    continue
                got = sha256_file(fpath)
                if got != expected:
                    if rel in ALLOWED_GOVERNANCE_DRIFT_PATHS:
                        result["allowed_drift"] += 1
                        allowed_drift += 1
                    else:
                        result["hard_mismatches"] += 1
                        hard_mismatches += 1

            manifest_results.append(result)

        gates.append({"name": "G3_MANIFESTS_INTEGRITY", "pass": hard_mismatches == 0 and parse_fail == 0 and missing_paths == 0,
                       "detail": f"manifests={len(PHASE8_MANIFESTS)}, total_entries={total_entries}, hard_mismatches={hard_mismatches}, allowed_drift={allowed_drift}, missing={missing_paths}, parse_fail={parse_fail}"})

        write_json(OUT_MANIFEST_CHECK, {
            "manifests_checked": len(PHASE8_MANIFESTS),
            "total_entries": total_entries,
            "hard_mismatches": hard_mismatches,
            "allowed_governance_drift": allowed_drift,
            "missing_paths": missing_paths,
            "parse_fail": parse_fail,
            "details": manifest_results,
        })

        # G4: Phase 8 winner snapshot
        winner_config_path = ROOT / "src/data_engine/portfolio/T108_SELECTED_CONFIG_NPOS_CADENCE_EXPANDED.json"
        winner_curve_path = ROOT / "src/data_engine/portfolio/T108_PORTFOLIO_CURVE_DUAL_MODE_EXPANDED_ML_TRIGGER_WINNER.parquet"
        metrics_path = ROOT / "outputs/governanca/T109-PHASE8-PLOTLY-COMPARATIVE-V1_evidence/metrics_snapshot.json"

        winner_ok = winner_config_path.exists() and winner_curve_path.exists() and metrics_path.exists()

        winner_snap = {"winner_config_exists": winner_config_path.exists(),
                       "winner_curve_exists": winner_curve_path.exists(),
                       "metrics_snapshot_exists": metrics_path.exists()}

        if winner_ok:
            config = json.loads(winner_config_path.read_text("utf-8"))
            ms = json.loads(metrics_path.read_text("utf-8"))
            winner_snap["config"] = config
            winner_snap["holdout_metrics"] = ms.get("phase8_winner_ml", {}).get("holdout", {})
            winner_snap["acid_metrics"] = ms.get("phase8_winner_ml", {}).get("acid", {})
            winner_snap["c060_holdout"] = ms.get("c060", {}).get("holdout", {})

        gates.append({"name": "G4_PHASE8_WINNER_SNAPSHOT", "pass": winner_ok,
                       "detail": f"config={winner_config_path.exists()}, curve={winner_curve_path.exists()}, metrics={metrics_path.exists()}"})

        write_json(OUT_PHASE8_WINNER, winner_snap)

        # Changelog
        ch_ok = append_changelog_idempotent(TRACEABILITY_LINE)
        gates.append({"name": "G_CHLOG_UPDATED", "pass": ch_ok, "detail": f"path={CHANGELOG_PATH}"})

        # Report + Manifest
        overall_pre = all(g["pass"] for g in gates)

        def build_report(gs, overall_flag):
            lines = [f"# HEADER: {TASK_ID}", "", "## STEP GATES"]
            for g in gs:
                lines.append(f"- {g['name']}: {'PASS' if g['pass'] else 'FAIL'} | {g['detail']}")
            lines += [
                "", "## RESUMO",
                "- STATE 3 Phase 8 governance closeout.",
                f"- {len(PHASE8_TASKS)} tasks verificadas em ROADMAP/TASK_REGISTRY.",
                f"- {len(PHASE8_MANIFESTS)} manifests auditados: {total_entries} entradas SHA256, {hard_mismatches} hard mismatches, {allowed_drift} allowed drift.",
                f"- Winner Phase 8: C010_N15_CB10 snapshot preservado.",
                "", "## RETRY LOG", "- none",
                "", "## ARTIFACT LINKS",
                f"- {OUT_REPORT.relative_to(ROOT)}",
                f"- {OUT_MANIFEST.relative_to(ROOT)}",
                f"- {OUT_REG_SNAP.relative_to(ROOT)}",
                f"- {OUT_CHLOG_SNAP.relative_to(ROOT)}",
                f"- {OUT_MANIFEST_CHECK.relative_to(ROOT)}",
                f"- {OUT_PHASE8_WINNER.relative_to(ROOT)}",
                "", f"## OVERALL STATUS: [[ {'PASS' if overall_flag else 'FAIL'} ]]", "",
            ]
            return "\n".join(lines)

        OUT_REPORT.write_text(build_report(gates, overall_pre), encoding="utf-8")

        outputs = [OUT_SCRIPT, OUT_REPORT, OUT_REG_SNAP, OUT_CHLOG_SNAP, OUT_MANIFEST_CHECK, OUT_PHASE8_WINNER, CHANGELOG_PATH]
        hashes = {str(p.relative_to(ROOT)): sha256_file(p) for p in outputs}
        manifest = {
            "task_id": TASK_ID,
            "run_id": RUN_ID,
            "manifest_policy": "no_self_hash",
            "inputs_consumed": [str(Path(m)) for m in PHASE8_MANIFESTS],
            "outputs_produced": [str(p.relative_to(ROOT)) for p in [OUT_REPORT, OUT_MANIFEST, OUT_REG_SNAP, OUT_CHLOG_SNAP, OUT_MANIFEST_CHECK, OUT_PHASE8_WINNER]],
            "hashes_sha256": hashes,
        }
        write_json(OUT_MANIFEST, manifest)
        gates.append({"name": "Gx_HASH_MANIFEST_PRESENT", "pass": OUT_MANIFEST.exists(), "detail": f"entries={len(hashes)}"})

        mismatches_self = [r for r, exp in hashes.items() if sha256_file(ROOT / r) != exp]
        gates.append({"name": "G_SHA256_INTEGRITY_SELF_CHECK", "pass": len(mismatches_self) == 0, "detail": f"mismatches={len(mismatches_self)}"})

        overall = all(g["pass"] for g in gates)
        OUT_REPORT.write_text(build_report(gates, overall), encoding="utf-8")
        final_hashes = {str(p.relative_to(ROOT)): sha256_file(p) for p in outputs}
        manifest["hashes_sha256"] = final_hashes
        write_json(OUT_MANIFEST, manifest)

        print(f"HEADER: {TASK_ID}")
        print("STEP GATES:")
        for g in gates:
            print(f"- {g['name']}: {'PASS' if g['pass'] else 'FAIL'} | {g['detail']}")
        print("RETRY LOG:\n- none")
        print("ARTIFACT LINKS:")
        for p in [OUT_REPORT, OUT_MANIFEST, OUT_REG_SNAP, OUT_CHLOG_SNAP, OUT_MANIFEST_CHECK, OUT_PHASE8_WINNER]:
            print(f"- {p}")
        print(f"OVERALL STATUS: [[ {'PASS' if overall else 'FAIL'} ]]")
        return 0 if overall else 2

    except Exception as exc:
        print(f"FATAL: {type(exc).__name__}: {exc}")
        import traceback; traceback.print_exc()
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
