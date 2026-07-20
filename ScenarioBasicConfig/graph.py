import os

import matplotlib.pyplot as plt

from simulation import run_simulation
from scenarios import list_scenarios, get_scenario


# =========================================================
# 1. OUTPUT FOLDER
# =========================================================

OUTPUT_FOLDER = "outputs"


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


# =========================================================
# 3. SAVE FIGURE
# =========================================================

def save_figure(
    figure,
    folder_path,
    filename,
):
    filepath = os.path.join(
        folder_path,
        filename,
    )

    figure.tight_layout()

    figure.savefig(
        filepath,
        dpi=300,
        bbox_inches="tight",
    )

    plt.close(figure)

    print(
        f"Generated: {filepath}"
    )


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
        figsize=(10, 6)
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
# 5. WAITING TIME BY TASK
# =========================================================

def create_waiting_time_graph(
    fifo_result,
    deferred_result,
    folder_path,
):
    fifo_tasks = sorted(
        fifo_result["tasks"],
        key=lambda task: task.task_id,
    )

    deferred_tasks = sorted(
        deferred_result["tasks"],
        key=lambda task: task.task_id,
    )

    task_ids = [
        task.task_id
        for task in fifo_tasks
    ]

    fifo_values = [
        task.waiting_time()
        for task in fifo_tasks
    ]

    deferred_values = [
        task.waiting_time()
        for task in deferred_tasks
    ]

    x_positions = range(
        len(task_ids)
    )

    bar_width = 0.35

    figure, axis = plt.subplots(
        figsize=(max(10, len(task_ids) * 0.8), 6)
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
        f"{fifo_result['summary']['scenario_name']}: Task Waiting Time"
    )

    axis.set_xlabel(
        "Task"
    )

    axis.set_ylabel(
        "Waiting Time"
    )

    axis.set_xticks(
        list(x_positions)
    )

    axis.set_xticklabels(
        task_ids
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
        "task_waiting_time.png",
    )


# =========================================================
# 6. COMPLETION TIME BY TASK
# =========================================================

def create_completion_time_graph(
    fifo_result,
    deferred_result,
    folder_path,
):
    fifo_tasks = sorted(
        fifo_result["tasks"],
        key=lambda task: task.task_id,
    )

    deferred_tasks = sorted(
        deferred_result["tasks"],
        key=lambda task: task.task_id,
    )

    task_ids = [
        task.task_id
        for task in fifo_tasks
    ]

    fifo_values = [
        task.cycle_time()
        for task in fifo_tasks
    ]

    deferred_values = [
        task.cycle_time()
        for task in deferred_tasks
    ]

    x_positions = range(
        len(task_ids)
    )

    bar_width = 0.35

    figure, axis = plt.subplots(
        figsize=(max(10, len(task_ids) * 0.8), 6)
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
        f"{fifo_result['summary']['scenario_name']}: Task Completion Time"
    )

    axis.set_xlabel(
        "Task"
    )

    axis.set_ylabel(
        "Completion Time"
    )

    axis.set_xticks(
        list(x_positions)
    )

    axis.set_xticklabels(
        task_ids
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
        "task_completion_time.png",
    )


# =========================================================
# 7. TRAVEL DISTANCE BY TASK
# =========================================================

def create_travel_distance_graph(
    fifo_result,
    deferred_result,
    folder_path,
):
    fifo_tasks = sorted(
        fifo_result["tasks"],
        key=lambda task: task.task_id,
    )

    deferred_tasks = sorted(
        deferred_result["tasks"],
        key=lambda task: task.task_id,
    )

    task_ids = [
        task.task_id
        for task in fifo_tasks
    ]

    fifo_values = [
        task.travel_distance
        for task in fifo_tasks
    ]

    deferred_values = [
        task.travel_distance
        for task in deferred_tasks
    ]

    x_positions = range(
        len(task_ids)
    )

    bar_width = 0.35

    figure, axis = plt.subplots(
        figsize=(max(10, len(task_ids) * 0.8), 6)
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
        f"{fifo_result['summary']['scenario_name']}: Task Travel Distance"
    )

    axis.set_xlabel(
        "Task"
    )

    axis.set_ylabel(
        "Travel Distance"
    )

    axis.set_xticks(
        list(x_positions)
    )

    axis.set_xticklabels(
        task_ids
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
        "task_travel_distance.png",
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
        figsize=(11, 6)
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
        figsize=(8, 6)
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
        figsize=(11, 6)
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
        figsize=(11, 6)
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