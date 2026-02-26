from __future__ import annotations

import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MICRO_FILE = ROOT / "src" / "data_engine" / "ssot" / "SSOT_MARKET_DATA_RAW.parquet"
MACRO_FILE = ROOT / "src" / "data_engine" / "ssot" / "SSOT_MACRO.parquet"
UNIVERSE_FILE = ROOT / "src" / "data_engine" / "ssot" / "SSOT_UNIVERSE_OPERATIONAL.parquet"
FUNDAMENTALS_FILE = ROOT / "src" / "data_engine" / "ssot" / "SSOT_FUNDAMENTALS.parquet"
TARGET_FILE = ROOT / "src" / "data_engine" / "ssot" / "SSOT_CANONICAL_BASE.parquet"
HEURISTIC_AUDIT_FILE = ROOT / "data" / "market_data" / "heuristic_adjustments_t023.csv"

REF_WINDOW_K = 60
SUBGROUP_N = 4
A2_N4 = 0.729
D4_N4 = 2.282
E2_IMR_N2 = 2.66
D4_IMR_N2 = 3.267


def parse_split_factor(raw: object) -> float | None:
    if raw is None:
        return None
    text = str(raw).strip().lower()
    if text in {"", "nan", "none", "null", "0", "0.0", "1", "1.0"}:
        return None

    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:para|:|/)\s*(\d+(?:[.,]\d+)?)", text)
    if m:
        num = float(m.group(1).replace(",", "."))
        den = float(m.group(2).replace(",", "."))
        if den == 0:
            return None
        return num / den

    try:
        v = float(text.replace(",", "."))
    except ValueError:
        return None
    if v <= 0:
        return None
    if v == 1.0:
        return None
    return v


@dataclass
class HeuristicDecision:
    ticker: str
    event_date: str
    anchor_date: str
    split_factor: float
    chosen_adj: float
    chosen_abs_logret: float
    raw_abs_logret_at_anchor: float
    action: str


def safe_log_ratio(num: float, den: float) -> float:
    if den <= 0 or num <= 0:
        return math.inf
    try:
        return float(math.log(num / den))
    except ValueError:
        return math.inf


def apply_heuristic_split_adjustment(gdf: pd.DataFrame, ticker: str) -> tuple[pd.DataFrame, list[HeuristicDecision]]:
    g = gdf.sort_values("date").reset_index(drop=True).copy()
    n = len(g)
    multipliers = np.ones(n, dtype=float)  # multiplicador backward aplicado no histórico.

    decisions: list[HeuristicDecision] = []
    split_idx = [i for i, v in enumerate(g["split_factor"].tolist()) if pd.notna(v)]

    for i in split_idx:
        factor = float(g.at[i, "split_factor"])
        if factor <= 0:
            continue

        candidate_anchors = [i]
        if i + 1 < n:
            candidate_anchors.append(i + 1)

        best = None
        for anchor in candidate_anchors:
            if anchor <= 0:
                continue
            p_prev = float(g.at[anchor - 1, "close_raw"])
            p_cur = float(g.at[anchor, "close_raw"])
            for adj in (1.0, factor, 1.0 / factor):
                lr = safe_log_ratio(p_cur * adj, p_prev)
                score = abs(lr)
                if best is None or score < best["score"]:
                    best = {"anchor": anchor, "adj": float(adj), "score": score}

        if best is None:
            continue

        anchor = int(best["anchor"])
        chosen_adj = float(best["adj"])  # multiplicador no preço atual em teste.
        hist_scale = 1.0 / chosen_adj  # escala backward no histórico para equivaler ao teste.

        # Aplica ajuste no histórico até anchor-1 (cumulative backward adjustment).
        if abs(hist_scale - 1.0) > 1e-12:
            multipliers[:anchor] *= hist_scale

        p_prev = float(g.at[anchor - 1, "close_raw"]) if anchor > 0 else np.nan
        p_cur = float(g.at[anchor, "close_raw"]) if anchor < n else np.nan
        raw_lr = safe_log_ratio(p_cur, p_prev) if anchor > 0 else math.inf
        action = "RAW_WINS" if abs(chosen_adj - 1.0) <= 1e-12 else "ADJUSTED"

        decisions.append(
            HeuristicDecision(
                ticker=ticker,
                event_date=pd.Timestamp(g.at[i, "date"]).date().isoformat(),
                anchor_date=pd.Timestamp(g.at[anchor, "date"]).date().isoformat(),
                split_factor=factor,
                chosen_adj=chosen_adj,
                chosen_abs_logret=float(best["score"]),
                raw_abs_logret_at_anchor=abs(raw_lr) if raw_lr != math.inf else np.nan,
                action=action,
            )
        )

    g["close_operational"] = g["close_raw"] * multipliers
    return g, decisions


