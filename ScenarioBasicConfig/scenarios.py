# =========================================================
# PREDEFINED SCENARIOS
# =========================================================

BASELINE_TASKS = [
    {"task_id": "T01", "task_type": "storage", "arrival_time": 0.0, "rack_name": "A3"},
    {"task_id": "T02", "task_type": "retrieval", "arrival_time": 4.0, "rack_name": "A2"},
    {"task_id": "T03", "task_type": "storage", "arrival_time": 8.0, "rack_name": "C2"},
    {"task_id": "T04", "task_type": "storage", "arrival_time": 12.0, "rack_name": "C2"},
    {"task_id": "T05", "task_type": "retrieval", "arrival_time": 16.0, "rack_name": "B1"},
    {"task_id": "T06", "task_type": "storage", "arrival_time": 20.0, "rack_name": "A1"},
    {"task_id": "T07", "task_type": "retrieval", "arrival_time": 24.0, "rack_name": "C1"},
    {"task_id": "T08", "task_type": "storage", "arrival_time": 28.0, "rack_name": "A1"},
    {"task_id": "T09", "task_type": "storage", "arrival_time": 32.0, "rack_name": "B2"},
    {"task_id": "T10", "task_type": "storage", "arrival_time": 36.0, "rack_name": "B1"},
    {"task_id": "T11", "task_type": "storage", "arrival_time": 40.0, "rack_name": "A2"},
    {"task_id": "T12", "task_type": "retrieval", "arrival_time": 44.0, "rack_name": "A1"},
    {"task_id": "T13", "task_type": "storage", "arrival_time": 48.0, "rack_name": "D2"},
    {"task_id": "T14", "task_type": "storage", "arrival_time": 52.0, "rack_name": "C1"},
    {"task_id": "T15", "task_type": "storage", "arrival_time": 56.0, "rack_name": "C1"},
    {"task_id": "T16", "task_type": "retrieval", "arrival_time": 60.0, "rack_name": "C3"},
    {"task_id": "T17", "task_type": "storage", "arrival_time": 64.0, "rack_name": "C2"},
    {"task_id": "T18", "task_type": "retrieval", "arrival_time": 68.0, "rack_name": "C3"},
]


HIGH_DEMAND_TASKS = [
    {"task_id": "T01", "task_type": "storage", "arrival_time": 0.0, "rack_name": "A3"},
    {"task_id": "T02", "task_type": "retrieval", "arrival_time": 1.5, "rack_name": "A2"},
    {"task_id": "T03", "task_type": "storage", "arrival_time": 3.0, "rack_name": "C2"},
    {"task_id": "T04", "task_type": "storage", "arrival_time": 4.5, "rack_name": "C2"},
    {"task_id": "T05", "task_type": "retrieval", "arrival_time": 6.0, "rack_name": "B1"},
    {"task_id": "T06", "task_type": "storage", "arrival_time": 7.5, "rack_name": "A1"},
    {"task_id": "T07", "task_type": "retrieval", "arrival_time": 9.0, "rack_name": "C1"},
    {"task_id": "T08", "task_type": "storage", "arrival_time": 10.5, "rack_name": "A1"},
    {"task_id": "T09", "task_type": "storage", "arrival_time": 12.0, "rack_name": "B2"},
    {"task_id": "T10", "task_type": "storage", "arrival_time": 13.5, "rack_name": "B1"},
    {"task_id": "T11", "task_type": "storage", "arrival_time": 15.0, "rack_name": "A2"},
    {"task_id": "T12", "task_type": "retrieval", "arrival_time": 16.5, "rack_name": "A1"},
    {"task_id": "T13", "task_type": "storage", "arrival_time": 18.0, "rack_name": "D2"},
    {"task_id": "T14", "task_type": "storage", "arrival_time": 19.5, "rack_name": "C1"},
    {"task_id": "T15", "task_type": "storage", "arrival_time": 21.0, "rack_name": "C1"},
    {"task_id": "T16", "task_type": "retrieval", "arrival_time": 22.5, "rack_name": "C3"},
    {"task_id": "T17", "task_type": "storage", "arrival_time": 24.0, "rack_name": "C2"},
    {"task_id": "T18", "task_type": "retrieval", "arrival_time": 25.5, "rack_name": "C3"},
    {"task_id": "T19", "task_type": "storage", "arrival_time": 27.0, "rack_name": "B1"},
    {"task_id": "T20", "task_type": "storage", "arrival_time": 28.5, "rack_name": "C2"},
    {"task_id": "T21", "task_type": "retrieval", "arrival_time": 30.0, "rack_name": "A1"},
    {"task_id": "T22", "task_type": "storage", "arrival_time": 31.5, "rack_name": "C3"},
    {"task_id": "T23", "task_type": "retrieval", "arrival_time": 33.0, "rack_name": "A2"},
    {"task_id": "T24", "task_type": "storage", "arrival_time": 34.5, "rack_name": "D3"},
]

