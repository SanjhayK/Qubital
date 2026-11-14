"""Interactive Streamlit dashboard for Qubital."""

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard_logic import (
    build_classical_dashboard_state,
    company_burden_rows,
    encounter_rows,
    frontier_rows,
    selected_action_rows,
)
from scoring import load_scenario


ROOT = Path(__file__).resolve().parent
SCENARIO_PATH = ROOT / "data" / "original.json"

NAVY = "#08111f"
PANEL = "#101c2d"
BLUE = "#4ea1ff"
CYAN = "#43d9c5"
GOLD = "#ffca58"
RED = "#ff6b7a"
MUTED = "#91a4bd"


st.set_page_config(
    page_title="Qubital",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded",
)


st.markdown(
    f"""
    <style>
        .stApp {{
            background:
                radial-gradient(circle at 15% 0%, #102845 0%, transparent 34%),
                radial-gradient(circle at 90% 10%, #12343c 0%, transparent 28%),
                {NAVY};
        }}

        [data-testid="stSidebar"] {{
            background: #091523;
            border-right: 1px solid #21344b;
        }}

        [data-testid="stMetric"] {{
            background: rgba(16, 28, 45, 0.88);
            border: 1px solid #263b55;
            border-radius: 14px;
            padding: 16px;
        }}

        div[data-testid="stVerticalBlockBorderWrapper"] {{
            background: rgba(16, 28, 45, 0.70);
            border-color: #263b55;
            border-radius: 16px;
        }}

        .qubital-kicker {{
            color: {CYAN};
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0.16em;
            text-transform: uppercase;
            margin-bottom: 0.3rem;
        }}

        .qubital-title {{
            color: #f6f9ff;
            font-size: 3.25rem;
            font-weight: 760;
            letter-spacing: -0.055em;
            line-height: 1;
            margin: 0;
        }}

        .qubital-subtitle {{
            color: #b4c3d7;
            font-size: 1.06rem;
            max-width: 850px;
            margin-top: 0.8rem;
            margin-bottom: 1.3rem;
        }}

        .model-notice {{
            background: linear-gradient(
                90deg,
                rgba(67, 217, 197, 0.13),
                rgba(78, 161, 255, 0.08)
            );
            border: 1px solid rgba(67, 217, 197, 0.32);
            border-radius: 12px;
            color: #cfe8e4;
            padding: 0.75rem 1rem;
            margin-bottom: 1.2rem;
        }}

        .agreement {{
            color: #f7fbff;
            font-size: 1.45rem;
            font-weight: 700;
            margin-bottom: 0.15rem;
        }}

        .small-muted {{
            color: {MUTED};
            font-size: 0.88rem;
        }}

        .pending {{
            color: {GOLD};
            font-weight: 700;
        }}

        .status-ready {{
            color: {CYAN};
            font-weight: 700;
        }}

        .status-unavailable {{
            color: {RED};
            font-weight: 700;
        }}

        h1, h2, h3 {{
            color: #f6f9ff;
        }}
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data
def load_original_scenario() -> dict:
    return load_scenario(SCENARIO_PATH)


@st.cache_data(show_spinner=False)
def compute_dashboard_state(
    alpha: float,
    unavailable_actions: tuple[str, ...],
) -> dict:
    return build_classical_dashboard_state(
        load_original_scenario(),
        alpha,
        unavailable_actions,
        annealing_seed=42,
    )


def agreement_name(plan: dict | None) -> str:
    if plan is None:
        return "No feasible agreement"

    if not plan["selected_actions"]:
        return "No actions"

    return " + ".join(plan["selected_actions"])


def make_network_figure(
    scenario: dict,
    plan: dict | None,
) -> go.Figure:
    selected = (
        set(plan["selected_actions"])
        if plan is not None
        else set()
    )
    action_order = scenario["action_order"]
    actions_by_id = {
        action["id"]: action
        for action in scenario["actions"]
    }

    company_colors = {
        scenario["companies"][0]: BLUE,
        scenario["companies"][1]: CYAN,
    }

    positions = {}
    company_x = {
        company: index * 2
        for index, company in enumerate(scenario["companies"])
    }

    for company in scenario["companies"]:
        company_actions = [
            action_id
            for action_id in action_order
            if actions_by_id[action_id]["company"] == company
        ]

        for index, action_id in enumerate(company_actions):
            positions[action_id] = (
                company_x[company],
                len(company_actions) - index - 1,
            )

    figure = go.Figure()

    for encounter in scenario["encounters"]:
        candidates = [
            action["id"]
            for action in scenario["actions"]
            if encounter in action["covers"]
        ]

        if len(candidates) != 2:
            continue

        first, second = candidates
        x0, y0 = positions[first]
        x1, y1 = positions[second]

        figure.add_trace(
            go.Scatter(
                x=[x0, x1],
                y=[y0, y1],
                mode="lines",
                line={
                    "color": "rgba(145, 164, 189, 0.44)",
                    "width": 2,
                },
                hoverinfo="skip",
                showlegend=False,
            )
        )

        figure.add_annotation(
            x=(x0 + x1) / 2,
            y=(y0 + y1) / 2,
            text=encounter,
            showarrow=False,
            font={"color": "#c4d1e1", "size": 11},
            bgcolor="rgba(8, 17, 31, 0.86)",
            bordercolor="#31465f",
            borderpad=3,
        )

    for company in scenario["companies"]:
        company_actions = [
            action_id
            for action_id in action_order
            if actions_by_id[action_id]["company"] == company
        ]

        figure.add_trace(
            go.Scatter(
                x=[positions[action_id][0] for action_id in company_actions],
                y=[positions[action_id][1] for action_id in company_actions],
                mode="markers+text",
                text=company_actions,
                textposition="middle center",
                textfont={
                    "color": NAVY,
                    "size": 12,
                    "family": "Arial Black",
                },
                marker={
                    "size": [
                        58 if action_id in selected else 48
                        for action_id in company_actions
                    ],
                    "color": [
                        (
                            "#4a5667"
                            if not actions_by_id[action_id]["available"]
                            else company_colors[company]
                        )
                        for action_id in company_actions
                    ],
                    "symbol": [
                        (
                            "x"
                            if not actions_by_id[action_id]["available"]
                            else "circle"
                        )
                        for action_id in company_actions
                    ],
                    "line": {
                        "color": [
                            GOLD if action_id in selected else "#d5e2f0"
                            for action_id in company_actions
                        ],
                        "width": 3,
                    },
                },
                customdata=[
                    [
                        actions_by_id[action_id]["satellite"],
                        actions_by_id[action_id]["fuel"],
                        actions_by_id[action_id]["remaining_reserve"],
                        (
                            "Selected"
                            if action_id in selected
                            else "Not selected"
                        ),
                        (
                            "Available"
                            if actions_by_id[action_id]["available"]
                            else "Unavailable"
                        ),
                    ]
                    for action_id in company_actions
                ],
                hovertemplate=(
                    "<b>%{text}</b><br>"
                    "%{customdata[0]}<br>"
                    "Fuel: %{customdata[1]:.2f}<br>"
                    "Reserve: %{customdata[2]:.2f}<br>"
                    "%{customdata[3]} · %{customdata[4]}"
                    "<extra></extra>"
                ),
                name=company,
            )
        )

    for company in scenario["companies"]:
        figure.add_annotation(
            x=company_x[company],
            y=3.0,
            text=f"<b>{company}</b>",
            showarrow=False,
            font={
                "color": company_colors[company],
                "size": 14,
            },
        )

    figure.update_layout(
        height=430,
        margin={"l": 10, "r": 10, "t": 20, "b": 10},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis={
            "visible": False,
            "range": [-0.55, 2.55],
        },
        yaxis={
            "visible": False,
            "range": [-0.6, 3.35],
        },
        legend={
            "orientation": "h",
            "x": 0.5,
            "xanchor": "center",
            "y": -0.03,
            "font": {"color": "#b4c3d7"},
        },
        hoverlabel={
            "bgcolor": PANEL,
            "font_color": "#f6f9ff",
        },
    )

    return figure


def make_burden_figure(rows: list[dict]) -> go.Figure:
    figure = go.Figure()

    figure.add_trace(
        go.Bar(
            x=[row["company"] for row in rows],
            y=[row["reserve_burden_index"] for row in rows],
            marker_color=[BLUE, CYAN],
            text=[
                f'{row["reserve_burden_index"]:.3f}'
                for row in rows
            ],
            textposition="outside",
            hovertemplate=(
                "<b>%{x}</b><br>"
                "Reserve-burden index: %{y:.4f}"
                "<extra></extra>"
            ),
        )
    )

    figure.update_layout(
        height=330,
        margin={"l": 25, "r": 20, "t": 25, "b": 25},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        yaxis={
            "title": "Reserve-burden index",
            "gridcolor": "rgba(145, 164, 189, 0.14)",
            "zeroline": False,
        },
        xaxis={"title": ""},
        font={"color": "#b4c3d7"},
    )

    return figure


def make_frontier_figure(
    rows: list[dict],
    exact: dict | None,
) -> go.Figure:
    figure = go.Figure()

    if rows:
        figure.add_trace(
            go.Scatter(
                x=[row["fuel_total"] for row in rows],
                y=[row["reserve_score"] for row in rows],
                mode="markers+lines",
                marker={
                    "size": 13,
                    "color": BLUE,
                    "line": {
                        "color": "#cfe4ff",
                        "width": 1,
                    },
                },
                line={
                    "color": "rgba(78, 161, 255, 0.38)",
                    "width": 2,
                },
                customdata=[
                    [
                        row["canonical_bits"],
                        row["agreement"],
                        row["objective_score"],
                    ]
                    for row in rows
                ],
                hovertemplate=(
                    "<b>%{customdata[1]}</b><br>"
                    "Bits: %{customdata[0]}<br>"
                    "Fuel: %{x:.2f}<br>"
                    "Reserve score: %{y:.4f}<br>"
                    "Current objective: %{customdata[2]:.4f}"
                    "<extra></extra>"
                ),
                name="Efficient agreements",
            )
        )

    if exact is not None:
        figure.add_trace(
            go.Scatter(
                x=[exact["fuel_total"]],
                y=[exact["reserve_score"]],
                mode="markers",
                marker={
                    "size": 21,
                    "color": GOLD,
                    "symbol": "star",
                    "line": {
                        "color": "#fff4cb",
                        "width": 1,
                    },
                },
                hovertemplate=(
                    "<b>Current recommendation</b><br>"
                    f"{agreement_name(exact)}<br>"
                    f'Bits: {exact["canonical_bits"]}'
                    "<extra></extra>"
                ),
                name="Current recommendation",
            )
        )

    figure.update_layout(
        height=440,
        margin={"l": 30, "r": 20, "t": 25, "b": 30},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis={
            "title": "Total maneuver fuel",
            "gridcolor": "rgba(145, 164, 189, 0.14)",
        },
        yaxis={
            "title": "Concentrated reserve burden",
            "gridcolor": "rgba(145, 164, 189, 0.14)",
        },
        font={"color": "#b4c3d7"},
        legend={
            "orientation": "h",
            "y": 1.08,
        },
    )

    return figure


scenario = load_original_scenario()
actions_by_id = {
    action["id"]: action
    for action in scenario["actions"]
}


with st.sidebar:
    st.markdown("## Decision controls")

    alpha = st.slider(
        "Reserve priority (α)",
        min_value=0.0,
        max_value=1.0,
        value=float(scenario["objective"]["default_alpha"]),
        step=0.05,
        help=(
            "At 0, Qubital prioritizes minimum total fuel. "
            "At 1, it prioritizes spreading normalized reserve burden."
        ),
    )

    if alpha == 0:
        st.caption("Fuel-only policy")
    elif alpha == 1:
        st.caption("Reserve-burden-only policy")
    else:
        st.caption(
            f"{(1 - alpha):.0%} fuel · {alpha:.0%} reserve priority"
        )

    unavailable = st.multiselect(
        "Unavailable maneuver actions",
        options=scenario["action_order"],
        default=[],
        format_func=lambda action_id: (
            f"{action_id} · "
            f'{actions_by_id[action_id]["satellite"]} · '
            f'{actions_by_id[action_id]["company"]}'
        ),
        help=(
            "Unavailable actions remain coverage candidates in the model, "
            "but selecting them receives a violation penalty."
        ),
    )

    qaoa_depth = st.selectbox(
        "Saved QAOA depth to display",
        options=[1, 2],
        index=0,
        format_func=lambda depth: f"p = {depth}",
        help=(
            "This only selects saved experiment results. "
            "It never submits a hardware job."
        ),
    )

    st.divider()
    st.markdown("### Current model")
    st.caption("6 candidate actions")
    st.caption("4 modeled encounters")
    st.caption("2 independent operators")
    st.caption("Synthetic, prevalidated maneuver packages")

    st.divider()
    st.caption(
        "Changing controls recomputes the classical model locally. "
        "It does not contact IBM Quantum or consume hardware allocation."
    )


state = compute_dashboard_state(
    alpha,
    tuple(unavailable),
)
adjusted_scenario = state["scenario"]
exact = state["exact"]


st.markdown(
    """
    <div class="qubital-kicker">Reserve-aware coordination</div>
    <div class="qubital-title">Qubital</div>
    <div class="qubital-subtitle">
        Explore how independent satellite operators can cover every modeled
        encounter while trading off total maneuver fuel against concentrated
        depletion of remaining maneuver reserves.
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="model-notice">
        <b>Decision-support prototype:</b> actions are synthetic,
        prevalidated maneuver packages. “Valid” means valid under the modeled
        rules—it is not a claim of physical orbital safety.
    </div>
    """,
    unsafe_allow_html=True,
)


if state["feasible"]:
    st.markdown(
        f"""
        <div class="agreement">{agreement_name(exact)}</div>
        <div class="small-muted">
            Recommended modeled agreement · canonical bits
            <code>{exact["canonical_bits"]}</code>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    st.error(
        "No feasible agreement exists under the current availability "
        "settings. At least one modeled encounter cannot be covered by an "
        "available action."
    )


metric_columns = st.columns(4)

metric_columns[0].metric(
    "Total maneuver fuel",
    f'{exact["fuel_total"]:.2f}' if exact else "—",
)
metric_columns[1].metric(
    "Reserve score",
    f'{exact["reserve_score"]:.4f}' if exact else "—",
)
metric_columns[2].metric(
    "Valid plans",
    f'{state["valid_plan_count"]} / {state["total_plan_count"]}',
)
metric_columns[3].metric(
    "Current objective",
    f'{exact["objective_score"]:.4f}' if exact else "—",
)


overview_tab, frontier_tab, quantum_tab, model_tab = st.tabs(
    [
        "Agreement",
        "Trade-off frontier",
        "Quantum evidence",
        "Model & limits",
    ]
)


with overview_tab:
    left, right = st.columns([1.35, 1])

    with left:
        with st.container(border=True):
            st.subheader("Encounter network")
            st.caption(
                "Gold outlines mark selected actions. Gray × markers are "
                "unavailable actions."
            )
            st.plotly_chart(
                make_network_figure(adjusted_scenario, exact),
                width="stretch",
                config={"displayModeBar": False},
            )

    with right:
        with st.container(border=True):
            st.subheader("Operator reserve burden")
            burden_data = company_burden_rows(
                adjusted_scenario,
                exact,
            )
            st.plotly_chart(
                make_burden_figure(burden_data),
                width="stretch",
                config={"displayModeBar": False},
            )

            burden_frame = pd.DataFrame(burden_data)
            st.dataframe(
                burden_frame,
                hide_index=True,
                width="stretch",
                column_config={
                    "company": "Operator",
                    "selected_fuel": st.column_config.NumberColumn(
                        "Selected fuel",
                        format="%.2f",
                    ),
                    "reserve_burden_index": (
                        st.column_config.NumberColumn(
                            "Reserve-burden index",
                            format="%.4f",
                        )
                    ),
                },
            )

    st.subheader("Selected maneuver packages")
    action_data = selected_action_rows(
        adjusted_scenario,
        exact,
    )

    if action_data:
        action_frame = pd.DataFrame(action_data)
        action_frame["reserve used by action"] = (
            100 * action_frame["action_reserve_fraction"]
        )

        st.dataframe(
            action_frame[
                [
                    "action",
                    "satellite",
                    "company",
                    "fuel",
                    "remaining_reserve",
                    "reserve used by action",
                    "covers",
                ]
            ],
            hide_index=True,
            width="stretch",
            column_config={
                "action": "Action",
                "satellite": "Satellite",
                "company": "Operator",
                "fuel": st.column_config.NumberColumn(
                    "Fuel",
                    format="%.2f",
                ),
                "remaining_reserve": st.column_config.NumberColumn(
                    "Remaining reserve",
                    format="%.2f",
                ),
                "reserve used by action": (
                    st.column_config.NumberColumn(
                        "Action reserve used",
                        format="%.1f%%",
                    )
                ),
                "covers": "Modeled encounters covered",
            },
        )
    else:
        st.info("No valid maneuver package selection is available.")

    st.subheader("Modeled encounter coverage")
    coverage_frame = pd.DataFrame(
        encounter_rows(adjusted_scenario, exact)
    )
    st.dataframe(
        coverage_frame,
        hide_index=True,
        width="stretch",
        column_config={
            "encounter": "Encounter",
            "candidate_actions": "Candidate actions",
            "selected_actions": "Selected coverage",
            "covered": st.column_config.CheckboxColumn("Covered"),
        },
    )

    st.subheader("Classical method comparison")
    method_rows = []

    for method_name, plan in [
        ("Exact enumeration", state["exact"]),
        ("Greedy baseline", state["greedy"]),
        ("Simulated annealing", state["simulated_annealing"]),
    ]:
        method_rows.append(
            {
                "method": method_name,
                "agreement": agreement_name(plan),
                "canonical_bits": (
                    plan["canonical_bits"]
                    if plan is not None
                    else "—"
                ),
                "valid": (
                    plan["valid"]
                    if plan is not None
                    else False
                ),
                "fuel": (
                    plan["fuel_total"]
                    if plan is not None
                    else None
                ),
                "reserve_score": (
                    plan["reserve_score"]
                    if plan is not None
                    else None
                ),
                "objective": (
                    plan["objective_score"]
                    if plan is not None
                    else None
                ),
            }
        )

    st.dataframe(
        pd.DataFrame(method_rows),
        hide_index=True,
        width="stretch",
        column_config={
            "method": "Method",
            "agreement": "Agreement",
            "canonical_bits": "Bits",
            "valid": st.column_config.CheckboxColumn("Valid"),
            "fuel": st.column_config.NumberColumn(
                "Fuel",
                format="%.2f",
            ),
            "reserve_score": st.column_config.NumberColumn(
                "Reserve score",
                format="%.4f",
            ),
            "objective": st.column_config.NumberColumn(
                "Objective",
                format="%.4f",
            ),
        },
    )


with frontier_tab:
    st.subheader("Price of preserving maneuver reserves")
    st.caption(
        "Every point is a valid agreement that is not dominated on both "
        "total fuel and concentrated reserve burden. The gold star is the "
        "recommendation at the current α."
    )

    frontier_data = frontier_rows(state["frontier"])

    if frontier_data:
        st.plotly_chart(
            make_frontier_figure(frontier_data, exact),
            width="stretch",
            config={"displayModeBar": False},
        )

        st.dataframe(
            pd.DataFrame(frontier_data),
            hide_index=True,
            width="stretch",
            column_config={
                "canonical_bits": "Bits",
                "agreement": "Agreement",
                "fuel_total": st.column_config.NumberColumn(
                    "Fuel",
                    format="%.2f",
                ),
                "reserve_score": st.column_config.NumberColumn(
                    "Reserve score",
                    format="%.4f",
                ),
                "objective_score": st.column_config.NumberColumn(
                    "Current objective",
                    format="%.4f",
                ),
            },
        )
    else:
        st.warning(
            "There is no valid Pareto frontier because the current "
            "availability settings make the modeled problem infeasible."
        )


with quantum_tab:
    st.subheader("Classical and quantum execution comparison")
    st.caption(
        "Experiment results are matched by scenario, unavailable actions, "
        f"α = {alpha:.2f}, and QAOA depth p = {qaoa_depth}."
    )

    exact_column, ideal_column, noisy_column, hardware_column = st.columns(4)

    with exact_column:
        with st.container(border=True):
            st.markdown("### Exact classical")
            if exact:
                st.markdown(
                    '<div class="status-ready">Available</div>',
                    unsafe_allow_html=True,
                )
                st.metric(
                    "Optimal objective",
                    f'{exact["objective_score"]:.4f}',
                )
                st.caption(
                    f'{exact["canonical_bits"]} · '
                    f"{agreement_name(exact)}"
                )
            else:
                st.markdown(
                    '<div class="status-unavailable">'
                    "No feasible agreement"
                    "</div>",
                    unsafe_allow_html=True,
                )

    with ideal_column:
        with st.container(border=True):
            st.markdown("### Ideal QAOA")
            st.markdown(
                '<div class="pending">Contract integration pending</div>',
                unsafe_allow_html=True,
            )
            st.caption(
                "A verified p=1 artifact exists, but this dashboard will "
                "only load it through the shared EXPERIMENTS.md contract."
            )

    with noisy_column:
        with st.container(border=True):
            st.markdown("### Noisy simulation")
            st.markdown(
                '<div class="pending">Results pending</div>',
                unsafe_allow_html=True,
            )
            st.caption(
                "Aer noise-model results will appear here when a matching "
                "saved experiment is available."
            )

    with hardware_column:
        with st.container(border=True):
            st.markdown("### IBM hardware")
            st.markdown(
                '<div class="pending">Hardware results pending</div>',
                unsafe_allow_html=True,
            )
            st.caption(
                "Only genuine IBM hardware measurements will populate this "
                "section. Dry runs remain labeled as mock data."
            )

    st.info(
        "Dashboard controls only select saved results. They never submit "
        "quantum jobs, access credentials, or consume IBM allocation."
    )

    st.markdown("#### Required hardware provenance")
    st.caption(
        "When available: backend, IBM job ID, run timestamp, shots, "
        "QAOA depth, circuit depth, and a clear statement that parameters "
        "were optimized locally before fixed-angle hardware execution."
    )


with model_tab:
    st.subheader("What Qubital optimizes")

    st.latex(
        r"""
        H(x) =
        (1-\alpha)\frac{F(x)}{9}
        +
        \alpha\frac{\sum_c B_c(x)^2}{0.8254830119}
        +
        2U(x)
        +
        2V(x)
        """
    )

    st.markdown(
        """
        - **F(x):** total fuel used by selected maneuver packages.
        - **B₍c₎(x):** the sum of selected fuel-to-remaining-reserve ratios
          for operator *c*.
        - **U(x):** number of uncovered modeled encounters.
        - **V(x):** number of unavailable actions selected.
        - **α:** policy priority between minimum fuel and preserving
          distributed maneuver reserves.
        """
    )

    st.subheader("Interpretation")
    st.markdown(
        """
        Each binary variable selects one predefined maneuver package.
        Qubital chooses a combination that covers every modeled encounter
        while exploring how much additional fuel may be justified to avoid
        concentrating reserve depletion on one operator.
        """
    )

    st.subheader("Honest limitations")
    st.markdown(
        """
        - The scenario and maneuver effects are synthetic.
        - Actions are assumed to be prevalidated and mutually compatible.
        - The optimizer does not propagate orbits or prove physical safety.
        - Reserve burden is a decision index, not a literal fleet-lifetime
          percentage.
        - This six-action instance is classically trivial and does not
          demonstrate quantum speedup.
        - Producing multiple candidate agreements is not uniquely quantum.
        - Hardware and noise results must be reported exactly as observed,
          including cases where deeper circuits perform worse.
        """
    )