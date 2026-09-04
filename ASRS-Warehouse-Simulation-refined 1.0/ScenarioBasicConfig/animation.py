# =========================================================
# animation.py
# Refined AS/RS warehouse animation generation
# =========================================================

from __future__ import annotations

import hashlib
import json
import math
import os
import time
from bisect import bisect_right
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
from matplotlib.animation import (
    FFMpegWriter,
    FuncAnimation,
    PillowWriter,
    writers,
)
from matplotlib.patches import Rectangle
from PIL import Image

try:
    from .simulation import (
        ACCESS_OFFSET,
        INPUT_STATION,
        LOAD_TIME,
        OUTPUT_STATION,
        PICK_TIME,
        RACK_HALF_WIDTH,
        ROBOT_SPEED,
        STORE_TIME,
        UNLOAD_TIME,
        manhattan_distance,
        route_waypoints,
        run_simulation,
    )
    from .scenarios import get_scenario
except ImportError:
    from simulation import (
        ACCESS_OFFSET,
        INPUT_STATION,
        LOAD_TIME,
        OUTPUT_STATION,
        PICK_TIME,
        RACK_HALF_WIDTH,
        ROBOT_SPEED,
        STORE_TIME,
        UNLOAD_TIME,
        manhattan_distance,
        route_waypoints,
        run_simulation,
    )
    from scenarios import get_scenario


# =========================================================
# 1. GLOBAL SETTINGS
# =========================================================

OUTPUT_FOLDER = "outputs"
SELECTED_SCENARIO = "baseline"

# Increment this whenever animation layout / lifecycle rendering changes.
# It prevents an old cached video from being reused after animation code
# has been refined while the underlying simulation result is unchanged.
ANIMATION_RENDER_VERSION = "v8_exact_simulation_steps"

# Fixed visualization time scale.
#
# Every scenario and every quality level uses the same playback meaning:
#     3 simulation time units = 1 second of video.
#
# Quality controls visual smoothness and image quality, not simulation speed.
# The number of rendered frames is calculated from the expected video
# duration so a large custom scenario does not become visibly jumpy simply
# because it has a larger makespan.
PLAYBACK_SIM_UNITS_PER_SECOND = 3.0

ANIMATION_QUALITY = {
    "fast": {
        "visual_fps": 1.0,
        "dpi": 100,
        "figure_size": (10.24, 5.76),   # about 1024 x 576
        "bitrate": 1800,
    },
    "standard": {
        "visual_fps": 2.0,
        "dpi": 100,
        "figure_size": (12.8, 7.2),    # about 1280 x 720
        "bitrate": 3000,
    },
    "detailed": {
        "visual_fps": 3.0,
        "dpi": 120,
        "figure_size": (14.4, 8.1),    # about 1728 x 972
        "bitrate": 4500,
    },
}

DEFAULT_QUALITY = "standard"
PREFERRED_FORMAT = "mp4"

# Right-side information panel. Keeping it separate from the warehouse axes
# prevents robot status and progress information from overlapping the plot.
WAREHOUSE_RIGHT = 0.69
INFO_LEFT = 0.72
INFO_WIDTH = 0.265


# =========================================================
# 2. OUTPUT / CACHE HELPERS
# =========================================================

def create_output_folder(folder_path: str | os.PathLike[str]) -> None:
    os.makedirs(folder_path, exist_ok=True)


