from __future__ import annotations

import inspect
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TARGETS = [
    ROOT / "src" / "data_engine",
    ROOT / "src" / "data_engine" / "ports",
    ROOT / "src" / "data_engine" / "adapters",
    ROOT / "src" / "data_engine" / "dtos",
    ROOT / "src" / "data_engine" / "__init__.py",
    ROOT / "src" / "data_engine" / "ports" / "__init__.py",
    ROOT / "src" / "data_engine" / "adapters" / "__init__.py",
    ROOT / "src" / "data_engine" / "dtos" / "__init__.py",
    ROOT / "src" / "data_engine" / "ports" / "market_data_port.py",
]


def validate_paths() -> list[tuple[str, bool]]:
    results = []
    for path in TARGETS:
        results.append((str(path.relative_to(ROOT)), path.exists()))
    return results


def validate_class() -> tuple[bool, list[str]]:
    from src.data_engine.ports.market_data_port import MarketDataPort

    issues: list[str] = []
    if not inspect.isclass(MarketDataPort):
        issues.append("MarketDataPort nao e classe.")
        return False, issues

    if not inspect.isabstract(MarketDataPort):
        issues.append("MarketDataPort nao foi definida como abstrata.")

    expected = {"get_current_price", "get_historical_data", "get_fundamentals"}
    abstract_methods = set(getattr(MarketDataPort, "__abstractmethods__", set()))
    missing = sorted(expected - abstract_methods)
    if missing:
        issues.append(f"Metodos abstratos ausentes: {', '.join(missing)}")

    source = inspect.getsource(MarketDataPort)
    if source.count("raise NotImplementedError") < 3:
        issues.append("Metodos devem usar raise NotImplementedError.")

    return len(issues) == 0, issues


def main() -> None:
    path_checks = validate_paths()
    class_ok, class_issues = validate_class()
    paths_ok = all(ok for _, ok in path_checks)
    overall = paths_ok and class_ok

    print("TASK T014 - DATA ENGINE SKELETON")
    print("")
    print("PATH CHECK")
    for rel, ok in path_checks:
        print(f"- {rel}: {'PASS' if ok else 'FAIL'}")
    print("")
    print("CLASS CHECK")
    print(f"- market_data_port_abc: {'PASS' if class_ok else 'FAIL'}")
    if class_issues:
        for issue in class_issues:
            print(f"- issue: {issue}")
    print("")
    print("OVERALL STATUS")
    print("OVERALL STATUS: [[ PASS ]]" if overall else "OVERALL STATUS: [[ FAIL ]]")


if __name__ == "__main__":
    main()
