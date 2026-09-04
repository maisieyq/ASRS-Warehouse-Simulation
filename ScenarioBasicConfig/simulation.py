from __future__ import annotations

import math
from typing import Any

import simpy

try:
    # Preferred when imported as ScenarioBasicConfig.simulation
    from .scenarios import get_scenario
except ImportError:
    # Fallback when this file is executed directly
    from scenarios import get_scenario


# =========================================================
# 1. DEFAULT WAREHOUSE / SIMULATION CONFIGURATION
# =========================================================

INPUT_STATION = (0.0, 0.0)
OUTPUT_STATION = (8.0, 0.0)

# Predefined scenarios use the baseline 7 x 9 warehouse geometry.
RACK_POSITIONS = {
    "A1": (1.0, 6.0),
    "A2": (1.0, 4.0),
    "A3": (1.0, 2.0),
    "B1": (3.0, 6.0),
    "B2": (3.0, 4.0),
    "B3": (3.0, 2.0),
    "C1": (5.0, 6.0),
    "C2": (5.0, 4.0),
    "C3": (5.0, 2.0),
    "D1": (7.0, 6.0),
    "D2": (7.0, 4.0),
    "D3": (7.0, 2.0),
}

# Visual rack half-width. The robot stops outside the rack block.
RACK_HALF_WIDTH = 0.3

# Horizontal offset from rack centre to the rack access aisle.
ACCESS_OFFSET = 0.5

# Main horizontal transit corridor. Input, output and robot starts
# are placed on this row.
CORRIDOR_Y = 0.0

# Base physical assumptions used by the simulation.
ROBOT_SPEED = 1.0
LOAD_TIME = 2.0
STORE_TIME = 2.0
PICK_TIME = 2.0
UNLOAD_TIME = 2.0


# =========================================================
# 2. WAREHOUSE HELPER FUNCTIONS
# =========================================================

def generate_robot_start_positions(
    number_of_robots: int,
    entry_point: tuple[float, float] = INPUT_STATION,
    exit_point: tuple[float, float] = OUTPUT_STATION,
) -> dict[int, tuple[float, float]]:
    """
    Evenly distribute robots between the entry and exit points.

    This replaces the old cyclic three-position logic. Therefore,
    predefined scenarios with more than three robots no longer place
    multiple robots on the same starting coordinate.

    Example for the baseline corridor (0,0) -> (8,0):
        3 robots -> x = 2, 4, 6
        5 robots -> x = 1.33, 2.67, 4.00, 5.33, 6.67
    """
    if number_of_robots < 1:
        raise ValueError(
            "The warehouse must contain at least one robot."
        )

    entry_x, entry_y = map(float, entry_point)
    exit_x, exit_y = map(float, exit_point)

    spacing_x = (
        exit_x - entry_x
    ) / (
        number_of_robots + 1
    )

    spacing_y = (
        exit_y - entry_y
    ) / (
        number_of_robots + 1
    )

    return {
        robot_id: (
            entry_x + robot_id * spacing_x,
            entry_y + robot_id * spacing_y,
        )
        for robot_id in range(
            1,
            number_of_robots + 1,
        )
    }


def get_rack_access_position(
    rack_name: str,
    rack_positions: dict[str, tuple[float, float]],
) -> tuple[float, float]:
    """
    Return the aisle-side stopping position for a rack.

    The rack coordinate represents its visual centre. The robot does
    not move through the rack block; it stops ACCESS_OFFSET units to
    the left of the rack centre.
    """
    if rack_name not in rack_positions:
        raise ValueError(
            f"Unknown rack name: {rack_name}"
        )

    rack_x, rack_y = rack_positions[rack_name]

    return (
        float(rack_x) - ACCESS_OFFSET,
        float(rack_y),
    )


# =========================================================
# 3. TASK CLASS
# =========================================================

class Task:
    def __init__(
        self,
        task_id: str,
        task_type: str,
        arrival_time: float,
        rack_name: str,
        rack_positions: dict[str, tuple[float, float]],
    ) -> None:
        if rack_name not in rack_positions:
            raise ValueError(
                f"Unknown rack name: {rack_name}"
            )

        normalized_task_type = task_type.lower()

        if normalized_task_type not in {
            "storage",
            "retrieval",
        }:
            raise ValueError(
                "Task type must be storage or retrieval."
            )

        self.task_id = str(task_id)
        self.task_type = normalized_task_type
        self.arrival_time = float(arrival_time)
        self.rack_name = rack_name

        # Rack centre is used for drawing / display.
        self.rack_position = tuple(
            map(float, rack_positions[rack_name])
        )

        # Rack access point is used for travel calculations.
        self.rack_access_position = (
            get_rack_access_position(
                rack_name,
                rack_positions,
            )
        )

        self.start_time: float | None = None
        self.completion_time: float | None = None
        self.robot_id: int | None = None

        self.estimated_distance: float | None = None
        self.travel_distance = 0.0

        # Rack-access reservation diagnostics. A task may be assigned to a
        # robot before its target rack access point becomes available.
        # These timestamps let the animation and analysis distinguish queue
        # waiting from waiting for the shared rack-access resource.
        self.rack_access_request_time: float | None = None
        self.rack_access_granted_time: float | None = None
        self.rack_access_wait_position: tuple[float, float] | None = None
        self.rack_access_wait_time = 0.0

    def waiting_time(self) -> float | None:
        if self.start_time is None:
            return None

        return self.start_time - self.arrival_time

    def cycle_time(self) -> float | None:
        if self.completion_time is None:
            return None

        return self.completion_time - self.arrival_time


# =========================================================
# 4. ROBOT CLASS
# =========================================================

class Robot:
    def __init__(
        self,
        env: simpy.Environment,
        robot_id: int,
        starting_position: tuple[float, float],
        is_standby: bool = False,
    ) -> None:
        self.robot_id = int(robot_id)
        self.starting_position = tuple(
            map(float, starting_position)
        )
        self.position = self.starting_position

        self.is_standby = bool(is_standby)
        self.standby_active = not self.is_standby

        # A standby robot exists physically from the beginning but is not
        # available for dispatch until the configured activation time.
        self.available = not self.is_standby
        self.available_since = 0.0
        self.current_task: Task | None = None

        self.failed = False
        self.failure_count = 0
        self.total_downtime = 0.0

        self.total_distance = 0.0
        self.busy_time = 0.0
        self.completed_tasks = 0

        self.assignment_store = simpy.Store(
            env,
            capacity=1,
        )


