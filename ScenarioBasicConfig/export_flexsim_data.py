import csv
from simulation import run_simulation
from animation import build_robot_timelines

strategy = "FIFO"   # later you can change to "DEFERRED"

result = run_simulation(strategy)
timelines = build_robot_timelines(result)

with open("outputs/flexsim_robot_timeline.csv", "w", newline="") as file:
    writer = csv.writer(file)

    writer.writerow([
        "robot_id",
        "start_time",
        "end_time",
        "start_x",
        "start_y",
        "end_x",
        "end_y",
        "status",
        "task_id",
        "task_type",
        "rack_name",
    ])

    for robot_id, segments in timelines.items():
        for segment in segments:
            writer.writerow([
                robot_id,
                segment["start_time"],
                segment["end_time"],
                segment["start_position"][0],
                segment["start_position"][1],
                segment["end_position"][0],
                segment["end_position"][1],
                segment["status"],
                segment["task_id"],
                segment["task_type"],
                segment["rack_name"],
            ])

print("Exported: outputs/flexsim_robot_timeline.csv")