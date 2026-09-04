from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import pandas as pd
import streamlit as st

PROJECT_FOLDER = Path(__file__).resolve().parent
SCENARIO_FOLDER = PROJECT_FOLDER / "ScenarioBasicConfig"

if str(SCENARIO_FOLDER) not in sys.path:
    sys.path.insert(
        0,
        str(SCENARIO_FOLDER),
    )

from ScenarioBasicConfig.scenarios import SCENARIOS
from ScenarioBasicConfig.simulation import run_simulation
from ScenarioBasicConfig import animation as animation_engine
from ScenarioBasicConfig import graph as graph_engine


IS_PACKAGED = getattr(sys, "frozen", False)
if IS_PACKAGED:
    # ==========================================
    # Packaged EXE version
    # ==========================================

    LOCAL_APP_DATA = Path(
        os.getenv(
            "LOCALAPPDATA",
            str(Path.home()),
        )
    )

    USER_DATA_FOLDER = (
        LOCAL_APP_DATA
        / "ASRS_Warehouse_Simulation"
    )

    OUTPUTS_FOLDER = (
        USER_DATA_FOLDER
        / "outputs"
    )

    ANIMATION_CACHE_FOLDER = (
        USER_DATA_FOLDER
        / "animation_cache"
    )

else:
    # ==========================================
    # Development version
    # streamlit run app.py
    # ==========================================

    OUTPUTS_FOLDER = (
        SCENARIO_FOLDER
        / "outputs"
    )

    ANIMATION_CACHE_FOLDER = (
        PROJECT_FOLDER
        / ".dashboard_animation_cache"
    )


# Make sure folders exist
OUTPUTS_FOLDER.mkdir(
    parents=True,
    exist_ok=True,
)

ANIMATION_CACHE_FOLDER.mkdir(
    parents=True,
    exist_ok=True,
)
PREDEFINED_VALID_RACKS = {
    f"{letter}{number}"
    for letter in "ABCD"
    for number in range(1, 4)
}

ARRIVAL_INTERVALS = {
    "Low demand": 4.0,
    "Normal demand": 2.0,
    "High demand": 1.0,
}


def clear_dashboard_selection() -> None:
    st.session_state["scenario_source"] = None
    st.session_state["basic_scenario_selection"] = None
    st.session_state["active_result_key"] = None

    result_keys = [
        key
        for key in list(st.session_state.keys())
        if str(key).startswith("results_")
    ]

    for key in result_keys:
        del st.session_state[key]

    animation_keys = [
        key
        for key in list(st.session_state.keys())
        if str(key).startswith("animation_path_")
    ]

    for key in animation_keys:
        del st.session_state[key]


def render_hero() -> None:
    st.html(
        """
        <div class="hero">
            <div class="hero-badge">
                AS/RS Warehouse Simulation
            </div>

            <div class="hero-title">
                Warehouse Strategy Comparison Dashboard
            </div>

            <div class="hero-subtitle">
                Compare FIFO and Deferred Commitment,
                select a predefined scenario or build a custom configuration,
                inspect robot and task performance, and export the complete
                simulation results.
            </div>
        </div>
        """
    )

def render_landing_message(
    title: str,
    description: str,
) -> None:
    st.markdown(
        f"""
        <div class="scenario-card">
            <b>{title}</b><br>
            {description}
        </div>
        """,
        unsafe_allow_html=True,
    )


def task_frame(
    result: dict,
    strategy_label: str,
) -> pd.DataFrame:
    rows: list[dict] = []

    for task in result["tasks"]:
        rows.append(
            {
                "Strategy": strategy_label,
                "Task ID": task.task_id,
                "Task Type": task.task_type.title(),
                "Rack": task.rack_name,
                "Arrival Time": task.arrival_time,
                "Start Time": task.start_time,
                "Completion Time": task.completion_time,
                "Waiting Time": task.waiting_time(),
                "Rack Access Wait": float(
                    getattr(
                        task,
                        "rack_access_wait_time",
                        0.0,
                    )
                ),
                "Cycle Time": task.cycle_time(),
                "Travel Distance": task.travel_distance,
                "Robot ID": f"R{task.robot_id}",
            }
        )

    return pd.DataFrame(rows)


