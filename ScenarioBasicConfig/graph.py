import os
import time
from pathlib import Path

import matplotlib.pyplot as plt

try:
    from .simulation import run_simulation
    from .scenarios import list_scenarios, get_scenario
except ImportError:
    from simulation import run_simulation
    from scenarios import list_scenarios, get_scenario


# =========================================================
# 1. OUTPUT FOLDER
# =========================================================

OUTPUT_FOLDER = "outputs"

# Web-friendly rendering settings
GRAPH_DPI = 120

# Increment this when graph layout/rendering rules change.
# dashboard_common.py includes this version in the graph cache path,
# so old graph files are not reused after a visual logic update.
GRAPH_RENDER_VERSION = "v6_clean_difference_title"

# Task graph readability thresholds.
TASK_DETAILED_LIMIT = 25
TASK_BAR_LIMIT = 50
REUSE_EXISTING_GRAPHS = True


def create_output_folder(folder_path):
    os.makedirs(
        folder_path,
        exist_ok=True,
    )


# =========================================================
# 2. RUN BOTH STRATEGIES FOR ONE SCENARIO
# =========================================================

def get_results(scenario_name):
    fifo_result = run_simulation(
        "FIFO",
        scenario_name,
    )

    deferred_result = run_simulation(
        "DEFERRED",
        scenario_name,
    )

    return fifo_result, deferred_result


def configure_task_axis(
    axis,
    task_ids,
):
    """
    Keep task identifiers readable as task volume grows.

    <= 25 tasks: show every task.
    26-50 tasks: show roughly every 5th task.
    > 50 tasks: show roughly every 10th task.
    """
    task_count = len(task_ids)

    if task_count <= TASK_DETAILED_LIMIT:
        tick_step = 1
    elif task_count <= TASK_BAR_LIMIT:
        tick_step = 5
    else:
        tick_step = 10

    visible_positions = list(
        range(
            0,
            task_count,
            tick_step,
        )
    )

    # Always include the final task so the displayed range is obvious.
    if (
        task_count > 0
        and (task_count - 1) not in visible_positions
    ):
        visible_positions.append(
            task_count - 1
        )

    axis.set_xticks(
        visible_positions
    )

    axis.set_xticklabels(
        [
            task_ids[index]
            for index in visible_positions
        ],
        rotation=(
            45
            if task_count <= TASK_DETAILED_LIMIT
            else 0
        ),
        ha=(
            "right"
            if task_count <= TASK_DETAILED_LIMIT
            else "center"
        ),
        fontsize=8,
    )


# =========================================================
# 3. SAVE FIGURE
# =========================================================

def save_figure(
    figure,
    folder_path,
    filename,
    force_rebuild=False,
):
    filepath = os.path.join(
        folder_path,
        filename,
    )

    path = Path(filepath)

    if (
        REUSE_EXISTING_GRAPHS
        and not force_rebuild
        and path.exists()
        and path.stat().st_size > 0
    ):
        plt.close(figure)

        print(
            f"Using existing graph: {filepath}"
        )

        return filepath

    start_time = time.perf_counter()

    figure.tight_layout()

    figure.savefig(
        filepath,
        dpi=GRAPH_DPI,
    )

    plt.close(figure)

    elapsed = time.perf_counter() - start_time

    print(
        f"Generated: {filepath}"
    )

    print(
        f"Graph generation time: "
        f"{elapsed:.2f} seconds"
    )

    return filepath


# =========================================================
# 4. MAIN METRICS COMPARISON
# =========================================================

