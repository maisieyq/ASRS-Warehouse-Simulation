# =========================================================
# PREDEFINED SCENARIOS
# =========================================================

BASELINE_TASKS = [
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


HIGH_DEMAND_TASKS = [
    {
        "task_id": "T01",
        "task_type": "storage",
        "arrival_time": 0,
        "rack_name": "A1",
    },
    {
        "task_id": "T02",
        "task_type": "retrieval",
        "arrival_time": 1,
        "rack_name": "D2",
    },
    {
        "task_id": "T03",
        "task_type": "storage",
        "arrival_time": 2,
        "rack_name": "B3",
    },
    {
        "task_id": "T04",
        "task_type": "retrieval",
        "arrival_time": 3,
        "rack_name": "A2",
    },
    {
        "task_id": "T05",
        "task_type": "storage",
        "arrival_time": 4,
        "rack_name": "C1",
    },
    {
        "task_id": "T06",
        "task_type": "retrieval",
        "arrival_time": 5,
        "rack_name": "D1",
    },
    {
        "task_id": "T07",
        "task_type": "storage",
        "arrival_time": 6,
        "rack_name": "B1",
    },
    {
        "task_id": "T08",
        "task_type": "retrieval",
        "arrival_time": 7,
        "rack_name": "C3",
    },
    {
        "task_id": "T09",
        "task_type": "storage",
        "arrival_time": 8,
        "rack_name": "D3",
    },
    {
        "task_id": "T10",
        "task_type": "retrieval",
        "arrival_time": 9,
        "rack_name": "B2",
    },
    {
        "task_id": "T11",
        "task_type": "storage",
        "arrival_time": 10,
        "rack_name": "A3",
    },
    {
        "task_id": "T12",
        "task_type": "retrieval",
        "arrival_time": 11,
        "rack_name": "C2",
    },
]

STORAGE_DOMINANT_TASKS = [
    {
        "task_id": "T01",
        "task_type": "storage",
        "arrival_time": 0,
        "rack_name": "A1",
    },
    {
        "task_id": "T02",
        "task_type": "storage",
        "arrival_time": 1,
        "rack_name": "B1",
    },
    {
        "task_id": "T03",
        "task_type": "storage",
        "arrival_time": 2,
        "rack_name": "C1",
    },
    {
        "task_id": "T04",
        "task_type": "retrieval",
        "arrival_time": 3,
        "rack_name": "D2",
    },
    {
        "task_id": "T05",
        "task_type": "storage",
        "arrival_time": 4,
        "rack_name": "A2",
    },
    {
        "task_id": "T06",
        "task_type": "storage",
        "arrival_time": 5,
        "rack_name": "B2",
    },
    {
        "task_id": "T07",
        "task_type": "retrieval",
        "arrival_time": 6,
        "rack_name": "C3",
    },
    {
        "task_id": "T08",
        "task_type": "storage",
        "arrival_time": 7,
        "rack_name": "D1",
    },
    {
        "task_id": "T09",
        "task_type": "storage",
        "arrival_time": 8,
        "rack_name": "A3",
    },
    {
        "task_id": "T10",
        "task_type": "retrieval",
        "arrival_time": 9,
        "rack_name": "B3",
    },
    {
        "task_id": "T11",
        "task_type": "storage",
        "arrival_time": 10,
        "rack_name": "C2",
    },
    {
        "task_id": "T12",
        "task_type": "retrieval",
        "arrival_time": 11,
        "rack_name": "D3",
    },
]


RETRIEVAL_DOMINANT_TASKS = [
    {
        "task_id": "T01",
        "task_type": "retrieval",
        "arrival_time": 0,
        "rack_name": "A1",
    },
    {
        "task_id": "T02",
        "task_type": "retrieval",
        "arrival_time": 1,
        "rack_name": "D2",
    },
    {
        "task_id": "T03",
        "task_type": "storage",
        "arrival_time": 2,
        "rack_name": "B3",
    },
    {
        "task_id": "T04",
        "task_type": "retrieval",
        "arrival_time": 3,
        "rack_name": "A2",
    },
    {
        "task_id": "T05",
        "task_type": "retrieval",
        "arrival_time": 4,
        "rack_name": "C1",
    },
    {
        "task_id": "T06",
        "task_type": "retrieval",
        "arrival_time": 5,
        "rack_name": "D1",
    },
    {
        "task_id": "T07",
        "task_type": "storage",
        "arrival_time": 6,
        "rack_name": "B1",
    },
    {
        "task_id": "T08",
        "task_type": "retrieval",
        "arrival_time": 7,
        "rack_name": "C3",
    },
    {
        "task_id": "T09",
        "task_type": "retrieval",
        "arrival_time": 8,
        "rack_name": "D3",
    },
    {
        "task_id": "T10",
        "task_type": "storage",
        "arrival_time": 9,
        "rack_name": "B2",
    },
    {
        "task_id": "T11",
        "task_type": "retrieval",
        "arrival_time": 10,
        "rack_name": "A3",
    },
    {
        "task_id": "T12",
        "task_type": "storage",
        "arrival_time": 11,
        "rack_name": "C2",
    },
]


SCENARIOS = {
    "baseline": {
        "name": "Baseline Scenario",
        "description": (
            "Normal warehouse condition with 3 robots and "
            "a balanced mix of storage and retrieval tasks."
        ),
        "number_of_robots": 3,
        "tasks": BASELINE_TASKS,
    },

    "high_demand": {
        "name": "High Demand Scenario",
        "description": (
            "Higher workload condition with more tasks arriving "
            "closely together. This creates queue pressure."
        ),
        "number_of_robots": 3,
        "tasks": HIGH_DEMAND_TASKS,
    },

    "low_availability": {
        "name": "Low Availability Scenario",
        "description": (
            "Limited robot availability condition with only "
            "2 robots handling the baseline workload."
        ),
        "number_of_robots": 2,
        "tasks": BASELINE_TASKS,
    },

    "high_availability": {
        "name": "High Availability Scenario",
        "description": (
            "Increased robot availability condition with "
            "5 robots handling the baseline workload."
        ),
        "number_of_robots": 5,
        "tasks": BASELINE_TASKS,
    },
    
    "storage_dominant": {
        "name": "Storage-Dominant Scenario",
        "description": (
            "Inbound-heavy warehouse condition with more storage "
            "tasks than retrieval tasks. This scenario evaluates "
            "how the dispatching strategies perform when robots "
            "frequently travel from the input station to rack "
            "access points."
        ),
        "number_of_robots": 3,
        "tasks": STORAGE_DOMINANT_TASKS,
    },

    "retrieval_dominant": {
        "name": "Retrieval-Dominant Scenario",
        "description": (
            "Outbound-heavy warehouse condition with more retrieval "
            "tasks than storage tasks. This scenario evaluates "
            "how the dispatching strategies perform when robots "
            "frequently travel from rack access points to the "
            "output station."
        ),
        "number_of_robots": 3,
        "tasks": RETRIEVAL_DOMINANT_TASKS,
    },
}


def get_scenario(scenario_name):
    scenario_name = scenario_name.lower()

    if scenario_name not in SCENARIOS:
        available = ", ".join(SCENARIOS.keys())

        raise ValueError(
            f"Unknown scenario: {scenario_name}. "
            f"Available scenarios: {available}"
        )

    return SCENARIOS[scenario_name]


def list_scenarios():
    return list(SCENARIOS.keys())