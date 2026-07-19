import os

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter
from matplotlib.patches import Rectangle

from simulation import (
    run_simulation,
    INPUT_STATION,
    OUTPUT_STATION,
    ROBOT_START_POSITIONS,
    RACK_POSITIONS,
    ROBOT_SPEED,
    LOAD_TIME,
    STORE_TIME,
    PICK_TIME,
    UNLOAD_TIME,
)


# =========================================================
# 1. ANIMATION SETTINGS
# =========================================================

OUTPUT_FOLDER = "outputs"

FRAME_STEP = 0.5
ANIMATION_FPS = 4

GRID_MIN_X = -0.5
GRID_MAX_X = 8.5

GRID_MIN_Y = -0.8
GRID_MAX_Y = 7.0


# =========================================================
# 2. OUTPUT FOLDER
# =========================================================

def create_output_folder():
    os.makedirs(
        OUTPUT_FOLDER,
        exist_ok=True,
    )


# =========================================================
# 3. DISTANCE
# =========================================================

def manhattan_distance(
    position_a,
    position_b,
):
    return (
        abs(position_a[0] - position_b[0])
        + abs(position_a[1] - position_b[1])
    )


# =========================================================
# 4. TIMELINE SEGMENT
# =========================================================

def create_segment(
    start_time,
    end_time,
    start_position,
    end_position,
    status,
    task_id=None,
    task_type=None,
    rack_name=None,
):
    return {
        "start_time": start_time,
        "end_time": end_time,
        "start_position": start_position,
        "end_position": end_position,
        "status": status,
        "task_id": task_id,
        "task_type": task_type,
        "rack_name": rack_name,
    }


# =========================================================
# 5. BUILD ROBOT TIMELINES
# =========================================================

def build_robot_timelines(result):
    makespan = result["summary"]["makespan"]

    timelines = {}

    for robot in result["robots"]:
        robot_tasks = sorted(
            [
                task
                for task in result["tasks"]
                if task.robot_id == robot.robot_id
            ],
            key=lambda task: task.start_time,
        )

        segments = []

        current_time = 0.0
        current_position = robot.starting_position

        for task in robot_tasks:
            if current_time < task.start_time:
                segments.append(
                    create_segment(
                        start_time=current_time,
                        end_time=task.start_time,
                        start_position=current_position,
                        end_position=current_position,
                        status="Idle",
                    )
                )

            current_time = task.start_time

            if task.task_type == "storage":
                distance_to_input = manhattan_distance(
                    current_position,
                    INPUT_STATION,
                )

                duration_to_input = (
                    distance_to_input
                    / ROBOT_SPEED
                )

                segments.append(
                    create_segment(
                        start_time=current_time,
                        end_time=(
                            current_time
                            + duration_to_input
                        ),
                        start_position=current_position,
                        end_position=INPUT_STATION,
                        status="Moving to input",
                        task_id=task.task_id,
                        task_type=task.task_type,
                        rack_name=task.rack_name,
                    )
                )

                current_time += duration_to_input
                current_position = INPUT_STATION

                segments.append(
                    create_segment(
                        start_time=current_time,
                        end_time=current_time + LOAD_TIME,
                        start_position=current_position,
                        end_position=current_position,
                        status="Loading",
                        task_id=task.task_id,
                        task_type=task.task_type,
                        rack_name=task.rack_name,
                    )
                )

                current_time += LOAD_TIME

                distance_to_rack = manhattan_distance(
                    INPUT_STATION,
                    task.rack_position,
                )

                duration_to_rack = (
                    distance_to_rack
                    / ROBOT_SPEED
                )

                segments.append(
                    create_segment(
                        start_time=current_time,
                        end_time=(
                            current_time
                            + duration_to_rack
                        ),
                        start_position=INPUT_STATION,
                        end_position=task.rack_position,
                        status="Moving to rack",
                        task_id=task.task_id,
                        task_type=task.task_type,
                        rack_name=task.rack_name,
                    )
                )

                current_time += duration_to_rack
                current_position = task.rack_position

                segments.append(
                    create_segment(
                        start_time=current_time,
                        end_time=current_time + STORE_TIME,
                        start_position=current_position,
                        end_position=current_position,
                        status="Storing",
                        task_id=task.task_id,
                        task_type=task.task_type,
                        rack_name=task.rack_name,
                    )
                )

                current_time += STORE_TIME

            elif task.task_type == "retrieval":
                distance_to_rack = manhattan_distance(
                    current_position,
                    task.rack_position,
                )

                duration_to_rack = (
                    distance_to_rack
                    / ROBOT_SPEED
                )

                segments.append(
                    create_segment(
                        start_time=current_time,
                        end_time=(
                            current_time
                            + duration_to_rack
                        ),
                        start_position=current_position,
                        end_position=task.rack_position,
                        status="Moving to rack",
                        task_id=task.task_id,
                        task_type=task.task_type,
                        rack_name=task.rack_name,
                    )
                )

                current_time += duration_to_rack
                current_position = task.rack_position

                segments.append(
                    create_segment(
                        start_time=current_time,
                        end_time=current_time + PICK_TIME,
                        start_position=current_position,
                        end_position=current_position,
                        status="Retrieving",
                        task_id=task.task_id,
                        task_type=task.task_type,
                        rack_name=task.rack_name,
                    )
                )

                current_time += PICK_TIME

                distance_to_output = manhattan_distance(
                    task.rack_position,
                    OUTPUT_STATION,
                )

                duration_to_output = (
                    distance_to_output
                    / ROBOT_SPEED
                )

                segments.append(
                    create_segment(
                        start_time=current_time,
                        end_time=(
                            current_time
                            + duration_to_output
                        ),
                        start_position=current_position,
                        end_position=OUTPUT_STATION,
                        status="Moving to output",
                        task_id=task.task_id,
                        task_type=task.task_type,
                        rack_name=task.rack_name,
                    )
                )

                current_time += duration_to_output
                current_position = OUTPUT_STATION

                segments.append(
                    create_segment(
                        start_time=current_time,
                        end_time=current_time + UNLOAD_TIME,
                        start_position=current_position,
                        end_position=current_position,
                        status="Unloading",
                        task_id=task.task_id,
                        task_type=task.task_type,
                        rack_name=task.rack_name,
                    )
                )

                current_time += UNLOAD_TIME

        if current_time < makespan:
            segments.append(
                create_segment(
                    start_time=current_time,
                    end_time=makespan,
                    start_position=current_position,
                    end_position=current_position,
                    status="Idle",
                )
            )

        timelines[robot.robot_id] = segments

    return timelines


