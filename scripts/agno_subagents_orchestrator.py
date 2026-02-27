from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

FIXED_AGENT_ROUTING = {
    "agno-architect": "Opus 4.6 (extended reasoning)",
    "agno-executor": "GPT-5.3 Codex",
    "agno-auditor": "Opus 4.6 (extended reasoning)",
    "agno-registry-curator": "Sonnet 4.6",
}


@dataclass
class Gate:
    gate_id: str
    status: str
    details: str


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def create_run_dir(repo_root: Path, task_id: str) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = repo_root / "outputs" / "governanca" / "subagents" / task_id / f"run_{ts}"
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def run_cmd(command: str, cwd: Path) -> tuple[int, str, str]:
    proc = subprocess.run(
        ["bash", "-lc", command],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def validate_spec(spec: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for key in ("meta", "context", "instruction", "traceability"):
        if key not in spec:
            missing.append(key)
    if "meta" in spec and "task_id" not in spec["meta"]:
        missing.append("meta.task_id")
    return missing


def validate_fixed_routing(spec: dict[str, Any]) -> tuple[bool, dict[str, str], list[str]]:
    raw = spec.get("agent_routing", {})
    effective = dict(FIXED_AGENT_ROUTING)
    if isinstance(raw, dict):
        for key, value in raw.items():
            effective[key] = str(value)
    mismatches: list[str] = []
    for agent, required_model in FIXED_AGENT_ROUTING.items():
        got = effective.get(agent)
        if got != required_model:
            mismatches.append(f"{agent}: expected='{required_model}' got='{got}'")
    return len(mismatches) == 0, effective, mismatches


def run_executor(spec: dict[str, Any], repo_root: Path, retry_limit: int) -> tuple[list[dict[str, Any]], bool]:
    commands = spec.get("executor", {}).get("commands", [])
    steps: list[dict[str, Any]] = []
    if not commands:
        return steps, True

    all_ok = True
    for index, command in enumerate(commands, start=1):
        ok = False
        attempts: list[dict[str, Any]] = []
        for attempt in range(1, retry_limit + 1):
            code, out, err = run_cmd(command, repo_root)
            attempts.append(
                {
                    "attempt": attempt,
                    "exit_code": code,
                    "stdout_tail": out[-2000:],
                    "stderr_tail": err[-2000:],
                }
            )
            if code == 0:
                ok = True
                break
        steps.append(
            {
                "step_number": index,
                "command": command,
                "status": "PASS" if ok else "FAIL",
                "attempts": attempts,
            }
        )
        if not ok:
            all_ok = False
    return steps, all_ok


def run_auditor(spec: dict[str, Any], repo_root: Path) -> tuple[list[dict[str, Any]], bool]:
    checks = spec.get("audit", {}).get("checks", [])
    if not checks:
        return [], True

    results: list[dict[str, Any]] = []
    all_ok = True
    for idx, check_cmd in enumerate(checks, start=1):
        code, out, err = run_cmd(check_cmd, repo_root)
        ok = code == 0
        results.append(
            {
                "check_number": idx,
                "command": check_cmd,
                "status": "PASS" if ok else "FAIL",
                "exit_code": code,
                "stdout_tail": out[-2000:],
                "stderr_tail": err[-2000:],
            }
        )
        if not ok:
            all_ok = False
    return results, all_ok


def build_terminal_log(task_id: str, gates: list[Gate], exec_steps: list[dict[str, Any]], audit_steps: list[dict[str, Any]], overall: bool) -> str:
    lines: list[str] = []
    lines.append(f"HEADER: {task_id}")
    lines.append("")
    lines.append("STEP GATES:")
    for g in gates:
        lines.append(f"- {g.gate_id}: {g.status} | {g.details}")
    lines.append("")
    lines.append("RETRY LOG:")
    if not exec_steps:
        lines.append("- no executor commands")
    for step in exec_steps:
        lines.append(f"- step {step['step_number']} ({step['status']}): {step['command']}")
        for a in step["attempts"]:
            lines.append(f"  - attempt {a['attempt']}: exit_code={a['exit_code']}")
    lines.append("")
    lines.append("ARTIFACT LINKS:")
    lines.append("- architect_packet.json")
    lines.append("- executor_report.json")
    lines.append("- auditor_report.json")
    lines.append("- run_summary.json")
    lines.append("")
    lines.append(f"OVERALL STATUS: [[ {'PASS' if overall else 'FAIL'} ]]")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Orquestrador local de subagentes AGNO.")
    parser.add_argument("--task-spec", required=True, help="JSON da task no formato CTO/AGNO.")
    parser.add_argument("--retry-limit", type=int, default=3, help="Numero maximo de tentativas por comando.")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    task_spec_path = Path(args.task_spec)
    if not task_spec_path.is_absolute():
        task_spec_path = repo_root / task_spec_path
    if not task_spec_path.exists():
        raise FileNotFoundError(f"task spec nao encontrado: {task_spec_path}")

    spec = read_json(task_spec_path)
    missing = validate_spec(spec)
    task_id = spec.get("meta", {}).get("task_id", "TASK_UNKNOWN")
    run_dir = create_run_dir(repo_root, task_id)

    gates: list[Gate] = []
    g1_ok = len(missing) == 0
    gates.append(Gate("G1_SPEC_SCHEMA_MIN", "PASS" if g1_ok else "FAIL", f"missing={missing}"))

    routing_ok, effective_routing, routing_mismatches = validate_fixed_routing(spec)
    gates.append(
        Gate(
            "G2_FIXED_MODEL_ROUTING",
            "PASS" if routing_ok else "FAIL",
            "routing_fixed" if routing_ok else "; ".join(routing_mismatches),
        )
    )

    arch_packet = {
        "task_id": task_id,
        "generated_at_utc": now_utc(),
        "priority": spec.get("meta", {}).get("priority", "Medium"),
        "agent_routing": effective_routing,
        "target_files": spec.get("context", {}).get("target_files", []),
        "step_by_step": spec.get("instruction", {}).get("step_by_step", []),
        "acceptance_criteria": spec.get("instruction", {}).get("acceptance_criteria", []),
    }
    write_json(run_dir / "architect_packet.json", arch_packet)
    gates.append(Gate("G3_ARCHITECT_PACKET", "PASS", "architect_packet.json gerado"))

    exec_steps, exec_ok = run_executor(spec, repo_root, retry_limit=max(1, args.retry_limit))
    write_json(run_dir / "executor_report.json", {"generated_at_utc": now_utc(), "steps": exec_steps, "status": "PASS" if exec_ok else "FAIL"})
    gates.append(Gate("G4_EXECUTOR", "PASS" if exec_ok else "FAIL", f"steps={len(exec_steps)}"))

    audit_steps, audit_ok = run_auditor(spec, repo_root)
    write_json(run_dir / "auditor_report.json", {"generated_at_utc": now_utc(), "checks": audit_steps, "status": "PASS" if audit_ok else "FAIL"})
    gates.append(Gate("G5_AUDITOR", "PASS" if audit_ok else "FAIL", f"checks={len(audit_steps)}"))

    overall = all(g.status == "PASS" for g in gates)
    summary = {
        "task_id": task_id,
        "task_spec": str(task_spec_path.relative_to(repo_root)),
        "run_dir": str(run_dir.relative_to(repo_root)),
        "gates": [g.__dict__ for g in gates],
        "overall_status": "PASS" if overall else "FAIL",
        "timestamp_utc": now_utc(),
    }
    write_json(run_dir / "run_summary.json", summary)
    (run_dir / "terminal_output.log").write_text(
        build_terminal_log(task_id, gates, exec_steps, audit_steps, overall),
        encoding="utf-8",
    )

    print(f"Run dir: {run_dir}")
    print(f"OVERALL STATUS: [[ {'PASS' if overall else 'FAIL'} ]]")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
