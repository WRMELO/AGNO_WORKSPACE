#!/usr/bin/env python3
"""T044-R1 - Plotly dashboard for ablation results."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


ROOT = Path("/home/wilson/AGNO_WORKSPACE")
TASK_ID = "T044-ANTI-DRIFT-GUARDRAILS-V2-PLOTLY"

INPUT_ABLATION = ROOT / "src/data_engine/portfolio/T044_GUARDRAILS_ABLATION_RESULTS.parquet"
INPUT_SELECTED = ROOT / "src/data_engine/portfolio/T044_GUARDRAILS_SELECTED_CONFIG.json"
INPUT_RULE = ROOT / "outputs/governanca/T044-ANTI-DRIFT-GUARDRAILS-V2_evidence/selection_rule.json"
INPUT_REPORT = ROOT / "outputs/governanca/T044-ANTI-DRIFT-GUARDRAILS-V2_report.md"
INPUT_MANIFEST = ROOT / "outputs/governanca/T044-ANTI-DRIFT-GUARDRAILS-V2_manifest.json"

OUTPUT_HTML = ROOT / "outputs/plots/T044_ABLATION_RESULTS_PLOTLY.html"
SCRIPT_PATH = ROOT / "scripts/t044_plotly_ablation_results.py"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.floating, float)):
        v = float(value)
        return v if np.isfinite(v) else None
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if pd.isna(value):
        return None
    return value


def parse_json_strict(path: Path) -> Any:
    return json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=lambda x: (_ for _ in ()).throw(ValueError(f"invalid JSON constant: {x}")),
    )


def write_json_strict(path: Path, payload: Any) -> None:
    safe = _json_safe(payload)
    txt = json.dumps(safe, indent=2, sort_keys=True, allow_nan=False)
    path.write_text(txt + "\n", encoding="utf-8")


def main() -> int:
    required = [INPUT_ABLATION, INPUT_SELECTED, INPUT_RULE, INPUT_REPORT, INPUT_MANIFEST]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        print(f"ERROR: missing required inputs: {missing}")
        return 1

    abl = pd.read_parquet(INPUT_ABLATION)
    selected = parse_json_strict(INPUT_SELECTED)
    _ = parse_json_strict(INPUT_RULE)
    winner_id = str(selected["selected_candidate_id"])

    agg = (
        abl.groupby("candidate_id", as_index=False)
        .agg(
            median_eq_ratio_vs_t037=("eq_ratio_vs_t037", "median"),
            median_mdd_delta_vs_t037=("mdd_delta_vs_t037", "median"),
            median_turnover_total=("turnover_total", "median"),
            buy_cadence_days=("buy_cadence_days", "first"),
            buy_turnover_cap_ratio=("buy_turnover_cap_ratio", "first"),
        )
        .sort_values(["median_eq_ratio_vs_t037", "median_mdd_delta_vs_t037"], ascending=[False, False])
        .reset_index(drop=True)
    )
    agg["rank"] = np.arange(1, len(agg) + 1)
    agg["is_winner"] = agg["candidate_id"].astype(str) == winner_id

    heat = abl.pivot_table(
        index="candidate_id",
        columns="subperiod",
        values="eq_ratio_vs_t037",
        aggfunc="median",
    )
    # Keep candidate order from ranking for readability.
    heat = heat.reindex(agg["candidate_id"].tolist())

    fig = make_subplots(
        rows=2,
        cols=1,
        vertical_spacing=0.12,
        subplot_titles=[
            "Ranking de candidatos (eq_ratio_vs_t037 x mdd_delta_vs_t037)",
            "Heatmap por candidato x subperiodo (eq_ratio_vs_t037)",
        ],
    )

    non_winner = agg[~agg["is_winner"]]
    winner = agg[agg["is_winner"]]

    fig.add_trace(
        go.Scatter(
            x=non_winner["median_eq_ratio_vs_t037"],
            y=non_winner["median_mdd_delta_vs_t037"],
            mode="markers+text",
            text=non_winner["candidate_id"],
            textposition="top center",
            marker=dict(
                size=10,
                color=non_winner["median_turnover_total"],
                colorscale="Viridis",
                showscale=True,
                colorbar=dict(title="median_turnover_total"),
            ),
            name="Candidatos",
            customdata=np.stack(
                [
                    non_winner["buy_cadence_days"].astype(float).to_numpy(),
                    np.where(non_winner["buy_turnover_cap_ratio"].isna(), -1.0, non_winner["buy_turnover_cap_ratio"]).astype(float),
                    non_winner["rank"].astype(float).to_numpy(),
                ],
                axis=1,
            ),
            hovertemplate=(
                "candidate=%{text}<br>rank=%{customdata[2]:.0f}<br>"
                "median_eq_ratio_vs_t037=%{x:.4f}<br>"
                "median_mdd_delta_vs_t037=%{y:.4f}<br>"
                "buy_cadence_days=%{customdata[0]:.0f}<br>"
                "buy_turnover_cap_ratio=%{customdata[1]:.4f}<extra></extra>"
            ),
        ),
        row=1,
        col=1,
    )

    if not winner.empty:
        fig.add_trace(
            go.Scatter(
                x=winner["median_eq_ratio_vs_t037"],
                y=winner["median_mdd_delta_vs_t037"],
                mode="markers+text",
                text=winner["candidate_id"],
                textposition="bottom center",
                marker=dict(size=18, color="red", symbol="star"),
                name="Vencedor",
                hovertemplate=(
                    "winner=%{text}<br>median_eq_ratio_vs_t037=%{x:.4f}<br>"
                    "median_mdd_delta_vs_t037=%{y:.4f}<extra></extra>"
                ),
            ),
            row=1,
            col=1,
        )

    fig.add_trace(
        go.Heatmap(
            z=heat.values,
            x=heat.columns.tolist(),
            y=heat.index.tolist(),
            colorscale="RdYlGn",
            zmid=1.0,
            colorbar=dict(title="eq_ratio_vs_t037"),
            hovertemplate="candidate=%{y}<br>subperiod=%{x}<br>eq_ratio_vs_t037=%{z:.4f}<extra></extra>",
        ),
        row=2,
        col=1,
    )

    # winner marker on heatmap axis.
    if winner_id in heat.index:
        fig.add_hline(y=winner_id, line_color="red", line_width=2, row=2, col=1)

    fig.update_layout(
        title="T044-R1 - Ablacao Guardrails (ranking + subperiodos)",
        template="plotly_white",
        height=1150,
        hovermode="closest",
    )
    fig.update_xaxes(title_text="median_eq_ratio_vs_t037", row=1, col=1)
    fig.update_yaxes(title_text="median_mdd_delta_vs_t037", row=1, col=1)
    fig.update_xaxes(title_text="subperiod", row=2, col=1)
    fig.update_yaxes(title_text="candidate_id", row=2, col=1)

    OUTPUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(OUTPUT_HTML, include_plotlyjs="cdn", full_html=True)

    # Update report with plotly link.
    report_txt = INPUT_REPORT.read_text(encoding="utf-8")
    plot_section = (
        "\n## 6) Plotly Ablacao (R1)\n\n"
        f"- `{OUTPUT_HTML}`\n"
        f"- Vencedor destacado: `{winner_id}`\n"
    )
    if "## 6) Plotly Ablacao (R1)" not in report_txt:
        report_txt = report_txt.rstrip() + "\n" + plot_section
        INPUT_REPORT.write_text(report_txt + "\n", encoding="utf-8")

    # Update manifest with new artifacts/hashes.
    manifest = parse_json_strict(INPUT_MANIFEST)
    outputs = manifest.get("outputs_produced", [])
    for p in [str(OUTPUT_HTML), str(SCRIPT_PATH)]:
        if p not in outputs:
            outputs.append(p)
    manifest["outputs_produced"] = outputs
    h = manifest.get("hashes_sha256", {})
    # Manifest must not hash itself (non-stable self-reference).
    h.pop(str(INPUT_MANIFEST), None)
    for p in [OUTPUT_HTML, SCRIPT_PATH, INPUT_REPORT]:
        h[str(p)] = __import__("hashlib").sha256(p.read_bytes()).hexdigest()
    manifest["hashes_sha256"] = h
    write_json_strict(INPUT_MANIFEST, manifest)

    print(f"HEADER: {TASK_ID}")
    print("STEP GATES:")
    print(f"- G1_PLOTLY_HTML_PRESENT: {'PASS' if OUTPUT_HTML.exists() else 'FAIL'}")
    print(f"- G2_REPORT_UPDATED: {'PASS' if '## 6) Plotly Ablacao (R1)' in INPUT_REPORT.read_text(encoding='utf-8') else 'FAIL'}")
    print(f"- G3_MANIFEST_UPDATED: {'PASS' if str(OUTPUT_HTML) in manifest.get('outputs_produced', []) else 'FAIL'}")
    print(f"- G4_MANIFEST_SELF_HASH_EXCLUDED: {'PASS' if str(INPUT_MANIFEST) not in manifest.get('hashes_sha256', {}) else 'FAIL'}")
    print("RETRY LOG:")
    print("- none")
    print("ARTIFACT LINKS:")
    print(f"- {OUTPUT_HTML}")
    print(f"- {INPUT_REPORT}")
    print(f"- {INPUT_MANIFEST}")
    print(f"- {SCRIPT_PATH}")
    ok = (
        OUTPUT_HTML.exists()
        and ("## 6) Plotly Ablacao (R1)" in INPUT_REPORT.read_text(encoding="utf-8"))
        and (str(OUTPUT_HTML) in manifest.get("outputs_produced", []))
        and (str(INPUT_MANIFEST) not in manifest.get("hashes_sha256", {}))
    )
    print(f"OVERALL STATUS: [[ {'PASS' if ok else 'FAIL'} ]]")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
