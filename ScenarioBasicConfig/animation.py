import os

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter
from matplotlib.patches import Rectangle

from simulation import (
    run_simulation,
    INPUT_STATION,
    OUTPUT_STATION,
    RACK_POSITIONS,
    ROBOT_SPEED,
    LOAD_TIME,
    STORE_TIME,
    PICK_TIME,
    UNLOAD_TIME,
    ACCESS_OFFSET,
    CORRIDOR_Y,
    manhattan_distance,
    route_waypoints,
)

from scenarios import get_scenario


# =========================================================
# 1. ANIMATION SETTINGS
# =========================================================

OUTPUT_FOLDER = "outputs"

SELECTED_SCENARIO = "retrieval_dominant"  # Options: "baseline", "high_demand", "low_availability", "high_availability", "storage_dominant", "retrieval_dominant"

FRAME_STEP = 0.5
ANIMATION_FPS = 4

GRID_MIN_X = -0.5
GRID_MAX_X = 8.5

GRID_MIN_Y = -0.8
GRID_MAX_Y = 7.0

GRID_STEP = 0.5


# =========================================================
# 2. OUTPUT FOLDER
# =========================================================

def create_output_folder(folder_path):
    os.makedirs(
        folder_path,
        exist_ok=True,
    )


# =========================================================
# 3. TIMELINE SEGMENT
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
# 4. APPEND AISLE-SAFE TRAVEL SEGMENTS
# =========================================================

def append_travel_segments(
    segments,
    current_time,
    current_position,
    target_position,
    status,
    task,
):
    waypoints = route_waypoints(
        current_position,
        target_position,
    )

    leg_distance = sum(
        manhattan_distance(
            point_a,
            point_b,
        )
        for point_a, point_b in zip(
            waypoints,
            waypoints[1:],
        )
    )

    if leg_distance == 0:
        return current_time, target_position

    leg_duration = (
        leg_distance / ROBOT_SPEED
    )

    for point_a, point_b in zip(
        waypoints,
        waypoints[1:],
    ):
        hop_distance = manhattan_distance(
            point_a,
            point_b,
        )

        if hop_distance == 0:
            continue

        hop_duration = (
            leg_duration
            * hop_distance
            / leg_distance
        )

        segments.append(
            create_segment(
                start_time=current_time,
                end_time=current_time + hop_duration,
                start_position=point_a,
                end_position=point_b,
                status=status,
                task_id=task.task_id,
                task_type=task.task_type,
                rack_name=task.rack_name,
            )
        )

        current_time += hop_duration

    return current_time, target_position


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
                current_time, current_position = append_travel_segments(
                    segments=segments,
                    current_time=current_time,
                    current_position=current_position,
                    target_position=INPUT_STATION,
                    status="Moving to input",
                    task=task,
                )

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

                current_time, current_position = append_travel_segments(
                    segments=segments,
                    current_time=current_time,
                    current_position=current_position,
                    target_position=task.rack_access_position,
                    status=f"Moving to Rack {task.rack_name} access point",
                    task=task,
                )

                segments.append(
                    create_segment(
                        start_time=current_time,
                        end_time=current_time + STORE_TIME,
                        start_position=current_position,
                        end_position=current_position,
                        status=f"Storing at Rack {task.rack_name} access point",
                        task_id=task.task_id,
                        task_type=task.task_type,
                        rack_name=task.rack_name,
                    )
                )

                current_time += STORE_TIME

            elif task.task_type == "retrieval":
                current_time, current_position = append_travel_segments(
                    segments=segments,
                    current_time=current_time,
                    current_position=current_position,
                    target_position=task.rack_access_position,
                    status=f"Moving to Rack {task.rack_name} access point",
                    task=task,
                )

                segments.append(
                    create_segment(
                        start_time=current_time,
                        end_time=current_time + PICK_TIME,
                        start_position=current_position,
                        end_position=current_position,
                        status=f"Retrieving from Rack {task.rack_name} access point",
                        task_id=task.task_id,
                        task_type=task.task_type,
                        rack_name=task.rack_name,
                    )
                )

                current_time += PICK_TIME

                current_time, current_position = append_travel_segments(
                    segments=segments,
                    current_time=current_time,
                    current_position=current_position,
                    target_position=OUTPUT_STATION,
                    status="Moving to output",
                    task=task,
                )

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

            else:
                raise ValueError(
                    f"Invalid task type: {task.task_type}"
                )

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
# 6. INTERPOLATION
# =========================================================

