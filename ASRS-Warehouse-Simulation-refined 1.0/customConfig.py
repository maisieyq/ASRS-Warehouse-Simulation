from __future__ import annotations

import json
import hashlib  # unique identifier for custom scenarios
from typing import Callable

import streamlit as st

from dashboard_common import ARRIVAL_INTERVALS


# ---------------------------------------------------------------------------
# Custom-configuration scope limits
# ---------------------------------------------------------------------------
# These are modelling limits for this 2D AS/RS simulator. They are chosen to
# keep layouts meaningful, simulation runs manageable, and animations readable.
MIN_WAREHOUSE_ROWS = 7
MAX_WAREHOUSE_ROWS = 15
MIN_WAREHOUSE_COLUMNS = 9
MAX_WAREHOUSE_COLUMNS = 15

MIN_RACK_ROWS = 2
MAX_RACK_ROWS = 6
MIN_RACK_COLUMNS = 2
MAX_RACK_COLUMNS = 6
MIN_RACK_SPACING = 2.0

MIN_ROBOTS = 2
MAX_ROBOTS = 8
MIN_ROBOT_START_SPACING = 1.5

MIN_TASKS = 10
MAX_TASKS = 100

MIN_STORAGE_RATIO = 20
MAX_STORAGE_RATIO = 80
STORAGE_RATIO_STEP = 10


def max_rack_rows_for_height(
    warehouse_rows: int,
) -> int:
    """Maximum rack rows while preserving about 2 grid units vertically."""
    minimum_y = 2.0
    maximum_y = float(warehouse_rows - 1)
    usable_span = max(0.0, maximum_y - minimum_y)

    spacing_limited = int(
        usable_span // MIN_RACK_SPACING
    ) + 1

    return max(
        MIN_RACK_ROWS,
        min(MAX_RACK_ROWS, spacing_limited),
    )


def max_rack_columns_for_width(
    warehouse_columns: int,
) -> int:
    """Maximum rack columns while preserving about 2 grid units horizontally."""
    minimum_x = 1.0
    maximum_x = float(warehouse_columns - 2)
    usable_span = max(0.0, maximum_x - minimum_x)

    spacing_limited = int(
        usable_span // MIN_RACK_SPACING
    ) + 1

    return max(
        MIN_RACK_COLUMNS,
        min(MAX_RACK_COLUMNS, spacing_limited),
    )


def max_robots_for_width(
    warehouse_columns: int,
) -> int:
    """Maximum robots that keep the bottom staging corridor readable."""
    corridor_length = float(warehouse_columns - 1)

    spacing_limited = int(
        corridor_length / MIN_ROBOT_START_SPACING
        - 1
    )

    return max(
        MIN_ROBOTS,
        min(MAX_ROBOTS, spacing_limited),
    )

def generate_rack_locations(
    warehouse_rows: int,
    warehouse_columns: int,
    rack_rows: int,
    rack_columns: int,
) -> dict[str, tuple[float, float]]:
    max_rack_rows = max_rack_rows_for_height(
        warehouse_rows
    )
    max_rack_columns = max_rack_columns_for_width(
        warehouse_columns
    )

    if not MIN_RACK_ROWS <= rack_rows <= max_rack_rows:
        raise ValueError(
            f"Rack rows must be between {MIN_RACK_ROWS} "
            f"and {max_rack_rows} for a warehouse "
            f"height of {warehouse_rows}."
        )

    if not MIN_RACK_COLUMNS <= rack_columns <= max_rack_columns:
        raise ValueError(
            f"Rack columns must be between {MIN_RACK_COLUMNS} "
            f"and {max_rack_columns} for a warehouse "
            f"width of {warehouse_columns}."
        )

    # Keep the bottom y=0 line as the robot corridor and leave an additional
    # grid unit of separation before the first rack row.
    minimum_x = 1.0
    maximum_x = float(
        warehouse_columns - 2
    )

    minimum_y = 2.0
    maximum_y = float(
        warehouse_rows - 1
    )

    if rack_columns == 1:
        column_positions = [
            (minimum_x + maximum_x) / 2
        ]
    else:
        column_spacing = (
            maximum_x - minimum_x
        ) / (
            rack_columns - 1
        )

        column_positions = [
            minimum_x
            + column_index * column_spacing
            for column_index in range(
                rack_columns
            )
        ]

    if rack_rows == 1:
        row_positions = [
            (minimum_y + maximum_y) / 2
        ]
    else:
        row_spacing = (
            maximum_y - minimum_y
        ) / (
            rack_rows - 1
        )

        # Number racks from top to bottom so A1/B1/... are always the top row,
        # matching the predefined warehouse convention.
        row_positions = [
            maximum_y
            - row_index * row_spacing
            for row_index in range(
                rack_rows
            )
        ]

    rack_positions: dict[
        str,
        tuple[float, float],
    ] = {}

    for row_index, row in enumerate(
        row_positions
    ):
        for column_index, column in enumerate(
            column_positions
        ):
            rack_letter = chr(
                65 + column_index
            )

            rack_name = (
                f"{rack_letter}"
                f"{row_index + 1}"
            )

            rack_positions[rack_name] = (
                float(column),
                float(row),
            )

    return rack_positions