def create_main_metrics_graph(
    fifo_result,
    deferred_result,
    folder_path,
):
    fifo = fifo_result["summary"]
    deferred = deferred_result["summary"]

    metric_names = [
        "Avg Waiting",
        "Avg Completion",
        "Avg Travel",
        "Makespan",
    ]

    fifo_values = [
        fifo["average_waiting_time"],
        fifo["average_completion_time"],
        fifo["average_travel_distance"],
        fifo["makespan"],
    ]

    deferred_values = [
        deferred["average_waiting_time"],
        deferred["average_completion_time"],
        deferred["average_travel_distance"],
        deferred["makespan"],
    ]

    x_positions = range(
        len(metric_names)
    )

    bar_width = 0.35

    figure, axis = plt.subplots(
        figsize=(9, 5.5)
    )

    fifo_bars = axis.bar(
        [
            x - bar_width / 2
            for x in x_positions
        ],
        fifo_values,
        width=bar_width,
        label="FIFO",
    )

    deferred_bars = axis.bar(
        [
            x + bar_width / 2
            for x in x_positions
        ],
        deferred_values,
        width=bar_width,
        label="Deferred Commitment",
    )

    axis.set_title(
        f"{fifo['scenario_name']}: Core Metrics"
    )

    axis.set_xlabel(
        "Performance Metric"
    )

    axis.set_ylabel(
        "Simulation Value"
    )

    axis.set_xticks(
        list(x_positions)
    )

    axis.set_xticklabels(
        metric_names
    )

    axis.legend()

    axis.grid(
        axis="y",
        alpha=0.3,
    )

    axis.bar_label(
        fifo_bars,
        fmt="%.2f",
        padding=3,
    )

    axis.bar_label(
        deferred_bars,
        fmt="%.2f",
        padding=3,
    )

    save_figure(
        figure,
        folder_path,
        "core_metrics_comparison.png",
    )


# =========================================================
# 5-7. ADAPTIVE TASK-LEVEL GRAPHS
# =========================================================

def _filter_tasks_by_id(
    result,
    selected_task_ids=None,
):
    tasks = sorted(
        result["tasks"],
        key=lambda task: task.task_id,
    )

    if selected_task_ids is None:
        return tasks

    selected_set = set(
        selected_task_ids
    )

    return [
        task
        for task in tasks
        if task.task_id in selected_set
    ]


def _create_task_comparison_graph(
    fifo_result,
    deferred_result,
    folder_path,
    value_getter,
    title_suffix,
    y_label,
    filename,
    selected_task_ids=None,
    difference_overview=False,
    view_label=None,
):
    """
    Render a task-level comparison that adapts to the selected view.

    Detailed range:
        FIFO and Deferred are displayed side-by-side.
        Up to 25 selected tasks receive exact value labels.

    All-task overview for a large configuration:
        A single difference series is displayed:
            Deferred - FIFO

        Negative value:
            Deferred Commitment achieved a lower metric value.

        Positive value:
            FIFO achieved a lower metric value.

    This avoids asking the user to visually pair two separate points for
    every task in a 100-task configuration.
    """
    fifo_tasks = _filter_tasks_by_id(
        fifo_result,
        selected_task_ids,
    )

    deferred_tasks = _filter_tasks_by_id(
        deferred_result,
        selected_task_ids,
    )

    fifo_by_id = {
        task.task_id: task
        for task in fifo_tasks
    }

    deferred_by_id = {
        task.task_id: task
        for task in deferred_tasks
    }

    task_ids = sorted(
        set(fifo_by_id)
        & set(deferred_by_id)
    )

    if not task_ids:
        raise ValueError(
            "No matching FIFO and Deferred tasks "
            "were found for the selected task view."
        )

    fifo_values = [
        float(
            value_getter(
                fifo_by_id[task_id]
            )
        )
        for task_id in task_ids
    ]

    deferred_values = [
        float(
            value_getter(
                deferred_by_id[task_id]
            )
        )
        for task_id in task_ids
    ]

    task_count = len(task_ids)
    x_positions = list(
        range(task_count)
    )

    figure_size = (
        (13.5, 6.5)
        if difference_overview
        else (
            (11.5, 6.0)
            if task_count <= TASK_DETAILED_LIMIT
            else (12.5, 6.0)
        )
    )

    figure, axis = plt.subplots(
        figsize=figure_size
    )

    scenario_name = (
        fifo_result["summary"][
            "scenario_name"
        ]
    )

    view_suffix = (
        f" ({view_label})"
        if view_label
        else ""
    )

    if difference_overview:
        differences = [
            deferred_value
            - fifo_value
            for fifo_value, deferred_value
            in zip(
                fifo_values,
                deferred_values,
            )
        ]

        tolerance = 1e-9

        deferred_better_count = sum(
            1
            for value in differences
            if value < -tolerance
        )

        fifo_better_count = sum(
            1
            for value in differences
            if value > tolerance
        )

        equal_count = (
            len(differences)
            - deferred_better_count
            - fifo_better_count
        )

        axis.scatter(
            x_positions,
            differences,
            s=34,
            alpha=0.85,
        )

        axis.axhline(
            0.0,
            linewidth=1.2,
            linestyle="--",
        )

        summary_text = (
            f"Deferred lower: {deferred_better_count} tasks"
            f"   |   FIFO lower: {fifo_better_count} tasks"
            f"   |   Equal: {equal_count} tasks"
        )

        # Use one controlled multiline title instead of placing a second
        # text object above the axes. This prevents the summary from
        # overlapping the chart title in wide/full-width dashboard views.
        axis.set_title(
            f"{scenario_name}: {title_suffix}\n"
            f"Difference = Deferred Commitment - FIFO\n"
            f"{summary_text}",
            fontsize=11,
            pad=12,
        )

        axis.set_ylabel(
            f"{y_label} Difference"
        )

        # Make the interpretation explicit inside the graph so a
        # first-time viewer does not need to infer the sign convention.
        axis.text(
            0.015,
            0.965,
            "Positive = FIFO better",
            transform=axis.transAxes,
            ha="left",
            va="top",
            fontsize=9,
            fontweight="bold",
        )

        axis.text(
            0.015,
            0.035,
            "Negative = Deferred Commitment better",
            transform=axis.transAxes,
            ha="left",
            va="bottom",
            fontsize=9,
            fontweight="bold",
        )

        axis.text(
            0.985,
            0.505,
            "Equal",
            transform=axis.transAxes,
            ha="right",
            va="bottom",
            fontsize=8,
        )


    else:
        bar_width = 0.36

        fifo_artists = axis.bar(
            [
                x - bar_width / 2
                for x in x_positions
            ],
            fifo_values,
            width=bar_width,
            label="FIFO",
        )

        deferred_artists = axis.bar(
            [
                x + bar_width / 2
                for x in x_positions
            ],
            deferred_values,
            width=bar_width,
            label="Deferred Commitment",
        )

        if task_count <= TASK_DETAILED_LIMIT:
            axis.bar_label(
                fifo_artists,
                fmt="%.1f",
                padding=3,
                fontsize=8,
            )

            axis.bar_label(
                deferred_artists,
                fmt="%.1f",
                padding=3,
                fontsize=8,
            )

        axis.set_title(
            f"{scenario_name}: "
            f"{title_suffix}"
            f"{view_suffix}"
        )

        axis.set_ylabel(
            y_label
        )

        axis.legend()

    axis.set_xlabel(
        "Task"
    )

    configure_task_axis(
        axis=axis,
        task_ids=task_ids,
    )

    axis.grid(
        axis="y",
        alpha=0.3,
    )

    axis.margins(
        x=0.01
    )

    save_figure(
        figure,
        folder_path,
        filename,
    )


