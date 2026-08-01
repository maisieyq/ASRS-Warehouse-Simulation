from __future__ import annotations

import json
import hashlib #unique identifier for custom scenarios
from typing import Callable

import pandas as pd #convert tasks to csv for hashing
import streamlit as st

from dashboard_common import ARRIVAL_INTERVALS

def generate_rack_locations(
    warehouse_rows: int,
    warehouse_columns: int,
    rack_rows: int,
    rack_columns: int,
) -> dict[str, tuple[int, int]]:
    if rack_rows > warehouse_rows - 2:
        raise ValueError(
            "The requested rack rows do not fit inside the warehouse."
        )

    if rack_columns > warehouse_columns - 2:
        raise ValueError(
            "The requested rack columns do not fit inside the warehouse."
        )

    row_positions = [
        round(
            1 + index * (warehouse_rows - 3) /
            max(rack_rows - 1, 1)
        )
        for index in range(rack_rows)
    ]

    column_positions = [
        round(
            1 + index * (warehouse_columns - 3) /
            max(rack_columns - 1, 1)
        )
        for index in range(rack_columns)
    ]

    rack_positions: dict[str, tuple[int, int]] = {}

    rack_number = 1

    for row in row_positions:
        for column in column_positions:
            rack_positions[f"R{rack_number:02d}"] = (
                column,
                row,
            )
            rack_number += 1

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
    rack_positions: dict[str, tuple[int, int]],
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
    warehouse_columns: int,
) -> dict[int, tuple[int, int]]:
    available_positions = [
        (column, 0)
        for column in range(
            1,
            warehouse_columns - 1,
        )
    ]

    if number_of_robots > len(
        available_positions
    ):
        raise ValueError(
            "There are too many robots for "
            "the selected warehouse width."
        )

    if number_of_robots == 1:
        selected_positions = [
            available_positions[
                len(available_positions) // 2
            ]
        ]
    else:
        last_index = len(
            available_positions
        ) - 1

        selected_positions = [
            available_positions[
                round(
                    index
                    * last_index
                    / (number_of_robots - 1)
                )
            ]
            for index in range(
                number_of_robots
            )
        ]

    return {
        robot_id: selected_positions[
            robot_id - 1
        ]
        for robot_id in range(
            1,
            number_of_robots + 1,
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
    helper_enabled: bool,
    helper_robot_id: int | None,
    helper_activation_time: float | None,
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

    robot_start_positions = (
        generate_robot_start_positions(
            number_of_robots=number_of_robots,
            warehouse_columns=warehouse_columns,
        )
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
            "helper_enabled": helper_enabled,
            "helper_robot_id": (
                int(helper_robot_id)
                if helper_robot_id is not None
                else None
            ),
            "helper_activation_time": (
                float(helper_activation_time)
                if helper_activation_time is not None
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

    # ????? 
    # this is to generate a unique identifier for the custom scenario based on its configuration. 
    # It creates a JSON string representation of the scenario, sorts the keys for consistency, and then computes a SHA-256 hash of this string combined with the number of robots and the arrival pattern. The first 12 characters of the hash are used as a unique digest to identify the custom scenario. This ensures that even if two scenarios have similar configurations, they will have different identifiers if any parameter differs.
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
    helper_enabled: bool,
    helper_robot_id: int | None,
    helper_activation_time: float | None,
) -> None:
    failure_text = "Disabled"

    if enable_robot_failure:
        failure_text = (
            f"Robot {failed_robot_id} fails at "
            f"time {failure_time}"
        )

        if helper_enabled:
            failure_text += (
                f"; Robot {helper_robot_id} "
                f"starts helping at time "
                f"{helper_activation_time}"
            )
        else:
            failure_text += (
                "; no helper selected, failed robot "
                "remains unavailable until simulation end"
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
        '<span>Robots</span>'
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
                min_value=4,
                max_value=20,
                value=7,
                step=1,
            )

        with right:
            warehouse_columns = st.number_input(
                "Columns (X)",
                min_value=4,
                max_value=20,
                value=9,
                step=1,
            )

        rack_left, rack_right = st.columns(2)

        with rack_left:
            rack_rows = st.number_input(
                "Rack rows",
                min_value=1,
                max_value=max(
                    1,
                    int(warehouse_rows) - 2,
                ),
                value=min(
                    3,
                    int(warehouse_rows) - 2,
                ),
                step=1,
            )

        with rack_right:
            rack_columns = st.number_input(
                "Rack columns",
                min_value=1,
                max_value=max(
                    1,
                    int(warehouse_columns) - 2,
                ),
                value=min(
                    4,
                    int(warehouse_columns) - 2,
                ),
                step=1,
            )

        st.markdown("### 2. Robot configuration")

        number_of_robots = st.number_input(
            "Number of robots",
            min_value=1,
            max_value=10,
            value=3,
            step=1,
        )

        enable_robot_failure = st.checkbox(
            "Enable robot failure",
            value=False,
            key="custom_enable_robot_failure",
        )

        failed_robot_id = None
        failure_time = None

        helper_enabled = False
        helper_robot_id = None
        helper_activation_time = None

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
                    "Simulation time when the selected "
                    "robot becomes unavailable."
                ),
            )

            helper_available = (
                int(number_of_robots) >= 2
            )

            helper_enabled = st.checkbox(
                "Enable helper robot",
                value=False,
                key="custom_helper_enabled",
                disabled=not helper_available,
                help=(
                    "Select another existing robot to receive "
                    "dispatch priority after the failure."
                ),
            )

            if helper_enabled:
                helper_robot_options = [
                    robot_id
                    for robot_id in range(
                        1,
                        int(number_of_robots) + 1,
                    )
                    if robot_id != failed_robot_id
                ]

                helper_robot_id = st.selectbox(
                    "Helper robot",
                    options=helper_robot_options,
                    format_func=lambda robot_id: (
                        f"Robot {robot_id}"
                    ),
                    key="custom_helper_robot_id",
                    help=(
                        "Select an existing robot to help "
                        "after the selected robot fails."
                    ),
                )

                helper_activation_time = st.number_input(
                    "Helper activation time",
                    min_value=float(
                        failure_time
                    ),
                    value=float(
                        failure_time + 20
                    ),
                    step=1.0,
                    key="custom_helper_activation_time",
                    help=(
                        "Simulation time when the selected "
                        "helper robot receives dispatch priority."
                    ),
                )
                
        st.markdown("### 3. Task configuration")

        number_of_tasks = st.number_input(
            "Total number of tasks",
            min_value=1,
            max_value=200,
            value=50,
            step=1,
        )

        arrival_pattern = st.selectbox(
            "Task arrival pattern",
            list(ARRIVAL_INTERVALS.keys()),
            index=1,
        )

        storage_ratio = st.slider(
            "Storage ratio (%)",
            min_value=0,
            max_value=100,
            value=50,
            step=5,
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
                helper_enabled=helper_enabled,
                helper_robot_id=helper_robot_id,
                helper_activation_time=(
                    helper_activation_time
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
            helper_enabled=helper_enabled,
            helper_robot_id=helper_robot_id,
            helper_activation_time=helper_activation_time,
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

            if helper_enabled:
                if helper_robot_id is None:
                    errors.append(
                        "Please select a helper robot."
                    )

                elif (
                    helper_robot_id
                    == failed_robot_id
                ):
                    errors.append(
                        "The failed robot cannot also "
                        "be the helper robot."
                    )

                if helper_activation_time is None:
                    errors.append(
                        "Please enter the helper "
                        "activation time."
                    )

                elif (
                    helper_activation_time
                    < failure_time
                ):
                    errors.append(
                        "Helper activation time cannot "
                        "be earlier than failure time."
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
) -> list[str]:
    errors: list[str] = []

    if warehouse_rows < 1:
        errors.append(
            "Warehouse height must be at least 1 row."
        )

    if warehouse_columns < 1:
        errors.append(
            "Warehouse width must be at least 1 column."
        )

    if rack_rows > warehouse_rows - 2:
        errors.append(
            "There are too many rack rows for the "
            "selected warehouse height."
        )

    if rack_columns > warehouse_columns - 2:
        errors.append(
            "There are too many rack columns for the "
            "selected warehouse width."
        )

    available_boundary_cells = (
        warehouse_rows * 2
        + warehouse_columns * 2
        - 4
    )

    if number_of_robots > available_boundary_cells:
        errors.append(
            "There are not enough starting cells "
            "for the selected number of robots."
        )

    available_starting_cells = (
        warehouse_columns - 2
    )

    if number_of_robots > available_starting_cells:
        errors.append(
            "There are too many robots for the "
            "available starting positions along "
            "the bottom corridor."
        )

    return errors