def generate_warehouse_grid(
    rows: int,
    columns: int,
    rack_row_spacing: int = 2,
    rack_column_spacing: int = 2,
) -> tuple[list[list[str]], dict[str, tuple[int, int]]]:
    grid = [
        ["empty" for _ in range(columns)]
        for _ in range(rows)
    ]

    rack_positions: dict[str, tuple[int, int]] = {}
    rack_number = 1

    for row in range(
        rack_row_spacing,
        rows - 1,
        rack_row_spacing + 1,
    ):
        for column in range(
            rack_column_spacing,
            columns - 1,
            rack_column_spacing + 1,
        ):
            rack_name = f"R{rack_number:02d}"

            grid[row][column] = rack_name
            rack_positions[rack_name] = (
                column,
                row,
            )

            rack_number += 1

    return grid, rack_positions

def generate_rack_names(
    rack_columns: int,
    rack_rows: int,
) -> list[str]:
    return [
        f"{chr(65 + column)}{row + 1}"
        for column in range(rack_columns)
        for row in range(rack_rows)
    ]

def generate_custom_tasks(
    number_of_tasks: int,
    storage_ratio: int,
    arrival_pattern: str,
    rack_positions: dict[str, tuple[float, float]],
) -> list[dict]:
    interval = ARRIVAL_INTERVALS[arrival_pattern]
    storage_target = storage_ratio / 100.0

    rack_names = sorted(rack_positions)
    #  Error handling for empty rack positions
    if not rack_names:
        raise ValueError(
            "The warehouse must contain at least one rack."
        )

    tasks: list[dict] = []
    storage_created = 0

    for index in range(number_of_tasks):
        expected_storage = round(
            (index + 1) * storage_target
        )

        if storage_created < expected_storage:
            task_type = "storage"
            storage_created += 1
        else:
            task_type = "retrieval"

        # Assign rack name based on index and available racks
        rack_name = rack_names[
            index % len(rack_names)
        ]


        tasks.append(
            {
                "task_id": f"T{index + 1:03d}",
                "task_type": task_type,
                "arrival_time": round(
                    index * interval,
                    2,
                ),
                "rack_name": rack_name,
                "rack_position": rack_positions[rack_name],
            }
        )

    return tasks

def generate_robot_start_positions(
    number_of_robots: int,
    entry_point: tuple[float, float],
    exit_point: tuple[float, float],
) -> dict[int, tuple[float, float]]:
    entry_x, entry_y = entry_point
    exit_x, exit_y = exit_point

    if number_of_robots < 1:
        raise ValueError(
            "The warehouse must contain at least "
            "one robot."
        )

    # Divide the full distance into equal gaps:
    #
    # Input -> R1 -> R2 -> ... -> Output
    #
    # Number of gaps = number of robots + 1
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
            entry_x
            + robot_id * spacing_x,
            entry_y
            + robot_id * spacing_y,
        )
        for robot_id in range(
            1,
            number_of_robots + 1
        )
    }