# =========================================================
# 5. DISTANCE AND ROUTING FUNCTIONS
# =========================================================

def manhattan_distance(
    position_a: tuple[float, float],
    position_b: tuple[float, float],
) -> float:
    return (
        abs(position_a[0] - position_b[0])
        + abs(position_a[1] - position_b[1])
    )


def travel_time(
    distance: float,
    robot_speed: float = ROBOT_SPEED,
) -> float:
    if robot_speed <= 0:
        raise ValueError(
            "Robot speed must be greater than zero."
        )

    return distance / robot_speed


def route_waypoints(
    start_position: tuple[float, float],
    end_position: tuple[float, float],
    corridor_y: float = CORRIDOR_Y,
) -> list[tuple[float, float]]:
    """
    Build an aisle-safe Manhattan route.

    Horizontal travel between rack aisles occurs only on the main
    corridor. Vertical travel occurs only along a single aisle x
    coordinate.
    """
    start_x, start_y = map(float, start_position)
    end_x, end_y = map(float, end_position)
    corridor_y = float(corridor_y)

    start = (start_x, start_y)
    end = (end_x, end_y)

    if math.isclose(start_x, end_x):
        return [start, end]

    if math.isclose(start_y, corridor_y):
        return [
            start,
            (end_x, corridor_y),
            end,
        ]

    if math.isclose(end_y, corridor_y):
        return [
            start,
            (start_x, corridor_y),
            end,
        ]

    return [
        start,
        (start_x, corridor_y),
        (end_x, corridor_y),
        end,
    ]


def route_distance(
    start_position: tuple[float, float],
    end_position: tuple[float, float],
    corridor_y: float = CORRIDOR_Y,
) -> float:
    """Return total distance along the aisle-safe route."""
    waypoints = route_waypoints(
        start_position,
        end_position,
        corridor_y=corridor_y,
    )

    return sum(
        manhattan_distance(point_a, point_b)
        for point_a, point_b in zip(
            waypoints,
            waypoints[1:],
        )
    )


def estimate_route_distance(
    robot: Robot,
    task: Task,
    input_station: tuple[float, float] = INPUT_STATION,
    output_station: tuple[float, float] = OUTPUT_STATION,
    corridor_y: float = CORRIDOR_Y,
) -> float:
    """
    Estimate the complete aisle-safe route before assignment.

    Storage:
        robot -> input -> rack access

    Retrieval:
        robot -> rack access -> output
    """
    if task.task_type == "storage":
        return (
            route_distance(
                robot.position,
                input_station,
                corridor_y=corridor_y,
            )
            + route_distance(
                input_station,
                task.rack_access_position,
                corridor_y=corridor_y,
            )
        )

    if task.task_type == "retrieval":
        return (
            route_distance(
                robot.position,
                task.rack_access_position,
                corridor_y=corridor_y,
            )
            + route_distance(
                task.rack_access_position,
                output_station,
                corridor_y=corridor_y,
            )
        )

    raise ValueError(
        f"Invalid task type: {task.task_type}"
    )


# =========================================================
# 6. TASK CREATION
# =========================================================

def create_tasks(
    task_data: list[dict[str, Any]],
    rack_positions: dict[str, tuple[float, float]],
) -> list[Task]:
    tasks: list[Task] = []

    for data in task_data:
        required_fields = {
            "task_id",
            "task_type",
            "arrival_time",
            "rack_name",
        }

        missing_fields = required_fields.difference(data)

        if missing_fields:
            raise ValueError(
                "Task is missing required fields: "
                + ", ".join(sorted(missing_fields))
            )

        task = Task(
            task_id=data["task_id"],
            task_type=data["task_type"],
            arrival_time=data["arrival_time"],
            rack_name=data["rack_name"],
            rack_positions=rack_positions,
        )

        tasks.append(task)

    return tasks


# =========================================================
# 7. EVENT LOG
# =========================================================

def record_event(
    event_log: list[dict[str, Any]],
    time: float,
    strategy: str,
    robot_id: int | None = None,
    task_id: str | None = None,
    task_type: str | None = None,
    rack_name: str | None = None,
    status: str = "",
    position: tuple[float, float] | None = None,
) -> None:
    event_log.append(
        {
            "time": float(time),
            "strategy": strategy,
            "robot_id": robot_id,
            "task_id": task_id,
            "task_type": task_type,
            "rack_name": rack_name,
            "status": status,
            "position": (
                tuple(map(float, position))
                if position is not None
                else None
            ),
        }
    )


# =========================================================
# 8. DISPATCHER SIGNAL
# =========================================================

def signal_dispatcher(state: dict[str, Any]) -> None:
    event = state["dispatch_event"]

    if not event.triggered:
        event.succeed()


# =========================================================
# 9. TASK GENERATOR
# =========================================================

def task_generator(
    env: simpy.Environment,
    strategy: str,
    tasks: list[Task],
    pending_tasks: list[Task],
    state: dict[str, Any],
    event_log: list[dict[str, Any]],
):
    previous_arrival = 0.0

    sorted_tasks = sorted(
        tasks,
        key=lambda task: (
            task.arrival_time,
            task.task_id,
        ),
    )

    for task in sorted_tasks:
        delay = task.arrival_time - previous_arrival

        if delay < 0:
            raise ValueError(
                "Task arrival times must not decrease."
            )

        yield env.timeout(delay)
        previous_arrival = task.arrival_time

        pending_tasks.append(task)

        record_event(
            event_log=event_log,
            time=env.now,
            strategy=strategy,
            task_id=task.task_id,
            task_type=task.task_type,
            rack_name=task.rack_name,
            status=(
                "Task arrived; "
                f"rack centre {task.rack_position}; "
                f"access point {task.rack_access_position}"
            ),
            position=task.rack_access_position,
        )

        signal_dispatcher(state)

    state["generation_finished"] = True
    signal_dispatcher(state)


# =========================================================
# 10. TASK SELECTION
# =========================================================