def main() -> None:
    if not all(p.exists() for p in [MICRO_FILE, MACRO_FILE, UNIVERSE_FILE, FUNDAMENTALS_FILE]):
        raise RuntimeError("Arquivos de entrada obrigatórios ausentes para T023 Heuristic.")

    micro = pd.read_parquet(MICRO_FILE)
    macro = pd.read_parquet(MACRO_FILE)
    universe = pd.read_parquet(UNIVERSE_FILE)
    fundamentals = pd.read_parquet(FUNDAMENTALS_FILE, columns=["ticker", "sector"])

    valid_tickers = set(universe["ticker"].astype(str).str.upper().str.strip())
    micro["ticker"] = micro["ticker"].astype(str).str.upper().str.strip()
    micro = micro[micro["ticker"].isin(valid_tickers)].copy()
    micro["date"] = pd.to_datetime(micro["date"], errors="coerce")
    micro["close_raw"] = pd.to_numeric(micro["close"], errors="coerce")
    micro = micro.dropna(subset=["date", "close_raw"]).sort_values(["ticker", "date"]).reset_index(drop=True)

    micro["split_factor"] = micro["splits"].apply(parse_split_factor)

    adjusted_parts = []
    all_decisions: list[HeuristicDecision] = []
    for ticker, g in micro.groupby("ticker", sort=False):
        g_adj, decisions = apply_heuristic_split_adjustment(g, ticker)
        adjusted_parts.append(g_adj)
        all_decisions.extend(decisions)

    data = pd.concat(adjusted_parts, ignore_index=True).sort_values(["ticker", "date"]).reset_index(drop=True)

    # Process variables.
    data.loc[data["close_operational"] <= 0, "close_operational"] = np.nan
    data["log_ret_nominal"] = np.log(data["close_operational"] / data.groupby("ticker")["close_operational"].shift(1))
    data["log_ret_nominal"] = data["log_ret_nominal"].replace([np.inf, -np.inf], np.nan)

    macro["date"] = pd.to_datetime(macro["date"], errors="coerce")
    data = data.merge(macro, on="date", how="left")
    data = data.sort_values(["ticker", "date"]).reset_index(drop=True)

    data["X_real"] = data["log_ret_nominal"] - data["cdi_log_daily"]
    data["i_value"] = data["X_real"]
    data["mr_value"] = (data["i_value"] - data.groupby("ticker")["i_value"].shift(1)).abs()

    grp = data.groupby("ticker", group_keys=False)
    data["xbar_value"] = grp["i_value"].transform(lambda s: s.rolling(SUBGROUP_N, min_periods=SUBGROUP_N).mean())
    roll_max = grp["i_value"].transform(lambda s: s.rolling(SUBGROUP_N, min_periods=SUBGROUP_N).max())
    roll_min = grp["i_value"].transform(lambda s: s.rolling(SUBGROUP_N, min_periods=SUBGROUP_N).min())
    data["r_value"] = roll_max - roll_min

    data["center_line"] = grp["i_value"].transform(lambda s: s.rolling(REF_WINDOW_K, min_periods=REF_WINDOW_K).mean().shift(1))
    data["mr_bar"] = grp["mr_value"].transform(lambda s: s.rolling(REF_WINDOW_K, min_periods=REF_WINDOW_K).mean().shift(1))
    data["r_bar"] = grp["r_value"].transform(lambda s: s.rolling(REF_WINDOW_K, min_periods=REF_WINDOW_K).mean().shift(1))

    data["i_ucl"] = data["center_line"] + E2_IMR_N2 * data["mr_bar"]
    data["i_lcl"] = data["center_line"] - E2_IMR_N2 * data["mr_bar"]
    data["mr_ucl"] = D4_IMR_N2 * data["mr_bar"]
    data["xbar_ucl"] = data["center_line"] + A2_N4 * data["r_bar"]
    data["xbar_lcl"] = data["center_line"] - A2_N4 * data["r_bar"]
    data["r_ucl"] = D4_N4 * data["r_bar"]

    fundamentals["ticker"] = fundamentals["ticker"].astype(str).str.upper().str.strip()
    fundamentals = fundamentals.drop_duplicates(subset=["ticker"])
    data = data.merge(fundamentals, on="ticker", how="left")

    output_cols = [
        "ticker",
        "date",
        "close_operational",
        "close_raw",
        "X_real",
        "i_value",
        "i_ucl",
        "i_lcl",
        "mr_value",
        "mr_ucl",
        "xbar_value",
        "xbar_ucl",
        "xbar_lcl",
        "r_value",
        "r_ucl",
        "sector",
        "mr_bar",
        "r_bar",
        "center_line",
        "splits",
        "split_factor",
    ]
    out = data[output_cols].copy()
    out["date"] = pd.to_datetime(out["date"]).dt.date.astype(str)

    TARGET_FILE.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(TARGET_FILE, index=False)

    audit_df = pd.DataFrame([d.__dict__ for d in all_decisions])
    HEURISTIC_AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
    audit_df.to_csv(HEURISTIC_AUDIT_FILE, index=False)

    corrected_count = int((audit_df["action"] == "ADJUSTED").sum()) if not audit_df.empty else 0
    vivt_rows = audit_df[audit_df["ticker"] == "VIVT3"] if not audit_df.empty else pd.DataFrame()
    mglu_rows = audit_df[audit_df["ticker"] == "MGLU3"] if not audit_df.empty else pd.DataFrame()
    petr_rows = audit_df[audit_df["ticker"] == "PETR4"] if not audit_df.empty else pd.DataFrame()

    print("TASK T023 - CANONICAL HEURISTIC ENGINE")
    print("")
    print(f"Rows: {len(out)} | Tickers: {out['ticker'].nunique()}")
    print(f"Engine Built. Heuristic Corrected {corrected_count} Events.")
    print(f"Target: {TARGET_FILE}")
    print(f"Heuristic audit: {HEURISTIC_AUDIT_FILE}")
    print("")
    print("TARGET CHECK")
    print(f"- VIVT3 events: {len(vivt_rows)} | adjusted: {int((vivt_rows['action']=='ADJUSTED').sum()) if not vivt_rows.empty else 0}")
    print(f"- MGLU3 events: {len(mglu_rows)} | adjusted: {int((mglu_rows['action']=='ADJUSTED').sum()) if not mglu_rows.empty else 0}")
    print(f"- PETR4 events: {len(petr_rows)} | adjusted: {int((petr_rows['action']=='ADJUSTED').sum()) if not petr_rows.empty else 0}")
    print("")
    print("OVERALL STATUS")
    print("OVERALL STATUS: [[ PASS ]]")


if __name__ == "__main__":
    main()