def build_custom_scenario(
    warehouse_rows: int,
    warehouse_columns: int,
    rack_rows: int,
    rack_columns: int,
    number_of_robots: int,
    number_of_tasks: int,
    storage_ratio: int,
    arrival_pattern: str,
    enable_robot_failure: bool,
    failed_robot_id: int | None,
    failure_time: float | None,
    enable_standby_robot: bool,
    standby_activation_delay: float | None,
) -> tuple[str, dict]:
    rack_positions = generate_rack_locations(
        warehouse_rows=warehouse_rows,
        warehouse_columns=warehouse_columns,
        rack_rows=rack_rows,
        rack_columns=rack_columns,
    )

    tasks = generate_custom_tasks(
        number_of_tasks=number_of_tasks,
        storage_ratio=storage_ratio,
        arrival_pattern=arrival_pattern,
        rack_positions=rack_positions,
    )

    entry_point = (0, 0)

    exit_point = (
        warehouse_columns - 1,
        0,
    )

    # A standby robot is a separate physical unit, not one of the
    # normal active robots. Reserve a distinct staging position for it.
    total_physical_robots = (
        number_of_robots
        + (1 if enable_standby_robot else 0)
    )

    robot_start_positions = (
        generate_robot_start_positions(
            number_of_robots=total_physical_robots,
            entry_point=entry_point,
            exit_point=exit_point,
        )
    )

    standby_robot_id = (
        number_of_robots + 1
        if enable_standby_robot
        else None
    )

    scenario = {
        "name": "Custom Configuration",
        "description": (
            "A user-configured scenario generated "
            "automatically from the selected parameters."
        ),
        "number_of_robots": number_of_robots,
        "robot_failure": {
            "enabled": enable_robot_failure,
            "robot_id": (
                int(failed_robot_id)
                if failed_robot_id is not None
                else None
            ),
            "failure_time": (
                float(failure_time)
                if failure_time is not None
                else None
            ),
        },
        "standby_robot": {
            "enabled": bool(enable_standby_robot),
            "robot_id": standby_robot_id,
            "activation_delay": (
                float(standby_activation_delay)
                if standby_activation_delay is not None
                else None
            ),
        },
        "warehouse": {
            "rows": warehouse_rows,
            "columns": warehouse_columns,
            "rack_positions": rack_positions,
            "entry_point": entry_point,
            "exit_point": exit_point,
            "robot_start_positions": (
                robot_start_positions
            ),
        },
        "tasks": tasks,
    }

    # Generate a stable identifier from the complete custom scenario.
    # Any meaningful configuration change produces a different cache key.
    signature = json.dumps(
        scenario,
        sort_keys=True,
    )

    digest = hashlib.sha256(
        (
            signature
            + str(number_of_robots)
            + arrival_pattern
        ).encode("utf-8")
    ).hexdigest()[:12]

    return f"custom_{digest}", scenario


def _summary_table(
    warehouse_rows: int,
    warehouse_columns: int,
    rack_count: int,
    rack_positions: dict[str, tuple[int, int]],
    number_of_robots: int,
    number_of_tasks: int,
    arrival_pattern: str,
    storage_ratio: int,
    retrieval_ratio: int,
    enable_robot_failure: bool,
    failed_robot_id: int | None,
    failure_time: float | None,
    enable_standby_robot: bool,
    standby_activation_delay: float | None,
) -> None:
    failure_text = "Disabled"

    standby_text = "Disabled"

    if enable_robot_failure:
        failure_text = (
            f"Robot {failed_robot_id} becomes unavailable "
            f"at time {failure_time}; remaining robots "
            "continue processing pending tasks"
        )

        if enable_standby_robot:
            standby_id = number_of_robots + 1
            standby_text = (
                f"Robot {standby_id} activates "
                f"{standby_activation_delay} time units "
                "after the failure"
            )

    summary_html = (
        '<div class="custom-summary-card">'

        '<div class="custom-summary-title">'
        'Custom Configuration'
        '</div>'

        '<div class="summary-row">'
        '<span>Warehouse Size</span>'
        f'<strong>{warehouse_rows} × '
        f'{warehouse_columns}</strong>'
        '</div>'

        '<div class="summary-row">'
        '<span>Rack Positions</span>'
        f'<strong>{rack_count}</strong>'
        '</div>'

        '<div class="summary-divider"></div>'

        '<div class="summary-row">'
        '<span>Active Robots</span>'
        f'<strong>{number_of_robots}</strong>'
        '</div>'

        '<div class="summary-row">'
        '<span>Tasks</span>'
        f'<strong>{number_of_tasks}</strong>'
        '</div>'

        '<div class="summary-row">'
        '<span>Arrival Pattern</span>'
        f'<strong>{arrival_pattern}</strong>'
        '</div>'

        '<div class="summary-row">'
        '<span>Storage / Retrieval</span>'
        f'<strong>{storage_ratio}% / '
        f'{retrieval_ratio}%</strong>'
        '</div>'

        '<div class="summary-row">'
        '<span>Robot Failure</span>'
        f'<strong>{failure_text}</strong>'
        '</div>'

        '<div class="summary-row">'
        '<span>Standby Robot</span>'
        f'<strong>{standby_text}</strong>'
        '</div>'

        '</div>'
    )

    st.html(summary_html)