# =========================================================
# 6. MANHATTAN MOVEMENT
# =========================================================

def interpolate_manhattan(
    start_position,
    end_position,
    progress,
):
    start_x, start_y = start_position
    end_x, end_y = end_position

    horizontal_distance = abs(
        end_x - start_x
    )

    vertical_distance = abs(
        end_y - start_y
    )

    total_distance = (
        horizontal_distance
        + vertical_distance
    )

    if total_distance == 0:
        return (
            float(start_x),
            float(start_y),
        )

    travelled = (
        progress
        * total_distance
    )

    if travelled <= horizontal_distance:
        if horizontal_distance == 0:
            current_x = start_x
        else:
            direction_x = (
                1
                if end_x > start_x
                else -1
            )

            current_x = (
                start_x
                + direction_x
                * travelled
            )

        current_y = start_y

    else:
        current_x = end_x

        remaining = (
            travelled
            - horizontal_distance
        )

        if vertical_distance == 0:
            current_y = start_y
        else:
            direction_y = (
                1
                if end_y > start_y
                else -1
            )

            current_y = (
                start_y
                + direction_y
                * remaining
            )

    return (
        float(current_x),
        float(current_y),
    )


# =========================================================
# 7. GET ROBOT STATE
# =========================================================

def get_robot_state(
    timeline,
    simulation_time,
):
    for index, segment in enumerate(timeline):
        is_last_segment = (
            index
            == len(timeline) - 1
        )

        within_segment = (
            segment["start_time"]
            <= simulation_time
            < segment["end_time"]
        )

        if (
            is_last_segment
            and simulation_time
            == segment["end_time"]
        ):
            within_segment = True

        if within_segment:
            duration = (
                segment["end_time"]
                - segment["start_time"]
            )

            if duration == 0:
                progress = 1.0
            else:
                progress = (
                    simulation_time
                    - segment["start_time"]
                ) / duration

            progress = max(
                0.0,
                min(1.0, progress),
            )

            position = interpolate_manhattan(
                segment["start_position"],
                segment["end_position"],
                progress,
            )

            return {
                "position": position,
                "status": segment["status"],
                "task_id": segment["task_id"],
                "task_type": segment["task_type"],
                "rack_name": segment["rack_name"],
            }

    final_segment = timeline[-1]

    return {
        "position": (
            final_segment["end_position"]
        ),
        "status": "Idle",
        "task_id": None,
        "task_type": None,
        "rack_name": None,
    }


