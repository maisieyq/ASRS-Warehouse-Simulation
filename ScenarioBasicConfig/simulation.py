import simpy


# =========================================================
# 1. WAREHOUSE CONFIGURATION
# =========================================================

INPUT_STATION = (0, 0)
OUTPUT_STATION = (8, 0)

ROBOT_START_POSITIONS = {
    1: (2, 0),
    2: (4, 0),
    3: (6, 0),
}

RACK_POSITIONS = {
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
}

NUMBER_OF_ROBOTS = 3

ROBOT_SPEED = 1.0

LOAD_TIME = 2.0
STORE_TIME = 2.0
PICK_TIME = 2.0
UNLOAD_TIME = 2.0


# =========================================================
# 2. DEFAULT TASK DATA
# =========================================================

TASK_DATA = [
    {
        "task_id": "T01",
        "task_type": "storage",
        "arrival_time": 0,
        "rack_name": "A1",
    },
    {
        "task_id": "T02",
        "task_type": "retrieval",
        "arrival_time": 2,
        "rack_name": "D2",
    },
    {
        "task_id": "T03",
        "task_type": "storage",
        "arrival_time": 4,
        "rack_name": "B3",
    },
    {
        "task_id": "T04",
        "task_type": "retrieval",
        "arrival_time": 6,
        "rack_name": "A2",
    },
    {
        "task_id": "T05",
        "task_type": "storage",
        "arrival_time": 8,
        "rack_name": "C1",
    },
    {
        "task_id": "T06",
        "task_type": "retrieval",
        "arrival_time": 10,
        "rack_name": "D1",
    },
]


# =========================================================
# 3. TASK CLASS
# =========================================================

class Task:
    def __init__(
        self,
        task_id,
        task_type,
        arrival_time,
        rack_name,
    ):
        if rack_name not in RACK_POSITIONS:
            raise ValueError(
                f"Unknown rack name: {rack_name}"
            )

        if task_type.lower() not in {
            "storage",
            "retrieval",
        }:
            raise ValueError(
                "Task type must be storage or retrieval."
            )

        self.task_id = task_id
        self.task_type = task_type.lower()
        self.arrival_time = float(arrival_time)

        self.rack_name = rack_name
        self.rack_position = (
            RACK_POSITIONS[rack_name]
        )

        self.start_time = None
        self.completion_time = None
        self.robot_id = None

        self.estimated_distance = None
        self.travel_distance = 0.0

    def waiting_time(self):
        if self.start_time is None:
            return None

        return (
            self.start_time
            - self.arrival_time
        )

    def cycle_time(self):
        if self.completion_time is None:
            return None

        return (
            self.completion_time
            - self.arrival_time
        )


# =========================================================
# 4. ROBOT CLASS
# =========================================================

class Robot:
    def __init__(
        self,
        env,
        robot_id,
        starting_position,
    ):
        self.robot_id = robot_id
        self.starting_position = (
            starting_position
        )

        self.position = starting_position

        self.available = True
        self.available_since = 0.0
        self.current_task = None

        self.total_distance = 0.0
        self.busy_time = 0.0
        self.completed_tasks = 0

        self.assignment_store = simpy.Store(
            env,
            capacity=1,
        )


# =========================================================
# 5. DISTANCE FUNCTIONS
# =========================================================

def manhattan_distance(
    position_a,
    position_b,
):
    return (
        abs(
            position_a[0]
            - position_b[0]
        )
        + abs(
            position_a[1]
            - position_b[1]
        )
    )


def travel_time(distance):
    return (
        distance
        / ROBOT_SPEED
    )


def estimate_route_distance(
    robot,
    task,
):
    if task.task_type == "storage":
        return (
            manhattan_distance(
                robot.position,
                INPUT_STATION,
            )
            + manhattan_distance(
                INPUT_STATION,
                task.rack_position,
            )
        )

    if task.task_type == "retrieval":
        return (
            manhattan_distance(
                robot.position,
                task.rack_position,
            )
            + manhattan_distance(
                task.rack_position,
                OUTPUT_STATION,
            )
        )

    raise ValueError(
        f"Invalid task type: "
        f"{task.task_type}"
    )


# =========================================================
# 6. TASK CREATION
# =========================================================

def create_tasks():
    tasks = []

    for data in TASK_DATA:
        task = Task(
            task_id=data["task_id"],
            task_type=data["task_type"],
            arrival_time=data[
                "arrival_time"
            ],
            rack_name=data["rack_name"],
        )

        tasks.append(task)

    return tasks