def render_custom_sidebar(
    clear_callback: Callable[[], None],
) -> dict:
    with st.sidebar:
        st.markdown("### 1. Warehouse layout")

        left, right = st.columns(2)

        with left:
            warehouse_rows = st.number_input(
                "Rows (Y)",
                min_value=MIN_WAREHOUSE_ROWS,
                max_value=MAX_WAREHOUSE_ROWS,
                value=7,
                step=1,
                help=(
                    "Custom simulation scope: "
                    f"{MIN_WAREHOUSE_ROWS}–{MAX_WAREHOUSE_ROWS} rows."
                ),
            )

        with right:
            warehouse_columns = st.number_input(
                "Columns (X)",
                min_value=MIN_WAREHOUSE_COLUMNS,
                max_value=MAX_WAREHOUSE_COLUMNS,
                value=9,
                step=1,
                help=(
                    "Custom simulation scope: "
                    f"{MIN_WAREHOUSE_COLUMNS}–"
                    f"{MAX_WAREHOUSE_COLUMNS} columns."
                ),
            )

        max_rack_rows = max_rack_rows_for_height(
            int(warehouse_rows)
        )
        max_rack_columns = max_rack_columns_for_width(
            int(warehouse_columns)
        )

        rack_left, rack_right = st.columns(2)

        with rack_left:
            rack_rows = st.number_input(
                "Rack rows",
                min_value=MIN_RACK_ROWS,
                max_value=max_rack_rows,
                value=min(3, max_rack_rows),
                step=1,
                help=(
                    "The maximum changes with warehouse "
                    "height to preserve rack spacing."
                ),
            )

        with rack_right:
            rack_columns = st.number_input(
                "Rack columns",
                min_value=MIN_RACK_COLUMNS,
                max_value=max_rack_columns,
                value=min(4, max_rack_columns),
                step=1,
                help=(
                    "The maximum changes with warehouse "
                    "width to preserve rack spacing."
                ),
            )

        st.caption(
            f"For a {int(warehouse_rows)} × "
            f"{int(warehouse_columns)} warehouse, "
            f"the supported rack layout is up to "
            f"{max_rack_rows} rows × "
            f"{max_rack_columns} columns."
        )

        st.markdown("### 2. Robot configuration")

        max_robots = max_robots_for_width(
            int(warehouse_columns)
        )

        number_of_robots = st.number_input(
            "Number of robots",
            min_value=MIN_ROBOTS,
            max_value=max_robots,
            value=min(3, max_robots),
            step=1,
            help=(
                "The maximum changes with warehouse width "
                "so robot starting positions remain separated "
                "along the bottom corridor."
            ),
        )

        st.caption(
            f"This warehouse width supports up to "
            f"{max_robots} robots in the custom model."
        )

        enable_robot_failure = st.checkbox(
            "Enable robot failure",
            value=False,
            key="custom_enable_robot_failure",
            disabled=int(number_of_robots) < 2,
            help=(
                "Robot failure requires at least two robots "
                "so remaining tasks can still be completed."
            ),
        )

        failed_robot_id = None
        failure_time = None
        enable_standby_robot = False
        standby_activation_delay = None

        if enable_robot_failure:
            failed_robot_id = st.selectbox(
                "Robot to fail",
                options=list(
                    range(
                        1,
                        int(number_of_robots) + 1,
                    )
                ),
                format_func=lambda robot_id: (
                    f"Robot {robot_id}"
                ),
                key="custom_failed_robot_id",
            )

            failure_time = st.number_input(
                "Failure time",
                min_value=0.0,
                value=30.0,
                step=1.0,
                key="custom_failure_time",
                help=(
                    "Simulation time when the selected robot "
                    "stops receiving new tasks."
                ),
            )

            st.caption(
                "Failure assumption: if the robot is already "
                "processing a task at the failure time, it "
                "finishes that task and then remains unavailable. "
                "The remaining operational robots continue with "
                "all pending tasks."
            )

            standby_slot_available = (
                int(number_of_robots) < max_robots
            )

            enable_standby_robot = st.checkbox(
                "Enable standby replacement robot",
                value=False,
                key="custom_enable_standby_robot",
                disabled=not standby_slot_available,
                help=(
                    "A separate standby robot is kept inactive until "
                    "a configured delay after the failure. It then joins "
                    "the available robot pool as replacement capacity."
                ),
            )

            if not standby_slot_available:
                enable_standby_robot = False
                st.caption(
                    "A standby robot requires one additional staging "
                    "position. Reduce the number of active robots to "
                    f"{max_robots - 1} or fewer to enable it."
                )

            if enable_standby_robot:
                standby_activation_delay = st.number_input(
                    "Standby activation delay",
                    min_value=0.0,
                    value=20.0,
                    step=1.0,
                    key="custom_standby_activation_delay",
                    help=(
                        "Delay after the failure before the standby "
                        "robot becomes operational."
                    ),
                )

                st.caption(
                    f"Standby Robot {int(number_of_robots) + 1} will "
                    "remain inactive at its staging position and enter "
                    "service after the selected delay."
                )

        st.markdown("### 3. Task configuration")

        number_of_tasks = st.number_input(
            "Total number of tasks",
            min_value=MIN_TASKS,
            max_value=MAX_TASKS,
            value=50,
            step=1,
            help=(
                "The custom configuration supports "
                f"{MIN_TASKS}–{MAX_TASKS} tasks. "
                "Higher-load edge cases can be represented "
                "through the predefined stress scenarios."
            ),
        )

        arrival_pattern = st.selectbox(
            "Task arrival pattern",
            list(ARRIVAL_INTERVALS.keys()),
            index=1,
        )

        storage_ratio = st.slider(
            "Storage ratio (%)",
            min_value=MIN_STORAGE_RATIO,
            max_value=MAX_STORAGE_RATIO,
            value=50,
            step=STORAGE_RATIO_STEP,
            help=(
                "The custom mode keeps both storage and "
                "retrieval tasks represented. Extreme "
                "single-type workloads are better handled "
                "as dedicated predefined scenarios."
            ),
        )

        retrieval_ratio = 100 - storage_ratio

        scenario_key, selected_scenario = (
            build_custom_scenario(
                warehouse_rows=int(
                    warehouse_rows
                ),
                warehouse_columns=int(
                    warehouse_columns
                ),
                rack_rows=int(rack_rows),
                rack_columns=int(rack_columns),
                number_of_robots=int(
                    number_of_robots
                ),
                number_of_tasks=int(
                    number_of_tasks
                ),
                storage_ratio=int(
                    storage_ratio
                ),
                arrival_pattern=arrival_pattern,
                enable_robot_failure=(
                    enable_robot_failure
                ),
                failed_robot_id=failed_robot_id,
                failure_time=failure_time,
                enable_standby_robot=(
                    enable_standby_robot
                ),
                standby_activation_delay=(
                    standby_activation_delay
                ),
            )
        )

        rack_positions = selected_scenario[
            "warehouse"
        ]["rack_positions"]

        st.markdown(
            "### Configuration summary"
        )

        _summary_table(
            warehouse_rows=int(
                warehouse_rows
            ),
            warehouse_columns=int(
                warehouse_columns
            ),
            rack_count=len(
                rack_positions
            ),
            rack_positions=rack_positions,
            number_of_robots=int(
                number_of_robots
            ),
            number_of_tasks=int(
                number_of_tasks
            ),
            arrival_pattern=arrival_pattern,
            storage_ratio=int(
                storage_ratio
            ),
            retrieval_ratio=int(
                retrieval_ratio
            ),
            enable_robot_failure=enable_robot_failure,
            failed_robot_id=failed_robot_id,
            failure_time=failure_time,
            enable_standby_robot=enable_standby_robot,
            standby_activation_delay=(
                standby_activation_delay
            ),
        )

        st.button(
            "Clear selection",
            use_container_width=True,
            on_click=clear_callback,
        )

        errors = validate_configuration(
            warehouse_rows=int(
                warehouse_rows
            ),
            warehouse_columns=int(
                warehouse_columns
            ),
            rack_rows=int(rack_rows),
            rack_columns=int(rack_columns),
            number_of_robots=int(
                number_of_robots
            ),
            number_of_tasks=int(
                number_of_tasks
            ),
            storage_ratio=int(
                storage_ratio
            ),
            enable_standby_robot=(
                enable_standby_robot
            ),
        )

        if enable_robot_failure:
            if failed_robot_id is None:
                errors.append(
                    "Please select a robot to fail."
                )

            if failure_time is None:
                errors.append(
                    "Please enter the failure time."
                )

            if enable_standby_robot:
                if standby_activation_delay is None:
                    errors.append(
                        "Please enter the standby activation delay."
                    )
                elif standby_activation_delay < 0:
                    errors.append(
                        "Standby activation delay cannot be negative."
                    )


        for error in errors:
            st.error(error)

        run_clicked = st.button(
            "▶ Run strategy comparison",
            use_container_width=True,
            type="primary",
            disabled=bool(errors),
        )

        st.caption(
            "Both FIFO and Deferred Commitment "
            "are run using the custom configuration."
        )

    return {
        "mode": "custom",
        "scenario_key": scenario_key,
        "scenario": selected_scenario,
        "run_clicked": run_clicked,
    }