# =========================================================
# 8. GET QUEUE LENGTH
# =========================================================

def get_queue_length(
    queue_history,
    simulation_time,
):
    valid_records = [
        record
        for record in queue_history
        if record["time"] <= simulation_time
    ]

    if not valid_records:
        return 0

    latest_record = max(
        valid_records,
        key=lambda record: record["time"],
    )

    return latest_record["queue_length"]


# =========================================================
# 9. DRAW WAREHOUSE
# =========================================================

def draw_warehouse(axis):
    axis.set_xlim(
        GRID_MIN_X,
        GRID_MAX_X,
    )

    axis.set_ylim(
        GRID_MIN_Y,
        GRID_MAX_Y,
    )

    axis.set_xticks(
        range(0, 9)
    )

    axis.set_yticks(
        range(0, 7)
    )

    axis.set_aspect(
        "equal",
        adjustable="box",
    )

    axis.grid(
        True,
        alpha=0.2,
    )

    axis.set_xlabel(
        "Warehouse X Coordinate"
    )

    axis.set_ylabel(
        "Warehouse Y Coordinate"
    )

    # Racks
    for rack_name, position in (
        RACK_POSITIONS.items()
    ):
        rack_x, rack_y = position

        rack_box = Rectangle(
            (
                rack_x - 0.42,
                rack_y - 0.34,
            ),
            0.84,
            0.68,
            facecolor="lightsteelblue",
            edgecolor="black",
            linewidth=1.2,
            zorder=1,
        )

        axis.add_patch(rack_box)

        axis.text(
            rack_x,
            rack_y,
            rack_name,
            ha="center",
            va="center",
            fontsize=9,
            fontweight="bold",
            zorder=2,
        )

    # Input station
    input_box = Rectangle(
        (
            INPUT_STATION[0] - 0.42,
            INPUT_STATION[1] - 0.34,
        ),
        0.84,
        0.68,
        facecolor="lightgreen",
        edgecolor="black",
        linewidth=1.2,
        zorder=1,
    )

    axis.add_patch(input_box)

    axis.text(
        INPUT_STATION[0],
        INPUT_STATION[1],
        "Input",
        ha="center",
        va="center",
        fontsize=8,
        fontweight="bold",
        zorder=2,
    )

    # Output station
    output_box = Rectangle(
        (
            OUTPUT_STATION[0] - 0.42,
            OUTPUT_STATION[1] - 0.34,
        ),
        0.84,
        0.68,
        facecolor="lightgreen",
        edgecolor="black",
        linewidth=1.2,
        zorder=1,
    )

    axis.add_patch(output_box)

    axis.text(
        OUTPUT_STATION[0],
        OUTPUT_STATION[1],
        "Output",
        ha="center",
        va="center",
        fontsize=8,
        fontweight="bold",
        zorder=2,
    )

    # Robot start points
    for robot_id, position in (
        ROBOT_START_POSITIONS.items()
    ):
        start_x, start_y = position

        start_box = Rectangle(
            (
                start_x - 0.42,
                start_y - 0.34,
            ),
            0.84,
            0.68,
            facecolor="lemonchiffon",
            edgecolor="black",
            linewidth=1.2,
            zorder=1,
        )

        axis.add_patch(start_box)

        axis.text(
            start_x,
            start_y,
            f"Start {robot_id}",
            ha="center",
            va="center",
            fontsize=8,
            zorder=2,
        )

    # Aisle labels
    aisle_positions = [
        (0, 3),
        (2, 3),
        (4, 3),
        (6, 3),
        (8, 3),
    ]

    for x_position, y_position in aisle_positions:
        axis.text(
            x_position,
            y_position,
            "Aisle",
            rotation=90,
            ha="center",
            va="center",
            fontsize=8,
            alpha=0.55,
        )


# =========================================================
# 10. CREATE ONE ANIMATION
# =========================================================

