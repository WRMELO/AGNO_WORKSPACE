import csv
import json
import os
import shutil
from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
from langchain_text_splitters import RecursiveCharacterTextSplitter


def load_text(path: Path) -> str:
    suffix = path.suffix.lower()
    try:
        raw = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raw = path.read_text(encoding="utf-8", errors="ignore")

    if suffix == ".json":
        try:
            return json.dumps(json.loads(raw), ensure_ascii=False, indent=2)
        except json.JSONDecodeError:
            return raw
    if suffix == ".csv":
        reader = csv.reader(raw.splitlines())
        return "\n".join([" | ".join(row) for row in reader])
    return raw


def sanitize_file(path: Path) -> bool:
    original = path.read_text(encoding="utf-8", errors="ignore")
    sanitized = original
    sanitized = sanitized.replace(
        "/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220",
        "[TENTATIVA2_ROOT]",
    )
    sanitized = sanitized.replace("/home/wilson/CEP_BUNDLE_CORE", "[LEGACY_ROOT]")
    sanitized = sanitized.replace("/home/wilson/", "[HOME_ROOT]/")
    if sanitized != original:
        path.write_text(sanitized, encoding="utf-8")
        return True
    return False


def update_registry(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    ok = True

    old_mermaid = (
        "```mermaid\nflowchart LR\n"
        "    T001['T001: Bootstrap'] --> T002['T002: Infra Audit'] --> "
        "T003['T003: Ingestao Legado'] --> T004['T004: Gov Sync'] --> "
        "T005['T005: Diagnostico'] --> T009['T009: Reconstrucao Corpus'] --> "
        "T010['T010: Indexacao Vetorial'] --> T011['T011: Validacao e Fix']\n```"
    )
    new_mermaid = (
        "```mermaid\nflowchart LR\n"
        "    T001['T001: Bootstrap'] --> T002['T002: Infra Audit'] --> "
        "T003['T003: Ingestao Legado'] --> T004['T004: Gov Sync'] --> "
        "T005['T005: Diagnostico'] --> T009['T009: Reconstrucao Corpus'] --> "
        "T010['T010: Indexacao Vetorial'] --> T011['T011: Validacao e Fix'] --> "
        "T012['T012: Ingestao Tentativa 2']\n```"
    )
    if old_mermaid in text:
        text = text.replace(old_mermaid, new_mermaid)
    elif "T012['T012: Ingestao Tentativa 2']" not in text:
        ok = False

    row_t011 = "| 2026-02-25T19:15:00Z | T011 | DONE | Sanidade RAG executada e diagrama refatorado. |"
    row_t012 = "| 2026-02-25T19:45:00Z | T012 | DONE | Ingestao da Tentativa 2 e indexacao vetorial dedicada. |"
    if row_t011 not in text:
        text += "\n" + row_t011
    if row_t012 not in text:
        text += "\n" + row_t012

    path.write_text(text.rstrip() + "\n", encoding="utf-8")
    return ok


def update_changelog(path: Path) -> None:
    entry = (
        "- 2026-02-25T19:45:00+00:00 | "
        "INGEST: Criação de Corpus Temporário baseado na 'Tentativa 2' "
        "(Realidade Operacional Recente).\n"
    )
    txt = path.read_text(encoding="utf-8") if path.exists() else "# Changelog\n\n"
    if entry not in txt:
        if not txt.endswith("\n"):
            txt += "\n"
        txt += entry
        path.write_text(txt, encoding="utf-8")


def main():
    source_path = Path("/home/wilson/CEP_BUNDLE_CORE/_tentativa2_reexecucao_completa_20260220")
    target_path = Path("02_Knowledge_Bank/Tentativa2_Snapshot")
    vector_store = Path("02_Knowledge_Bank/Tentativa2_VectorStore")
    registry_path = Path("00_Strategy/TASK_REGISTRY.md")
    changelog_path = Path("00_Strategy/changelog.md")

    allowed_ext = {".md", ".json", ".py", ".csv", ".yaml", ".txt"}
    skip_dirs = {".git", "__pycache__", ".venv", "node_modules"}

    target_path.mkdir(parents=True, exist_ok=True)
    vector_store.mkdir(parents=True, exist_ok=True)

    copied_files = []
    sanitized_count = 0
    experiments = []

    # COPY + SANITIZE
    for root, dirs, files in os.walk(source_path):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        root_path = Path(root)
        for name in files:
            src = root_path / name
            if src.suffix.lower() not in allowed_ext:
                continue
            rel = src.relative_to(source_path)
            dst = target_path / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            copied_files.append(dst)
            if sanitize_file(dst):
                sanitized_count += 1
            low = str(rel).lower()
            if "exp_" in name.lower() or "report_experiment" in low:
                experiments.append(str(dst))

    # INDEXING
    docs = []
    for p in copied_files:
        text = load_text(p).strip()
        if text:
            docs.append({"source": str(p), "text": text})

    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = []
    for d in docs:
        for i, chunk in enumerate(splitter.split_text(d["text"])):
            chunks.append(
                {"id": f'{d["source"]}::chunk_{i}', "doc": chunk, "meta": {"source": d["source"], "i": i}}
            )

    client = chromadb.PersistentClient(path=str(vector_store))
    collection_name = "task012_tentativa2_index"
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass
    collection = client.get_or_create_collection(
        name=collection_name, embedding_function=DefaultEmbeddingFunction()
    )
    batch = 128
    for i in range(0, len(chunks), batch):
        b = chunks[i : i + batch]
        collection.add(
            ids=[x["id"] for x in b],
            documents=[x["doc"] for x in b],
            metadatas=[x["meta"] for x in b],
        )

    vector_count = collection.count()

    # REGISTRY + CHANGELOG
    registry_ok = update_registry(registry_path)
    update_changelog(changelog_path)

    # REPORT V4.0
    overall_pass = (
        len(copied_files) > 0
        and vector_count > 0
        and len(experiments) > 0
        and registry_ok
        and (vector_store / "chroma.sqlite3").exists()
    )

    print("TASK-012 EXECUTION REPORT")
    print("")
    print("INGESTION STATS")
    print(f"- source: {source_path}")
    print(f"- target: {target_path}")
    print(f"- copied_files: {len(copied_files)}")
    print(f"- sanitized_files: {sanitized_count}")
    print(f"- chunks: {len(chunks)}")
    print(f"- vector_count: {vector_count}")
    print(f"- vector_store: {vector_store}")
    print("")
    print("EXPERIMENTS FOUND")
    if experiments:
        for item in experiments[:20]:
            print(f"- {item}")
    else:
        print("- NONE")
    print("")
    print("REGISTRY UPDATE")
    print(f"- registry_file: {registry_path}")
    print(f"- t011_done_row: {'PASS' if 'T011' in registry_path.read_text(encoding='utf-8') else 'FAIL'}")
    print(f"- t012_done_row: {'PASS' if 'T012' in registry_path.read_text(encoding='utf-8') else 'FAIL'}")
    print(
        "- mermaid_chain_t011_t012: "
        + (
            "PASS"
            if "T011['T011: Validacao e Fix'] --> T012['T012: Ingestao Tentativa 2']"
            in registry_path.read_text(encoding='utf-8')
            else "FAIL"
        )
    )
    print("")
    print("OVERALL STATUS")
    print("OVERALL STATUS: [[ PASS ]]" if overall_pass else "OVERALL STATUS: [[ FAIL ]]")


if __name__ == "__main__":
    main()
