from __future__ import annotations

import json
from pathlib import Path


ROOT = Path("/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220")
OUTPUT_SNIPPET = Path("data/market_data/vivt3_legacy_solution.txt")
CODE_EXTS = {".py", ".ipynb"}
TEXT_EXTS = {".py", ".ipynb", ".json", ".md", ".txt", ".yaml", ".yml"}


def iter_files(root: Path):
    for p in root.rglob("*"):
        if p.is_file():
            yield p


def search_vivt3_code(root: Path) -> list[tuple[Path, int, str]]:
    matches: list[tuple[Path, int, str]] = []
    for path in iter_files(root):
        if path.suffix.lower() not in CODE_EXTS:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        if path.suffix.lower() == ".ipynb":
            try:
                nb = json.loads(text)
                cells = nb.get("cells") or []
                for c_idx, cell in enumerate(cells):
                    source = "".join(cell.get("source") or [])
                    for l_idx, line in enumerate(source.splitlines(), start=1):
                        if "VIVT3" in line:
                            snippet = f"[cell {c_idx} line {l_idx}] {line.strip()}"
                            matches.append((path, l_idx, snippet))
            except Exception:
                if "VIVT3" in text:
                    for l_idx, line in enumerate(text.splitlines(), start=1):
                        if "VIVT3" in line:
                            matches.append((path, l_idx, line.strip()))
        else:
            for l_idx, line in enumerate(text.splitlines(), start=1):
                if "VIVT3" in line:
                    matches.append((path, l_idx, line.strip()))
    return matches


def search_vivt3_text(root: Path) -> list[tuple[Path, int, str]]:
    matches: list[tuple[Path, int, str]] = []
    for path in iter_files(root):
        if path.suffix.lower() not in TEXT_EXTS:
            continue
        try:
            txt = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for l_idx, line in enumerate(txt.splitlines(), start=1):
            if "VIVT3" in line:
                matches.append((path, l_idx, line.strip()))
    return matches


def search_corporate_action_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for path in iter_files(root):
        name = path.name.lower()
        if "corporate_actions" in name:
            out.append(path)
    return sorted(out)


def search_experiment_notebook_fixes(root: Path) -> list[Path]:
    out: list[Path] = []
    for path in iter_files(root):
        low = str(path).lower()
        if ("experiments" in low or "notebook" in low or "notebooks" in low) and path.suffix.lower() in CODE_EXTS:
            try:
                txt = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            if any(k in txt.lower() for k in ["vivt3", "split", "grupamento", "corporate_actions"]):
                out.append(path)
    return sorted(out)


def pick_authoritative_snippet(vivt_matches: list[tuple[Path, int, str]]) -> tuple[Path, str] | None:
    prioritized = []
    for path, _, line in vivt_matches:
        low = str(path).lower()
        score = 0
        if "vivt3_policy_resolution" in low:
            score += 10
        if "policy_fix_vivt3" in low:
            score += 8
        if "corporate_actions" in low:
            score += 5
        if "state" in low or "governanca" in low:
            score += 3
        if "fix" in low or "forense" in low:
            score += 2
        if any(k in line.lower() for k in ["chosen_factor", "chosen_candidate", "decision_reason", "factor", "adjust", "grupamento", "split", "vivt3"]):
            score += 2
        prioritized.append((score, path, line))
    if not prioritized:
        return None
    prioritized.sort(key=lambda x: x[0], reverse=True)
    _, p, snippet = prioritized[0]
    return p, snippet


def main() -> None:
    if not ROOT.exists():
        raise RuntimeError(f"Root inexistente: {ROOT}")

    vivt_matches_code = search_vivt3_code(ROOT)
    vivt_matches_text = search_vivt3_text(ROOT)
    vivt_matches = vivt_matches_code + [m for m in vivt_matches_text if m not in vivt_matches_code]
    corp_files = search_corporate_action_files(ROOT)
    exp_nb_hits = search_experiment_notebook_fixes(ROOT)

    print("TASK T023 - LEGACY HUNT (VIVT3)")
    print("")
    print("SEARCH 1 - VIVT3 EM PY/IPYNB/TEXT")
    if not vivt_matches:
        print("- Nenhuma ocorrência encontrada.")
    else:
        for path, line_no, line in vivt_matches[:120]:
            print(f"- {path}:{line_no} | {line}")

    print("")
    print("SEARCH 2 - ARQUIVOS COM 'corporate_actions' NO NOME")
    if not corp_files:
        print("- Nenhum arquivo encontrado.")
    else:
        for p in corp_files[:120]:
            print(f"- {p}")

    print("")
    print("SEARCH 3 - SUBPASTAS experiments/notebooks COM PISTAS")
    if not exp_nb_hits:
        print("- Nenhuma pista encontrada.")
    else:
        for p in exp_nb_hits[:120]:
            print(f"- {p}")

    chosen = pick_authoritative_snippet(vivt_matches)
    OUTPUT_SNIPPET.parent.mkdir(parents=True, exist_ok=True)

    if chosen is None:
        text = "FOUND: NONE\nLOGIC EXTRACTED: NONE\n"
        OUTPUT_SNIPPET.write_text(text, encoding="utf-8")
        print("")
        print("FOUND: NONE")
        print("LOGIC EXTRACTED: NONE")
        print(f"SNIPPET_FILE: {OUTPUT_SNIPPET}")
        print("OVERALL STATUS: [[ FAIL ]]")
        return

    file_path, snippet = chosen
    result = (
        f"FOUND: {file_path}\n"
        f"LOGIC EXTRACTED: {snippet}\n"
    )
    OUTPUT_SNIPPET.write_text(result, encoding="utf-8")

    print("")
    print(f"FOUND: {file_path}")
    print(f"LOGIC EXTRACTED: {snippet}")
    print(f"SNIPPET_FILE: {OUTPUT_SNIPPET}")
    print("OVERALL STATUS: [[ PASS ]]")


if __name__ == "__main__":
    main()
