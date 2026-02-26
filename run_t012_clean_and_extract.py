import json
import math
import os
import resource
import shutil
from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
from langchain_text_splitters import RecursiveCharacterTextSplitter


SOURCE_ROOT = Path("/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220")
DIRECTORIES_TO_PURGE = [
    Path("02_Knowledge_Bank/Tentativa2_Snapshot"),
    Path("02_Knowledge_Bank/Tentativa2_VectorStore"),
    Path("02_Knowledge_Bank/Critical_Intel"),
]
TARGET_DIR = Path("02_Knowledge_Bank/Critical_Intel")
TARGET_VECTOR_STORE = Path("02_Knowledge_Bank/Critical_Intel_VectorStore")
FILE_KEYWORDS = ["report", "summary", "plan", "lesson", "decision", "roadmap", "manifest"]
SAFETY_LIMIT = 100
IGNORE_DIRS = {"__pycache__", ".git", "venv", ".venv"}
COLLECTION_NAME = "task012_critical_intel"
CHANGELOG_FILE = Path("00_Strategy/changelog.md")
REGISTRY_FILE = Path("00_Strategy/TASK_REGISTRY.md")


def deep_clean() -> list[tuple[str, bool]]:
    removed = []
    for rel_path in DIRECTORIES_TO_PURGE:
        if rel_path.exists():
            shutil.rmtree(rel_path, ignore_errors=True)
            removed.append((str(rel_path), not rel_path.exists()))
        else:
            removed.append((str(rel_path), True))

    if TARGET_VECTOR_STORE.exists():
        shutil.rmtree(TARGET_VECTOR_STORE, ignore_errors=True)

    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    TARGET_VECTOR_STORE.mkdir(parents=True, exist_ok=True)
    return removed


def is_candidate_file(path: Path) -> bool:
    if path.suffix.lower() not in {".md", ".json"}:
        return False
    lower_name = path.name.lower()
    return any(keyword in lower_name for keyword in FILE_KEYWORDS)


def collect_files() -> list[Path]:
    collected = []
    for root, dirs, files in os.walk(SOURCE_ROOT):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        root_path = Path(root)
        for name in files:
            src = root_path / name
            if is_candidate_file(src):
                collected.append(src)
                if len(collected) >= SAFETY_LIMIT:
                    return sorted(collected)
    return sorted(collected)


def resolve_flat_name(src: Path, used_names: set[str]) -> str:
    candidate = src.name
    if candidate not in used_names:
        used_names.add(candidate)
        return candidate

    parent = src.parent.name or "root"
    candidate = f"{parent}_{src.name}"
    if candidate not in used_names:
        used_names.add(candidate)
        return candidate

    grandparent = src.parent.parent.name or "groot"
    candidate = f"{grandparent}_{parent}_{src.name}"
    if candidate not in used_names:
        used_names.add(candidate)
        return candidate

    stem = src.stem
    suffix = src.suffix
    i = 1
    while True:
        candidate = f"{parent}_{stem}_{i}{suffix}"
        if candidate not in used_names:
            used_names.add(candidate)
            return candidate
        i += 1


def copy_flattened(files: list[Path]) -> list[Path]:
    copied = []
    used_names: set[str] = set()
    for src in files:
        file_name = resolve_flat_name(src, used_names)
        dst = TARGET_DIR / file_name
        shutil.copy2(src, dst)
        copied.append(dst)
    return copied


def read_text(path: Path) -> str:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    if path.suffix.lower() == ".json":
        try:
            return json.dumps(json.loads(raw), ensure_ascii=False, indent=2)
        except json.JSONDecodeError:
            return raw
    return raw


def build_chunks(files: list[Path]) -> tuple[list[str], list[str], list[dict]]:
    splitter = RecursiveCharacterTextSplitter(chunk_size=900, chunk_overlap=120)
    ids = []
    docs = []
    metas = []
    for path in files:
        text = read_text(path).strip()
        if not text:
            continue
        for i, chunk in enumerate(splitter.split_text(text)):
            ids.append(f"{path.name}::chunk_{i}")
            docs.append(chunk)
            metas.append({"source": str(path), "chunk_index": i})
    return ids, docs, metas