def select_task(
    strategy: str,
    robot: Robot,
    pending_tasks: list[Task],
    input_station: tuple[float, float] = INPUT_STATION,
    output_station: tuple[float, float] = OUTPUT_STATION,
    corridor_y: float = CORRIDOR_Y,
) -> Task:
    strategy = strategy.upper()

    def estimated_distance(task: Task) -> float:
        return estimate_route_distance(
            robot=robot,
            task=task,
            input_station=input_station,
            output_station=output_station,
            corridor_y=corridor_y,
        )

    if strategy == "FIFO":
        selected_task = min(
            pending_tasks,
            key=lambda task: (
                task.arrival_time,
                task.task_id,
            ),
        )

    elif strategy == "DEFERRED":
        selected_task = min(
            pending_tasks,
            key=lambda task: (
                estimated_distance(task),
                task.arrival_time,
                task.task_id,
            ),
        )

    else:
        raise ValueError(
            "Strategy must be FIFO or DEFERRED."
        )

    selected_task.estimated_distance = (
        estimated_distance(selected_task)
    )

    return selected_task


# =========================================================
# 11. CENTRAL DISPATCHER
# =========================================================

def central_dispatcher(
    env: simpy.Environment,
    strategy: str,
    pending_tasks: list[Task],
    available_robots: list[Robot],
    state: dict[str, Any],
    event_log: list[dict[str, Any]],
    input_station: tuple[float, float] = INPUT_STATION,
    output_station: tuple[float, float] = OUTPUT_STATION,
    corridor_y: float = CORRIDOR_Y,
):
    while True:
        while pending_tasks:
            usable_robots = [
                robot
                for robot in available_robots
                if not robot.failed
            ]

            if not usable_robots:
                break

            usable_robots.sort(
                key=lambda robot: (
                    robot.available_since,
                    robot.robot_id,
                )
            )

            robot = usable_robots[0]
            available_robots.remove(robot)

            task = select_task(
                strategy=strategy,
                robot=robot,
                pending_tasks=pending_tasks,
                input_station=input_station,
                output_station=output_station,
                corridor_y=corridor_y,
            )

            pending_tasks.remove(task)

            robot.available = False
            robot.current_task = task

            task.start_time = env.now
            task.robot_id = robot.robot_id

            record_event(
                event_log=event_log,
                time=env.now,
                strategy=strategy,
                robot_id=robot.robot_id,
                task_id=task.task_id,
                task_type=task.task_type,
                rack_name=task.rack_name,
                status=(
                    "Task assigned; "
                    f"estimated distance "
                    f"{task.estimated_distance:.1f}; "
                    f"rack access point "
                    f"{task.rack_access_position}"
                ),
                position=robot.position,
            )

            yield robot.assignment_store.put(task)

        current_event = state["dispatch_event"]

        if current_event.triggered:
            state["dispatch_event"] = env.event()
            continue

        yield current_event

        if state["dispatch_event"] is current_event:
            state["dispatch_event"] = env.event()


# =========================================================
# 12. STORAGE TASK PROCESS
# =========================================================

def perform_storage_task(
    env: simpy.Environment,
    strategy: str,
    robot: Robot,
    task: Task,
    event_log: list[dict[str, Any]],
    input_station: tuple[float, float],
    rack_access_resources: dict[str, simpy.Resource],
    robot_speed: float = ROBOT_SPEED,
    corridor_y: float = CORRIDOR_Y,
):
    """Perform one storage task with exclusive rack-access reservation.

    The robot first travels to the input station and loads the item. Before
    leaving for the target rack, it reserves that rack's access point. If
    another robot already owns the same rack access, this robot waits at the
    input station. This prevents two robots from converging on and occupying
    the same physical rack access point simultaneously.
    """
    distance_to_input = route_distance(
        robot.position,
        input_station,
        corridor_y=corridor_y,
    )

    record_event(
        event_log=event_log,
        time=env.now,
        strategy=strategy,
        robot_id=robot.robot_id,
        task_id=task.task_id,
        task_type=task.task_type,
        rack_name=task.rack_name,
        status="Travelling to input station",
        position=robot.position,
    )

    yield env.timeout(
        travel_time(
            distance_to_input,
            robot_speed,
        )
    )

    robot.position = input_station

    record_event(
        event_log=event_log,
        time=env.now,
        strategy=strategy,
        robot_id=robot.robot_id,
        task_id=task.task_id,
        task_type=task.task_type,
        rack_name=task.rack_name,
        status="Arrived at input station",
        position=robot.position,
    )

    record_event(
        event_log=event_log,
        time=env.now,
        strategy=strategy,
        robot_id=robot.robot_id,
        task_id=task.task_id,
        task_type=task.task_type,
        rack_name=task.rack_name,
        status="Loading item",
        position=robot.position,
    )

    yield env.timeout(LOAD_TIME)

    rack_resource = rack_access_resources[
        task.rack_name
    ]

    # Reserve the target access point before travelling toward it.
    # Only report a Waiting state when the access point is genuinely busy.
    task.rack_access_request_time = float(env.now)
    task.rack_access_wait_position = tuple(robot.position)

    with rack_resource.request() as request:
        if not request.triggered:
            record_event(
                event_log=event_log,
                time=env.now,
                strategy=strategy,
                robot_id=robot.robot_id,
                task_id=task.task_id,
                task_type=task.task_type,
                rack_name=task.rack_name,
                status=(
                    f"Waiting for Rack {task.rack_name} access"
                ),
                position=robot.position,
            )

        yield request

        task.rack_access_granted_time = float(
            env.now
        )
        task.rack_access_wait_time = max(
            0.0,
            task.rack_access_granted_time
            - task.rack_access_request_time,
        )

        record_event(
            event_log=event_log,
            time=env.now,
            strategy=strategy,
            robot_id=robot.robot_id,
            task_id=task.task_id,
            task_type=task.task_type,
            rack_name=task.rack_name,
            status=(
                f"Rack {task.rack_name} access granted"
            ),
            position=robot.position,
        )

        distance_to_rack_access = route_distance(
            robot.position,
            task.rack_access_position,
            corridor_y=corridor_y,
        )

        record_event(
            event_log=event_log,
            time=env.now,
            strategy=strategy,
            robot_id=robot.robot_id,
            task_id=task.task_id,
            task_type=task.task_type,
            rack_name=task.rack_name,
            status=(
                f"Travelling to Rack {task.rack_name} "
                f"access point"
            ),
            position=robot.position,
        )

        yield env.timeout(
            travel_time(
                distance_to_rack_access,
                robot_speed,
            )
        )

        robot.position = task.rack_access_position

        record_event(
            event_log=event_log,
            time=env.now,
            strategy=strategy,
            robot_id=robot.robot_id,
            task_id=task.task_id,
            task_type=task.task_type,
            rack_name=task.rack_name,
            status=(
                f"Storing item at Rack {task.rack_name} "
                f"from access point"
            ),
            position=robot.position,
        )

        yield env.timeout(STORE_TIME)

        record_event(
            event_log=event_log,
            time=env.now,
            strategy=strategy,
            robot_id=robot.robot_id,
            task_id=task.task_id,
            task_type=task.task_type,
            rack_name=task.rack_name,
            status=(
                f"Rack {task.rack_name} access released"
            ),
            position=robot.position,
        )

    task.travel_distance = (
        distance_to_input
        + distance_to_rack_access
    )


