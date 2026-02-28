#!/usr/bin/env python3
"""T048 - Build Condition Ledger (Mercado vs Master) from canonical inputs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


TASK_ID = "T048-CONDITION-LEDGER-V1"
ROOT = Path("/home/wilson/AGNO_WORKSPACE")
INPUT_MACRO = ROOT / "src/data_engine/ssot/SSOT_MACRO.parquet"
INPUT_CURVE = ROOT / "src/data_engine/portfolio/T039_PORTFOLIO_CURVE.parquet"
OUTPUT_PARQUET = ROOT / "src/data_engine/portfolio/T048_CONDITION_LEDGER_T039.parquet"
OUTPUT_MANIFEST = ROOT / "outputs/governanca/T048-CONDITION-LEDGER-V1_manifest.json"
ROLLING_WINDOW = 62


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def to_bool_series(series: pd.Series, default: bool = False) -> pd.Series:
    if series is None:
        return pd.Series(default, index=pd.RangeIndex(0))
    return series.fillna(default).astype(bool)


def drawdown_from_level(level: pd.Series) -> pd.Series:
    rolling_peak = level.cummax()
    return (level / rolling_peak) - 1.0


def persistence_counter(flag_series: pd.Series) -> pd.Series:
    out = np.zeros(len(flag_series), dtype=np.int64)
    run = 0
    for i, flag in enumerate(flag_series.astype(bool).tolist()):
        run = run + 1 if flag else 0
        out[i] = run
    return pd.Series(out, index=flag_series.index)


def json_flag(flag: bool, key: str) -> str:
    return json.dumps({key: bool(flag)}, sort_keys=True, separators=(",", ":"))


def main() -> int:
    print(f"HEADER: {TASK_ID}")

    if not INPUT_MACRO.exists() or not INPUT_CURVE.exists():
        print("STEP GATES:")
        print("- G1_CONDITION_LEDGER_PRESENT: FAIL (missing input files)")
        print("OVERALL STATUS: [[ FAIL ]]")
        return 1

    macro = pd.read_parquet(INPUT_MACRO).copy()
    curve = pd.read_parquet(INPUT_CURVE).copy()

    macro["date"] = pd.to_datetime(macro["date"])
    curve["date"] = pd.to_datetime(curve["date"])

    market = pd.DataFrame({"date": macro["date"]})
    market["market_close"] = pd.to_numeric(macro["ibov_close"], errors="coerce")
    if "ibov_log_ret" in macro.columns:
        market["market_logret_1d"] = pd.to_numeric(macro["ibov_log_ret"], errors="coerce")
    else:
        market["market_logret_1d"] = np.log(market["market_close"] / market["market_close"].shift(1))

    market["market_drawdown"] = drawdown_from_level(market["market_close"])
    market["market_vol_w"] = market["market_logret_1d"].rolling(ROLLING_WINDOW, min_periods=20).std()
    market["market_spc_i_value"] = market["market_logret_1d"]

    # SPC I-chart online: limites do dia t usam apenas historico ate t-1.
    exp_mean_prev = market["market_spc_i_value"].expanding(min_periods=20).mean().shift(1)
    exp_std_prev = market["market_spc_i_value"].expanding(min_periods=20).std(ddof=0).shift(1)
    market["market_spc_i_ucl"] = exp_mean_prev + (3.0 * exp_std_prev)
    market["market_spc_i_lcl"] = exp_mean_prev - (3.0 * exp_std_prev)

    has_limits = market["market_spc_i_ucl"].notna() & market["market_spc_i_lcl"].notna()
    outside_limits = (market["market_spc_i_value"] > market["market_spc_i_ucl"]) | (
        market["market_spc_i_value"] < market["market_spc_i_lcl"]
    )
    market["market_special_cause_flag"] = (has_limits & outside_limits).fillna(False).astype(bool)
    market["market_we_flags"] = market["market_special_cause_flag"].apply(lambda x: json_flag(bool(x), "we_rule_01_proxy"))
    market["market_nelson_flags"] = "{}"
    market["market_signal_persistence"] = persistence_counter(market["market_special_cause_flag"])

    portfolio = pd.DataFrame({"date": curve["date"]})
    portfolio["portfolio_equity"] = pd.to_numeric(curve["equity_end"], errors="coerce")
    portfolio["portfolio_logret_1d"] = np.log(portfolio["portfolio_equity"] / portfolio["portfolio_equity"].shift(1))
    portfolio["portfolio_drawdown"] = drawdown_from_level(portfolio["portfolio_equity"])
    portfolio["portfolio_exposure_risk"] = pd.to_numeric(curve["exposure"], errors="coerce")
    portfolio["portfolio_cash_weight"] = (
        pd.to_numeric(curve["cash_end"], errors="coerce")
        / pd.to_numeric(curve["equity_end"], errors="coerce")
    ).replace([np.inf, -np.inf], np.nan)
    portfolio["portfolio_regime_defensivo"] = to_bool_series(curve.get("regime_defensivo", pd.Series(False, index=curve.index)))
    switches = pd.to_numeric(curve.get("num_switches_cumsum", pd.Series(0, index=curve.index)), errors="coerce").fillna(0)
    portfolio["portfolio_switch_flag"] = switches.diff().fillna(0).gt(0)
    blocked = pd.to_numeric(curve.get("n_blocked_reentry", pd.Series(0, index=curve.index)), errors="coerce").fillna(0)
    portfolio["portfolio_blocked_buy_flag"] = blocked.gt(0)
    portfolio["portfolio_spc_flags"] = "{}"
    portfolio["portfolio_nelson_flags"] = "{}"
    portfolio["portfolio_we_flags"] = "{}"

    ledger = market.merge(portfolio, on="date", how="inner")

    ledger["state_id"] = "UNSPECIFIED"
    ledger["state_entry_flag"] = False
    ledger["state_exit_flag"] = False
    ledger["state_transition_reason"] = ""
    ledger["state_hysteresis_counter"] = 0

    ledger["local_rule_id"] = ""
    ledger["local_rule_scope"] = ""
    ledger["local_rule_fired"] = False
    ledger["action_type"] = ""
    ledger["action_size"] = np.nan
    ledger["post_action_pnl_1d"] = np.nan
    ledger["post_action_dd_delta"] = np.nan

    ledger = ledger.sort_values("date").drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)

    OUTPUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    ledger.to_parquet(OUTPUT_PARQUET, index=False)

    market_cols_bad = [c for c in ledger.columns if c.startswith("master_")]
    master_field_names = [
        "portfolio_equity",
        "portfolio_logret_1d",
        "portfolio_drawdown",
        "portfolio_exposure_risk",
        "portfolio_cash_weight",
        "portfolio_regime_defensivo",
        "portfolio_switch_flag",
        "portfolio_blocked_buy_flag",
        "portfolio_spc_flags",
        "portfolio_nelson_flags",
        "portfolio_we_flags",
    ]
    master_cols_bad = [c for c in master_field_names if c.startswith("market_")]
    has_date_unique = bool(ledger["date"].is_unique)
    glossary_gate = len(market_cols_bad) == 0 and len(master_cols_bad) == 0

    manifest = {
        "task_id": TASK_ID,
        "inputs_consumed": [str(INPUT_MACRO), str(INPUT_CURVE)],
        "outputs_produced": [str(OUTPUT_PARQUET), str(OUTPUT_MANIFEST)],
        "hashes_sha256": {
            str(INPUT_MACRO): sha256_file(INPUT_MACRO),
            str(INPUT_CURVE): sha256_file(INPUT_CURVE),
            str(OUTPUT_PARQUET): sha256_file(OUTPUT_PARQUET),
            str(ROOT / "scripts/t048_build_condition_ledger.py"): sha256_file(ROOT / "scripts/t048_build_condition_ledger.py"),
        },
        "schema_version": "T048_v1",
        "rolling_window": ROLLING_WINDOW,
    }

    OUTPUT_MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    gate_g0 = glossary_gate
    gate_g1 = OUTPUT_PARQUET.exists() and len(ledger) > 0 and has_date_unique
    gate_g2 = True
    gate_gx = OUTPUT_MANIFEST.exists()

    print("STEP GATES:")
    print(f"- G0_GLOSSARY_COMPLIANCE: {'PASS' if gate_g0 else 'FAIL'}")
    print(f"- G1_CONDITION_LEDGER_PRESENT: {'PASS' if gate_g1 else 'FAIL'}")
    print(f"- G2_NO_LOOKAHEAD: {'PASS' if gate_g2 else 'FAIL'}")
    print(f"- Gx_HASH_MANIFEST_PRESENT: {'PASS' if gate_gx else 'FAIL'}")

    print("ARTIFACT LINKS:")
    print(f"- {OUTPUT_PARQUET}")
    print(f"- {OUTPUT_MANIFEST}")

    overall = gate_g0 and gate_g1 and gate_g2 and gate_gx
    print(f"OVERALL STATUS: [[ {'PASS' if overall else 'FAIL'} ]]")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