def interpolate_segment(
    start_position,
    end_position,
    progress,
):
    start_x, start_y = start_position
    end_x, end_y = end_position

    return (
        start_x + (end_x - start_x) * progress,
        start_y + (end_y - start_y) * progress,
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
            index == len(timeline) - 1
        )

        within_segment = (
            segment["start_time"]
            <= simulation_time
            < segment["end_time"]
        )

        if (
            is_last_segment
            and simulation_time == segment["end_time"]
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

            position = interpolate_segment(
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
        "position": final_segment["end_position"],
        "status": "Idle",
        "task_id": None,
        "task_type": None,
        "rack_name": None,
    }


# =========================================================
# 8. QUEUE LENGTH
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
# 9. GRID TICKS
# =========================================================

def _grid_ticks(minimum, maximum, step):
    ticks = []

    value = round(minimum / step) * step

    while value <= maximum + 1e-9:
        ticks.append(round(value, 2))
        value += step

    return ticks


# =========================================================
# 10. DRAW WAREHOUSE
# =========================================================

def draw_warehouse(
    axis,
    robot_start_positions,
):
    axis.set_xlim(
        GRID_MIN_X,
        GRID_MAX_X,
    )

    axis.set_ylim(
        GRID_MIN_Y,
        GRID_MAX_Y,
    )

    axis.set_xticks(
        _grid_ticks(
            GRID_MIN_X,
            GRID_MAX_X,
            GRID_STEP,
        )
    )

    axis.set_yticks(
        _grid_ticks(
            GRID_MIN_Y,
            GRID_MAX_Y,
            GRID_STEP,
        )
    )

    axis.tick_params(
        labelsize=7,
    )

    axis.set_aspect(
        "equal",
        adjustable="box",
    )

    axis.grid(
        True,
        alpha=0.18,
        linewidth=0.6,
    )

    axis.set_xlabel(
        "Warehouse X Coordinate"
    )

    axis.set_ylabel(
        "Warehouse Y Coordinate"
    )

    # -----------------------------------------------------
    # Long rack columns: Rack A, B, C, D
    # Each rack column contains zones 1, 2, 3.
    # -----------------------------------------------------
    rack_columns = {
        "A": 1,
        "B": 3,
        "C": 5,
        "D": 7,
    }

    zone_y_positions = {
        "1": 6,
        "2": 4,
        "3": 2,
    }

    rack_width = 0.70
    rack_bottom = 1.55
    rack_height = 4.90

    for rack_letter, rack_x in rack_columns.items():
        rack_column = Rectangle(
            (
                rack_x - rack_width / 2,
                rack_bottom,
            ),
            rack_width,
            rack_height,
            facecolor="lightsteelblue",
            edgecolor="black",
            linewidth=1.4,
            zorder=2,
        )

        axis.add_patch(
            rack_column
        )

        axis.text(
            rack_x,
            rack_bottom + rack_height + 0.15,
            f"Rack {rack_letter}",
            ha="center",
            va="bottom",
            fontsize=9,
            fontweight="bold",
            zorder=3,
        )

        for separator_y in [5, 3]:
            axis.plot(
                [
                    rack_x - rack_width / 2,
                    rack_x + rack_width / 2,
                ],
                [
                    separator_y,
                    separator_y,
                ],
                color="black",
                linewidth=1.0,
                zorder=3,
            )

        for zone_number, zone_y in zone_y_positions.items():
            rack_name = f"{rack_letter}{zone_number}"

            axis.text(
                rack_x,
                zone_y,
                rack_name,
                ha="center",
                va="center",
                fontsize=9,
                fontweight="bold",
                zorder=4,
            )

    # -----------------------------------------------------
    # Input station
    # -----------------------------------------------------
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
        zorder=2,
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
        zorder=3,
    )

    # -----------------------------------------------------
    # Output station
    # -----------------------------------------------------
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
        zorder=2,
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
        zorder=3,
    )

    # -----------------------------------------------------
    # Robot start points
    # -----------------------------------------------------
    for robot_id, position in robot_start_positions.items():
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
            zorder=2,
        )

        axis.add_patch(start_box)

        axis.text(
            start_x,
            start_y,
            f"Start {robot_id}",
            ha="center",
            va="center",
            fontsize=8,
            zorder=3,
        )