# =========================================================
# 13. RETRIEVAL TASK PROCESS
# =========================================================

def perform_retrieval_task(
    env: simpy.Environment,
    strategy: str,
    robot: Robot,
    task: Task,
    event_log: list[dict[str, Any]],
    output_station: tuple[float, float],
    rack_access_resources: dict[str, simpy.Resource],
    robot_speed: float = ROBOT_SPEED,
    corridor_y: float = CORRIDOR_Y,
):
    """Perform one retrieval task with exclusive rack-access reservation.

    The target rack access point is reserved before the robot starts moving
    toward it. If it is occupied, the assigned robot waits at its current
    position until the access point becomes available. Different racks can
    still be served concurrently.
    """
    rack_resource = rack_access_resources[
        task.rack_name
    ]

    task.rack_access_request_time = float(env.now)
    task.rack_access_wait_position = tuple(robot.position)

    with rack_resource.request() as request:
        if not request.triggered:
            record_event(
                event_log=event_log,
                time=env.now,
                strategy=strategy,
                robot_id=robot.robot_id,
                task_id=task.task_id,
                task_type=task.task_type,
                rack_name=task.rack_name,
                status=(
                    f"Waiting for Rack {task.rack_name} access"
                ),
                position=robot.position,
            )

        yield request

        task.rack_access_granted_time = float(
            env.now
        )
        task.rack_access_wait_time = max(
            0.0,
            task.rack_access_granted_time
            - task.rack_access_request_time,
        )

        record_event(
            event_log=event_log,
            time=env.now,
            strategy=strategy,
            robot_id=robot.robot_id,
            task_id=task.task_id,
            task_type=task.task_type,
            rack_name=task.rack_name,
            status=(
                f"Rack {task.rack_name} access granted"
            ),
            position=robot.position,
        )

        distance_to_rack_access = route_distance(
            robot.position,
            task.rack_access_position,
            corridor_y=corridor_y,
        )

        record_event(
            event_log=event_log,
            time=env.now,
            strategy=strategy,
            robot_id=robot.robot_id,
            task_id=task.task_id,
            task_type=task.task_type,
            rack_name=task.rack_name,
            status=(
                f"Travelling to Rack {task.rack_name} "
                f"access point"
            ),
            position=robot.position,
        )

        yield env.timeout(
            travel_time(
                distance_to_rack_access,
                robot_speed,
            )
        )

        robot.position = task.rack_access_position

        record_event(
            event_log=event_log,
            time=env.now,
            strategy=strategy,
            robot_id=robot.robot_id,
            task_id=task.task_id,
            task_type=task.task_type,
            rack_name=task.rack_name,
            status=(
                f"Retrieving item from Rack {task.rack_name} "
                f"at access point"
            ),
            position=robot.position,
        )

        yield env.timeout(PICK_TIME)

        record_event(
            event_log=event_log,
            time=env.now,
            strategy=strategy,
            robot_id=robot.robot_id,
            task_id=task.task_id,
            task_type=task.task_type,
            rack_name=task.rack_name,
            status=(
                f"Rack {task.rack_name} access released"
            ),
            position=robot.position,
        )

    # Once the access point is released, the robot can travel to output.
    distance_to_output = route_distance(
        task.rack_access_position,
        output_station,
        corridor_y=corridor_y,
    )

    record_event(
        event_log=event_log,
        time=env.now,
        strategy=strategy,
        robot_id=robot.robot_id,
        task_id=task.task_id,
        task_type=task.task_type,
        rack_name=task.rack_name,
        status="Travelling to output station",
        position=robot.position,
    )

    yield env.timeout(
        travel_time(
            distance_to_output,
            robot_speed,
        )
    )

    robot.position = output_station

    record_event(
        event_log=event_log,
        time=env.now,
        strategy=strategy,
        robot_id=robot.robot_id,
        task_id=task.task_id,
        task_type=task.task_type,
        rack_name=task.rack_name,
        status="Unloading item",
        position=robot.position,
    )

    yield env.timeout(UNLOAD_TIME)

    task.travel_distance = (
        distance_to_rack_access
        + distance_to_output
    )


# =========================================================
# 14. ROBOT FAILURE PROCESS
# =========================================================

def robot_failure_process(
    env: simpy.Environment,
    strategy: str,
    robot: Robot,
    available_robots: list[Robot],
    state: dict[str, Any],
    event_log: list[dict[str, Any]],
    failure_time: float,
):
    """
    Make one robot permanently unavailable from ``failure_time`` onward.

    Modelling assumption:
    - If the robot is idle, it becomes unavailable immediately.
    - If it is already processing a task, that task is allowed to finish.
    - The failed robot receives no new tasks afterward.
    - All pending and future tasks continue to be handled by the remaining
      operational robots.

    This models reduced system capacity after a failure without introducing
    a separate helper-priority dispatch rule that could confound the FIFO
    versus Deferred Commitment comparison.
    """
    yield env.timeout(failure_time)

    robot.failed = True
    robot.failure_count += 1
    robot.available = False

    if robot in available_robots:
        available_robots.remove(robot)

    record_event(
        event_log=event_log,
        time=env.now,
        strategy=strategy,
        robot_id=robot.robot_id,
        status=(
            "Robot became unavailable due to failure; "
            "remaining robots continue pending tasks"
        ),
        position=robot.position,
    )

    signal_dispatcher(state)


def standby_activation_process(
    env: simpy.Environment,
    strategy: str,
    standby_robot: Robot,
    available_robots: list[Robot],
    state: dict[str, Any],
    event_log: list[dict[str, Any]],
    activation_time: float,
    failed_robot_id: int,
):
    """Activate a separate standby replacement robot after a failure.

    The standby unit is not part of the normal active fleet before the
    failure. It waits at its staging position and joins the dispatcher only
    at ``activation_time``. This restores replacement capacity without giving
    any existing robot special dispatch priority.
    """
    if activation_time < 0:
        raise ValueError(
            "Standby activation time cannot be negative."
        )

    yield env.timeout(activation_time)

    if standby_robot.failed:
        return

    standby_robot.standby_active = True
    standby_robot.available = True
    standby_robot.available_since = env.now

    if standby_robot not in available_robots:
        available_robots.append(standby_robot)

    record_event(
        event_log=event_log,
        time=env.now,
        strategy=strategy,
        robot_id=standby_robot.robot_id,
        status=(
            f"Standby robot activated to replace Robot "
            f"{failed_robot_id}"
        ),
        position=standby_robot.position,
    )

    signal_dispatcher(state)