def _serialise_tasks(result: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    for task in result.get("tasks", []):
        records.append(
            {
                "task_id": str(task.task_id),
                "task_type": str(task.task_type),
                "arrival_time": float(task.arrival_time),
                "rack_name": str(task.rack_name),
                "start_time": (
                    None
                    if task.start_time is None
                    else float(task.start_time)
                ),
                "completion_time": (
                    None
                    if task.completion_time is None
                    else float(task.completion_time)
                ),
                "robot_id": (
                    None
                    if task.robot_id is None
                    else int(task.robot_id)
                ),
                "rack_access_request_time": (
                    None
                    if getattr(
                        task,
                        "rack_access_request_time",
                        None,
                    ) is None
                    else float(task.rack_access_request_time)
                ),
                "rack_access_granted_time": (
                    None
                    if getattr(
                        task,
                        "rack_access_granted_time",
                        None,
                    ) is None
                    else float(task.rack_access_granted_time)
                ),
                "rack_access_wait_time": float(
                    getattr(
                        task,
                        "rack_access_wait_time",
                        0.0,
                    )
                ),
                "travel_distance": float(task.travel_distance),
            }
        )

    return records


def create_configuration_hash(
    scenario_name: str,
    result: dict[str, Any],
) -> str:
    """Create a result-aware cache identifier.

    The old animation cache key mostly represented inputs. This version also
    includes task assignments/timing and key lifecycle information, so a
    changed simulation result is much less likely to reuse a stale video.
    """
    warehouse = result.get("warehouse", {})
    scenario = result.get("scenario", {})
    summary = result.get("summary", {})

    robots_data = []
    for robot in result.get("robots", []):
        robots_data.append(
            {
                "robot_id": int(robot.robot_id),
                "starting_position": list(robot.starting_position),
                "is_standby": bool(
                    getattr(robot, "is_standby", False)
                ),
            }
        )

    hash_data = {
        "render_version": ANIMATION_RENDER_VERSION,
        "playback_sim_units_per_second": (
            PLAYBACK_SIM_UNITS_PER_SECOND
        ),
        "scenario_name": str(scenario_name),
        "scenario": scenario,
        "warehouse": warehouse,
        "tasks": _serialise_tasks(result),
        "robots": robots_data,
        "summary": {
            "makespan": summary.get("makespan"),
            "total_distance": summary.get("total_distance"),
            "average_waiting_time": summary.get(
                "average_waiting_time"
            ),
        },
    }

    encoded = json.dumps(
        hash_data,
        sort_keys=True,
        default=str,
    ).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()[:12]


# =========================================================
# 3. LIFECYCLE CONFIGURATION
# =========================================================

def get_lifecycle_configuration(
    result: dict[str, Any],
) -> dict[str, Any]:
    scenario = result.get("scenario", {})
    warehouse = result.get("warehouse", {})

    failure_config = scenario.get("robot_failure", {}) or {}
    failure_enabled = bool(failure_config.get("enabled", False))

    failed_robot_id = None
    failure_time = None

    if failure_enabled:
        raw_robot_id = failure_config.get("robot_id")
        raw_failure_time = failure_config.get("failure_time")

        if raw_robot_id is not None:
            failed_robot_id = int(raw_robot_id)

        if raw_failure_time is not None:
            failure_time = float(raw_failure_time)

    standby_enabled = bool(
        warehouse.get(
            "standby_robot_enabled",
            (scenario.get("standby_robot", {}) or {}).get(
                "enabled",
                False,
            ),
        )
    )

    standby_robot_id = warehouse.get("standby_robot_id")
    if standby_robot_id is not None:
        standby_robot_id = int(standby_robot_id)

    standby_activation_time = warehouse.get(
        "standby_activation_time"
    )

    if standby_activation_time is None and standby_enabled:
        standby_config = scenario.get("standby_robot", {}) or {}
        raw_delay = standby_config.get("activation_delay")

        if (
            failure_time is not None
            and raw_delay is not None
        ):
            standby_activation_time = (
                failure_time + float(raw_delay)
            )

    if standby_activation_time is not None:
        standby_activation_time = float(standby_activation_time)

    return {
        "failure_enabled": failure_enabled,
        "failed_robot_id": failed_robot_id,
        "failure_time": failure_time,
        "standby_enabled": standby_enabled,
        "standby_robot_id": standby_robot_id,
        "standby_activation_time": standby_activation_time,
    }


# =========================================================
# 4. TIMELINE SEGMENTS
# =========================================================

def create_segment(
    start_time: float,
    end_time: float,
    start_position: tuple[float, float],
    end_position: tuple[float, float],
    status: str,
    task_id: str | None = None,
    task_type: str | None = None,
    rack_name: str | None = None,
) -> dict[str, Any]:
    return {
        "start_time": float(start_time),
        "end_time": float(end_time),
        "start_position": tuple(start_position),
        "end_position": tuple(end_position),
        "status": str(status),
        "task_id": task_id,
        "task_type": task_type,
        "rack_name": rack_name,
    }


def append_travel_segments(
    segments: list[dict[str, Any]],
    current_time: float,
    current_position: tuple[float, float],
    target_position: tuple[float, float],
    status: str,
    task: Any,
    corridor_y: float = 0.0,
    robot_speed: float = ROBOT_SPEED,
) -> tuple[float, tuple[float, float]]:
    waypoints = route_waypoints(
        current_position,
        target_position,
        corridor_y=corridor_y,
    )

    leg_distance = sum(
        manhattan_distance(point_a, point_b)
        for point_a, point_b in zip(
            waypoints,
            waypoints[1:],
        )
    )

    if leg_distance <= 0:
        return current_time, tuple(target_position)

    leg_duration = leg_distance / robot_speed

    for point_a, point_b in zip(
        waypoints,
        waypoints[1:],
    ):
        hop_distance = manhattan_distance(
            point_a,
            point_b,
        )

        if hop_distance <= 0:
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

    return current_time, tuple(target_position)


# =========================================================
# 5. BUILD ROBOT TIMELINES
# =========================================================

def build_robot_timelines(
    result: dict[str, Any],
    entry_point: tuple[float, float],
    exit_point: tuple[float, float],
    corridor_y: float = 0.0,
    robot_speed: float = ROBOT_SPEED,
) -> dict[int, list[dict[str, Any]]]:
    makespan = float(result["summary"]["makespan"])
    timelines: dict[int, list[dict[str, Any]]] = {}

    for robot in result.get("robots", []):
        robot_tasks = sorted(
            [
                task
                for task in result.get("tasks", [])
                if task.robot_id == robot.robot_id
            ],
            key=lambda task: (
                float(task.start_time)
                if task.start_time is not None
                else math.inf
            ),
        )

        segments: list[dict[str, Any]] = []
        current_time = 0.0
        current_position = tuple(robot.starting_position)

        for task in robot_tasks:
            if task.start_time is None:
                continue

            task_start = float(task.start_time)

            if current_time < task_start:
                segments.append(
                    create_segment(
                        start_time=current_time,
                        end_time=task_start,
                        start_position=current_position,
                        end_position=current_position,
                        status="Idle",
                    )
                )

            current_time = task_start

            if task.task_type == "storage":
                current_time, current_position = append_travel_segments(
                    segments=segments,
                    current_time=current_time,
                    current_position=current_position,
                    target_position=entry_point,
                    status="Moving to input",
                    task=task,
                    corridor_y=corridor_y,
                    robot_speed=robot_speed,
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

                rack_granted_time = getattr(
                    task,
                    "rack_access_granted_time",
                    None,
                )

                if (
                    rack_granted_time is not None
                    and float(rack_granted_time) > current_time
                ):
                    segments.append(
                        create_segment(
                            start_time=current_time,
                            end_time=float(rack_granted_time),
                            start_position=current_position,
                            end_position=current_position,
                            status=(
                                f"Waiting for Rack "
                                f"{task.rack_name} access"
                            ),
                            task_id=task.task_id,
                            task_type=task.task_type,
                            rack_name=task.rack_name,
                        )
                    )
                    current_time = float(
                        rack_granted_time
                    )

                current_time, current_position = append_travel_segments(
                    segments=segments,
                    current_time=current_time,
                    current_position=current_position,
                    target_position=task.rack_access_position,
                    status=f"Moving to Rack {task.rack_name}",
                    task=task,
                    corridor_y=corridor_y,
                    robot_speed=robot_speed,
                )

                segments.append(
                    create_segment(
                        start_time=current_time,
                        end_time=current_time + STORE_TIME,
                        start_position=current_position,
                        end_position=current_position,
                        status=f"Storing at Rack {task.rack_name}",
                        task_id=task.task_id,
                        task_type=task.task_type,
                        rack_name=task.rack_name,
                    )
                )
                current_time += STORE_TIME

            elif task.task_type == "retrieval":
                rack_granted_time = getattr(
                    task,
                    "rack_access_granted_time",
                    None,
                )

                if (
                    rack_granted_time is not None
                    and float(rack_granted_time) > current_time
                ):
                    segments.append(
                        create_segment(
                            start_time=current_time,
                            end_time=float(rack_granted_time),
                            start_position=current_position,
                            end_position=current_position,
                            status=(
                                f"Waiting for Rack "
                                f"{task.rack_name} access"
                            ),
                            task_id=task.task_id,
                            task_type=task.task_type,
                            rack_name=task.rack_name,
                        )
                    )
                    current_time = float(
                        rack_granted_time
                    )

                current_time, current_position = append_travel_segments(
                    segments=segments,
                    current_time=current_time,
                    current_position=current_position,
                    target_position=task.rack_access_position,
                    status=f"Moving to Rack {task.rack_name}",
                    task=task,
                    corridor_y=corridor_y,
                    robot_speed=robot_speed,
                )

                segments.append(
                    create_segment(
                        start_time=current_time,
                        end_time=current_time + PICK_TIME,
                        start_position=current_position,
                        end_position=current_position,
                        status=f"Retrieving from Rack {task.rack_name}",
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
                    corridor_y=corridor_y,
                    robot_speed=robot_speed,
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

        # A zero-duration simulation or a robot with no task may otherwise
        # have an empty timeline. Preserve its staging position.
        if not segments:
            segments.append(
                create_segment(
                    start_time=0.0,
                    end_time=max(makespan, 0.000001),
                    start_position=current_position,
                    end_position=current_position,
                    status="Idle",
                )
            )

        timelines[int(robot.robot_id)] = segments

    return timelines


# =========================================================
# 6. INTERPOLATION / FAST LOOKUP
# =========================================================

def interpolate_segment(
    start_position: tuple[float, float],
    end_position: tuple[float, float],
    progress: float,
) -> tuple[float, float]:
    start_x, start_y = start_position
    end_x, end_y = end_position

    return (
        start_x + (end_x - start_x) * progress,
        start_y + (end_y - start_y) * progress,
    )


def prepare_timeline_index(
    timeline: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "segments": timeline,
        "end_times": [
            segment["end_time"]
            for segment in timeline
        ],
    }


def _base_robot_state(
    indexed_timeline: dict[str, Any],
    simulation_time: float,
) -> dict[str, Any]:
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

    progress = max(0.0, min(1.0, progress))

    return {
        "position": interpolate_segment(
            segment["start_position"],
            segment["end_position"],
            progress,
        ),
        "status": segment["status"],
        "task_id": segment["task_id"],
        "task_type": segment["task_type"],
        "rack_name": segment["rack_name"],
    }


def get_robot_state(
    indexed_timeline: dict[str, Any],
    simulation_time: float,
    robot_id: int,
    lifecycle: dict[str, Any],
) -> dict[str, Any]:
    """Return movement state plus failure / standby lifecycle state."""
    state = _base_robot_state(
        indexed_timeline,
        simulation_time,
    )
    state["lifecycle"] = "normal"

    standby_robot_id = lifecycle.get("standby_robot_id")
    standby_activation_time = lifecycle.get(
        "standby_activation_time"
    )

    if (
        lifecycle.get("standby_enabled")
        and standby_robot_id == robot_id
        and standby_activation_time is not None
        and simulation_time < standby_activation_time
    ):
        state["status"] = "Standby"
        state["task_id"] = None
        state["task_type"] = None
        state["rack_name"] = None
        state["lifecycle"] = "standby"
        return state

    failed_robot_id = lifecycle.get("failed_robot_id")
    failure_time = lifecycle.get("failure_time")

    if (
        lifecycle.get("failure_enabled")
        and failed_robot_id == robot_id
        and failure_time is not None
        and simulation_time >= failure_time
    ):
        # The simulation deliberately lets an already-started task finish.
        # Distinguish that period from the final permanently unavailable state.
        if state.get("task_id") is not None and state.get("status") != "Idle":
            state["lifecycle"] = "failed_finishing"
            state["status"] = "Failure detected - finishing task"
        else:
            state["lifecycle"] = "failed"
            state["status"] = "FAILED / unavailable"
            state["task_id"] = None
            state["task_type"] = None
            state["rack_name"] = None

    return state


# =========================================================
# 7. QUEUE LOOKUP
# =========================================================

def prepare_queue_history(
    queue_history: list[dict[str, Any]],
) -> tuple[list[float], list[int]]:
    sorted_history = sorted(
        queue_history,
        key=lambda record: record["time"],
    )

    return (
        [float(record["time"]) for record in sorted_history],
        [int(record["queue_length"]) for record in sorted_history],
    )


def get_queue_length(
    queue_times: list[float],
    queue_lengths: list[int],
    simulation_time: float,
) -> int:
    index = bisect_right(
        queue_times,
        simulation_time,
    ) - 1

    if index < 0:
        return 0

    return queue_lengths[index]


# =========================================================
# 8. STRICT FRAME CAP
# =========================================================

def create_frame_times(
    makespan: float,
    visual_fps: float,
    simulation_units_per_second: float = (
        PLAYBACK_SIM_UNITS_PER_SECOND
    ),
) -> list[float]:
    """
    Create frame timestamps using an exact simulation-time increment.

    The increment is:

        simulation_units_per_second / visual_fps

    With the current playback scale of 3 simulation units per second:

        Fast     (1 FPS) -> 3.0 simulation units per frame
        Standard (2 FPS) -> 1.5 simulation units per frame
        Detailed (3 FPS) -> 1.0 simulation unit per frame

    This keeps the animation clock visually consistent across scenarios.
    Only the final frame may use a shorter interval so the animation lands
    exactly on the simulation makespan.
    """
    makespan = float(makespan)
    visual_fps = float(visual_fps)
    simulation_units_per_second = float(
        simulation_units_per_second
    )

    if makespan <= 0:
        return [0.0]

    if visual_fps <= 0:
        raise ValueError(
            "visual_fps must be greater than 0."
        )

    if simulation_units_per_second <= 0:
        raise ValueError(
            "simulation_units_per_second must be greater than 0."
        )

    frame_step = (
        simulation_units_per_second
        / visual_fps
    )

    frame_times = [0.0]
    current_time = frame_step

    while current_time < makespan:
        frame_times.append(
            round(current_time, 10)
        )
        current_time += frame_step

    # Always include the exact final simulation makespan.
    if not math.isclose(
        frame_times[-1],
        makespan,
        rel_tol=1e-9,
        abs_tol=1e-9,
    ):
        frame_times.append(
            makespan
        )

    return frame_times


def calculate_playback_fps(
    frame_times: list[float],
    makespan: float,
    simulation_units_per_second: float = (
        PLAYBACK_SIM_UNITS_PER_SECOND
    ),
) -> float:
    """
    Calculate the encoder FPS so the final video follows the fixed playback
    scale exactly.

    The rendered frame count is chosen from the quality preset's target
    visual FPS. The encoder FPS may differ slightly from that target because
    the final frame must land exactly on the simulation makespan.
    """
    makespan = float(makespan)
    simulation_units_per_second = float(
        simulation_units_per_second
    )

    if simulation_units_per_second <= 0:
        raise ValueError(
            "simulation_units_per_second must be greater than 0."
        )

    if makespan <= 0 or len(frame_times) <= 1:
        return 1.0

    target_video_duration = (
        makespan
        / simulation_units_per_second
    )

    if target_video_duration <= 0:
        return 1.0

    # There are N-1 intervals between N rendered frames.
    return (
        (len(frame_times) - 1)
        / target_video_duration
    )


# =========================================================
# 9. WAREHOUSE DRAWING
# =========================================================

def _minimum_spacing(values: list[float], fallback: float) -> float:
    unique = sorted(set(float(value) for value in values))

    if len(unique) < 2:
        return fallback

    return min(
        b - a
        for a, b in zip(unique, unique[1:])
        if b > a
    )


def draw_warehouse(
    axis: Any,
    warehouse_rows: int,
    warehouse_columns: int,
    rack_positions: dict[str, tuple[float, float]],
    entry_point: tuple[float, float],
    exit_point: tuple[float, float],
    robot_start_positions: dict[int, tuple[float, float]],
    standby_robot_id: int | None = None,
) -> None:
    warehouse_rows = int(warehouse_rows)
    warehouse_columns = int(warehouse_columns)

    entry_point = tuple(map(float, entry_point))
    exit_point = tuple(map(float, exit_point))

    # Extra top margin is intentional. Rack column headings no longer collide
    # with the plot border or with the figure title.
    axis.set_xlim(
        -0.75,
        warehouse_columns - 0.25,
    )
    axis.set_ylim(
        -0.75,
        warehouse_rows + 0.75,
    )

    axis.set_xticks(range(warehouse_columns))
    axis.set_yticks(range(warehouse_rows))
    axis.tick_params(labelsize=7)
    axis.set_aspect("equal", adjustable="box")
    axis.grid(
        True,
        alpha=0.16,
        linewidth=0.6,
        zorder=0,
    )
    axis.set_xlabel(
        "Warehouse X Coordinate",
        fontsize=9,
        labelpad=6,
    )
    axis.set_ylabel(
        "Warehouse Y Coordinate",
        fontsize=9,
        labelpad=6,
    )

    # -----------------------------------------------------
    # Group racks by x coordinate
    # -----------------------------------------------------
    rack_columns: dict[float, list[dict[str, Any]]] = {}

    for rack_name, position in rack_positions.items():
        rack_x = float(position[0])
        rack_y = float(position[1])

        rack_columns.setdefault(rack_x, []).append(
            {
                "name": str(rack_name),
                "x": rack_x,
                "y": rack_y,
            }
        )

    sorted_column_x = sorted(rack_columns.keys())

    all_y = [
        float(position[1])
        for position in rack_positions.values()
    ]

    row_spacing = _minimum_spacing(
        all_y,
        fallback=2.0,
    )

    # Match the simulation's actual rack half-width. The previous animation
    # could draw racks wider than the physical model, making an access point
    # at rack_x - ACCESS_OFFSET appear to sit inside the rack.
    rack_width = max(
        0.45,
        2.0 * float(RACK_HALF_WIDTH),
    )
    rack_section_height = max(
        0.65,
        min(1.65, row_spacing * 0.78),
    )

    rack_font_size = 8 if len(rack_positions) <= 25 else 7
    rack_header_font_size = 9 if len(sorted_column_x) <= 4 else 8

    for column_index, rack_x in enumerate(
        sorted_column_x,
        start=1,
    ):
        column_racks = sorted(
            rack_columns[rack_x],
            key=lambda rack: rack["y"],
            reverse=True,
        )

        y_positions = [rack["y"] for rack in column_racks]
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

        rack_column_box = Rectangle(
            (
                rack_x - rack_width / 2,
                rack_column_bottom,
            ),
            rack_width,
            rack_column_top - rack_column_bottom,
            facecolor="lightsteelblue",
            edgecolor="black",
            linewidth=1.0,
            zorder=2,
        )
        axis.add_patch(rack_column_box)

        # Use the actual rack-name prefix where possible. This keeps headings
        # aligned even if naming is changed later.
        first_name = column_racks[0]["name"]
        column_label = "".join(
            character
            for character in first_name
            if character.isalpha()
        ) or chr(64 + column_index)

        axis.text(
            rack_x,
            rack_column_top + 0.16,
            f"Rack {column_label}",
            ha="center",
            va="bottom",
            fontsize=rack_header_font_size,
            fontweight="bold",
            clip_on=False,
            zorder=4,
        )

        for rack_index, rack in enumerate(column_racks):
            rack_y = float(rack["y"])

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
                next_y = float(
                    column_racks[rack_index + 1]["y"]
                )
                separator_y = (rack_y + next_y) / 2

                axis.plot(
                    [
                        rack_x - rack_width / 2,
                        rack_x + rack_width / 2,
                    ],
                    [separator_y, separator_y],
                    color="black",
                    linewidth=0.7,
                    zorder=3,
                )

    # -----------------------------------------------------
    # Input / output stations
    # -----------------------------------------------------
    def draw_station(
        position: tuple[float, float],
        label: str,
    ) -> None:
        x_position, y_position = position

        box = Rectangle(
            (
                x_position - 0.40,
                y_position - 0.31,
            ),
            0.80,
            0.62,
            facecolor="lightgreen",
            edgecolor="black",
            linewidth=1.0,
            zorder=2,
        )
        axis.add_patch(box)
        axis.text(
            x_position,
            y_position,
            label,
            ha="center",
            va="center",
            fontsize=7,
            fontweight="bold",
            zorder=3,
        )

    draw_station(entry_point, "Input")
    draw_station(exit_point, "Output")

    # -----------------------------------------------------
    # Robot staging positions
    # -----------------------------------------------------
    start_positions = [
        tuple(map(float, position))
        for position in robot_start_positions.values()
    ]
    x_spacing = _minimum_spacing(
        [position[0] for position in start_positions],
        fallback=1.2,
    )
    start_width = max(
        0.34,
        min(0.58, x_spacing * 0.46),
    )

    for robot_id, position in sorted(
        robot_start_positions.items()
    ):
        start_x = float(position[0])
        start_y = float(position[1])

        start_box = Rectangle(
            (
                start_x - start_width / 2,
                start_y - 0.23,
            ),
            start_width,
            0.46,
            facecolor="lemonchiffon",
            edgecolor="0.35",
            linewidth=0.8,
            zorder=2,
        )
        axis.add_patch(start_box)

        if standby_robot_id == int(robot_id):
            start_label = f"SB{robot_id}"
        else:
            start_label = f"S{robot_id}"

        axis.text(
            start_x,
            start_y,
            start_label,
            ha="center",
            va="center",
            fontsize=6.5,
            zorder=3,
        )

    # Small modelling note. It explains why rack access points are beside the
    # rack rather than inside the rack block without cluttering the drawing.
    axis.text(
        0.005,
        0.995,
        f"Rack access offset = {float(ACCESS_OFFSET):.1f}",
        transform=axis.transAxes,
        ha="left",
        va="top",
        fontsize=6.5,
        color="0.35",
    )


# =========================================================
# 10. OUTPUT VALIDATION
# =========================================================

def is_valid_gif(filepath: str | os.PathLike[str]) -> bool:
    path = Path(filepath)

    if not path.exists() or path.stat().st_size == 0:
        return False

    try:
        with Image.open(path) as image:
            image.verify()
        return True
    except Exception:
        return False


def is_valid_video(filepath: str | os.PathLike[str]) -> bool:
    path = Path(filepath)

    if not path.exists():
        return False

    return path.stat().st_size >= 1024


def is_valid_animation(filepath: str | os.PathLike[str]) -> bool:
    extension = Path(filepath).suffix.lower()

    if extension == ".gif":
        return is_valid_gif(filepath)

    if extension == ".mp4":
        return is_valid_video(filepath)

    return False


def determine_output_format(preferred_format: str = "mp4") -> str:
    if (
        preferred_format == "mp4"
        and writers.is_available("ffmpeg")
    ):
        return "mp4"

    print(
        "FFmpeg is not available. Falling back to GIF."
    )
    return "gif"


# =========================================================
# 11. STATUS PANEL HELPERS
# =========================================================

def compact_status(state: dict[str, Any]) -> str:
    lifecycle = state.get("lifecycle", "normal")

    if lifecycle == "standby":
        return "STANDBY"

    if lifecycle == "failed":
        return "FAILED"

    if lifecycle == "failed_finishing":
        return "FAIL-FINISH"

    status = str(state.get("status", "Idle"))
    rack_name = state.get("rack_name")

    if status == "Idle":
        return "Idle"
    if status == "Loading":
        return "Loading"
    if status == "Unloading":
        return "Unloading"
    if "input" in status.lower():
        return "To input"
    if "output" in status.lower():
        return "To output"
    if "storing" in status.lower():
        return f"Store {rack_name or '-'}"
    if "retrieving" in status.lower():
        return f"Pick {rack_name or '-'}"
    if "waiting for rack" in status.lower():
        return f"Wait {rack_name or '-'}"
    if "moving to rack" in status.lower():
        return f"To {rack_name or '-'}"

    return status[:12]


def _marker_style(
    robot_id: int,
    state: dict[str, Any],
    normal_color: str,
) -> dict[str, Any]:
    lifecycle = state.get("lifecycle", "normal")

    if lifecycle == "failed":
        return {
            "marker": "X",
            "color": "firebrick",
            "label_suffix": " FAILED",
            "markersize": 10,
        }

    if lifecycle == "failed_finishing":
        return {
            "marker": "o",
            "color": "darkorange",
            "label_suffix": " !",
            "markersize": 9,
        }

    if lifecycle == "standby":
        return {
            "marker": "s",
            "color": "dimgray",
            "label_suffix": " STBY",
            "markersize": 8,
        }

    return {
        "marker": "o",
        "color": normal_color,
        "label_suffix": "",
        "markersize": 9,
    }


# =========================================================
# 12. CREATE ANIMATION
# =========================================================

def create_animation(
    strategy: str,
    scenario_name: str,
    result: dict[str, Any],
    force_rebuild: bool = False,
    quality: str = DEFAULT_QUALITY,
    preferred_format: str = PREFERRED_FORMAT,
) -> str:
    strategy = strategy.upper()

    if quality not in ANIMATION_QUALITY:
        quality = DEFAULT_QUALITY

    quality_settings = ANIMATION_QUALITY[quality]
    visual_fps = float(
        quality_settings["visual_fps"]
    )
    dpi = int(quality_settings["dpi"])
    figure_size = tuple(quality_settings["figure_size"])
    bitrate = int(quality_settings["bitrate"])

    warehouse = result.get("warehouse", {})
    warehouse_rows = int(warehouse.get("rows", 7))
    warehouse_columns = int(warehouse.get("columns", 9))

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
        warehouse.get("entry_point", INPUT_STATION)
    )
    exit_point = tuple(
        warehouse.get("exit_point", OUTPUT_STATION)
    )
    corridor_y = float(
        warehouse.get("corridor_y", 0.0)
    )
    robot_speed = float(
        warehouse.get("robot_speed", ROBOT_SPEED)
    )

    lifecycle = get_lifecycle_configuration(result)

    timelines = build_robot_timelines(
        result=result,
        entry_point=entry_point,
        exit_point=exit_point,
        corridor_y=corridor_y,
        robot_speed=robot_speed,
    )

    indexed_timelines = {
        robot_id: prepare_timeline_index(timeline)
        for robot_id, timeline in timelines.items()
    }

    queue_times, queue_lengths = prepare_queue_history(
        result.get("queue_history", [])
    )

    completion_times = sorted(
        float(task.completion_time)
        for task in result.get("tasks", [])
        if task.completion_time is not None
    )

    makespan = float(result["summary"]["makespan"])

    robot_start_positions = {
        int(robot_id): tuple(position)
        for robot_id, position in result.get(
            "robot_start_positions",
            {},
        ).items()
    }

    # Ensure standby / replacement robots are represented even if an older
    # result format did not include them in robot_start_positions.
    for robot in result.get("robots", []):
        robot_start_positions.setdefault(
            int(robot.robot_id),
            tuple(robot.starting_position),
        )

    configuration_id = create_configuration_hash(
        scenario_name,
        result,
    )

    scenario_folder = os.path.join(
        OUTPUT_FOLDER,
        str(scenario_name),
    )
    create_output_folder(scenario_folder)

    output_format = determine_output_format(
        preferred_format
    )

    frame_times = create_frame_times(
        makespan=makespan,
        visual_fps=visual_fps,
        simulation_units_per_second=(
            PLAYBACK_SIM_UNITS_PER_SECOND
        ),
    )

    fps = calculate_playback_fps(
        frame_times=frame_times,
        makespan=makespan,
        simulation_units_per_second=(
            PLAYBACK_SIM_UNITS_PER_SECOND
        ),
    )

    # The intended presentation duration follows the fixed playback scale,
    # independent of quality/frame cap.
    expected_duration = (
        makespan
        / PLAYBACK_SIM_UNITS_PER_SECOND
        if makespan > 0
        else 0.0
    )

    playback_scale_token = str(
        PLAYBACK_SIM_UNITS_PER_SECOND
    ).replace(".", "p")

    visual_fps_token = str(
        visual_fps
    ).replace(".", "p")

    filename = (
        f"{strategy.lower()}_"
        f"{configuration_id}_"
        f"{ANIMATION_RENDER_VERSION}_"
        f"{quality}_"
        f"{visual_fps_token}vfps_"
        f"{playback_scale_token}simps."
        f"{output_format}"
    )

    filepath = os.path.join(
        scenario_folder,
        filename,
    )

    if (
        not force_rebuild
        and is_valid_animation(filepath)
    ):
        print(f"Using existing animation: {filepath}")
        return filepath
    pixel_width = int(round(figure_size[0] * dpi))
    pixel_height = int(round(figure_size[1] * dpi))

    print()
    print("=" * 72)
    print(f"Animation strategy: {strategy}")
    print(f"Quality: {quality}")
    print(f"Format: {output_format.upper()}")
    print(f"Resolution: {pixel_width} x {pixel_height}")
    print(f"Makespan: {makespan:.2f}")
    print(
        "Target visual FPS: "
        f"{visual_fps:.1f}"
    )
    exact_simulation_step = (
        PLAYBACK_SIM_UNITS_PER_SECOND
        / visual_fps
    )

    print(
        "Target simulation step per frame: "
        f"{exact_simulation_step:.3f}"
    )

    if len(frame_times) > 1:
        final_interval = (
            frame_times[-1]
            - frame_times[-2]
        )
    else:
        final_interval = 0.0

    print(
        "Final frame interval: "
        f"{final_interval:.3f}"
    )
    print(f"Actual rendered frames: {len(frame_times)}")
    print(
        "Playback scale: "
        f"{PLAYBACK_SIM_UNITS_PER_SECOND:.1f} "
        "simulation units / video second"
    )
    print(
        "Calculated encoder FPS: "
        f"{fps:.3f}"
    )
    print(
        "Expected playback duration: "
        f"{expected_duration:.1f} seconds"
    )
    print("=" * 72)

    # -----------------------------------------------------
    # Figure layout
    # -----------------------------------------------------
    figure, axis = plt.subplots(
        figsize=figure_size,
        dpi=dpi,
        constrained_layout=False,
    )

    figure.subplots_adjust(
        left=0.075,
        right=WAREHOUSE_RIGHT,
        bottom=0.10,
        top=0.88,
    )

    info_axis = figure.add_axes(
        [INFO_LEFT, 0.08, INFO_WIDTH, 0.82]
    )
    info_axis.axis("off")

    scenario_display = str(
        result.get("summary", {}).get(
            "scenario_name",
            scenario_name,
        )
    )

    figure.suptitle(
        f"{scenario_display} - {strategy}",
        fontsize=13,
        fontweight="bold",
        y=0.97,
    )

    time_text = figure.text(
        0.375,
        0.915,
        "Simulation Time = 0.0",
        ha="center",
        va="center",
        fontsize=10,
        fontweight="bold",
    )

    draw_warehouse(
        axis=axis,
        warehouse_rows=warehouse_rows,
        warehouse_columns=warehouse_columns,
        rack_positions=rack_positions,
        entry_point=entry_point,
        exit_point=exit_point,
        robot_start_positions=robot_start_positions,
        standby_robot_id=lifecycle.get(
            "standby_robot_id"
        ),
    )

    # -----------------------------------------------------
    # Robot artists
    # -----------------------------------------------------
    robot_markers: dict[int, Any] = {}
    robot_labels: dict[int, Any] = {}

    default_colors = plt.rcParams[
        "axes.prop_cycle"
    ].by_key().get(
        "color",
        ["C0"],
    )

    normal_colors: dict[int, str] = {}

    for index, robot_id in enumerate(
        sorted(robot_start_positions)
    ):
        start_position = robot_start_positions[robot_id]
        normal_color = default_colors[
            index % len(default_colors)
        ]
        normal_colors[robot_id] = normal_color

        marker_line, = axis.plot(
            [start_position[0]],
            [start_position[1]],
            linestyle="",
            marker="o",
            markersize=9,
            markerfacecolor=normal_color,
            markeredgecolor="white",
            markeredgewidth=0.8,
            zorder=6,
        )

        label = axis.text(
            start_position[0],
            start_position[1] + 0.32,
            f"R{robot_id}",
            ha="center",
            va="bottom",
            fontsize=6.8,
            fontweight="bold",
            bbox={
                "boxstyle": "round,pad=0.12",
                "facecolor": "white",
                "edgecolor": "none",
                "alpha": 0.72,
            },
            zorder=7,
        )

        robot_markers[robot_id] = marker_line
        robot_labels[robot_id] = label

    # -----------------------------------------------------
    # Dedicated right-side panel
    # -----------------------------------------------------
    live_text = info_axis.text(
        0.0,
        1.0,
        "",
        transform=info_axis.transAxes,
        ha="left",
        va="top",
        fontsize=7.4,
        family="monospace",
    )

    robot_status_text = info_axis.text(
        0.0,
        0.72,
        "",
        transform=info_axis.transAxes,
        ha="left",
        va="top",
        fontsize=7.1,
        family="monospace",
        linespacing=1.25,
    )

    final_metrics_text = info_axis.text(
        0.0,
        0.20,
        "",
        transform=info_axis.transAxes,
        ha="left",
        va="top",
        fontsize=7.1,
        family="monospace",
    )

    # -----------------------------------------------------
    # Update function
    # -----------------------------------------------------
    def update(frame_index: int):
        simulation_time = frame_times[frame_index]

        queue_length = get_queue_length(
            queue_times,
            queue_lengths,
            simulation_time,
        )

        completed_count = bisect_right(
            completion_times,
            simulation_time,
        )

        time_text.set_text(
            f"Simulation Time = {simulation_time:.1f}"
        )

        live_lines = [
            "LIVE SIMULATION",
            "----------------",
            f"Time      : {simulation_time:>7.1f}",
            f"Queue     : {queue_length:>7}",
            (
                f"Completed : {completed_count:>3}/"
                f"{len(result.get('tasks', [])):<3}"
            ),
        ]
        live_text.set_text("\n".join(live_lines))

        status_lines = [
            "ROBOT STATUS",
            "-------------------------------",
            "ID   State        Task   Rack",
            "-------------------------------",
        ]

        for robot_id in sorted(indexed_timelines):
            state = get_robot_state(
                indexed_timeline=indexed_timelines[robot_id],
                simulation_time=simulation_time,
                robot_id=robot_id,
                lifecycle=lifecycle,
            )

            x_position, y_position = state["position"]

            marker_style = _marker_style(
                robot_id,
                state,
                normal_colors[robot_id],
            )

            marker = robot_markers[robot_id]
            marker.set_data(
                [x_position],
                [y_position],
            )
            marker.set_marker(marker_style["marker"])
            marker.set_markersize(
                marker_style["markersize"]
            )
            marker.set_markerfacecolor(
                marker_style["color"]
            )
            marker.set_markeredgecolor("white")

            label_suffix = marker_style[
                "label_suffix"
            ]
            robot_labels[robot_id].set_text(
                f"R{robot_id}{label_suffix}"
            )
            robot_labels[robot_id].set_position(
                (
                    x_position,
                    y_position + 0.32,
                )
            )

            task_text = str(
                state.get("task_id") or "-"
            )
            rack_text = str(
                state.get("rack_name") or "-"
            )
            state_text = compact_status(state)

            status_lines.append(
                f"R{robot_id:<2}  "
                f"{state_text:<12} "
                f"{task_text:<5} "
                f"{rack_text:<4}"
            )

        robot_status_text.set_text(
            "\n".join(status_lines)
        )

        summary = result.get("summary", {})

        final_lines = [
            "FINAL RESULT",
            "-------------------------------",
            f"Makespan      : {makespan:>8.1f}",
            (
                "Total distance: "
                f"{float(summary.get('total_distance', 0.0)):>8.1f}"
            ),
            (
                "Avg waiting   : "
                f"{float(summary.get('average_waiting_time', 0.0)):>8.2f}"
            ),
        ]

        if lifecycle.get("failure_enabled"):
            final_lines.append(
                "Failure       : "
                f"R{lifecycle.get('failed_robot_id')} "
                f"at t={float(lifecycle.get('failure_time') or 0):.1f}"
            )

        if lifecycle.get("standby_enabled"):
            activation_time = lifecycle.get(
                "standby_activation_time"
            )
            final_lines.append(
                "Standby       : "
                f"R{lifecycle.get('standby_robot_id')} "
                f"at t={float(activation_time or 0):.1f}"
            )

        final_metrics_text.set_text(
            "\n".join(final_lines)
        )

        return (
            list(robot_markers.values())
            + list(robot_labels.values())
            + [
                time_text,
                live_text,
                robot_status_text,
                final_metrics_text,
            ]
        )

    animation = FuncAnimation(
        figure,
        update,
        frames=len(frame_times),
        interval=1000 / fps,
        blit=False,
        repeat=True,
        cache_frame_data=False,
    )

    if output_format == "mp4":
        temporary_filepath = (
            os.path.splitext(filepath)[0]
            + "_temp.mp4"
        )
    else:
        temporary_filepath = (
            os.path.splitext(filepath)[0]
            + "_temp.gif"
        )

    if os.path.exists(temporary_filepath):
        os.remove(temporary_filepath)

    save_start = time.perf_counter()

    try:
        if output_format == "mp4":
            writer = FFMpegWriter(
                fps=fps,
                codec="libx264",
                bitrate=bitrate,
                extra_args=[
                    "-pix_fmt",
                    "yuv420p",
                    "-preset",
                    "medium",
                ],
            )

            animation.save(
                temporary_filepath,
                writer=writer,
                dpi=dpi,
            )
        else:
            writer = PillowWriter(fps=fps)
            animation.save(
                temporary_filepath,
                writer=writer,
                dpi=dpi,
            )

        if not is_valid_animation(temporary_filepath):
            raise RuntimeError(
                "Animation generation produced an invalid file."
            )

        os.replace(
            temporary_filepath,
            filepath,
        )

    finally:
        if os.path.exists(temporary_filepath):
            os.remove(temporary_filepath)

        plt.close(figure)

    generation_time = time.perf_counter() - save_start

    print()
    print(f"Generated animation: {filepath}")
    print(
        "Animation generation time: "
        f"{generation_time:.2f} seconds"
    )
    print()

    return filepath


# =========================================================
# 13. PUBLIC WRAPPER
# =========================================================

def generate_strategy_animation(
    strategy: str,
    scenario_name: str,
    result: dict[str, Any],
    quality: str = DEFAULT_QUALITY,
    force_rebuild: bool = False,
) -> str:
    return create_animation(
        strategy=strategy,
        scenario_name=scenario_name,
        result=result,
        quality=quality,
        force_rebuild=force_rebuild,
    )


# =========================================================
# 14. MAIN PROGRAM
# =========================================================

def main() -> None:
    scenario_name = SELECTED_SCENARIO
    scenario = get_scenario(scenario_name)

    print()
    print("=" * 80)
    print(
        "Generating animations for: "
        f"{scenario['name']}"
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
        quality="standard",
    )

    deferred_result = run_simulation(
        "DEFERRED",
        scenario_name,
    )
    create_animation(
        strategy="DEFERRED",
        scenario_name=scenario_name,
        result=deferred_result,
        quality="standard",
    )

    print()
    print(
        "Scenario animations were generated successfully."
    )


if __name__ == "__main__":
    main()