def create_waiting_time_graph(
    fifo_result,
    deferred_result,
    folder_path,
    selected_task_ids=None,
    difference_overview=False,
    view_label=None,
):
    _create_task_comparison_graph(
        fifo_result=fifo_result,
        deferred_result=deferred_result,
        folder_path=folder_path,
        value_getter=(
            lambda task: task.waiting_time()
        ),
        title_suffix="Task Waiting Time",
        y_label="Waiting Time",
        filename="task_waiting_time.png",
        selected_task_ids=selected_task_ids,
        difference_overview=(
            difference_overview
        ),
        view_label=view_label,
    )


def create_completion_time_graph(
    fifo_result,
    deferred_result,
    folder_path,
    selected_task_ids=None,
    difference_overview=False,
    view_label=None,
):
    _create_task_comparison_graph(
        fifo_result=fifo_result,
        deferred_result=deferred_result,
        folder_path=folder_path,
        value_getter=(
            lambda task: task.cycle_time()
        ),
        title_suffix="Task Completion Time",
        y_label="Completion Time",
        filename="task_completion_time.png",
        selected_task_ids=selected_task_ids,
        difference_overview=(
            difference_overview
        ),
        view_label=view_label,
    )


def create_travel_distance_graph(
    fifo_result,
    deferred_result,
    folder_path,
    selected_task_ids=None,
    difference_overview=False,
    view_label=None,
):
    _create_task_comparison_graph(
        fifo_result=fifo_result,
        deferred_result=deferred_result,
        folder_path=folder_path,
        value_getter=(
            lambda task: task.travel_distance
        ),
        title_suffix="Task Travel Distance",
        y_label="Travel Distance",
        filename="task_travel_distance.png",
        selected_task_ids=selected_task_ids,
        difference_overview=(
            difference_overview
        ),
        view_label=view_label,
    )