# =========================================================
# 7. EVENT LOG
# =========================================================

def record_event(
    event_log,
    time,
    strategy,
    robot_id=None,
    task_id=None,
    task_type=None,
    rack_name=None,
    status="",
    position=None,
):
    event_log.append(
        {
            "time": float(time),
            "strategy": strategy,
            "robot_id": robot_id,
            "task_id": task_id,
            "task_type": task_type,
            "rack_name": rack_name,
            "status": status,
            "position": position,
        }
    )


# =========================================================
# 8. DISPATCHER SIGNAL
# =========================================================

def signal_dispatcher(state):
    event = state["dispatch_event"]

    if not event.triggered:
        event.succeed()


# =========================================================
# 9. TASK GENERATOR
# =========================================================

def task_generator(
    env,
    strategy,
    tasks,
    pending_tasks,
    state,
    event_log,
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
        delay = (
            task.arrival_time
            - previous_arrival
        )

        if delay < 0:
            raise ValueError(
                "Task arrival times "
                "must not decrease."
            )

        yield env.timeout(delay)

        previous_arrival = (
            task.arrival_time
        )

        pending_tasks.append(task)

        record_event(
            event_log=event_log,
            time=env.now,
            strategy=strategy,
            task_id=task.task_id,
            task_type=task.task_type,
            rack_name=task.rack_name,
            status="Task arrived",
            position=task.rack_position,
        )

        signal_dispatcher(state)

    state["generation_finished"] = True

    signal_dispatcher(state)


# =========================================================
# 10. TASK SELECTION
# =========================================================

def select_task(
    strategy,
    robot,
    pending_tasks,
):
    strategy = strategy.upper()

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
                estimate_route_distance(
                    robot,
                    task,
                ),
                task.arrival_time,
                task.task_id,
            ),
        )

    else:
        raise ValueError(
            "Strategy must be FIFO "
            "or DEFERRED."
        )

    selected_task.estimated_distance = (
        estimate_route_distance(
            robot,
            selected_task,
        )
    )

    return selected_task


# =========================================================
# 11. CENTRAL DISPATCHER
# =========================================================

def central_dispatcher(
    env,
    strategy,
    pending_tasks,
    available_robots,
    state,
    event_log,
):
    while True:
        while (
            pending_tasks
            and available_robots
        ):
            available_robots.sort(
                key=lambda robot: (
                    robot.available_since,
                    robot.robot_id,
                )
            )

            robot = (
                available_robots.pop(0)
            )

            task = select_task(
                strategy,
                robot,
                pending_tasks,
            )

            pending_tasks.remove(task)

            robot.available = False
            robot.current_task = task

            task.start_time = env.now
            task.robot_id = (
                robot.robot_id
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
                    "Task assigned; "
                    f"estimated distance "
                    f"{task.estimated_distance:.1f}"
                ),
                position=robot.position,
            )

            yield (
                robot.assignment_store.put(
                    task
                )
            )

        current_event = (
            state["dispatch_event"]
        )

        if current_event.triggered:
            state["dispatch_event"] = (
                env.event()
            )
            continue

        yield current_event

        if (
            state["dispatch_event"]
            is current_event
        ):
            state["dispatch_event"] = (
                env.event()
            )


# =========================================================
# 12. STORAGE TASK PROCESS
# =========================================================

def perform_storage_task(
    env,
    strategy,
    robot,
    task,
    event_log,
):
    distance_to_input = (
        manhattan_distance(
            robot.position,
            INPUT_STATION,
        )
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
            "Travelling to input station"
        ),
        position=robot.position,
    )

    yield env.timeout(
        travel_time(
            distance_to_input
        )
    )

    robot.position = INPUT_STATION

    record_event(
        event_log=event_log,
        time=env.now,
        strategy=strategy,
        robot_id=robot.robot_id,
        task_id=task.task_id,
        task_type=task.task_type,
        rack_name=task.rack_name,
        status=(
            "Arrived at input station"
        ),
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

    distance_to_rack = (
        manhattan_distance(
            INPUT_STATION,
            task.rack_position,
        )
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
            f"Travelling to Rack "
            f"{task.rack_name}"
        ),
        position=robot.position,
    )

    yield env.timeout(
        travel_time(
            distance_to_rack
        )
    )

    robot.position = (
        task.rack_position
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
            f"Storing item at Rack "
            f"{task.rack_name}"
        ),
        position=robot.position,
    )

    yield env.timeout(STORE_TIME)

    task.travel_distance = (
        distance_to_input
        + distance_to_rack
    )


