import os
import time
from bisect import bisect_right
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, FFMpegWriter
from matplotlib.patches import Rectangle


from simulation import (
    run_simulation,
    INPUT_STATION,
    OUTPUT_STATION,
    ROBOT_SPEED,
    LOAD_TIME,
    STORE_TIME,
    PICK_TIME,
    UNLOAD_TIME,
    manhattan_distance,
    route_waypoints,
)

from scenarios import get_scenario


# =========================================================
# 1. ANIMATION SETTINGS
# =========================================================

OUTPUT_FOLDER = "outputs"

SELECTED_SCENARIO = "retrieval_dominant"  # Options: "baseline", "high_demand", "low_availability", "high_availability", "storage_dominant", "retrieval_dominant"

ANIMATION_FPS = 5
ANIMATION_DPI = 85
FIGURE_SIZE = (10, 6.5)

# Do not generate thousands of frames for long simulations.
MAX_ANIMATION_FRAMES = 300


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

def build_robot_timelines(result,entry_point, exit_point):
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
                    target_position=entry_point,
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
                    target_position=exit_point,
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
# 7. FAST ROBOT STATE LOOKUP
# =========================================================

def prepare_timeline_index(timeline):
    return {
        "segments": timeline,
        "end_times": [
            segment["end_time"]
            for segment in timeline
        ],
    }


def get_robot_state(
    indexed_timeline,
    simulation_time,
):
    segments = indexed_timeline["segments"]
    end_times = indexed_timeline["end_times"]

    if not segments:
        return {
            "position": (0.0, 0.0),
            "status": "Idle",
            "task_id": None,
            "task_type": None,
            "rack_name": None,
        }

    segment_index = bisect_right(
        end_times,
        simulation_time,
    )

    if segment_index >= len(segments):
        segment_index = len(segments) - 1

    segment = segments[segment_index]

    duration = (
        segment["end_time"]
        - segment["start_time"]
    )

    if duration <= 0:
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


# =========================================================
# 8. FAST QUEUE LOOKUP
# =========================================================

def prepare_queue_history(queue_history):
    sorted_history = sorted(
        queue_history,
        key=lambda record: record["time"],
    )

    return (
        [
            record["time"]
            for record in sorted_history
        ],
        [
            record["queue_length"]
            for record in sorted_history
        ],
    )


