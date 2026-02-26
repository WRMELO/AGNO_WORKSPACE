# Bootstrap Report - CEP_BUNDLE_CORE

- task_id: `TASK_CEP_BUNDLE_CORE_F0_001_BOOTSTRAP_REPO_AND_VENV_GATES_V1`
- timestamp_utc: `2026-02-15T14:03:17.613788+00:00`
- overall: `PASS`
- sys.executable: `/home/wilson/PortfolioZero/.venv/bin/python`
- python_version: `3.12.12`

## Gates
- `S1_GATE_ALLOWLIST`: PASS - repo_root=[LEGACY_ROOT]
- `S2_CHECK_COMPILE_OR_IMPORTS`: PASS - py_compile ok
- `S3_GATE_VENV_OFFICIAL_PYTHON`: PASS - sys.executable=/home/wilson/PortfolioZero/.venv/bin/python
- `S4_RUN_SMOKE`: PASS - smoke ok
- `S5_VERIFY_OUTPUTS_EXIST_AND_NONEMPTY`: PASS - checked=2 arquivos
- `S6_WRITE_MANIFEST_HASHES`: PASS - hashes_registrados=3

## Smoke Summary
- returncode: `0`
- evidence_dir: `outputs/governanca/bootstrap_repo/20260215/evidence`

## Repository Tree
```text
CEP_BUNDLE_CORE/
- configs/
- docs/
  - CONSTITUICAO.md
  - emendas/
    - .gitkeep
- outputs/
  - governanca/
    - bootstrap_repo/
      - 20260215/
        - evidence/
          - smoke_evidence.txt
        - manifest.json
        - report.md
- planning/
- pyproject.toml
- requirements.lock.txt
- scripts/
  - run_task.py
  - smoke.py
- src/
  - adapters/
  - core/
- tests/
```

## Outputs e Hashes
- `evidence/smoke_evidence.txt`: `e0a81c57eb649dfad93de9a22ea8e9a8695b1b3bcda3154051bcd23358777f7a`
- `manifest_json`: `99d634e2e787bccef4f19b58d6a39f45d0c33305bb808d0f7af777a243eb6975`
- `report_md`: `e7870421f026985f932c66797a08197889a210ba2317c0c37df8fd42f1f9e401`
- `requirements_lock`: `69ef2ff678cb27396ca33f5230fde2790e219e38579611c838bd36878790931e`

## Git Status
```text
git status indisponivel (diretorio nao e repo git)
```