# =========================================================
# 8. QUEUE LENGTH OVER TIME
# =========================================================

def create_queue_length_graph(
    fifo_result,
    deferred_result,
    folder_path,
):
    fifo_history = (
        fifo_result["queue_history"]
    )

    deferred_history = (
        deferred_result["queue_history"]
    )

    fifo_times = [
        record["time"]
        for record in fifo_history
    ]

    fifo_queue = [
        record["queue_length"]
        for record in fifo_history
    ]

    deferred_times = [
        record["time"]
        for record in deferred_history
    ]

    deferred_queue = [
        record["queue_length"]
        for record in deferred_history
    ]

    figure, axis = plt.subplots(
        figsize=(10, 5.5)
    )

    axis.step(
        fifo_times,
        fifo_queue,
        where="post",
        label="FIFO",
        linewidth=2,
    )

    axis.step(
        deferred_times,
        deferred_queue,
        where="post",
        label="Deferred Commitment",
        linewidth=2,
    )

    axis.set_title(
        f"{fifo_result['summary']['scenario_name']}: Queue Length Over Time"
    )

    axis.set_xlabel(
        "Simulation Time"
    )

    axis.set_ylabel(
        "Number of Waiting Tasks"
    )

    axis.legend()

    axis.grid(
        alpha=0.3,
    )

    save_figure(
        figure,
        folder_path,
        "queue_length_over_time.png",
    )


# =========================================================
# 9. ROBOT TOTAL DISTANCE
# =========================================================

def create_robot_distance_graph(
    fifo_result,
    deferred_result,
    folder_path,
):
    fifo_robots = sorted(
        fifo_result["robots"],
        key=lambda robot: robot.robot_id,
    )

    deferred_robots = sorted(
        deferred_result["robots"],
        key=lambda robot: robot.robot_id,
    )

    robot_names = [
        f"Robot {robot.robot_id}"
        for robot in fifo_robots
    ]

    fifo_values = [
        robot.total_distance
        for robot in fifo_robots
    ]

    deferred_values = [
        robot.total_distance
        for robot in deferred_robots
    ]

    x_positions = range(
        len(robot_names)
    )

    bar_width = 0.35

    figure, axis = plt.subplots(
        figsize=(max(9, len(robot_names) * 1.2), 6)
    )

    fifo_bars = axis.bar(
        [
            x - bar_width / 2
            for x in x_positions
        ],
        fifo_values,
        width=bar_width,
        label="FIFO",
    )

    deferred_bars = axis.bar(
        [
            x + bar_width / 2
            for x in x_positions
        ],
        deferred_values,
        width=bar_width,
        label="Deferred Commitment",
    )

    axis.set_title(
        f"{fifo_result['summary']['scenario_name']}: Total Distance by Robot"
    )

    axis.set_xlabel(
        "Robot"
    )

    axis.set_ylabel(
        "Total Travel Distance"
    )

    axis.set_xticks(
        list(x_positions)
    )

    axis.set_xticklabels(
        robot_names
    )

    axis.legend()

    axis.grid(
        axis="y",
        alpha=0.3,
    )

    axis.bar_label(
        fifo_bars,
        fmt="%.1f",
        padding=3,
    )

    axis.bar_label(
        deferred_bars,
        fmt="%.1f",
        padding=3,
    )

    save_figure(
        figure,
        folder_path,
        "robot_total_distance.png",
    )


# =========================================================
# 10. ROBOT UTILIZATION
# =========================================================

