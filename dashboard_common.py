from __future__ import annotations

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

from scenarios import SCENARIOS
from simulation import run_simulation
import animation as animation_engine
import graph as graph_engine


OUTPUTS_FOLDER = SCENARIO_FOLDER / "outputs"
ANIMATION_CACHE_FOLDER = (
    PROJECT_FOLDER
    / ".dashboard_animation_cache"
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


def shipped_animation_path(
    scenario_key: str,
    strategy: str,
) -> Path:
    return (
        OUTPUTS_FOLDER
        / scenario_key
        / (
            f"{strategy.lower()}"
            "_warehouse_animation.gif"
        )
    )


def cached_animation_path(
    scenario_key: str,
    strategy: str,
) -> Path:
    return (
        ANIMATION_CACHE_FOLDER
        / scenario_key
        / (
            f"{strategy.lower()}"
            "_warehouse_animation.gif"
        )
    )


def get_or_build_animation(
    scenario_key: str,
    strategy: str,
    result: dict,
) -> Path:
    shipped_path = shipped_animation_path(
        scenario_key,
        strategy,
    )

    if shipped_path.exists():
        return shipped_path

    cache_path = cached_animation_path(
        scenario_key,
        strategy,
    )

    if not cache_path.exists():
        original_output_folder = (
            animation_engine.OUTPUT_FOLDER
        )

        animation_engine.OUTPUT_FOLDER = str(
            ANIMATION_CACHE_FOLDER
        )

        try:
            animation_engine.create_animation(
                strategy=strategy.upper(),
                scenario_name=scenario_key,
                result=result,
            )
        finally:
            animation_engine.OUTPUT_FOLDER = (
                original_output_folder
            )

    return cache_path


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
        'Performance snapshot'
        '</div>',
        unsafe_allow_html=True,
    )

    metric_columns = st.columns(6)

    headline_metrics = [
        (
            "Avg waiting",
            "average_waiting_time",
        ),
        (
            "Avg completion",
            "average_completion_time",
        ),
        (
            "Avg distance",
            "average_travel_distance",
        ),
        ("Makespan", "makespan"),
        (
            "Avg queue",
            "average_queue_length",
        ),
        (
            "Max queue",
            "maximum_queue_length",
        ),
    ]

    for column, (label, key) in zip(
        metric_columns,
        headline_metrics,
    ):
        fifo_value = float(
            fifo_summary[key]
        )

        deferred_value = float(
            deferred_summary[key]
        )

        improvement = (
            (
                fifo_value - deferred_value
            )
            / fifo_value
            * 100
            if fifo_value
            else 0
        )

        column.metric(
            label,
            f"{deferred_value:.2f}",
            f"{improvement:+.1f}% vs FIFO",
            delta_color="normal",
            help=(
                "The main value is Deferred "
                "Commitment. The delta compares "
                "it with FIFO."
            ),
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

    left, right = st.columns(2)

    with st.spinner(
        "Preparing 2D animations..."
    ):
        fifo_path = get_or_build_animation(
            scenario_key,
            "FIFO",
            fifo_result,
        )

        deferred_path = get_or_build_animation(
            scenario_key,
            "DEFERRED",
            deferred_result,
        )

    with left:
        st.markdown(
            """
            <div class="animation-title fifo-title">
                ● FIFO
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.image(
            str(fifo_path),
            use_container_width=True,
        )

    with right:
        st.markdown(
            """
            <div class="
                animation-title deferred-title
            ">
                ● Deferred Commitment
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.image(
            str(deferred_path),
            use_container_width=True,
        )

def generate_graph_files(
    scenario_key: str,
    fifo_result: dict,
    deferred_result: dict,
) -> Path:
    scenario_folder = (
        OUTPUTS_FOLDER / scenario_key
    )

    scenario_folder.mkdir(
        parents=True,
        exist_ok=True,
    )

    folder_path = str(scenario_folder)

    graph_engine.create_main_metrics_graph(
        fifo_result,
        deferred_result,
        folder_path,
    )

    graph_engine.create_waiting_time_graph(
        fifo_result,
        deferred_result,
        folder_path,
    )

    graph_engine.create_completion_time_graph(
        fifo_result,
        deferred_result,
        folder_path,
    )

    graph_engine.create_travel_distance_graph(
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

    with st.spinner(
        "Preparing performance graphs..."
    ):
        scenario_folder = generate_graph_files(
            scenario_key,
            fifo_result,
            deferred_result,
        )

    graph_files = [
        (
            "Core Metrics Comparison",
            "core_metrics_comparison.png",
        ),
        (
            "Task Waiting Time",
            "task_waiting_time.png",
        ),
        (
            "Task Completion Time",
            "task_completion_time.png",
        ),
        (
            "Task Travel Distance",
            "task_travel_distance.png",
        ),
        (
            "Queue Length Over Time",
            "queue_length_over_time.png",
        ),
        (
            "Robot Total Distance",
            "robot_total_distance.png",
        ),
        (
            "Robot Utilization",
            "robot_utilization.png",
        ),
        (
            "Overall Strategy Performance",
            "overall_strategy_performance.png",
        ),
    ]

    for index in range(
        0,
        len(graph_files),
        2,
    ):
        left, right = st.columns(2)

        title, filename = graph_files[index]
        graph_path = scenario_folder / filename

        with left:
            st.markdown(
                f"###### {title}"
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

        if index + 1 < len(graph_files):
            title, filename = graph_files[
                index + 1
            ]

            graph_path = (
                scenario_folder / filename
            )

            with right:
                st.markdown(
                    f"###### {title}"
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

        st.dataframe(
            pd.DataFrame(
                scenario["tasks"]
            ).head(20),
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
            "animations, graphs, tables, and exports."
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

    all_queues = pd.concat(
        [
            queue_frame(
                fifo_result,
                "FIFO",
            ),
            queue_frame(
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