def validate_configuration(
    warehouse_rows: int,
    warehouse_columns: int,
    rack_rows: int,
    rack_columns: int,
    number_of_robots: int,
    number_of_tasks: int,
    storage_ratio: int,
    enable_standby_robot: bool = False,
) -> list[str]:
    errors: list[str] = []

    if not (
        MIN_WAREHOUSE_ROWS
        <= warehouse_rows
        <= MAX_WAREHOUSE_ROWS
    ):
        errors.append(
            "Warehouse rows must be between "
            f"{MIN_WAREHOUSE_ROWS} and "
            f"{MAX_WAREHOUSE_ROWS}."
        )

    if not (
        MIN_WAREHOUSE_COLUMNS
        <= warehouse_columns
        <= MAX_WAREHOUSE_COLUMNS
    ):
        errors.append(
            "Warehouse columns must be between "
            f"{MIN_WAREHOUSE_COLUMNS} and "
            f"{MAX_WAREHOUSE_COLUMNS}."
        )

    max_rack_rows = max_rack_rows_for_height(
        warehouse_rows
    )
    max_rack_columns = max_rack_columns_for_width(
        warehouse_columns
    )

    if not (
        MIN_RACK_ROWS
        <= rack_rows
        <= max_rack_rows
    ):
        errors.append(
            f"For a warehouse height of {warehouse_rows}, "
            f"rack rows must be between {MIN_RACK_ROWS} "
            f"and {max_rack_rows}."
        )

    if not (
        MIN_RACK_COLUMNS
        <= rack_columns
        <= max_rack_columns
    ):
        errors.append(
            f"For a warehouse width of {warehouse_columns}, "
            f"rack columns must be between "
            f"{MIN_RACK_COLUMNS} and "
            f"{max_rack_columns}."
        )

    max_robots = max_robots_for_width(
        warehouse_columns
    )

    if not (
        MIN_ROBOTS
        <= number_of_robots
        <= max_robots
    ):
        errors.append(
            f"For a warehouse width of {warehouse_columns}, "
            f"the number of robots must be between "
            f"{MIN_ROBOTS} and {max_robots}."
        )

    total_physical_robots = (
        number_of_robots
        + (1 if enable_standby_robot else 0)
    )

    if total_physical_robots > max_robots:
        errors.append(
            "The selected standby robot requires one additional "
            "staging position. Reduce the number of active robots "
            f"to {max_robots - 1} or fewer for this warehouse width."
        )

    if not (
        MIN_TASKS
        <= number_of_tasks
        <= MAX_TASKS
    ):
        errors.append(
            "Total tasks must be between "
            f"{MIN_TASKS} and {MAX_TASKS}."
        )

    if not (
        MIN_STORAGE_RATIO
        <= storage_ratio
        <= MAX_STORAGE_RATIO
    ):
        errors.append(
            "Storage ratio must be between "
            f"{MIN_STORAGE_RATIO}% and "
            f"{MAX_STORAGE_RATIO}%."
        )

    if (
        storage_ratio - MIN_STORAGE_RATIO
    ) % STORAGE_RATIO_STEP != 0:
        errors.append(
            "Storage ratio must use "
            f"{STORAGE_RATIO_STEP}% increments."
        )

    return errors