def create_robot_utilization_graph(
    fifo_result,
    deferred_result,
    folder_path,
):
    fifo_robots = sorted(
        fifo_result["robots"],
        key=lambda robot: robot.robot_id,
    )

    deferred_robots = sorted(
        deferred_result["robots"],
        key=lambda robot: robot.robot_id,
    )

    fifo_makespan = (
        fifo_result["summary"]["makespan"]
    )

    deferred_makespan = (
        deferred_result["summary"]["makespan"]
    )

    robot_names = [
        f"Robot {robot.robot_id}"
        for robot in fifo_robots
    ]

    fifo_values = [
        (
            robot.busy_time
            / fifo_makespan
            * 100
        )
        for robot in fifo_robots
    ]

    deferred_values = [
        (
            robot.busy_time
            / deferred_makespan
            * 100
        )
        for robot in deferred_robots
    ]

    x_positions = range(
        len(robot_names)
    )

    bar_width = 0.35

    figure, axis = plt.subplots(
        figsize=(max(9, len(robot_names) * 1.2), 6)
    )

    fifo_bars = axis.bar(
        [
            x - bar_width / 2
            for x in x_positions
        ],
        fifo_values,
        width=bar_width,
        label="FIFO",
    )

    deferred_bars = axis.bar(
        [
            x + bar_width / 2
            for x in x_positions
        ],
        deferred_values,
        width=bar_width,
        label="Deferred Commitment",
    )

    axis.set_title(
        f"{fifo_result['summary']['scenario_name']}: Robot Utilization"
    )

    axis.set_xlabel(
        "Robot"
    )

    axis.set_ylabel(
        "Utilization (%)"
    )

    axis.set_ylim(
        0,
        110,
    )

    axis.set_xticks(
        list(x_positions)
    )

    axis.set_xticklabels(
        robot_names
    )

    axis.legend()

    axis.grid(
        axis="y",
        alpha=0.3,
    )

    axis.bar_label(
        fifo_bars,
        fmt="%.1f%%",
        padding=3,
    )

    axis.bar_label(
        deferred_bars,
        fmt="%.1f%%",
        padding=3,
    )

    save_figure(
        figure,
        folder_path,
        "robot_utilization.png",
    )


# =========================================================
# 11. OVERALL STRATEGY PERFORMANCE
# =========================================================

def create_total_performance_graph(
    fifo_result,
    deferred_result,
    folder_path,
):
    fifo = fifo_result["summary"]
    deferred = deferred_result["summary"]

    metric_names = [
        "Total Distance",
        "Makespan",
    ]

    fifo_values = [
        fifo["total_distance"],
        fifo["makespan"],
    ]

    deferred_values = [
        deferred["total_distance"],
        deferred["makespan"],
    ]

    x_positions = range(
        len(metric_names)
    )

    bar_width = 0.35

    figure, axis = plt.subplots(
        figsize=(8, 5.5)
    )

    fifo_bars = axis.bar(
        [
            x - bar_width / 2
            for x in x_positions
        ],
        fifo_values,
        width=bar_width,
        label="FIFO",
    )

    deferred_bars = axis.bar(
        [
            x + bar_width / 2
            for x in x_positions
        ],
        deferred_values,
        width=bar_width,
        label="Deferred Commitment",
    )

    axis.set_title(
        f"{fifo_result['summary']['scenario_name']}: Overall Strategy Performance"
    )

    axis.set_xlabel(
        "Performance Metric"
    )

    axis.set_ylabel(
        "Simulation Value"
    )

    axis.set_xticks(
        list(x_positions)
    )

    axis.set_xticklabels(
        metric_names
    )

    axis.legend()

    axis.grid(
        axis="y",
        alpha=0.3,
    )

    axis.bar_label(
        fifo_bars,
        fmt="%.1f",
        padding=3,
    )

    axis.bar_label(
        deferred_bars,
        fmt="%.1f",
        padding=3,
    )

    save_figure(
        figure,
        folder_path,
        "overall_strategy_performance.png",
    )


# =========================================================
# 12. SCENARIO SUMMARY CHART
# =========================================================

