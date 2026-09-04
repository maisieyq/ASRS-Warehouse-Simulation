from __future__ import annotations

from typing import Callable

import pandas as pd
import streamlit as st

from dashboard_common import SCENARIOS


def _sidebar_stat_card(
    label: str,
    value: str | int,
) -> None:
    st.markdown(
        f"""
        <div class="sidebar-stat-card">
            <div class="sidebar-stat-label">{label}</div>
            <div class="sidebar-stat-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_predefined_sidebar(
    clear_callback: Callable[[], None],
) -> dict | None:
    scenario_options = {
        config["name"]: key
        for key, config in SCENARIOS.items()
    }

    with st.sidebar:
        selected_name = st.selectbox(
            "Basic scenario",
            list(scenario_options.keys()),
            index=None,
            placeholder="Choose a scenario...",
            key="basic_scenario_selection",
        )

        if selected_name is None:
            st.caption(
                "Choose a predefined scenario to continue."
            )

            st.button(
                "Clear selection",
                use_container_width=True,
                on_click=clear_callback,
            )

            return None

        scenario_key = scenario_options[selected_name]
        selected_scenario = SCENARIOS[scenario_key]

        tasks_frame = pd.DataFrame(
            selected_scenario["tasks"]
        )

        storage_ratio = int(
            round(
                tasks_frame["task_type"]
                .str.lower()
                .eq("storage")
                .mean()
                * 100
            )
        )

        retrieval_ratio = 100 - storage_ratio

        st.markdown("### Scenario profile")
        st.write(selected_scenario["description"])

        left, right = st.columns(2)

        with left:
            _sidebar_stat_card(
                "Robots",
                selected_scenario["number_of_robots"],
            )

        with right:
            _sidebar_stat_card(
                "Tasks",
                len(selected_scenario["tasks"]),
            )

        left, right = st.columns(2)

        with left:
            _sidebar_stat_card(
                "Storage",
                f"{storage_ratio}%",
            )

        with right:
            _sidebar_stat_card(
                "Retrieval",
                f"{retrieval_ratio}%",
            )

        st.button(
            "Clear selection",
            use_container_width=True,
            on_click=clear_callback,
        )

        run_clicked = st.button(
            "▶ Run strategy comparison",
            use_container_width=True,
            type="primary",
        )

        st.caption(
            "Both FIFO and Deferred Commitment are run "
            "using the selected predefined scenario."
        )

    return {
        "mode": "predefined",
        "scenario_key": scenario_key,
        "scenario": selected_scenario,
        "run_clicked": run_clicked,
    }
