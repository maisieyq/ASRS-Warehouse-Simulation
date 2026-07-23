from __future__ import annotations

import hashlib
from typing import Callable

import pandas as pd
import streamlit as st

from dashboard_common import ARRIVAL_INTERVALS, VALID_RACKS


def generate_custom_tasks(
    number_of_tasks: int,
    storage_ratio: int,
    arrival_pattern: str,
) -> list[dict]:
    interval = ARRIVAL_INTERVALS[arrival_pattern]
    storage_target = storage_ratio / 100.0

    rack_names = sorted(VALID_RACKS)
    tasks: list[dict] = []
    storage_created = 0

    for index in range(number_of_tasks):
        expected_storage = round(
            (index + 1) * storage_target
        )

        if storage_created < expected_storage:
            task_type = "storage"
            storage_created += 1
        else:
            task_type = "retrieval"

        tasks.append(
            {
                "task_id": f"T{index + 1:03d}",
                "task_type": task_type,
                "arrival_time": round(
                    index * interval,
                    2,
                ),
                "rack_name": rack_names[
                    index % len(rack_names)
                ],
            }
        )

    return tasks


def build_custom_scenario(
    number_of_robots: int,
    number_of_tasks: int,
    storage_ratio: int,
    arrival_pattern: str,
) -> tuple[str, dict]:
    tasks = generate_custom_tasks(
        number_of_tasks=number_of_tasks,
        storage_ratio=storage_ratio,
        arrival_pattern=arrival_pattern,
    )

    scenario = {
        "name": "Custom Configuration",
        "description": (
            "A user-configured scenario generated "
            "automatically from the selected parameters."
        ),
        "number_of_robots": int(number_of_robots),
        "tasks": tasks,
    }

    signature = pd.DataFrame(tasks).to_csv(
        index=False
    )

    digest = hashlib.sha256(
        (
            signature
            + str(number_of_robots)
            + arrival_pattern
        ).encode("utf-8")
    ).hexdigest()[:12]

    return f"custom_{digest}", scenario


def _summary_table(
    number_of_robots: int,
    number_of_tasks: int,
    arrival_pattern: str,
    storage_ratio: int,
    retrieval_ratio: int,
) -> None:
    st.success("NEW CUSTOM SUMMARY FILE IS LOADED")
    summary_html = (
        '<div class="custom-summary-card">'
        '<div class="custom-summary-title">'
        'Custom Configuration'
        '</div>'

        '<div class="summary-row">'
        '<span>Warehouse Size</span>'
        '<strong>9 × 7 (Fixed)</strong>'
        '</div>'

        '<div class="summary-row">'
        '<span>Rack Locations</span>'
        '<strong>12 (Fixed)</strong>'
        '</div>'

        '<div class="summary-divider"></div>'

        '<div class="summary-row">'
        '<span>Robots</span>'
        f'<strong>{number_of_robots}</strong>'
        '</div>'

        '<div class="summary-row">'
        '<span>Tasks</span>'
        f'<strong>{number_of_tasks}</strong>'
        '</div>'

        '<div class="summary-row">'
        '<span>Arrival Pattern</span>'
        f'<strong>{arrival_pattern}</strong>'
        '</div>'

        '<div class="summary-row">'
        '<span>Storage / Retrieval</span>'
        f'<strong>{storage_ratio}% / {retrieval_ratio}%</strong>'
        '</div>'

        '</div>'
    )

    st.html(summary_html)


def render_custom_sidebar(
    clear_callback: Callable[[], None],
) -> dict:
    with st.sidebar:
        st.markdown("### 1. Warehouse layout")

        left, right = st.columns(2)

        with left:
            st.number_input(
                "Rows (Y)",
                min_value=7,
                max_value=7,
                value=7,
                disabled=True,
                help=(
                    "The current backend uses a fixed "
                    "seven-row warehouse."
                ),
            )

        with right:
            st.number_input(
                "Columns (X)",
                min_value=9,
                max_value=9,
                value=9,
                disabled=True,
                help=(
                    "The current backend uses a fixed "
                    "nine-column warehouse."
                ),
            )

        st.selectbox(
            "Rack layout",
            ["4 rack columns × 3 rack rows"],
            disabled=True,
        )

        st.markdown("### 2. Robot configuration")

        number_of_robots = st.number_input(
            "Number of robots",
            min_value=1,
            max_value=10,
            value=3,
            step=1,
        )

        st.number_input(
            "Robot speed (cell/sec)",
            min_value=1.0,
            max_value=1.0,
            value=1.0,
            disabled=True,
            help=(
                "Robot speed is currently fixed "
                "inside simulation.py."
            ),
        )

        st.markdown("### 3. Task configuration")

        number_of_tasks = st.number_input(
            "Total number of tasks",
            min_value=1,
            max_value=200,
            value=50,
            step=1,
        )

        arrival_pattern = st.selectbox(
            "Task arrival pattern",
            list(ARRIVAL_INTERVALS.keys()),
            index=1,
        )

        storage_ratio = st.slider(
            "Storage ratio (%)",
            min_value=0,
            max_value=100,
            value=50,
            step=5,
        )

        retrieval_ratio = 100 - storage_ratio

        scenario_key, selected_scenario = (
            build_custom_scenario(
                number_of_robots=int(
                    number_of_robots
                ),
                number_of_tasks=int(
                    number_of_tasks
                ),
                storage_ratio=int(storage_ratio),
                arrival_pattern=arrival_pattern,
            )
        )

        st.markdown("### Configuration summary")

        _summary_table(
            number_of_robots=int(number_of_robots),
            number_of_tasks=int(number_of_tasks),
            arrival_pattern=arrival_pattern,
            storage_ratio=int(storage_ratio),
            retrieval_ratio=int(retrieval_ratio),
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
            "using the custom configuration."
        )

    return {
        "mode": "custom",
        "scenario_key": scenario_key,
        "scenario": selected_scenario,
        "run_clicked": run_clicked,
    }