def create_scenario_summary_graph(all_results):
    scenario_names = []
    fifo_makespans = []
    deferred_makespans = []
    fifo_distances = []
    deferred_distances = []

    for scenario_name, result_pair in all_results.items():
        fifo_result, deferred_result = result_pair

        scenario = get_scenario(scenario_name)

        scenario_names.append(
            scenario["name"].replace(" Scenario", "")
        )

        fifo_makespans.append(
            fifo_result["summary"]["makespan"]
        )

        deferred_makespans.append(
            deferred_result["summary"]["makespan"]
        )

        fifo_distances.append(
            fifo_result["summary"]["total_distance"]
        )

        deferred_distances.append(
            deferred_result["summary"]["total_distance"]
        )

    x_positions = range(
        len(scenario_names)
    )

    bar_width = 0.35

    comparison_folder = os.path.join(
        OUTPUT_FOLDER,
        "scenario_comparison",
    )

    create_output_folder(
        comparison_folder
    )

    # Makespan comparison
    figure, axis = plt.subplots(
        figsize=(10, 5.5)
    )

    fifo_bars = axis.bar(
        [
            x - bar_width / 2
            for x in x_positions
        ],
        fifo_makespans,
        width=bar_width,
        label="FIFO",
    )

    deferred_bars = axis.bar(
        [
            x + bar_width / 2
            for x in x_positions
        ],
        deferred_makespans,
        width=bar_width,
        label="Deferred Commitment",
    )

    axis.set_title(
        "Makespan Comparison Across Scenarios"
    )

    axis.set_xlabel(
        "Scenario"
    )

    axis.set_ylabel(
        "Makespan"
    )

    axis.set_xticks(
        list(x_positions)
    )

    axis.set_xticklabels(
        scenario_names,
        rotation=15,
        ha="right",
    )

    axis.legend()

    axis.grid(
        axis="y",
        alpha=0.3,
    )

    axis.bar_label(
        fifo_bars,
        fmt="%.1f",
        padding=3,
    )

    axis.bar_label(
        deferred_bars,
        fmt="%.1f",
        padding=3,
    )

    save_figure(
        figure,
        comparison_folder,
        "makespan_across_scenarios.png",
    )

    # Total distance comparison
    figure, axis = plt.subplots(
        figsize=(10, 5.5)
    )

    fifo_bars = axis.bar(
        [
            x - bar_width / 2
            for x in x_positions
        ],
        fifo_distances,
        width=bar_width,
        label="FIFO",
    )

    deferred_bars = axis.bar(
        [
            x + bar_width / 2
            for x in x_positions
        ],
        deferred_distances,
        width=bar_width,
        label="Deferred Commitment",
    )

    axis.set_title(
        "Total Travel Distance Comparison Across Scenarios"
    )

    axis.set_xlabel(
        "Scenario"
    )

    axis.set_ylabel(
        "Total Travel Distance"
    )

    axis.set_xticks(
        list(x_positions)
    )

    axis.set_xticklabels(
        scenario_names,
        rotation=15,
        ha="right",
    )

    axis.legend()

    axis.grid(
        axis="y",
        alpha=0.3,
    )

    axis.bar_label(
        fifo_bars,
        fmt="%.1f",
        padding=3,
    )

    axis.bar_label(
        deferred_bars,
        fmt="%.1f",
        padding=3,
    )

    save_figure(
        figure,
        comparison_folder,
        "total_distance_across_scenarios.png",
    )


# =========================================================
# 13. GENERATE ALL GRAPHS FOR ONE SCENARIO
# =========================================================

def generate_graphs_for_scenario(scenario_name):
    scenario_folder = os.path.join(
        OUTPUT_FOLDER,
        scenario_name,
    )

    create_output_folder(
        scenario_folder
    )

    fifo_result, deferred_result = get_results(
        scenario_name
    )

    create_main_metrics_graph(
        fifo_result,
        deferred_result,
        scenario_folder,
    )

    create_waiting_time_graph(
        fifo_result,
        deferred_result,
        scenario_folder,
    )

    create_completion_time_graph(
        fifo_result,
        deferred_result,
        scenario_folder,
    )

    create_travel_distance_graph(
        fifo_result,
        deferred_result,
        scenario_folder,
    )

    create_queue_length_graph(
        fifo_result,
        deferred_result,
        scenario_folder,
    )

    create_robot_distance_graph(
        fifo_result,
        deferred_result,
        scenario_folder,
    )

    create_robot_utilization_graph(
        fifo_result,
        deferred_result,
        scenario_folder,
    )

    create_total_performance_graph(
        fifo_result,
        deferred_result,
        scenario_folder,
    )

    return fifo_result, deferred_result


# =========================================================
# 14. MAIN
# =========================================================

def main():
    create_output_folder(
        OUTPUT_FOLDER
    )

    all_results = {}

    for scenario_name in list_scenarios():
        print()
        print("=" * 80)
        print(
            f"Generating graphs for scenario: {scenario_name}"
        )
        print("=" * 80)

        all_results[scenario_name] = (
            generate_graphs_for_scenario(
                scenario_name
            )
        )

    create_scenario_summary_graph(
        all_results
    )

    print()
    print(
        "All scenario graphs were generated successfully."
    )


if __name__ == "__main__":
    main()