# =========================================================
# 13. RETRIEVAL TASK PROCESS
# =========================================================

def perform_retrieval_task(
    env,
    strategy,
    robot,
    task,
    event_log,
):
    distance_to_rack = (
        manhattan_distance(
            robot.position,
            task.rack_position,
        )
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
            f"Travelling to Rack "
            f"{task.rack_name}"
        ),
        position=robot.position,
    )

    yield env.timeout(
        travel_time(
            distance_to_rack
        )
    )

    robot.position = (
        task.rack_position
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
            f"Retrieving item from Rack "
            f"{task.rack_name}"
        ),
        position=robot.position,
    )

    yield env.timeout(PICK_TIME)

    distance_to_output = (
        manhattan_distance(
            task.rack_position,
            OUTPUT_STATION,
        )
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
            "Travelling to output station"
        ),
        position=robot.position,
    )

    yield env.timeout(
        travel_time(
            distance_to_output
        )
    )

    robot.position = OUTPUT_STATION

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
        distance_to_rack
        + distance_to_output
    )


# =========================================================
# 14. ROBOT WORKER
# =========================================================

def robot_worker(
    env,
    strategy,
    robot,
    available_robots,
    completed_tasks,
    total_task_count,
    state,
    completion_event,
    event_log,
):
    while True:
        task = yield (
            robot.assignment_store.get()
        )

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
                )
            )

        else:
            raise ValueError(
                f"Invalid task type: "
                f"{task.task_type}"
            )

        task.completion_time = env.now

        robot.busy_time += (
            env.now - busy_start
        )

        robot.total_distance += (
            task.travel_distance
        )

        robot.completed_tasks += 1
        robot.available = True
        robot.available_since = env.now
        robot.current_task = None

        completed_tasks.append(task)
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
                f"cycle time "
                f"{task.cycle_time():.1f}; "
                f"distance "
                f"{task.travel_distance:.1f}"
            ),
            position=robot.position,
        )

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
            and len(completed_tasks)
            == total_task_count
            and not completion_event.triggered
        ):
            completion_event.succeed()


# =========================================================
# 15. QUEUE MONITOR
# =========================================================

def queue_monitor(
    env,
    pending_tasks,
    queue_history,
    completion_event,
):
    while not completion_event.triggered:
        queue_history.append(
            {
                "time": env.now,
                "queue_length": len(
                    pending_tasks
                ),
            }
        )

        yield env.timeout(1.0)


# =========================================================
# 16. SUMMARY CALCULATION
# =========================================================

def calculate_summary(
    strategy,
    completed_tasks,
    robots,
    makespan,
    queue_history,
):
    task_count = len(
        completed_tasks
    )

    total_waiting = sum(
        task.waiting_time()
        for task in completed_tasks
    )

    total_cycle = sum(
        task.cycle_time()
        for task in completed_tasks
    )

    total_distance = sum(
        task.travel_distance
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
        "makespan": makespan,
        "average_waiting_time": (
            total_waiting
            / task_count
        ),
        "average_completion_time": (
            total_cycle
            / task_count
        ),
        "average_travel_distance": (
            total_distance
            / task_count
        ),
        "total_distance": total_distance,
        "average_queue_length": (
            average_queue_length
        ),
        "maximum_queue_length": (
            maximum_queue_length
        ),
    }


# =========================================================
# 17. RUN ONE STRATEGY
# =========================================================