def create_animation(
    strategy,
    result,
):
    timelines = build_robot_timelines(
        result
    )

    makespan = result["summary"][
        "makespan"
    ]

    frame_times = []

    current_time = 0.0

    while current_time <= makespan:
        frame_times.append(
            current_time
        )

        current_time += FRAME_STEP

    if frame_times[-1] < makespan:
        frame_times.append(
            makespan
        )

    figure, axis = plt.subplots(
        figsize=(13, 8)
    )

    figure.subplots_adjust(
        right=0.72
    )

    draw_warehouse(axis)

    robot_markers = {}
    robot_labels = {}

    for robot_id in sorted(
        ROBOT_START_POSITIONS
    ):
        start_position = (
            ROBOT_START_POSITIONS[
                robot_id
            ]
        )

        marker = axis.scatter(
            start_position[0],
            start_position[1],
            s=220,
            marker="o",
            zorder=5,
            label=f"Robot {robot_id}",
        )

        label = axis.text(
            start_position[0],
            start_position[1] + 0.45,
            f"R{robot_id}",
            ha="center",
            fontsize=9,
            fontweight="bold",
            zorder=6,
        )

        robot_markers[robot_id] = marker
        robot_labels[robot_id] = label

    status_text = figure.text(
        0.74,
        0.90,
        "",
        va="top",
        fontsize=9,
        family="monospace",
    )

    summary_text = figure.text(
        0.74,
        0.28,
        "",
        va="top",
        fontsize=9,
        family="monospace",
    )

    def update(frame_index):
        simulation_time = (
            frame_times[frame_index]
        )

        status_lines = [
            f"Strategy: {strategy}",
            f"Time: {simulation_time:.1f}",
            (
                "Queue length: "
                f"{get_queue_length(result['queue_history'], simulation_time)}"
            ),
            "",
        ]

        for robot_id in sorted(
            timelines
        ):
            state = get_robot_state(
                timelines[robot_id],
                simulation_time,
            )

            x_position, y_position = (
                state["position"]
            )

            robot_markers[
                robot_id
            ].set_offsets(
                [[
                    x_position,
                    y_position,
                ]]
            )

            robot_labels[
                robot_id
            ].set_position(
                (
                    x_position,
                    y_position + 0.45,
                )
            )

            task_text = (
                state["task_id"]
                if state["task_id"]
                else "-"
            )

            rack_text = (
                state["rack_name"]
                if state["rack_name"]
                else "-"
            )

            status_lines.extend(
                [
                    f"Robot {robot_id}",
                    f"  Status: {state['status']}",
                    f"  Task: {task_text}",
                    f"  Rack: {rack_text}",
                    "",
                ]
            )

        status_text.set_text(
            "\n".join(status_lines)
        )

        completed_count = sum(
            1
            for task in result["tasks"]
            if (
                task.completion_time
                <= simulation_time
            )
        )

        summary_text.set_text(
            "\n".join(
                [
                    "Simulation Progress",
                    "-------------------",
                    (
                        f"Completed: "
                        f"{completed_count}/"
                        f"{len(result['tasks'])}"
                    ),
                    (
                        f"Makespan: "
                        f"{makespan:.1f}"
                    ),
                    (
                        "Total distance: "
                        f"{result['summary']['total_distance']:.1f}"
                    ),
                    (
                        "Avg waiting: "
                        f"{result['summary']['average_waiting_time']:.2f}"
                    ),
                ]
            )
        )

        axis.set_title(
            (
                f"{strategy} Warehouse Simulation\n"
                f"Simulation Time = "
                f"{simulation_time:.1f}"
            ),
            fontsize=14,
            fontweight="bold",
        )

        return (
            list(robot_markers.values())
            + list(robot_labels.values())
            + [
                status_text,
                summary_text,
            ]
        )

    animation = FuncAnimation(
        figure,
        update,
        frames=len(frame_times),
        interval=(
            1000
            / ANIMATION_FPS
        ),
        blit=False,
        repeat=True,
    )

    filename = (
        strategy.lower()
        + "_warehouse_animation.gif"
    )

    filepath = os.path.join(
        OUTPUT_FOLDER,
        filename,
    )

    animation.save(
        filepath,
        writer=PillowWriter(
            fps=ANIMATION_FPS
        ),
        dpi=110,
    )

    plt.close(figure)

    print(
        f"Generated: {filepath}"
    )


# =========================================================
# 11. MAIN
# =========================================================

def main():
    create_output_folder()

    print(
        "Generating FIFO animation..."
    )

    fifo_result = run_simulation(
        "FIFO"
    )

    create_animation(
        strategy="FIFO",
        result=fifo_result,
    )

    print(
        "Generating Deferred animation..."
    )

    deferred_result = run_simulation(
        "DEFERRED"
    )

    create_animation(
        strategy="DEFERRED",
        result=deferred_result,
    )

    print()
    print(
        "Both animations were generated successfully."
    )


if __name__ == "__main__":
    main()