# =========================================================
# 15. ROBOT WORKER
# =========================================================

def robot_worker(
    env: simpy.Environment,
    strategy: str,
    robot: Robot,
    available_robots: list[Robot],
    completed_tasks: list[Task],
    total_task_count: int,
    state: dict[str, Any],
    completion_event: simpy.Event,
    event_log: list[dict[str, Any]],
    rack_access_resources: dict[str, simpy.Resource],
    input_station: tuple[float, float] = INPUT_STATION,
    output_station: tuple[float, float] = OUTPUT_STATION,
    robot_speed: float = ROBOT_SPEED,
    corridor_y: float = CORRIDOR_Y,
):
    while True:
        task = yield robot.assignment_store.get()
        busy_start = env.now

        record_event(
            event_log=event_log,
            time=env.now,
            strategy=strategy,
            robot_id=robot.robot_id,
            task_id=task.task_id,
            task_type=task.task_type,
            rack_name=task.rack_name,
            status="Robot starts task",
            position=robot.position,
        )

        if task.task_type == "storage":
            yield env.process(
                perform_storage_task(
                    env=env,
                    strategy=strategy,
                    robot=robot,
                    task=task,
                    event_log=event_log,
                    input_station=input_station,
                    rack_access_resources=rack_access_resources,
                    robot_speed=robot_speed,
                    corridor_y=corridor_y,
                )
            )

        elif task.task_type == "retrieval":
            yield env.process(
                perform_retrieval_task(
                    env=env,
                    strategy=strategy,
                    robot=robot,
                    task=task,
                    event_log=event_log,
                    output_station=output_station,
                    rack_access_resources=rack_access_resources,
                    robot_speed=robot_speed,
                    corridor_y=corridor_y,
                )
            )

        else:
            raise ValueError(
                f"Invalid task type: {task.task_type}"
            )

        task.completion_time = env.now

        robot.busy_time += (
            env.now - busy_start
        )
        robot.total_distance += task.travel_distance
        robot.completed_tasks += 1
        robot.current_task = None

        completed_tasks.append(task)

        if robot.failed:
            robot.available = False

            record_event(
                event_log=event_log,
                time=env.now,
                strategy=strategy,
                robot_id=robot.robot_id,
                status=(
                    "Task completed, but robot remains "
                    "unavailable due to failure"
                ),
                position=robot.position,
            )

        else:
            robot.available = True
            robot.available_since = env.now

            if robot not in available_robots:
                available_robots.append(robot)

        record_event(
            event_log=event_log,
            time=env.now,
            strategy=strategy,
            robot_id=robot.robot_id,
            task_id=task.task_id,
            task_type=task.task_type,
            rack_name=task.rack_name,
            status=(
                "Task completed; "
                f"cycle time {task.cycle_time():.1f}; "
                f"distance {task.travel_distance:.1f}"
            ),
            position=robot.position,
        )

        if not robot.failed:
            record_event(
                event_log=event_log,
                time=env.now,
                strategy=strategy,
                robot_id=robot.robot_id,
                status="Robot available",
                position=robot.position,
            )

        signal_dispatcher(state)

        if (
            state["generation_finished"]
            and len(completed_tasks) == total_task_count
            and not completion_event.triggered
        ):
            completion_event.succeed()


# =========================================================
# 16. QUEUE MONITOR
# =========================================================

def queue_monitor(
    env: simpy.Environment,
    pending_tasks: list[Task],
    queue_history: list[dict[str, float]],
    completion_event: simpy.Event,
):
    while not completion_event.triggered:
        queue_history.append(
            {
                "time": float(env.now),
                "queue_length": len(pending_tasks),
            }
        )

        yield env.timeout(1.0)


# =========================================================
# 17. SUMMARY CALCULATION
# =========================================================

def calculate_summary(
    strategy: str,
    completed_tasks: list[Task],
    robots: list[Robot],
    makespan: float,
    queue_history: list[dict[str, float]],
) -> dict[str, Any]:
    task_count = len(completed_tasks)

    if task_count == 0:
        raise ValueError(
            "No tasks were completed, so summary metrics cannot be calculated."
        )

    total_waiting = sum(
        float(task.waiting_time())
        for task in completed_tasks
        if task.waiting_time() is not None
    )

    total_cycle = sum(
        float(task.cycle_time())
        for task in completed_tasks
        if task.cycle_time() is not None
    )

    total_distance = sum(
        task.travel_distance
        for task in completed_tasks
    )

    total_rack_access_wait = sum(
        float(task.rack_access_wait_time)
        for task in completed_tasks
    )

    if queue_history:
        average_queue_length = (
            sum(
                record["queue_length"]
                for record in queue_history
            )
            / len(queue_history)
        )

        maximum_queue_length = max(
            record["queue_length"]
            for record in queue_history
        )

    else:
        average_queue_length = 0.0
        maximum_queue_length = 0

    return {
        "strategy": strategy,
        "completed_tasks": task_count,
        "makespan": float(makespan),
        "average_waiting_time": (
            total_waiting / task_count
        ),
        "average_completion_time": (
            total_cycle / task_count
        ),
        "average_travel_distance": (
            total_distance / task_count
        ),
        "total_distance": total_distance,
        "average_rack_access_waiting_time": (
            total_rack_access_wait / task_count
        ),
        "total_rack_access_waiting_time": (
            total_rack_access_wait
        ),
        "average_queue_length": average_queue_length,
        "maximum_queue_length": maximum_queue_length,
    }


# =========================================================
# 18. CONFIGURATION NORMALISATION / VALIDATION
# =========================================================

def _normalise_rack_positions(
    rack_positions: dict[str, Any],
) -> dict[str, tuple[float, float]]:
    normalised: dict[str, tuple[float, float]] = {}

    for rack_name, position in rack_positions.items():
        if (
            not isinstance(position, (list, tuple))
            or len(position) != 2
        ):
            raise ValueError(
                f"Rack {rack_name} must contain exactly two coordinates."
            )

        normalised[str(rack_name)] = (
            float(position[0]),
            float(position[1]),
        )

    return normalised