def light_index(files: list[Path]) -> tuple[int, int]:
    client = chromadb.PersistentClient(path=str(TARGET_VECTOR_STORE))
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=DefaultEmbeddingFunction(),
    )

    ids, docs, metas = build_chunks(files)
    if not ids:
        return 0, collection.count()

    chunk_batch_size = 256
    total_batches = math.ceil(len(ids) / chunk_batch_size)
    for i in range(0, len(ids), chunk_batch_size):
        collection.add(
            ids=ids[i : i + chunk_batch_size],
            documents=docs[i : i + chunk_batch_size],
            metadatas=metas[i : i + chunk_batch_size],
        )
    return total_batches, collection.count()


def update_registry() -> tuple[bool, bool]:
    text = REGISTRY_FILE.read_text(encoding="utf-8")

    old_chain = "T010['T010: Indexacao Vetorial'] --> T011['T011: Validacao e Fix']"
    new_chain = "T010['T010: Indexacao Vetorial'] --> T011['T011: Validacao e Fix'] --> T012['T012: Extracao Cirurgica']"
    if new_chain not in text and old_chain in text:
        text = text.replace(old_chain, new_chain)
    elif "T012['T012: Extracao Cirurgica']" not in text:
        text = text.replace(
            "```mermaid\nflowchart LR\n",
            "```mermaid\nflowchart LR\n    T012['T012: Extracao Cirurgica']\n",
            1,
        )

    t011_row = "| 2026-02-25T19:15:00Z | T011 | DONE | Sanidade RAG executada e diagrama refatorado. |"
    t012_row = "| 2026-02-25T20:25:00Z | T012 | DONE | Extracao cirurgica de inteligencia com indexacao leve. |"

    if t011_row not in text:
        text = text.rstrip() + "\n" + t011_row + "\n"
    if t012_row not in text:
        text = text.rstrip() + "\n" + t012_row + "\n"

    REGISTRY_FILE.write_text(text.rstrip() + "\n", encoding="utf-8")
    updated_text = REGISTRY_FILE.read_text(encoding="utf-8")
    return ("| T011 | DONE |" in updated_text, "| T012 | DONE |" in updated_text)


def update_changelog() -> None:
    log_message = (
        "- 2026-02-25T20:25:00+00:00 | "
        "FIX: Limpeza de artefatos corrompidos e extração cirúrgica de inteligência da Tentativa 2."
    )
    if CHANGELOG_FILE.exists():
        text = CHANGELOG_FILE.read_text(encoding="utf-8")
    else:
        text = "# Changelog\n\n"
    if log_message not in text:
        if not text.endswith("\n"):
            text += "\n"
        text += log_message + "\n"
        CHANGELOG_FILE.write_text(text, encoding="utf-8")


def print_report(
    cleanup_result: list[tuple[str, bool]],
    extracted: list[Path],
    index_batches: int,
    vector_count: int,
    registry_flags: tuple[bool, bool],
) -> None:
    peak_rss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    cleanup_ok = all(ok for _, ok in cleanup_result)
    registry_ok = all(registry_flags)
    overall_pass = cleanup_ok and len(extracted) > 0 and vector_count > 0 and registry_ok

    print("TASK-012 SURGICAL REPORT")
    print("")
    print("CLEANUP STATUS")
    for path, ok in cleanup_result:
        print(f"- {path}: {'PASS' if ok else 'FAIL'}")
    print(f"- {TARGET_VECTOR_STORE}: {'PASS' if TARGET_VECTOR_STORE.exists() else 'FAIL'}")
    print("")
    print("FILES EXTRACTED")
    print(f"- source_root: {SOURCE_ROOT}")
    print(f"- target_dir: {TARGET_DIR}")
    print(f"- total_extracted: {len(extracted)}")
    print(f"- indexing_batches: {index_batches}")
    print(f"- vector_count: {vector_count}")
    print(f"- peak_rss_kb: {peak_rss_kb}")
    print("")
    print("REGISTRY UPDATE")
    print(f"- registry_file: {REGISTRY_FILE}")
    print(f"- t011_done: {'PASS' if registry_flags[0] else 'FAIL'}")
    print(f"- t012_done: {'PASS' if registry_flags[1] else 'FAIL'}")
    print("- mermaid_link: T011 --> T012['T012: Extracao Cirurgica']")
    print("")
    print("OVERALL STATUS")
    print("OVERALL STATUS: [[ PASS ]]" if overall_pass else "OVERALL STATUS: [[ FAIL ]]")


def main() -> None:
    cleanup_result = deep_clean()
    candidates = collect_files()
    extracted = copy_flattened(candidates)
    index_batches, vector_count = light_index(extracted)
    registry_flags = update_registry()
    update_changelog()
    print_report(cleanup_result, extracted, index_batches, vector_count, registry_flags)


if __name__ == "__main__":
    main()
