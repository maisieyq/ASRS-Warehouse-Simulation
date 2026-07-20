import hashlib
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

PROJECT_FOLDER = Path(__file__).resolve().parent
SCENARIO_FOLDER = PROJECT_FOLDER / "ScenarioBasicConfig"
if str(SCENARIO_FOLDER) not in sys.path:
    sys.path.insert(0, str(SCENARIO_FOLDER))

from scenarios import SCENARIOS
from simulation import run_simulation

st.set_page_config(
    page_title="Warehouse Strategy Dashboard",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .stApp {background: #f5f7fb;}
    .block-container {padding-top: 1.25rem; padding-bottom: 2rem; max-width: 1500px;}
    [data-testid="stSidebar"] {background: linear-gradient(180deg, #15243b 0%, #223653 100%);}
    [data-testid="stSidebar"] * {color: #f6f8fc;}
    [data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] > div {background: #ffffff; color: #172033;}
    [data-testid="stSidebar"] .stSelectbox svg {fill: #172033;}
    .hero {
        padding: 1.15rem 1.35rem;
        border-radius: 18px;
        color: white;
        background: linear-gradient(120deg, #172a46 0%, #264b73 60%, #3679a5 100%);
        box-shadow: 0 12px 30px rgba(31, 54, 82, 0.18);
        margin-bottom: 1rem;
    }
    .hero h1 {font-size: 2rem; margin: 0 0 .25rem 0;}
    .hero p {margin: 0; opacity: .88;}
    .section-title {font-size: 1.1rem; font-weight: 750; color: #172033; margin: .4rem 0 .55rem;}
    div[data-testid="stMetric"] {
        background: white;
        border: 1px solid #e1e7f0;
        padding: .85rem 1rem;
        border-radius: 14px;
        box-shadow: 0 5px 16px rgba(27, 45, 73, .07);
    }
    div[data-testid="stMetricLabel"] {font-weight: 650; color: #556176;}
    div[data-testid="stMetricValue"] {color: #172033;}
    .scenario-card {
        background: white;
        border-left: 5px solid #2f78a5;
        border-radius: 12px;
        padding: .8rem 1rem;
        box-shadow: 0 5px 16px rgba(27, 45, 73, .06);
        margin-bottom: .8rem;
    }
    .winner {
        padding: .75rem 1rem;
        border-radius: 12px;
        background: #eaf7f1;
        border: 1px solid #bae6d3;
        color: #155e43;
        font-weight: 700;
    }
    .stDownloadButton > button, .stButton > button {
        border-radius: 10px;
        font-weight: 700;
        min-height: 2.65rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def task_frame(result: dict, strategy_label: str) -> pd.DataFrame:
    rows = []
    for task in result["tasks"]:
        rows.append(
            {
                "Strategy": strategy_label,
                "Task ID": task.task_id,
                "Task Type": task.task_type.title(),
                "Rack": task.rack_name,
                "Arrival Time": task.arrival_time,
                "Start Time": task.start_time,
                "Completion Time": task.completion_time,
                "Waiting Time": task.waiting_time(),
                "Cycle Time": task.cycle_time(),
                "Travel Distance": task.travel_distance,
                "Robot ID": f"R{task.robot_id}",
            }
        )
    return pd.DataFrame(rows)


def robot_frame(result: dict, strategy_label: str) -> pd.DataFrame:
    makespan = result["summary"]["makespan"]
    rows = []
    for robot in result["robots"]:
        rows.append(
            {
                "Strategy": strategy_label,
                "Robot": f"R{robot.robot_id}",
                "Completed Tasks": robot.completed_tasks,
                "Total Distance": robot.total_distance,
                "Busy Time": robot.busy_time,
                "Utilization (%)": (robot.busy_time / makespan * 100) if makespan else 0,
            }
        )
    return pd.DataFrame(rows)


def queue_frame(result: dict, strategy_label: str) -> pd.DataFrame:
    df = pd.DataFrame(result["queue_history"])
    df["Strategy"] = strategy_label
    return df


def comparison_frame(fifo_summary: dict, deferred_summary: dict) -> pd.DataFrame:
    metrics = [
        ("Average Waiting Time", "average_waiting_time"),
        ("Average Completion Time", "average_completion_time"),
        ("Average Travel Distance", "average_travel_distance"),
        ("Makespan", "makespan"),
        ("Average Queue Length", "average_queue_length"),
        ("Maximum Queue Length", "maximum_queue_length"),
        ("Total Distance", "total_distance"),
    ]
    records = []
    for label, key in metrics:
        fifo_value = float(fifo_summary[key])
        deferred_value = float(deferred_summary[key])
        change = ((deferred_value - fifo_value) / fifo_value * 100) if fifo_value else 0.0
        records.append(
            {
                "Metric": label,
                "FIFO": fifo_value,
                "Deferred Commitment": deferred_value,
                "Deferred vs FIFO (%)": change,
                "Better Strategy": "FIFO" if fifo_value < deferred_value else "Deferred Commitment" if deferred_value < fifo_value else "Tie",
            }
        )
    return pd.DataFrame(records)


scenario_options = {config["name"]: key for key, config in SCENARIOS.items()}
REQUIRED_CSV_COLUMNS = ["task_id", "task_type", "arrival_time", "rack_name"]
VALID_TASK_TYPES = {"storage", "retrieval"}
VALID_RACKS = {f"{letter}{number}" for letter in "ABCD" for number in range(1, 4)}


def validate_uploaded_tasks(uploaded_df: pd.DataFrame) -> tuple[pd.DataFrame | None, list[str]]:
    """Validate and normalize an uploaded task CSV."""
    errors = []
    normalized = uploaded_df.copy()
    normalized.columns = [str(column).strip().lower() for column in normalized.columns]

    missing = [column for column in REQUIRED_CSV_COLUMNS if column not in normalized.columns]
    if missing:
        return None, [f"Missing required column(s): {', '.join(missing)}"]

    normalized = normalized[REQUIRED_CSV_COLUMNS].copy()
    if normalized.empty:
        errors.append("The uploaded CSV does not contain any task rows.")
        return None, errors

    for column in ["task_id", "task_type", "rack_name"]:
        normalized[column] = normalized[column].astype(str).str.strip()
    normalized["task_type"] = normalized["task_type"].str.lower()
    normalized["rack_name"] = normalized["rack_name"].str.upper()
    normalized["arrival_time"] = pd.to_numeric(normalized["arrival_time"], errors="coerce")

    if normalized["task_id"].eq("").any():
        errors.append("Every row must have a task_id.")
    duplicates = normalized.loc[normalized["task_id"].duplicated(), "task_id"].unique().tolist()
    if duplicates:
        errors.append(f"task_id values must be unique. Duplicates: {', '.join(duplicates)}")
    invalid_types = sorted(set(normalized["task_type"]) - VALID_TASK_TYPES)
    if invalid_types:
        errors.append(f"task_type must be storage or retrieval. Invalid value(s): {', '.join(invalid_types)}")
    invalid_racks = sorted(set(normalized["rack_name"]) - VALID_RACKS)
    if invalid_racks:
        errors.append(f"rack_name must be A1-A3, B1-B3, C1-C3, or D1-D3. Invalid value(s): {', '.join(invalid_racks)}")
    if normalized["arrival_time"].isna().any():
        errors.append("arrival_time must contain numeric values only.")
    elif (normalized["arrival_time"] < 0).any():
        errors.append("arrival_time cannot be negative.")

    if errors:
        return None, errors

    normalized = normalized.sort_values(["arrival_time", "task_id"]).reset_index(drop=True)
    return normalized, []


template_df = pd.DataFrame(
    [
        {"task_id": "T01", "task_type": "storage", "arrival_time": 0, "rack_name": "A1"},
        {"task_id": "T02", "task_type": "retrieval", "arrival_time": 2, "rack_name": "D2"},
    ]
)

with st.sidebar:
    st.markdown("## 🏭 Simulation Controls")
    input_mode = st.radio(
        "Scenario source",
        ["Predefined scenario", "Import CSV"],
        help="Choose an included scenario or upload your own task list.",
    )

    uploaded_tasks_df = None
    upload_errors = []

    if input_mode == "Predefined scenario":
        selected_name = st.selectbox("Basic scenario", list(scenario_options.keys()))
        scenario_key = scenario_options[selected_name]
        selected_scenario = SCENARIOS[scenario_key]
    else:
        uploaded_file = st.file_uploader("Upload task CSV", type=["csv"])
        number_of_robots = st.number_input(
            "Number of robots", min_value=1, max_value=20, value=3, step=1
        )
        st.download_button(
            "⬇ Download CSV template",
            template_df.to_csv(index=False).encode("utf-8"),
            file_name="warehouse_task_template.csv",
            mime="text/csv",
            use_container_width=True,
        )
        st.caption("Required columns: task_id, task_type, arrival_time, rack_name")

        if uploaded_file is not None:
            try:
                raw_upload = pd.read_csv(uploaded_file)
                uploaded_tasks_df, upload_errors = validate_uploaded_tasks(raw_upload)
            except Exception as exc:
                upload_errors = [f"The CSV could not be read: {exc}"]

        if uploaded_tasks_df is not None:
            file_hash = hashlib.sha256(uploaded_tasks_df.to_csv(index=False).encode("utf-8")).hexdigest()[:12]
            scenario_key = f"custom_{file_hash}_{int(number_of_robots)}"
            selected_name = "Imported CSV Scenario"
            selected_scenario = {
                "name": selected_name,
                "description": "A custom scenario created from the uploaded task CSV.",
                "number_of_robots": int(number_of_robots),
                "tasks": uploaded_tasks_df.to_dict("records"),
            }
        else:
            scenario_key = "custom_pending"
            selected_name = "Imported CSV Scenario"
            selected_scenario = {
                "name": selected_name,
                "description": "Upload a valid CSV file to create a custom scenario.",
                "number_of_robots": int(number_of_robots),
                "tasks": [],
            }

    st.markdown("### Scenario profile")
    st.write(selected_scenario["description"])
    st.caption(f"Robots: {selected_scenario['number_of_robots']}  •  Tasks: {len(selected_scenario['tasks'])}")

    if upload_errors:
        for error in upload_errors:
            st.error(error)

    can_run = input_mode == "Predefined scenario" or uploaded_tasks_df is not None
    run_clicked = st.button(
        "▶ Run strategy comparison",
        use_container_width=True,
        type="primary",
        disabled=not can_run,
    )
    st.caption("Both FIFO and Deferred Commitment are run using the selected scenario.")

st.markdown(
    """
    <div class="hero">
      <h1>Warehouse Strategy Comparison</h1>
      <p>Interactive SimPy dashboard for comparing FIFO and Deferred Commitment dispatching.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    f"""
    <div class="scenario-card">
      <b>{selected_scenario['name']}</b><br>
      {selected_scenario['description']}
    </div>
    """,
    unsafe_allow_html=True,
)

if input_mode == "Import CSV" and uploaded_tasks_df is not None:
    st.markdown('<div class="section-title">Imported task preview</div>', unsafe_allow_html=True)
    st.dataframe(uploaded_tasks_df, use_container_width=True, hide_index=True)

cache_key = f"results_{scenario_key}"
if can_run and (run_clicked or cache_key not in st.session_state):
    with st.spinner(f"Running {selected_name} under both strategies..."):
        if input_mode == "Import CSV":
            st.session_state[cache_key] = {
                "fifo": run_simulation("FIFO", scenario_config=selected_scenario),
                "deferred": run_simulation("DEFERRED", scenario_config=selected_scenario),
            }
        else:
            st.session_state[cache_key] = {
                "fifo": run_simulation("FIFO", scenario_name=scenario_key),
                "deferred": run_simulation("DEFERRED", scenario_name=scenario_key),
            }

if not can_run:
    st.info("Upload a valid CSV file to run the custom scenario. You can use the downloadable template in the sidebar.")
    st.stop()

results = st.session_state[cache_key]
fifo_result = results["fifo"]
deferred_result = results["deferred"]
fifo_summary = fifo_result["summary"]
deferred_summary = deferred_result["summary"]
comparison_df = comparison_frame(fifo_summary, deferred_summary)

fifo_tasks = task_frame(fifo_result, "FIFO")
deferred_tasks = task_frame(deferred_result, "Deferred Commitment")
all_tasks = pd.concat([fifo_tasks, deferred_tasks], ignore_index=True)
all_robots = pd.concat(
    [robot_frame(fifo_result, "FIFO"), robot_frame(deferred_result, "Deferred Commitment")],
    ignore_index=True,
)
all_queues = pd.concat(
    [queue_frame(fifo_result, "FIFO"), queue_frame(deferred_result, "Deferred Commitment")],
    ignore_index=True,
)

st.markdown('<div class="section-title">Performance snapshot</div>', unsafe_allow_html=True)
metric_cols = st.columns(6)
headline_metrics = [
    ("Avg waiting", "average_waiting_time"),
    ("Avg completion", "average_completion_time"),
    ("Avg distance", "average_travel_distance"),
    ("Makespan", "makespan"),
    ("Avg queue", "average_queue_length"),
    ("Max queue", "maximum_queue_length"),
]
for column, (label, key) in zip(metric_cols, headline_metrics):
    fifo_value = float(fifo_summary[key])
    deferred_value = float(deferred_summary[key])
    improvement = ((fifo_value - deferred_value) / fifo_value * 100) if fifo_value else 0
    column.metric(
        label,
        f"{deferred_value:.2f}",
        f"{improvement:+.1f}% vs FIFO",
        delta_color="normal",
        help="Main value is Deferred Commitment; delta compares it with FIFO. Positive means Deferred Commitment is lower/better.",
    )

fifo_score = sum(comparison_df["Better Strategy"].eq("FIFO"))
deferred_score = sum(comparison_df["Better Strategy"].eq("Deferred Commitment"))
winner = "Deferred Commitment" if deferred_score > fifo_score else "FIFO" if fifo_score > deferred_score else "Tie"
st.markdown(
    f'<div class="winner">Overall metric winner: {winner} &nbsp;•&nbsp; FIFO wins {fifo_score} metrics &nbsp;•&nbsp; Deferred Commitment wins {deferred_score} metrics</div>',
    unsafe_allow_html=True,
)

left, middle, right = st.columns([1.15, 1.15, 1])
with left:
    st.markdown('<div class="section-title">Core metric comparison</div>', unsafe_allow_html=True)
    plot_df = comparison_df[comparison_df["Metric"].isin(["Average Waiting Time", "Average Completion Time", "Makespan", "Average Queue Length"])].melt(
        id_vars="Metric", value_vars=["FIFO", "Deferred Commitment"], var_name="Strategy", value_name="Value"
    )
    fig = px.bar(plot_df, x="Metric", y="Value", color="Strategy", barmode="group", text_auto=".2f", color_discrete_sequence=["#2f78a5", "#ef8f2f"])
    fig.update_layout(height=350, margin=dict(l=10, r=10, t=10, b=10), legend_title_text="", xaxis_title="", yaxis_title="Value")
    st.plotly_chart(fig, use_container_width=True)

with middle:
    st.markdown('<div class="section-title">Queue length over time</div>', unsafe_allow_html=True)
    fig = px.line(all_queues, x="time", y="queue_length", color="Strategy", color_discrete_sequence=["#2f78a5", "#ef8f2f"])
    fig.update_layout(height=350, margin=dict(l=10, r=10, t=10, b=10), legend_title_text="", xaxis_title="Simulation time", yaxis_title="Pending tasks")
    st.plotly_chart(fig, use_container_width=True)

with right:
    st.markdown('<div class="section-title">Completed tasks by robot</div>', unsafe_allow_html=True)
    fig = px.bar(all_robots, x="Robot", y="Completed Tasks", color="Strategy", barmode="group", text_auto=True, color_discrete_sequence=["#2f78a5", "#ef8f2f"])
    fig.update_layout(height=350, margin=dict(l=10, r=10, t=10, b=10), legend_title_text="", yaxis=dict(dtick=1))
    st.plotly_chart(fig, use_container_width=True)

lower_left, lower_middle, lower_right = st.columns([1.1, 1.1, 1])
with lower_left:
    st.markdown('<div class="section-title">Task waiting-time distribution</div>', unsafe_allow_html=True)
    fig = px.box(all_tasks, x="Strategy", y="Waiting Time", points="all", color="Strategy", color_discrete_sequence=["#2f78a5", "#ef8f2f"])
    fig.update_layout(height=330, margin=dict(l=10, r=10, t=10, b=10), showlegend=False, xaxis_title="", yaxis_title="Waiting time")
    st.plotly_chart(fig, use_container_width=True)

with lower_middle:
    st.markdown('<div class="section-title">Robot utilization</div>', unsafe_allow_html=True)
    fig = px.bar(all_robots, x="Robot", y="Utilization (%)", color="Strategy", barmode="group", text_auto=".1f", color_discrete_sequence=["#2f78a5", "#ef8f2f"])
    fig.update_layout(height=330, margin=dict(l=10, r=10, t=10, b=10), legend_title_text="", yaxis_title="Utilization (%)")
    st.plotly_chart(fig, use_container_width=True)

with lower_right:
    st.markdown('<div class="section-title">Task mix</div>', unsafe_allow_html=True)
    task_mix = pd.DataFrame(selected_scenario["tasks"])["task_type"].value_counts().rename_axis("Task Type").reset_index(name="Tasks")
    fig = go.Figure(data=[go.Pie(labels=task_mix["Task Type"].str.title(), values=task_mix["Tasks"], hole=.58, marker=dict(colors=["#2f78a5", "#ef8f2f"]))])
    fig.update_layout(height=330, margin=dict(l=10, r=10, t=10, b=10), showlegend=True)
    st.plotly_chart(fig, use_container_width=True)

summary_tab, tasks_tab, robots_tab = st.tabs(["📊 Comparison table", "📦 Task details", "🤖 Robot details"])
with summary_tab:
    display_comparison = comparison_df.copy()
    for col in ["FIFO", "Deferred Commitment", "Deferred vs FIFO (%)"]:
        display_comparison[col] = display_comparison[col].round(2)
    st.dataframe(display_comparison, use_container_width=True, hide_index=True)

with tasks_tab:
    strategy_filter = st.multiselect("Show strategies", ["FIFO", "Deferred Commitment"], default=["FIFO", "Deferred Commitment"])
    st.dataframe(all_tasks[all_tasks["Strategy"].isin(strategy_filter)].round(2), use_container_width=True, hide_index=True)

with robots_tab:
    st.dataframe(all_robots.round(2), use_container_width=True, hide_index=True)

st.markdown('<div class="section-title">Export results</div>', unsafe_allow_html=True)
export1, export2, export3, _ = st.columns([1, 1, 1, 2])
scenario_slug = scenario_key.replace(" ", "_")
with export1:
    st.download_button(
        "⬇ Export comparison CSV",
        comparison_df.to_csv(index=False).encode("utf-8"),
        file_name=f"{scenario_slug}_strategy_comparison.csv",
        mime="text/csv",
        use_container_width=True,
    )
with export2:
    st.download_button(
        "⬇ Export task details CSV",
        all_tasks.to_csv(index=False).encode("utf-8"),
        file_name=f"{scenario_slug}_task_details.csv",
        mime="text/csv",
        use_container_width=True,
    )
with export3:
    st.download_button(
        "⬇ Export robot details CSV",
        all_robots.to_csv(index=False).encode("utf-8"),
        file_name=f"{scenario_slug}_robot_details.csv",
        mime="text/csv",
        use_container_width=True,
    )