def _normalise_robot_start_positions(
    configured_positions: dict[Any, Any],
    expected_robot_count: int,
) -> dict[int, tuple[float, float]]:
    if not isinstance(configured_positions, dict):
        raise ValueError(
            "robot_start_positions must be a dictionary."
        )

    robot_start_positions: dict[
        int,
        tuple[float, float],
    ] = {}

    for robot_id, position in configured_positions.items():
        converted_robot_id = int(robot_id)

        if (
            not isinstance(position, (list, tuple))
            or len(position) != 2
        ):
            raise ValueError(
                "Every robot start position must contain "
                "exactly two coordinates."
            )

        robot_start_positions[converted_robot_id] = (
            float(position[0]),
            float(position[1]),
        )

    expected_robot_ids = set(
        range(1, expected_robot_count + 1)
    )
    actual_robot_ids = set(
        robot_start_positions.keys()
    )

    if actual_robot_ids != expected_robot_ids:
        raise ValueError(
            "Custom robot_start_positions must contain "
            "exactly one position for every robot. "
            f"Expected: {sorted(expected_robot_ids)}. "
            f"Received: {sorted(actual_robot_ids)}."
        )

    return robot_start_positions


# =========================================================
# 19. RUN ONE STRATEGY
# =========================================================

def run_simulation(
    strategy: str,
    scenario_name: str = "baseline",
    scenario_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    strategy = strategy.upper()

    if strategy not in {"FIFO", "DEFERRED"}:
        raise ValueError(
            "Strategy must be FIFO or DEFERRED."
        )

    is_custom_scenario = scenario_config is not None

    # -----------------------------------------------------
    # 1. Load the scenario
    # -----------------------------------------------------
    if is_custom_scenario:
        scenario = scenario_config
        scenario_name = scenario.get(
            "name",
            scenario_name,
        )
    else:
        scenario = get_scenario(scenario_name)

    if scenario is None:
        raise ValueError(
            "The scenario could not be loaded."
        )

    # -----------------------------------------------------
    # 2. Validate basic scenario structure
    # -----------------------------------------------------
    required_keys = {
        "name",
        "description",
        "number_of_robots",
        "tasks",
    }

    missing_keys = required_keys.difference(scenario)

    if missing_keys:
        raise ValueError(
            "Scenario is missing required fields: "
            + ", ".join(sorted(missing_keys))
        )

    number_of_robots = int(
        scenario["number_of_robots"]
    )

    if number_of_robots < 1:
        raise ValueError(
            "number_of_robots must be at least 1."
        )

    task_data = scenario["tasks"]

    if not task_data:
        raise ValueError(
            "The scenario must contain at least one task."
        )

    # -----------------------------------------------------
    # 3. Resolve failure configuration
    # -----------------------------------------------------
    failure_config = scenario.get(
        "robot_failure",
        {},
    )

    failure_enabled = bool(
        failure_config.get("enabled", False)
    )

    failed_robot_id: int | None = None
    failure_time: float | None = None

    if failure_enabled:
        raw_failed_robot_id = failure_config.get(
            "robot_id"
        )
        raw_failure_time = failure_config.get(
            "failure_time"
        )

        if raw_failed_robot_id is None:
            raise ValueError(
                "A failed robot ID is required when robot failure is enabled."
            )

        if raw_failure_time is None:
            raise ValueError(
                "A failure time is required when robot failure is enabled."
            )

        failed_robot_id = int(raw_failed_robot_id)
        failure_time = float(raw_failure_time)

        if failed_robot_id not in range(
            1,
            number_of_robots + 1,
        ):
            raise ValueError(
                "The selected failed robot does not exist."
            )

        if failure_time < 0:
            raise ValueError(
                "Failure time cannot be negative."
            )

    # -----------------------------------------------------
    # 4. Resolve standby replacement configuration
    # -----------------------------------------------------
    standby_config = scenario.get(
        "standby_robot",
        {},
    )

    standby_enabled = bool(
        standby_config.get("enabled", False)
    )

    standby_robot_id: int | None = None
    standby_activation_delay: float | None = None
    standby_activation_time: float | None = None

    if standby_enabled:
        if not failure_enabled:
            raise ValueError(
                "A standby robot can only be enabled when "
                "robot failure is enabled."
            )

        raw_standby_robot_id = standby_config.get(
            "robot_id"
        )
        raw_activation_delay = standby_config.get(
            "activation_delay"
        )

        if raw_standby_robot_id is None:
            standby_robot_id = number_of_robots + 1
        else:
            standby_robot_id = int(raw_standby_robot_id)

        if standby_robot_id != number_of_robots + 1:
            raise ValueError(
                "The standby robot ID must be exactly one greater "
                "than the number of active robots."
            )

        if raw_activation_delay is None:
            raise ValueError(
                "A standby activation delay is required when "
                "the standby robot is enabled."
            )

        standby_activation_delay = float(
            raw_activation_delay
        )

        if standby_activation_delay < 0:
            raise ValueError(
                "Standby activation delay cannot be negative."
            )

        assert failure_time is not None
        standby_activation_time = (
            failure_time + standby_activation_delay
        )

    total_physical_robots = (
        number_of_robots
        + (1 if standby_enabled else 0)
    )

    # -----------------------------------------------------
    # 5. Resolve warehouse geometry
    # -----------------------------------------------------
    if is_custom_scenario:
        warehouse_config = scenario.get(
            "warehouse",
            {},
        )

        if not warehouse_config:
            raise ValueError(
                "Custom scenarios must define scenario['warehouse']."
            )

        raw_rack_positions = warehouse_config.get(
            "rack_positions"
        )

        if not raw_rack_positions:
            raise ValueError(
                "Custom scenarios must define "
                "scenario['warehouse']['rack_positions']."
            )

        rack_positions = _normalise_rack_positions(
            raw_rack_positions
        )

        input_station = tuple(
            map(
                float,
                warehouse_config.get(
                    "entry_point",
                    INPUT_STATION,
                ),
            )
        )

        output_station = tuple(
            map(
                float,
                warehouse_config.get(
                    "exit_point",
                    OUTPUT_STATION,
                ),
            )
        )

        corridor_y = float(
            warehouse_config.get(
                "corridor_y",
                CORRIDOR_Y,
            )
        )

        robot_speed = float(
            warehouse_config.get(
                "robot_speed",
                scenario.get(
                    "robot_speed",
                    ROBOT_SPEED,
                ),
            )
        )

        if robot_speed <= 0:
            raise ValueError(
                "Robot speed must be greater than zero."
            )

        configured_positions = warehouse_config.get(
            "robot_start_positions"
        )

        if configured_positions is None:
            raise ValueError(
                "Custom scenarios must define "
                "scenario['warehouse']['robot_start_positions']."
            )

        robot_start_positions = (
            _normalise_robot_start_positions(
                configured_positions,
                total_physical_robots,
            )
        )

        warehouse_rows = int(
            warehouse_config.get("rows", 7)
        )
        warehouse_columns = int(
            warehouse_config.get("columns", 9)
        )

    else:
        # Preserve baseline warehouse geometry for predefined scenarios.
        warehouse_config = {}
        rack_positions = dict(RACK_POSITIONS)
        input_station = INPUT_STATION
        output_station = OUTPUT_STATION
        corridor_y = CORRIDOR_Y
        robot_speed = ROBOT_SPEED
        warehouse_rows = 7
        warehouse_columns = 9

        # Even spacing prevents overlap for predefined high-availability
        # scenarios with more than three robots.
        robot_start_positions = (
            generate_robot_start_positions(
                number_of_robots=total_physical_robots,
                entry_point=input_station,
                exit_point=output_station,
            )
        )

    if warehouse_rows < 1 or warehouse_columns < 1:
        raise ValueError(
            "Warehouse rows and columns must both be positive."
        )

    # -----------------------------------------------------
    # 5. Build one resolved warehouse object for animation,
    #    dashboard and graph modules.
    # -----------------------------------------------------
    resolved_warehouse = {
        "rows": warehouse_rows,
        "columns": warehouse_columns,
        "rack_positions": rack_positions,
        "entry_point": tuple(input_station),
        "exit_point": tuple(output_station),
        "corridor_y": float(corridor_y),
        "robot_speed": float(robot_speed),
        "robot_start_positions": robot_start_positions,
        "active_robot_count": number_of_robots,
        "total_physical_robots": total_physical_robots,
        "standby_robot_enabled": standby_enabled,
        "standby_robot_id": standby_robot_id,
        "standby_activation_time": standby_activation_time,
        "rack_access_capacity": 1,
        "rack_access_reservation_enabled": True,
    }

    # -----------------------------------------------------
    # 6. Create simulation environment and tasks
    # -----------------------------------------------------
    env = simpy.Environment()

    tasks = create_tasks(
        task_data=task_data,
        rack_positions=rack_positions,
    )

    pending_tasks: list[Task] = []
    completed_tasks: list[Task] = []
    queue_history: list[dict[str, float]] = []
    event_log: list[dict[str, Any]] = []

    # Each physical rack access point is an exclusive SimPy resource.
    # Different racks can be served concurrently, but only one robot may
    # reserve/travel to/use a given rack access point at a time.
    rack_access_resources: dict[str, simpy.Resource] = {
        rack_name: simpy.Resource(
            env,
            capacity=1,
        )
        for rack_name in rack_positions
    }

    # -----------------------------------------------------
    # 7. Create robots
    # -----------------------------------------------------
    robots = [
        Robot(
            env=env,
            robot_id=robot_id,
            starting_position=(
                robot_start_positions[robot_id]
            ),
            is_standby=(
                standby_enabled
                and robot_id == standby_robot_id
            ),
        )
        for robot_id in range(
            1,
            total_physical_robots + 1,
        )
    ]

    # Only normal active robots are dispatchable at time 0.
    available_robots = [
        robot
        for robot in robots
        if not robot.is_standby
    ]
    completion_event = env.event()

    state: dict[str, Any] = {
        "generation_finished": False,
        "dispatch_event": env.event(),
    }

    standby_robot: Robot | None = None

    if standby_enabled:
        assert standby_robot_id is not None

        standby_robot = next(
            robot
            for robot in robots
            if robot.robot_id == standby_robot_id
        )

        record_event(
            event_log=event_log,
            time=0.0,
            strategy=strategy,
            robot_id=standby_robot.robot_id,
            status="Standby robot waiting for activation",
            position=standby_robot.position,
        )

    # -----------------------------------------------------
    # 8. Start failure process if configured
    # -----------------------------------------------------
    if failure_enabled:
        assert failed_robot_id is not None
        assert failure_time is not None

        failed_robot = next(
            robot
            for robot in robots
            if robot.robot_id == failed_robot_id
        )

        env.process(
            robot_failure_process(
                env=env,
                strategy=strategy,
                robot=failed_robot,
                available_robots=available_robots,
                state=state,
                event_log=event_log,
                failure_time=failure_time,
            )
        )

        if standby_enabled:
            assert standby_robot is not None
            assert standby_activation_time is not None

            env.process(
                standby_activation_process(
                    env=env,
                    strategy=strategy,
                    standby_robot=standby_robot,
                    available_robots=available_robots,
                    state=state,
                    event_log=event_log,
                    activation_time=(
                        standby_activation_time
                    ),
                    failed_robot_id=failed_robot_id,
                )
            )

    # -----------------------------------------------------
    # 9. Start task generator
    # -----------------------------------------------------
    env.process(
        task_generator(
            env=env,
            strategy=strategy,
            tasks=tasks,
            pending_tasks=pending_tasks,
            state=state,
            event_log=event_log,
        )
    )

    # -----------------------------------------------------
    # 10. Start central dispatcher
    # -----------------------------------------------------
    env.process(
        central_dispatcher(
            env=env,
            strategy=strategy,
            pending_tasks=pending_tasks,
            available_robots=available_robots,
            state=state,
            event_log=event_log,
            input_station=input_station,
            output_station=output_station,
            corridor_y=corridor_y,
        )
    )

    # -----------------------------------------------------
    # 11. Start robot workers
    # -----------------------------------------------------
    for robot in robots:
        env.process(
            robot_worker(
                env=env,
                strategy=strategy,
                robot=robot,
                available_robots=available_robots,
                completed_tasks=completed_tasks,
                total_task_count=len(tasks),
                state=state,
                completion_event=completion_event,
                event_log=event_log,
                rack_access_resources=rack_access_resources,
                input_station=input_station,
                output_station=output_station,
                robot_speed=robot_speed,
                corridor_y=corridor_y,
            )
        )

    # -----------------------------------------------------
    # 12. Start queue monitoring
    # -----------------------------------------------------
    env.process(
        queue_monitor(
            env=env,
            pending_tasks=pending_tasks,
            queue_history=queue_history,
            completion_event=completion_event,
        )
    )

    # -----------------------------------------------------
    # 13. Run until all tasks are complete
    # -----------------------------------------------------
    env.run(until=completion_event)

    # -----------------------------------------------------
    # 14. Calculate final summary
    # -----------------------------------------------------
    summary = calculate_summary(
        strategy=strategy,
        completed_tasks=completed_tasks,
        robots=robots,
        makespan=env.now,
        queue_history=queue_history,
    )

    summary["scenario"] = scenario_name
    summary["scenario_name"] = scenario["name"]
    summary["scenario_description"] = scenario[
        "description"
    ]
    summary["active_robot_count"] = number_of_robots
    summary["total_physical_robots"] = total_physical_robots
    summary["standby_robot_enabled"] = standby_enabled
    summary["standby_robot_id"] = standby_robot_id
    summary["standby_activation_time"] = (
        standby_activation_time
    )

    # -----------------------------------------------------
    # 15. Return complete result
    # -----------------------------------------------------
    return {
        "summary": summary,
        "tasks": completed_tasks,
        "robots": robots,
        "queue_history": queue_history,
        "event_log": event_log,
        "scenario": scenario,
        "warehouse": resolved_warehouse,
        "robot_start_positions": robot_start_positions,
    }


# =========================================================
# 20. PRINT EVENT LOG
# =========================================================

def print_event_log(result: dict[str, Any]) -> None:
    strategy = result["summary"]["strategy"]

    print()
    print("=" * 135)
    print(f"{strategy} TASK AND ROBOT STATUS LOG")
    print("=" * 135)

    print(
        f"{'Time':<8}"
        f"{'Robot':<10}"
        f"{'Task':<10}"
        f"{'Type':<12}"
        f"{'Rack':<8}"
        f"{'Position':<16}"
        f"{'Status'}"
    )

    print("-" * 135)

    sorted_events = sorted(
        enumerate(result["event_log"]),
        key=lambda item: (
            item[1]["time"],
            item[0],
        ),
    )

    for _, event in sorted_events:
        robot_text = (
            f"R{event['robot_id']}"
            if event["robot_id"] is not None
            else "-"
        )

        task_text = (
            event["task_id"]
            if event["task_id"] is not None
            else "-"
        )

        type_text = (
            event["task_type"]
            if event["task_type"] is not None
            else "-"
        )

        rack_text = (
            event["rack_name"]
            if event["rack_name"] is not None
            else "-"
        )

        position_text = (
            str(event["position"])
            if event["position"] is not None
            else "-"
        )

        print(
            f"{event['time']:<8.1f}"
            f"{robot_text:<10}"
            f"{task_text:<10}"
            f"{type_text:<12}"
            f"{rack_text:<8}"
            f"{position_text:<16}"
            f"{event['status']}"
        )


# =========================================================
# 21. PERCENTAGE CHANGE
# =========================================================

def percentage_change(
    fifo_value: float,
    deferred_value: float,
) -> float | None:
    if fifo_value == 0:
        if deferred_value == 0:
            return 0.0

        return None

    return (
        (fifo_value - deferred_value)
        / fifo_value
        * 100
    )


# =========================================================
# 22. PRINT COMPARISON
# =========================================================

def print_comparison(
    fifo_result: dict[str, Any],
    deferred_result: dict[str, Any],
) -> None:
    fifo = fifo_result["summary"]
    deferred = deferred_result["summary"]

    rows = [
        (
            "Average waiting time",
            fifo["average_waiting_time"],
            deferred["average_waiting_time"],
        ),
        (
            "Average completion time",
            fifo["average_completion_time"],
            deferred["average_completion_time"],
        ),
        (
            "Average rack access wait",
            fifo["average_rack_access_waiting_time"],
            deferred["average_rack_access_waiting_time"],
        ),
        (
            "Average travel distance",
            fifo["average_travel_distance"],
            deferred["average_travel_distance"],
        ),
        (
            "Total travel distance",
            fifo["total_distance"],
            deferred["total_distance"],
        ),
        (
            "Simulation makespan",
            fifo["makespan"],
            deferred["makespan"],
        ),
        (
            "Average queue length",
            fifo["average_queue_length"],
            deferred["average_queue_length"],
        ),
    ]

    print()
    print("=" * 100)
    print("FIFO VS DEFERRED COMMITMENT COMPARISON")
    print("=" * 100)

    print(
        f"{'Metric':<35}"
        f"{'FIFO':<18}"
        f"{'Deferred':<18}"
        f"{'Change':<18}"
    )

    print("-" * 100)

    for metric, fifo_value, deferred_value in rows:
        change = percentage_change(
            fifo_value,
            deferred_value,
        )

        change_text = (
            f"{change:.2f}%"
            if change is not None
            else "N/A"
        )

        print(
            f"{metric:<35}"
            f"{fifo_value:<18.2f}"
            f"{deferred_value:<18.2f}"
            f"{change_text:<18}"
        )

    print(
        f"{'Maximum queue length':<35}"
        f"{fifo['maximum_queue_length']:<18}"
        f"{deferred['maximum_queue_length']:<18}"
        f"{'--':<18}"
    )

    print(
        f"{'Completed tasks':<35}"
        f"{fifo['completed_tasks']:<18}"
        f"{deferred['completed_tasks']:<18}"
        f"{'--':<18}"
    )

    print("=" * 100)

    print(
        "Positive change means Deferred Commitment "
        "achieved a lower value."
    )

    print(
        "Negative change means Deferred Commitment "
        "produced a higher value."
    )


# =========================================================
# 23. MAIN PROGRAM
# =========================================================

def main() -> None:
    scenario_name = "high_availability"

    fifo_result = run_simulation(
        "FIFO",
        scenario_name,
    )

    deferred_result = run_simulation(
        "DEFERRED",
        scenario_name,
    )

    print()
    print("=" * 100)
    print(
        f"SCENARIO: "
        f"{fifo_result['summary']['scenario_name']}"
    )
    print("=" * 100)

    print(
        fifo_result["summary"][
            "scenario_description"
        ]
    )

    print_event_log(fifo_result)
    print_event_log(deferred_result)
    print_comparison(
        fifo_result,
        deferred_result,
    )


if __name__ == "__main__":
    main()