def get_queue_length(
    queue_times,
    queue_lengths,
    simulation_time,
):
    index = bisect_right(
        queue_times,
        simulation_time,
    ) - 1

    if index < 0:
        return 0

    return queue_lengths[index]


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
    warehouse_rows,
    warehouse_columns,
    rack_positions,
    entry_point,
    exit_point,
    robot_start_positions,
):
    warehouse_rows = int(warehouse_rows)
    warehouse_columns = int(warehouse_columns)

    entry_point = tuple(entry_point)
    exit_point = tuple(exit_point)

    # warehouse display limits and ticks
    axis.set_xlim(-0.6, warehouse_columns - 0.4)
    axis.set_ylim(-0.6, warehouse_rows - 0.1)

    axis.set_xticks(range(warehouse_columns))
    axis.set_yticks(range(warehouse_rows))

    axis.tick_params(labelsize=7,)
    axis.set_aspect("equal", adjustable="box")
    axis.grid(True, alpha=0.18, linewidth=0.6, zorder=0,)

    axis.set_xlabel("Warehouse X Coordinate")
    axis.set_ylabel("Warehouse Y Coordinate")

    # -----------------------------------------------------
    # Group racks by X coordinate
    # -----------------------------------------------------
    rack_columns = {}

    for rack_name, position in rack_positions.items():
        rack_x = float(position[0])
        rack_y = float(position[1])

        rack_columns.setdefault(
            rack_x,
            []
        ).append(
            {
                "name": str(rack_name),
                "x": rack_x,
                "y": rack_y,
            }
        )


    # -----------------------------------------------------
    # Resolve rack layout information
    # -----------------------------------------------------
    sorted_column_x = sorted(
        rack_columns.keys()
    )

    rack_column_count = len(
        sorted_column_x
    )

    rack_row_count = max(
        (
            len(column_racks)
            for column_racks in rack_columns.values()
        ),
        default=1,
    )


    # -----------------------------------------------------
    # Calculate rack dimensions from warehouse layout
    # -----------------------------------------------------
    usable_warehouse_width = max(
        1.0,
        warehouse_columns - 2.0,
    )

    usable_warehouse_height = max(
        1.0,
        warehouse_rows - 2.0,
    )

    # Each rack column receives part of the available width.
    column_slot_width = (
        usable_warehouse_width
        / max(rack_column_count, 1)
    )

    # Each rack section receives part of the available height.
    row_slot_height = (
        usable_warehouse_height
        / max(rack_row_count, 1)
    )

    # Keep visible aisle space between rack columns.
    rack_width = (
        column_slot_width * 0.45
    )

    # Make rack cells fill most of the vertical slot.
    rack_section_height = (
        row_slot_height * 0.82
    )

    # Prevent extreme rack sizes.
    rack_width = max(
        0.30,
        min(
            rack_width,
            1.20,
        ),
    )

    rack_section_height = max(
        0.35,
        min(
            rack_section_height,
            2.00,
        ),
    )


    # -----------------------------------------------------
    # Calculate flexible text size
    # -----------------------------------------------------
    rack_font_size = max(
        7,
        min(
            10,
            rack_width * 10,
            rack_section_height * 6,
        ),
    )

    title_font_size = max(
        8,
        min(
            11,
            rack_width * 10,
        ),
    )


    # -----------------------------------------------------
    # Draw each rack column
    # -----------------------------------------------------
    for column_index, rack_x in enumerate(
        sorted_column_x,
        start=1,
    ):
        column_racks = sorted(
            rack_columns[rack_x],
            key=lambda rack: rack["y"],
            reverse=True,
        )

        # Centre the full rack column around its rack positions.
        y_positions = [
            rack["y"]
            for rack in column_racks
        ]

        top_rack_y = max(y_positions)
        bottom_rack_y = min(y_positions)

        rack_column_bottom = (
            bottom_rack_y
            - rack_section_height / 2
        )

        rack_column_top = (
            top_rack_y
            + rack_section_height / 2
        )

        rack_column_height = (
            rack_column_top
            - rack_column_bottom
        )

        # Draw one outer rack column.
        rack_column_box = Rectangle(
            (
                rack_x - rack_width / 2,
                rack_column_bottom,
            ),
            rack_width,
            rack_column_height,
            facecolor="lightsteelblue",
            edgecolor="black",
            linewidth=1.4,
            zorder=2,
        )

        axis.add_patch(
            rack_column_box
        )

        rack_column_letter = chr(
            64 + column_index
        )

        axis.text(
            rack_x,
            rack_column_top + 0.08,
            f"Rack {rack_column_letter}",
            ha="center",
            va="bottom",
            fontsize=title_font_size,
            fontweight="bold",
            zorder=4,
        )

        # Draw rack names and separators.
        for rack_index, rack in enumerate(
            column_racks
        ):
            rack_y = rack["y"]

            axis.text(
                rack_x,
                rack_y,
                rack["name"],
                ha="center",
                va="center",
                fontsize=rack_font_size,
                fontweight="bold",
                zorder=4,
            )

            if rack_index < len(column_racks) - 1:
                current_y = rack["y"]

                next_y = column_racks[
                    rack_index + 1
                ]["y"]

                separator_y = (
                    current_y + next_y
                ) / 2

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
        
   

    






  

    # Draw input station    
    input_x, input_y = entry_point

    input_box = Rectangle(
        (
            input_x - 0.42,
            input_y - 0.34,
        ),
        0.84,
        0.68,
        facecolor="lightgreen",
        edgecolor="black",
        linewidth=1.2,
        zorder=2,
    )

    axis.add_patch(
        input_box
    )

    axis.text(
        input_x,
        input_y,
        "Input",
        ha="center",
        va="center",
        fontsize=7,
        fontweight="bold",
        zorder=3,
    )


    # Draw output station
    output_x, output_y = exit_point

    output_box = Rectangle(
        (
            output_x - 0.42,
            output_y - 0.34,
        ),
        0.84,
        0.68,
        facecolor="lightgreen",
        edgecolor="black",
        linewidth=1.2,
        zorder=2,
    )

    axis.add_patch(
        output_box
    )

    axis.text(
        output_x,
        output_y,
        "Output",
        ha="center",
        va="center",
        fontsize=7,
        fontweight="bold",
        zorder=3,
    )

    # Draw robot starting positions
    for robot_id, position in sorted(
        robot_start_positions.items()
    ):
        start_x = float(position[0])
        start_y = float(position[1])

        start_box = Rectangle(
            (
                start_x - 0.35,
                start_y - 0.28,
            ),
            0.70,
            0.56,
            facecolor="lemonchiffon",
            edgecolor="black",
            linewidth=1.0,
            zorder=2,
        )

        axis.add_patch(
            start_box
        )

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
# 11. GIF VALIDATION
# =========================================================

def is_valid_mp4(filepath):
    path = Path(filepath)

    return (
        path.exists()
        and path.is_file()
        and path.stat().st_size > 0
    )