def run_simulation(strategy):
    strategy = strategy.upper()

    env = simpy.Environment()

    tasks = create_tasks()

    pending_tasks = []
    completed_tasks = []
    queue_history = []
    event_log = []

    robots = [
        Robot(
            env=env,
            robot_id=robot_id,
            starting_position=(
                ROBOT_START_POSITIONS[
                    robot_id
                ]
            ),
        )
        for robot_id in range(
            1,
            NUMBER_OF_ROBOTS + 1,
        )
    ]

    available_robots = (
        robots.copy()
    )

    completion_event = (
        env.event()
    )

    state = {
        "generation_finished": False,
        "dispatch_event": env.event(),
    }

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

    env.process(
        central_dispatcher(
            env=env,
            strategy=strategy,
            pending_tasks=pending_tasks,
            available_robots=(
                available_robots
            ),
            state=state,
            event_log=event_log,
        )
    )

    for robot in robots:
        env.process(
            robot_worker(
                env=env,
                strategy=strategy,
                robot=robot,
                available_robots=(
                    available_robots
                ),
                completed_tasks=(
                    completed_tasks
                ),
                total_task_count=len(
                    tasks
                ),
                state=state,
                completion_event=(
                    completion_event
                ),
                event_log=event_log,
            )
        )

    env.process(
        queue_monitor(
            env=env,
            pending_tasks=(
                pending_tasks
            ),
            queue_history=(
                queue_history
            ),
            completion_event=(
                completion_event
            ),
        )
    )

    env.run(
        until=completion_event
    )

    summary = calculate_summary(
        strategy=strategy,
        completed_tasks=(
            completed_tasks
        ),
        robots=robots,
        makespan=env.now,
        queue_history=queue_history,
    )

    return {
        "summary": summary,
        "tasks": completed_tasks,
        "robots": robots,
        "queue_history": (
            queue_history
        ),
        "event_log": event_log,
    }


# =========================================================
# 18. PRINT EVENT LOG
# =========================================================

def print_event_log(result):
    strategy = result["summary"][
        "strategy"
    ]

    print()
    print("=" * 125)
    print(
        f"{strategy} TASK AND ROBOT STATUS LOG"
    )
    print("=" * 125)

    print(
        f"{'Time':<8}"
        f"{'Robot':<10}"
        f"{'Task':<10}"
        f"{'Type':<12}"
        f"{'Rack':<8}"
        f"{'Position':<16}"
        f"{'Status'}"
    )

    print("-" * 125)

    sorted_events = sorted(
        enumerate(
            result["event_log"]
        ),
        key=lambda item: (
            item[1]["time"],
            item[0],
        ),
    )

    for _, event in sorted_events:
        robot_text = (
            f"R{event['robot_id']}"
            if event["robot_id"]
            is not None
            else "-"
        )

        task_text = (
            event["task_id"]
            if event["task_id"]
            is not None
            else "-"
        )

        type_text = (
            event["task_type"]
            if event["task_type"]
            is not None
            else "-"
        )

        rack_text = (
            event["rack_name"]
            if event["rack_name"]
            is not None
            else "-"
        )

        position_text = (
            str(event["position"])
            if event["position"]
            is not None
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
# 19. PERCENTAGE CHANGE
# =========================================================

def percentage_change(
    fifo_value,
    deferred_value,
):
    if fifo_value == 0:
        if deferred_value == 0:
            return 0.0

        return None

    return (
        (
            fifo_value
            - deferred_value
        )
        / fifo_value
        * 100
    )


# =========================================================
# 20. PRINT COMPARISON
# =========================================================

def print_comparison(
    fifo_result,
    deferred_result,
):
    fifo = fifo_result["summary"]
    deferred = (
        deferred_result["summary"]
    )

    rows = [
        (
            "Average waiting time",
            fifo[
                "average_waiting_time"
            ],
            deferred[
                "average_waiting_time"
            ],
        ),
        (
            "Average completion time",
            fifo[
                "average_completion_time"
            ],
            deferred[
                "average_completion_time"
            ],
        ),
        (
            "Average travel distance",
            fifo[
                "average_travel_distance"
            ],
            deferred[
                "average_travel_distance"
            ],
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
            fifo[
                "average_queue_length"
            ],
            deferred[
                "average_queue_length"
            ],
        ),
    ]

    print()
    print("=" * 100)
    print(
        "FIFO VS DEFERRED COMMITMENT "
        "COMPARISON"
    )
    print("=" * 100)

    print(
        f"{'Metric':<35}"
        f"{'FIFO':<18}"
        f"{'Deferred':<18}"
        f"{'Change':<18}"
    )

    print("-" * 100)

    for (
        metric,
        fifo_value,
        deferred_value,
    ) in rows:
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
        "Positive change means Deferred "
        "Commitment achieved a lower value."
    )

    print(
        "Negative change means Deferred "
        "Commitment produced a higher value."
    )


# =========================================================
# 21. MAIN PROGRAM
# =========================================================

def main():
    fifo_result = run_simulation(
        "FIFO"
    )

    deferred_result = run_simulation(
        "DEFERRED"
    )

    print_event_log(
        fifo_result
    )

    print_event_log(
        deferred_result
    )

    print_comparison(
        fifo_result,
        deferred_result,
    )


if __name__ == "__main__":
    main()