def robot_frame(
    result: dict,
    strategy_label: str,
) -> pd.DataFrame:
    makespan = result["summary"]["makespan"]
    rows: list[dict] = []

    for robot in result["robots"]:
        utilization = (
            robot.busy_time / makespan * 100
            if makespan
            else 0
        )

        rows.append(
            {
                "Strategy": strategy_label,
                "Robot": f"R{robot.robot_id}",
                "Completed Tasks": (
                    robot.completed_tasks
                ),
                "Total Distance": robot.total_distance,
                "Busy Time": robot.busy_time,
                "Utilization (%)": utilization,
            }
        )

    return pd.DataFrame(rows)


def queue_frame(
    result: dict,
    strategy_label: str,
) -> pd.DataFrame:
    frame = pd.DataFrame(
        result["queue_history"]
    )

    frame["Strategy"] = strategy_label
    return frame


def comparison_frame(
    fifo_summary: dict,
    deferred_summary: dict,
) -> pd.DataFrame:
    metrics = [
        (
            "Average Waiting Time",
            "average_waiting_time",
        ),
        (
            "Average Rack Access Waiting Time",
            "average_rack_access_waiting_time",
        ),
        (
            "Average Completion Time",
            "average_completion_time",
        ),
        (
            "Average Travel Distance",
            "average_travel_distance",
        ),
        ("Makespan", "makespan"),
        (
            "Average Queue Length",
            "average_queue_length",
        ),
        (
            "Maximum Queue Length",
            "maximum_queue_length",
        ),
        ("Total Distance", "total_distance"),
    ]

    records: list[dict] = []

    for label, key in metrics:
        # Keep compatibility with results generated before rack-access
        # waiting was introduced.
        if (
            key not in fifo_summary
            or key not in deferred_summary
        ):
            continue

        fifo_value = float(
            fifo_summary[key]
        )

        deferred_value = float(
            deferred_summary[key]
        )

        change = (
            (
                deferred_value - fifo_value
            )
            / fifo_value
            * 100
            if fifo_value
            else 0
        )

        if fifo_value < deferred_value:
            better_strategy = "FIFO"
        elif deferred_value < fifo_value:
            better_strategy = (
                "Deferred Commitment"
            )
        else:
            better_strategy = "Tie"

        records.append(
            {
                "Metric": label,
                "FIFO": fifo_value,
                "Deferred Commitment": (
                    deferred_value
                ),
                "Deferred vs FIFO (%)": change,
                "Better Strategy": (
                    better_strategy
                ),
            }
        )

    return pd.DataFrame(records)


def get_or_build_animation(
    scenario_key: str,
    strategy: str,
    result: dict,
    quality: str = "standard",
) -> Path:
    original_output_folder = (
        animation_engine.OUTPUT_FOLDER
    )

    animation_engine.OUTPUT_FOLDER = str(
        ANIMATION_CACHE_FOLDER
    )

    try:
        animation_path = (
            animation_engine.create_animation(
                strategy=strategy.upper(),
                scenario_name=scenario_key,
                result=result,
                quality=quality,
            )
        )
    finally:
        animation_engine.OUTPUT_FOLDER = (
            original_output_folder
        )

    return Path(animation_path)


def _display_animation(path: Path) -> None:
    if not path.exists():
        st.error(
            "The animation file could not be found."
        )
        return

    if path.suffix.lower() == ".mp4":
        st.video(str(path))
    else:
        st.image(
            str(path),
            use_container_width=True,
        )


def _run_results(
    mode: str,
    scenario_key: str,
    scenario: dict,
) -> dict:
    if mode == "custom":
        return {
            "fifo": run_simulation(
                "FIFO",
                scenario_config=scenario,
            ),
            "deferred": run_simulation(
                "DEFERRED",
                scenario_config=scenario,
            ),
        }

    return {
        "fifo": run_simulation(
            "FIFO",
            scenario_name=scenario_key,
        ),
        "deferred": run_simulation(
            "DEFERRED",
            scenario_name=scenario_key,
        ),
    }