# =========================================================
# 12. CREATE ONE ANIMATION
# =========================================================

def create_animation(
    strategy,
    scenario_name,
    result,
    force_rebuild=False,
    output_folder=None,
):
    total_start = time.perf_counter()

    if output_folder is None:
        output_folder = OUTPUT_FOLDER

    scenario = result.get(
        "scenario",
        {}
    )

    warehouse = scenario.get(
        "warehouse",
        {}
    )

    # Use the configured warehouse for custom scenarios.
    # Fall back to the original layout for predefined scenarios.
    warehouse_rows = int(
        warehouse.get(
            "rows",
            7,
        )
    )

    warehouse_columns = int(
        warehouse.get(
            "columns",
            9,
        )
    )

    rack_positions = warehouse.get(
        "rack_positions",
        {
            "A1": (1, 6),
            "A2": (1, 4),
            "A3": (1, 2),
            "B1": (3, 6),
            "B2": (3, 4),
            "B3": (3, 2),
            "C1": (5, 6),
            "C2": (5, 4),
            "C3": (5, 2),
            "D1": (7, 6),
            "D2": (7, 4),
            "D3": (7, 2),
        },
    )

    entry_point = tuple(
        warehouse.get(
            "entry_point",
            INPUT_STATION,
        )
    )

    exit_point = tuple(
        warehouse.get(
            "exit_point",
            OUTPUT_STATION,
        )
    )

    timeline_start = time.perf_counter()

    timelines = build_robot_timelines(
        result,
        entry_point=entry_point,
        exit_point=exit_point,
    )

    timeline_duration = (
        time.perf_counter()
        - timeline_start
    )

    print(
        f"[{strategy}] "
        f"Timeline build time: "
        f"{timeline_duration:.2f} seconds"
    )

    data_prepare_start = time.perf_counter()

    indexed_timelines = {
        robot_id: prepare_timeline_index(timeline)
        for robot_id, timeline in timelines.items()
    }

    queue_times, queue_lengths = prepare_queue_history(
        result["queue_history"]
    )

    completion_times = sorted(
        task.completion_time
        for task in result["tasks"]
    )

    data_prepare_duration = (
        time.perf_counter()
        - data_prepare_start
    )

    print(
        f"[{strategy}] "
        f"Animation data preparation time: "
        f"{data_prepare_duration:.2f} seconds"
    )

    makespan = result["summary"]["makespan"]

    robot_start_positions = dict(
        result["robot_start_positions"]
    )




    # Add any backup/replacement robots created during simulation.
    for robot in result["robots"]:
        if robot.robot_id not in robot_start_positions:
            robot_start_positions[
                robot.robot_id
            ] = robot.starting_position

    scenario_folder = os.path.join(
        output_folder,
        scenario_name,
    )

    create_output_folder(
        scenario_folder
    )

    filename = (
        strategy.lower()
        + "_warehouse_animation.mp4"
    )

    filepath = os.path.join(
        scenario_folder,
        filename,
    )

    # Reuse a valid existing MP4 unless a rebuild is requested.
    if (
        not force_rebuild
        and is_valid_mp4(filepath)
    ):
        print(
            f"Using existing animation: {filepath}"
        )
        return filepath

    if os.path.exists(filepath):
        os.remove(filepath)

    # =====================================================
    # Generate a limited number of animation frames
    # =====================================================
    frame_prepare_start = time.perf_counter()

    if makespan <= 0:
        frame_times = [0.0]
    else:
        frame_count = min(
            MAX_ANIMATION_FRAMES,
            max(
                2,
                int(makespan) + 1,
            ),
        )

        frame_step = (
            makespan
            / (frame_count - 1)
        )

        frame_times = [
            index * frame_step
            for index in range(frame_count)
        ]

        # Make sure final frame is exactly the makespan
        frame_times[-1] = makespan

    
    frame_prepare_duration = (
        time.perf_counter()
        - frame_prepare_start
    )

    print(
        f"[{strategy}] "
        f"Frame preparation time: "
        f"{frame_prepare_duration:.2f} seconds"
    )

    print(
        f"[{strategy}] "
        f"Number of frames: "
        f"{len(frame_times)}"
    )

    figure_start = time.perf_counter()
    figure, axis = plt.subplots(
        figsize=FIGURE_SIZE,
        dpi=ANIMATION_DPI,
        constrained_layout=False,
    )

    figure.subplots_adjust(
        right=0.70
    )

    info_axis = figure.add_axes(
        [
            0.72,
            0.08,
            0.27,
            0.84,
        ]
    )

    info_axis.set_xlim(0, 1)
    info_axis.set_ylim(0, 1)
    info_axis.axis("off")
    
    
    draw_warehouse(
        axis=axis,
        warehouse_rows=warehouse_rows,
        warehouse_columns=warehouse_columns,
        rack_positions=rack_positions,
        entry_point=entry_point,
        exit_point=exit_point,
        robot_start_positions=robot_start_positions,
    )

    robot_markers = {}
    robot_labels = {}

    for robot_id in sorted(robot_start_positions):
        start_position = robot_start_positions[robot_id]

        marker = axis.scatter(
            start_position[0],
            start_position[1],
            s=180,
            marker="o",
            zorder=5,
            label=f"Robot {robot_id}",
        )

        label = axis.text(
            start_position[0],
            start_position[1] + 0.35,
            f"R{robot_id}",
            ha="center",
            fontsize=8,
            fontweight="bold",
            zorder=6,
        )

        robot_markers[robot_id] = marker
        robot_labels[robot_id] = label

    status_text = info_axis.text(
        0.0,
        1.0,
        "",
        transform=info_axis.transAxes,
        ha="left",
        va="top",
        fontsize=8,
        family="monospace",
    )

    summary_text = info_axis.text(
        0.0,
        0.28,
        "",
        transform=info_axis.transAxes,
        ha="left",
        va="top",
        fontsize=8,
        family="monospace",
)
    title_text = axis.set_title(
        "",
        fontsize=12,
        fontweight="bold",
    )

    figure_duration = (
        time.perf_counter()
        - figure_start
    )

    print(
        f"[{strategy}] "
        f"Figure setup time: "
        f"{figure_duration:.2f} seconds"
    )
    
    def update(frame_index):
        simulation_time = frame_times[frame_index]

        queue_length = get_queue_length(
            queue_times,
            queue_lengths,
            simulation_time,
        )

        status_lines = [
            f"Scenario: {scenario_name}",
            f"Strategy: {strategy}",
            f"Time: {simulation_time:.1f}",
            f"Queue length: {queue_length}",
            "",
        ]

        for robot_id in sorted(indexed_timelines):
            state = get_robot_state(
                indexed_timelines[robot_id],
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
                    (
                        f"Robot {robot_id}: "
                        f"{state['status']}"
                    ),
                    (
                        f"  Task {task_text} | "
                        f"Rack {rack_text}"
                    ),
                ]
            )

        status_text.set_text(
            "\n".join(status_lines)
        )

        completed_count = bisect_right(
            completion_times,
            simulation_time,
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

        title_text.set_text(
            (
                f"{result['summary']['scenario_name']} - {strategy}\n"
                f"Simulation Time = {simulation_time:.1f}"
            )
        )

        return (
            list(robot_markers.values())
            + list(robot_labels.values())
            + [
                status_text,
                summary_text,
                title_text,
            ]
        )

    animation = FuncAnimation(
        figure,
        update,
        frames=len(frame_times),
        interval=1000 / ANIMATION_FPS,
        blit=True,
        repeat=True,
        cache_frame_data=False,
    )

    temporary_filepath = os.path.join(
        scenario_folder,
        strategy.lower()
        + "_warehouse_animation_temp.mp4",
    )

    if os.path.exists(temporary_filepath):
        os.remove(temporary_filepath)

    save_start = time.perf_counter()


    try:
        writer = FFMpegWriter(
            fps=ANIMATION_FPS,
            codec="libx264",
            extra_args=[
                "-preset",
                "ultrafast",  #very fast, faster, fast, medium, slow, slower, veryslow
                "-pix_fmt",
                "yuv420p",
            ],
        )

        animation.save(
            temporary_filepath,
            writer=writer,
            dpi=ANIMATION_DPI,
        )

        if not is_valid_mp4(
            temporary_filepath
        ):
            raise RuntimeError(
                "Animation generation produced "
                "an invalid video."
            )

        os.replace(
            temporary_filepath,
            filepath,
        )

    finally:
        if os.path.exists(temporary_filepath):
            os.remove(temporary_filepath)

        plt.close(figure)

    save_duration = time.perf_counter() - save_start

    print(
        f"Generated: {filepath}"
    )

    print(
        f"[{strategy}] "
        f"Video rendering + encoding time: "
        f"{save_duration:.2f} seconds"
    )

    total_duration = (
        time.perf_counter()
        - total_start
    )

    print()
    print(
        f"[{strategy}] "
        f"TOTAL animation generation time: "
        f"{total_duration:.2f} seconds"
    )
    print("-" * 60)

    return filepath


# =========================================================
# 13. MAIN
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