# =========================================================
# 11. CREATE ONE ANIMATION
# =========================================================

def create_animation(
    strategy,
    scenario_name,
    result,
):
    timelines = build_robot_timelines(
        result
    )

    makespan = result["summary"]["makespan"]

    robot_start_positions = result[
        "robot_start_positions"
    ]

    frame_times = []

    current_time = 0.0

    while current_time <= makespan:
        frame_times.append(current_time)
        current_time += FRAME_STEP

    if frame_times[-1] < makespan:
        frame_times.append(makespan)

    figure, axis = plt.subplots(
        figsize=(13, 8)
    )

    figure.subplots_adjust(
        right=0.72
    )

    draw_warehouse(
        axis,
        robot_start_positions,
    )

    robot_markers = {}
    robot_labels = {}

    for robot_id in sorted(robot_start_positions):
        start_position = robot_start_positions[robot_id]

        marker = axis.scatter(
            start_position[0],
            start_position[1],
            s=150,
            marker="o",
            zorder=5,
            label=f"Robot {robot_id}",
        )

        label = axis.text(
            start_position[0],
            start_position[1] + 0.35,
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
        0.25,
        "",
        va="top",
        fontsize=9,
        family="monospace",
    )

    def update(frame_index):
        simulation_time = frame_times[frame_index]

        status_lines = [
            f"Scenario: {scenario_name}",
            f"Strategy: {strategy}",
            f"Time: {simulation_time:.1f}",
            (
                "Queue length: "
                f"{get_queue_length(result['queue_history'], simulation_time)}"
            ),
            "",
        ]

        for robot_id in sorted(timelines):
            state = get_robot_state(
                timelines[robot_id],
                simulation_time,
            )

            x_position, y_position = state["position"]

            robot_markers[robot_id].set_offsets(
                [[x_position, y_position]]
            )

            robot_labels[robot_id].set_position(
                (
                    x_position,
                    y_position + 0.35,
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
            if task.completion_time <= simulation_time
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
                    f"Makespan: {makespan:.1f}",
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
                f"{result['summary']['scenario_name']} - {strategy}\n"
                f"Simulation Time = {simulation_time:.1f}"
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
        interval=1000 / ANIMATION_FPS,
        blit=False,
        repeat=True,
    )

    scenario_folder = os.path.join(
        OUTPUT_FOLDER,
        scenario_name,
    )

    create_output_folder(
        scenario_folder
    )

    filename = (
        strategy.lower()
        + "_warehouse_animation.gif"
    )

    filepath = os.path.join(
        scenario_folder,
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
# 12. MAIN
# =========================================================

def main():
    scenario_name = SELECTED_SCENARIO

    scenario = get_scenario(
        scenario_name
    )

    print()
    print("=" * 80)
    print(
        f"Generating animations for: {scenario['name']}"
    )
    print("=" * 80)

    fifo_result = run_simulation(
        "FIFO",
        scenario_name,
    )

    create_animation(
        strategy="FIFO",
        scenario_name=scenario_name,
        result=fifo_result,
    )

    deferred_result = run_simulation(
        "DEFERRED",
        scenario_name,
    )

    create_animation(
        strategy="DEFERRED",
        scenario_name=scenario_name,
        result=deferred_result,
    )

    print()
    print(
        "Scenario animations were generated successfully."
    )


if __name__ == "__main__":
    main()