STORAGE_DOMINANT_TASKS = [
    {"task_id": "T01", "task_type": "storage", "arrival_time": 0.0, "rack_name": "A3"},
    {"task_id": "T02", "task_type": "storage", "arrival_time": 4.0, "rack_name": "A2"},
    {"task_id": "T03", "task_type": "storage", "arrival_time": 8.0, "rack_name": "C2"},
    {"task_id": "T04", "task_type": "storage", "arrival_time": 12.0, "rack_name": "C2"},
    {"task_id": "T05", "task_type": "retrieval", "arrival_time": 16.0, "rack_name": "B1"},
    {"task_id": "T06", "task_type": "storage", "arrival_time": 20.0, "rack_name": "A1"},
    {"task_id": "T07", "task_type": "storage", "arrival_time": 24.0, "rack_name": "C1"},
    {"task_id": "T08", "task_type": "storage", "arrival_time": 28.0, "rack_name": "A1"},
    {"task_id": "T09", "task_type": "storage", "arrival_time": 32.0, "rack_name": "B2"},
    {"task_id": "T10", "task_type": "storage", "arrival_time": 36.0, "rack_name": "B1"},
    {"task_id": "T11", "task_type": "storage", "arrival_time": 40.0, "rack_name": "A2"},
    {"task_id": "T12", "task_type": "retrieval", "arrival_time": 44.0, "rack_name": "A1"},
    {"task_id": "T13", "task_type": "storage", "arrival_time": 48.0, "rack_name": "D2"},
    {"task_id": "T14", "task_type": "storage", "arrival_time": 52.0, "rack_name": "C1"},
    {"task_id": "T15", "task_type": "storage", "arrival_time": 56.0, "rack_name": "C1"},
    {"task_id": "T16", "task_type": "storage", "arrival_time": 60.0, "rack_name": "C3"},
    {"task_id": "T17", "task_type": "storage", "arrival_time": 64.0, "rack_name": "C2"},
    {"task_id": "T18", "task_type": "storage", "arrival_time": 68.0, "rack_name": "C3"},
]


RETRIEVAL_DOMINANT_TASKS = [
    {"task_id": "T01", "task_type": "retrieval", "arrival_time": 0.0, "rack_name": "A3"},
    {"task_id": "T02", "task_type": "retrieval", "arrival_time": 4.0, "rack_name": "A2"},
    {"task_id": "T03", "task_type": "retrieval", "arrival_time": 8.0, "rack_name": "C2"},
    {"task_id": "T04", "task_type": "retrieval", "arrival_time": 12.0, "rack_name": "C2"},
    {"task_id": "T05", "task_type": "retrieval", "arrival_time": 16.0, "rack_name": "B1"},
    {"task_id": "T06", "task_type": "storage", "arrival_time": 20.0, "rack_name": "A1"},
    {"task_id": "T07", "task_type": "retrieval", "arrival_time": 24.0, "rack_name": "C1"},
    {"task_id": "T08", "task_type": "retrieval", "arrival_time": 28.0, "rack_name": "A1"},
    {"task_id": "T09", "task_type": "retrieval", "arrival_time": 32.0, "rack_name": "B2"},
    {"task_id": "T10", "task_type": "retrieval", "arrival_time": 36.0, "rack_name": "B1"},
    {"task_id": "T11", "task_type": "storage", "arrival_time": 40.0, "rack_name": "A2"},
    {"task_id": "T12", "task_type": "retrieval", "arrival_time": 44.0, "rack_name": "A1"},
    {"task_id": "T13", "task_type": "retrieval", "arrival_time": 48.0, "rack_name": "D2"},
    {"task_id": "T14", "task_type": "retrieval", "arrival_time": 52.0, "rack_name": "C1"},
    {"task_id": "T15", "task_type": "retrieval", "arrival_time": 56.0, "rack_name": "C1"},
    {"task_id": "T16", "task_type": "retrieval", "arrival_time": 60.0, "rack_name": "C3"},
    {"task_id": "T17", "task_type": "storage", "arrival_time": 64.0, "rack_name": "C2"},
    {"task_id": "T18", "task_type": "retrieval", "arrival_time": 68.0, "rack_name": "C3"},
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