def _render_scenario_card(
    scenario: dict,
) -> None:
    st.markdown(
        f"""
        <div class="scenario-card">
            <b>{scenario['name']}</b><br>
            {scenario['description']}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_metrics(
    fifo_summary: dict,
    deferred_summary: dict,
) -> None:
    st.markdown(
        '<div class="section-title">'
        'Performance snapshot — Deferred Commitment vs FIFO'
        '</div>',
        unsafe_allow_html=True,
    )

    st.caption(
        "The large value on each card is the Deferred Commitment result. "
        "The delta is the actual percentage difference from FIFO: "
        "a negative delta means Deferred Commitment is lower (better for "
        "these metrics), while a positive delta means it is higher."
    )

    # Six cards in one row become unreadable whenever the configuration
    # sidebar is open. A responsive 3 x 2 layout keeps the full values and
    # delta text visible without asking the user to collapse the sidebar.
    first_row = st.columns(3)
    second_row = st.columns(3)

    headline_metrics = [
        (
            "Average waiting time",
            "average_waiting_time",
            "float",
        ),
        (
            "Average completion time",
            "average_completion_time",
            "float",
        ),
        (
            "Average travel distance",
            "average_travel_distance",
            "float",
        ),
        (
            "Makespan",
            "makespan",
            "float",
        ),
        (
            "Average queue length",
            "average_queue_length",
            "float",
        ),
        (
            "Maximum queue length",
            "maximum_queue_length",
            "integer",
        ),
    ]

    metric_columns = (
        first_row
        + second_row
    )

    for column, (
        label,
        key,
        value_format,
    ) in zip(
        metric_columns,
        headline_metrics,
    ):
        fifo_value = float(
            fifo_summary[key]
        )

        deferred_value = float(
            deferred_summary[key]
        )

        difference_percent = (
            (
                deferred_value - fifo_value
            )
            / fifo_value
            * 100
            if fifo_value
            else 0
        )

        if value_format == "integer":
            value_text = str(
                int(round(deferred_value))
            )
        else:
            value_text = (
                f"{deferred_value:.2f}"
            )

        column.metric(
            label,
            value_text,
            f"{difference_percent:+.1f}% vs FIFO",
            # Lower values are better for all six headline metrics.
            # Inverse makes a negative difference (Deferred is lower)
            # appear as the favourable/green direction.
            delta_color="inverse",
            help=(
                "Main value: Deferred Commitment. "
                "Delta = (Deferred - FIFO) / FIFO × 100%. "
                "Negative means Deferred Commitment is lower; "
                "positive means it is higher."
            ),
        )

    # Rack-access waiting is a useful secondary diagnostic after the
    # exclusive rack reservation rule was introduced, but keeping it
    # outside the six headline cards avoids crowding the snapshot.
    if (
        "average_rack_access_waiting_time"
        in deferred_summary
    ):
        st.caption(
            "Average rack-access waiting time "
            "(Deferred Commitment): "
            f"{float(deferred_summary['average_rack_access_waiting_time']):.2f}. "
            "See the comparison table for FIFO and Deferred values."
        )


def _render_animations(
    scenario_key: str,
    fifo_result: dict,
    deferred_result: dict,
) -> None:
    st.markdown(
        '<div class="section-title">'
        '2D robot animation'
        '</div>',
        unsafe_allow_html=True,
    )

    st.caption(
        "Animations are generated only when requested. "
        "This avoids blocking the analysis while video "
        "files are being rendered."
    )

    quality = st.selectbox(
        "Animation quality",
        ["fast", "standard", "detailed"],
        index=1,
        key=f"animation_quality_{scenario_key}",
    )

    left, right = st.columns(2)

    specs = [
        (left, "FIFO", fifo_result, "FIFO"),
        (
            right,
            "DEFERRED",
            deferred_result,
            "Deferred Commitment",
        ),
    ]

    for column, strategy, result, label in specs:
        state_key = (
            f"animation_path_{scenario_key}_"
            f"{strategy.lower()}_{quality}"
        )

        with column:
            st.markdown(f"#### {label}")

            if st.button(
                f"Generate {label} animation",
                key=(
                    f"generate_{scenario_key}_"
                    f"{strategy.lower()}_{quality}"
                ),
                use_container_width=True,
            ):
                with st.spinner(
                    f"Generating {label} animation..."
                ):
                    path = get_or_build_animation(
                        scenario_key=scenario_key,
                        strategy=strategy,
                        result=result,
                        quality=quality,
                    )
                    st.session_state[
                        state_key
                    ] = str(path)

            existing_path = (
                st.session_state.get(state_key)
            )

            if existing_path:
                _display_animation(
                    Path(existing_path)
                )
            else:
                st.info(
                    "Generate this animation when needed."
                )


def _graph_result_hash(
    fifo_result: dict,
    deferred_result: dict,
) -> str:
    """
    Build a stable hash from the data that affects graph output.

    This prevents an old PNG from being reused after simulation logic,
    rack-access waiting, robot allocation, or graph rendering rules change.
    """
    def serialise_result(
        result: dict,
    ) -> dict:
        summary = {
            key: (
                float(value)
                if isinstance(
                    value,
                    (int, float),
                )
                else str(value)
            )
            for key, value
            in result["summary"].items()
        }

        tasks = [
            {
                "task_id": str(task.task_id),
                "waiting": float(
                    task.waiting_time()
                    or 0.0
                ),
                "cycle": float(
                    task.cycle_time()
                    or 0.0
                ),
                "distance": float(
                    task.travel_distance
                ),
                "rack_wait": float(
                    getattr(
                        task,
                        "rack_access_wait_time",
                        0.0,
                    )
                ),
            }
            for task in sorted(
                result["tasks"],
                key=lambda item: item.task_id,
            )
        ]

        robots = [
            {
                "robot_id": int(
                    robot.robot_id
                ),
                "completed": int(
                    robot.completed_tasks
                ),
                "distance": float(
                    robot.total_distance
                ),
                "busy": float(
                    robot.busy_time
                ),
            }
            for robot in sorted(
                result["robots"],
                key=lambda item: item.robot_id,
            )
        ]

        return {
            "summary": summary,
            "tasks": tasks,
            "robots": robots,
        }

    payload = {
        "graph_version": getattr(
            graph_engine,
            "GRAPH_RENDER_VERSION",
            "v1",
        ),
        "fifo": serialise_result(
            fifo_result
        ),
        "deferred": serialise_result(
            deferred_result
        ),
    }

    signature = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        signature.encode("utf-8")
    ).hexdigest()[:12]


def generate_graph_files(
    scenario_key: str,
    fifo_result: dict,
    deferred_result: dict,
) -> Path:
    """
    Generate/cache graphs that do not depend on the task-range selector.
    """
    result_hash = _graph_result_hash(
        fifo_result,
        deferred_result,
    )

    scenario_folder = (
        OUTPUTS_FOLDER
        / scenario_key
        / result_hash
        / "base"
    )

    scenario_folder.mkdir(
        parents=True,
        exist_ok=True,
    )

    expected_files = [
        "core_metrics_comparison.png",
        "queue_length_over_time.png",
        "robot_total_distance.png",
        "robot_utilization.png",
        "overall_strategy_performance.png",
    ]

    if all(
        (scenario_folder / filename).exists()
        and (scenario_folder / filename).stat().st_size > 0
        for filename in expected_files
    ):
        return scenario_folder

    folder_path = str(
        scenario_folder
    )

    graph_engine.create_main_metrics_graph(
        fifo_result,
        deferred_result,
        folder_path,
    )

    graph_engine.create_queue_length_graph(
        fifo_result,
        deferred_result,
        folder_path,
    )

    graph_engine.create_robot_distance_graph(
        fifo_result,
        deferred_result,
        folder_path,
    )

    graph_engine.create_robot_utilization_graph(
        fifo_result,
        deferred_result,
        folder_path,
    )

    graph_engine.create_total_performance_graph(
        fifo_result,
        deferred_result,
        folder_path,
    )

    return scenario_folder


def generate_task_graph_files(
    scenario_key: str,
    fifo_result: dict,
    deferred_result: dict,
    selected_task_ids: list[str] | None,
    task_view_label: str,
    difference_overview: bool,
) -> Path:
    """
    Generate/cache only the three task-level graphs for the selected view.

    Switching from "All tasks" to "Tasks 1-25" therefore does not
    regenerate core metrics, queue, or robot graphs.
    """
    result_hash = _graph_result_hash(
        fifo_result,
        deferred_result,
    )

    view_payload = {
        "graph_version": getattr(
            graph_engine,
            "GRAPH_RENDER_VERSION",
            "v1",
        ),
        "task_view_label": task_view_label,
        "difference_overview": (
            difference_overview
        ),
        "selected_task_ids": (
            selected_task_ids
            if selected_task_ids is not None
            else "ALL"
        ),
    }

    view_signature = json.dumps(
        view_payload,
        sort_keys=True,
        separators=(",", ":"),
    )

    view_hash = hashlib.sha256(
        view_signature.encode("utf-8")
    ).hexdigest()[:10]

    task_folder = (
        OUTPUTS_FOLDER
        / scenario_key
        / result_hash
        / "task_views"
        / view_hash
    )

    task_folder.mkdir(
        parents=True,
        exist_ok=True,
    )

    expected_files = [
        "task_waiting_time.png",
        "task_completion_time.png",
        "task_travel_distance.png",
    ]

    if all(
        (task_folder / filename).exists()
        and (task_folder / filename).stat().st_size > 0
        for filename in expected_files
    ):
        return task_folder

    folder_path = str(
        task_folder
    )

    graph_engine.create_waiting_time_graph(
        fifo_result,
        deferred_result,
        folder_path,
        selected_task_ids=(
            selected_task_ids
        ),
        difference_overview=(
            difference_overview
        ),
        view_label=task_view_label,
    )

    graph_engine.create_completion_time_graph(
        fifo_result,
        deferred_result,
        folder_path,
        selected_task_ids=(
            selected_task_ids
        ),
        difference_overview=(
            difference_overview
        ),
        view_label=task_view_label,
    )

    graph_engine.create_travel_distance_graph(
        fifo_result,
        deferred_result,
        folder_path,
        selected_task_ids=(
            selected_task_ids
        ),
        difference_overview=(
            difference_overview
        ),
        view_label=task_view_label,
    )

    return task_folder


def _render_charts(
    scenario_key: str,
    fifo_result: dict,
    deferred_result: dict,
) -> None:
    st.markdown(
        '<div class="section-title">'
        'Performance Analysis'
        '</div>',
        unsafe_allow_html=True,
    )

    unique_task_ids = sorted(
        task.task_id
        for task in fifo_result["tasks"]
    )

    task_count = len(
        unique_task_ids
    )

    # -----------------------------------------------------
    # Task graph selector
    # -----------------------------------------------------
    task_view_options = [
        "All tasks"
    ]

    task_view_mapping: dict[
        str,
        list[str] | None,
    ] = {
        "All tasks": None
    }

    range_size = 25

    if task_count > range_size:
        for start_index in range(
            0,
            task_count,
            range_size,
        ):
            end_index = min(
                start_index + range_size,
                task_count,
            )

            selected_ids = (
                unique_task_ids[
                    start_index:end_index
                ]
            )

            range_label = (
                f"Tasks "
                f"{start_index + 1}-"
                f"{end_index}"
            )

            task_view_options.append(
                range_label
            )

            task_view_mapping[
                range_label
            ] = selected_ids

    if task_count > range_size:
        selected_task_view = st.selectbox(
            "Task graph view",
            task_view_options,
            index=0,
            key=(
                "task_graph_view_"
                f"{scenario_key}"
            ),
            help=(
                "Use All tasks for an overall "
                "comparison. Select a 25-task "
                "range for detailed FIFO and "
                "Deferred values."
            ),
        )
    else:
        selected_task_view = (
            "All tasks"
        )

    selected_task_ids = (
        task_view_mapping[
            selected_task_view
        ]
    )

    difference_overview = (
        selected_task_view
        == "All tasks"
        and task_count > 50
    )

    if difference_overview:
        st.info(
            "How to read the All tasks view: "
            "each point is Deferred Commitment minus FIFO. "
            "A negative value means Deferred Commitment "
            "achieved the lower metric value; a positive "
            "value means FIFO achieved the lower value; "
            "zero means both strategies were equal. "
            "The graph also shows how many tasks favour "
            "each strategy. Choose a 25-task range for "
            "side-by-side FIFO and Deferred values."
        )
    elif (
        selected_task_ids is not None
    ):
        st.caption(
            f"Detailed task graph view: "
            f"{selected_task_view}. "
            "FIFO and Deferred Commitment are "
            "shown side-by-side."
        )
    elif task_count > 25:
        st.caption(
            f"{task_count} tasks are shown. "
            "Numeric bar labels are hidden when "
            "necessary to preserve readability."
        )

    # -----------------------------------------------------
    # Generate cached graph groups
    # -----------------------------------------------------
    with st.spinner(
        "Preparing performance graphs..."
    ):
        base_graph_folder = (
            generate_graph_files(
                scenario_key,
                fifo_result,
                deferred_result,
            )
        )

        task_graph_folder = (
            generate_task_graph_files(
                scenario_key=(
                    scenario_key
                ),
                fifo_result=(
                    fifo_result
                ),
                deferred_result=(
                    deferred_result
                ),
                selected_task_ids=(
                    selected_task_ids
                ),
                task_view_label=(
                    selected_task_view
                ),
                difference_overview=(
                    difference_overview
                ),
            )
        )

    def render_graph(
        title: str,
        filename: str,
        folder: Path,
    ) -> None:
        st.markdown(
            f"###### {title}"
        )

        graph_path = (
            folder
            / filename
        )

        if graph_path.exists():
            st.image(
                str(graph_path),
                use_container_width=True,
            )
        else:
            st.warning(
                f"{filename} was not generated."
            )

    # -----------------------------------------------------
    # Aggregated metrics
    # -----------------------------------------------------
    left, right = st.columns(2)

    with left:
        render_graph(
            "Core Metrics Comparison",
            "core_metrics_comparison.png",
            base_graph_folder,
        )

    with right:
        render_graph(
            "Queue Length Over Time",
            "queue_length_over_time.png",
            base_graph_folder,
        )

    # -----------------------------------------------------
    # Task-level metrics
    # -----------------------------------------------------
    render_graph(
        "Task Waiting Time",
        "task_waiting_time.png",
        task_graph_folder,
    )

    render_graph(
        "Task Completion Time",
        "task_completion_time.png",
        task_graph_folder,
    )

    render_graph(
        "Task Travel Distance",
        "task_travel_distance.png",
        task_graph_folder,
    )

    # -----------------------------------------------------
    # Robot metrics
    # -----------------------------------------------------
    left, right = st.columns(2)

    with left:
        render_graph(
            "Robot Total Distance",
            "robot_total_distance.png",
            base_graph_folder,
        )

    with right:
        render_graph(
            "Robot Utilization",
            "robot_utilization.png",
            base_graph_folder,
        )

    render_graph(
        "Overall Strategy Performance",
        "overall_strategy_performance.png",
        base_graph_folder,
    )


def _render_tables(
    comparison: pd.DataFrame,
    all_tasks: pd.DataFrame,
    all_robots: pd.DataFrame,
) -> None:
    result_view = st.selectbox(
        "Result view",
        [
            "Comparison table",
            "Task details",
            "Robot details",
        ],
    )

    if result_view == "Comparison table":
        display_frame = comparison.copy()

        for column in [
            "FIFO",
            "Deferred Commitment",
            "Deferred vs FIFO (%)",
        ]:
            display_frame[column] = (
                display_frame[column].round(2)
            )

        st.dataframe(
            display_frame,
            use_container_width=True,
            hide_index=True,
        )

    elif result_view == "Task details":
        strategy_filter = st.multiselect(
            "Show strategies",
            [
                "FIFO",
                "Deferred Commitment",
            ],
            default=[
                "FIFO",
                "Deferred Commitment",
            ],
        )

        filtered_tasks = all_tasks[
            all_tasks["Strategy"].isin(
                strategy_filter
            )
        ]

        unique_task_ids = sorted(
            filtered_tasks[
                "Task ID"
            ].unique()
        )

        if len(unique_task_ids) > 25:
            range_size = 25

            range_options = [
                "All tasks"
            ]

            range_mapping = {}

            for start in range(
                0,
                len(unique_task_ids),
                range_size,
            ):
                end = min(
                    start + range_size,
                    len(unique_task_ids),
                )

                label = (
                    f"Tasks {start + 1}-{end}"
                )

                selected_ids = (
                    unique_task_ids[
                        start:end
                    ]
                )

                range_options.append(
                    label
                )

                range_mapping[label] = (
                    selected_ids
                )

            selected_range = st.selectbox(
                "Task range",
                range_options,
                key="task_detail_range",
            )

            if (
                selected_range
                != "All tasks"
            ):
                filtered_tasks = (
                    filtered_tasks[
                        filtered_tasks[
                            "Task ID"
                        ].isin(
                            range_mapping[
                                selected_range
                            ]
                        )
                    ]
                )

        st.dataframe(
            filtered_tasks.round(2),
            use_container_width=True,
            hide_index=True,
        )

    else:
        st.dataframe(
            all_robots.round(2),
            use_container_width=True,
            hide_index=True,
        )


def _render_exports(
    scenario_key: str,
    comparison: pd.DataFrame,
    all_tasks: pd.DataFrame,
    all_robots: pd.DataFrame,
) -> None:
    st.markdown(
        '<div class="section-title">'
        'Export results'
        '</div>',
        unsafe_allow_html=True,
    )

    left, middle, right = st.columns(3)

    with left:
        st.download_button(
            "Export comparison",
            comparison.to_csv(
                index=False
            ).encode("utf-8"),
            file_name=(
                f"{scenario_key}_comparison.csv"
            ),
            mime="text/csv",
            use_container_width=True,
        )

    with middle:
        st.download_button(
            "Export tasks",
            all_tasks.to_csv(
                index=False
            ).encode("utf-8"),
            file_name=(
                f"{scenario_key}_tasks.csv"
            ),
            mime="text/csv",
            use_container_width=True,
        )

    with right:
        st.download_button(
            "Export robots",
            all_robots.to_csv(
                index=False
            ).encode("utf-8"),
            file_name=(
                f"{scenario_key}_robots.csv"
            ),
            mime="text/csv",
            use_container_width=True,
        )


def run_and_render_dashboard(
    scenario_payload: dict,
) -> None:
    mode = scenario_payload["mode"]
    scenario_key = scenario_payload[
        "scenario_key"
    ]
    scenario = scenario_payload["scenario"]
    run_clicked = scenario_payload[
        "run_clicked"
    ]

    _render_scenario_card(scenario)

    if mode == "custom":
        st.markdown(
            '<div class="section-title">'
            'Generated task preview'
            '</div>',
            unsafe_allow_html=True,
        )

        preview_frame = pd.DataFrame(
            scenario["tasks"]
        )

        # Display rack positions as integers only
        preview_frame["rack_position"] = (
            preview_frame["rack_position"]
            .apply(
                lambda position: (
                    int(round(position[0])),
                    int(round(position[1])),
                )
            )
        )


        st.dataframe(
            preview_frame,
            use_container_width=True,
            hide_index=True,
        )

    cache_key = f"results_{scenario_key}"

    if run_clicked:
        with st.spinner(
            f"Running {scenario['name']} "
            "under both strategies..."
        ):
            st.session_state[
                cache_key
            ] = _run_results(
                mode=mode,
                scenario_key=scenario_key,
                scenario=scenario,
            )

            st.session_state[
                "active_result_key"
            ] = cache_key

    if (
        st.session_state.get(
            "active_result_key"
        )
        != cache_key
        or cache_key
        not in st.session_state
    ):
        st.info(
            "The configuration is ready. "
            "Click **Run strategy comparison** "
            "to display the performance snapshot, "
            "graphs, tables, and exports. Animations "
            "can then be generated on demand."
        )
        st.stop()

    results = st.session_state[cache_key]

    fifo_result = results["fifo"]
    deferred_result = results["deferred"]

    fifo_summary = fifo_result["summary"]
    deferred_summary = (
        deferred_result["summary"]
    )

    comparison = comparison_frame(
        fifo_summary,
        deferred_summary,
    )

    all_tasks = pd.concat(
        [
            task_frame(
                fifo_result,
                "FIFO",
            ),
            task_frame(
                deferred_result,
                "Deferred Commitment",
            ),
        ],
        ignore_index=True,
    )

    all_robots = pd.concat(
        [
            robot_frame(
                fifo_result,
                "FIFO",
            ),
            robot_frame(
                deferred_result,
                "Deferred Commitment",
            ),
        ],
        ignore_index=True,
    )


    animation_tab, analysis_tab = st.tabs(
        ["2D Animation", "Analysis"]
    )

    with animation_tab:
        _render_animations(
            scenario_key,
            fifo_result,
            deferred_result,
        )

    with analysis_tab:
        _render_metrics(
            fifo_summary,
            deferred_summary,
        )

        _render_charts(
            scenario_key,
            fifo_result,
            deferred_result,
        )

        st.markdown(
            '<div class="section-title">'
            'Detailed Results'
            '</div>',
            unsafe_allow_html=True,
        )

        _render_tables(
            comparison,
            all_tasks,
            all_robots,
        )

        _render_exports(
            scenario_key,
            comparison,
            all_tasks,
            all_robots,
        )