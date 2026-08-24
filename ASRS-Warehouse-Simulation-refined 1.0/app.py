from pathlib import Path

import streamlit as st

from predefinedScenario import render_predefined_sidebar
from customConfig import render_custom_sidebar
from dashboard_common import (
    clear_dashboard_selection,
    render_landing_message,
    run_and_render_dashboard,
)


PROJECT_FOLDER = Path(__file__).resolve().parent


def load_css(filename: str) -> None:
    css_path = PROJECT_FOLDER / filename

    if not css_path.exists():
        st.warning(f"Missing stylesheet: {filename}")
        return

    st.markdown(
        f"<style>{css_path.read_text(encoding='utf-8')}</style>",
        unsafe_allow_html=True,
    )


st.set_page_config(
    page_title="Warehouse Strategy Dashboard",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded",
)

load_css("common.css")

if "scenario_source" not in st.session_state:
    st.session_state["scenario_source"] = None

if "active_result_key" not in st.session_state:
    st.session_state["active_result_key"] = None


with st.sidebar:
    st.markdown("## 🏭 Simulation Controls")

    scenario_source = st.radio(
        "Scenario source",
        [
            "Predefined scenario",
            "Custom configuration",
        ],
        index=None,
        key="scenario_source",
        help=(
            "Choose a predefined scenario or create "
            "a custom simulation configuration."
        ),
    )


hero_html = (
    '<div class="hero">'
    '<div class="hero-badge">AS/RS Warehouse Simulation</div>'
    '<div class="hero-title">'
    'Warehouse Strategy Comparison Dashboard'
    '</div>'
    '<div class="hero-subtitle">'
    'Compare FIFO and Deferred Commitment, select a predefined '
    'scenario or build a custom configuration, inspect robot and '
    'task performance, and export the complete simulation results.'
    '</div>'
    '</div>'
)

st.markdown(
    hero_html,
    unsafe_allow_html=True,
)

if scenario_source is None:
    render_landing_message(
        title="Welcome to the AS/RS simulation dashboard",
        description=(
            "Select a scenario source from the left panel. "
            "You can use an included warehouse scenario or "
            "create a custom configuration."
        ),
    )
    st.stop()


if scenario_source == "Predefined scenario":
    load_css("predefinedScenario.css")

    scenario_payload = render_predefined_sidebar(
        clear_callback=clear_dashboard_selection,
    )

else:
    load_css("customConfig.css")

    scenario_payload = render_custom_sidebar(
        clear_callback=clear_dashboard_selection,
    )


if scenario_payload is None:
    st.stop()


run_and_render_dashboard(
    scenario_payload=scenario_payload,
)
