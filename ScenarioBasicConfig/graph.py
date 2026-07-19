import os

import matplotlib.pyplot as plt

from simulation import run_simulation


# =========================================================
# 1. OUTPUT FOLDER
# =========================================================

OUTPUT_FOLDER = "outputs"


def create_output_folder():
    os.makedirs(
        OUTPUT_FOLDER,
        exist_ok=True,
    )


# =========================================================
# 2. RUN BOTH STRATEGIES
# =========================================================

def get_results():
    fifo_result = run_simulation(
        "FIFO"
    )

    deferred_result = run_simulation(
        "DEFERRED"
    )

    return fifo_result, deferred_result


# =========================================================
# 3. SAVE FIGURE
# =========================================================

def save_figure(
    figure,
    filename,
):
    filepath = os.path.join(
        OUTPUT_FOLDER,
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
        "FIFO vs Deferred Commitment: Core Metrics"
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
        "core_metrics_comparison.png",
    )


# =========================================================
# 5. WAITING TIME BY TASK
# =========================================================

def create_waiting_time_graph(
    fifo_result,
    deferred_result,
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
        "Task Waiting Time Comparison"
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
        "task_waiting_time.png",
    )


# =========================================================
# 6. COMPLETION TIME BY TASK
# =========================================================

def create_completion_time_graph(
    fifo_result,
    deferred_result,
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
        "Task Completion Time Comparison"
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
        "task_completion_time.png",
    )


# =========================================================
# 7. TRAVEL DISTANCE BY TASK
# =========================================================

def create_travel_distance_graph(
    fifo_result,
    deferred_result,
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
        "Task Travel Distance Comparison"
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
        "task_travel_distance.png",
    )


# =========================================================
# 8. QUEUE LENGTH OVER TIME
# =========================================================

def create_queue_length_graph(
    fifo_result,
    deferred_result,
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
        "Queue Length Over Simulation Time"
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
        "queue_length_over_time.png",
    )


# =========================================================
# 9. ROBOT TOTAL DISTANCE
# =========================================================

def create_robot_distance_graph(
    fifo_result,
    deferred_result,
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
        figsize=(9, 6)
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
        "Total Travel Distance by Robot"
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
        "robot_total_distance.png",
    )


# =========================================================
# 10. ROBOT UTILIZATION
# =========================================================

def create_robot_utilization_graph(
    fifo_result,
    deferred_result,
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
        figsize=(9, 6)
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
        "Robot Utilization Comparison"
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
        "robot_utilization.png",
    )


# =========================================================
# 11. TOTAL DISTANCE AND MAKESPAN
# =========================================================

def create_total_performance_graph(
    fifo_result,
    deferred_result,
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
        "Overall Strategy Performance"
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
        "overall_strategy_performance.png",
    )


# =========================================================
# 12. MAIN
# =========================================================

def main():
    create_output_folder()

    fifo_result, deferred_result = (
        get_results()
    )

    create_main_metrics_graph(
        fifo_result,
        deferred_result,
    )

    create_waiting_time_graph(
        fifo_result,
        deferred_result,
    )

    create_completion_time_graph(
        fifo_result,
        deferred_result,
    )

    create_travel_distance_graph(
        fifo_result,
        deferred_result,
    )

    create_queue_length_graph(
        fifo_result,
        deferred_result,
    )

    create_robot_distance_graph(
        fifo_result,
        deferred_result,
    )

    create_robot_utilization_graph(
        fifo_result,
        deferred_result,
    )

    create_total_performance_graph(
        fifo_result,
        deferred_result,
    )

    print()
    print(
        "All graphs were generated successfully."
    )


if __name__ == "__main__":
    main()