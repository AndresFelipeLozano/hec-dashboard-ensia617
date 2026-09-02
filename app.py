"""Streamlit Community Cloud-compatible entry point for the HEC dashboard."""

from __future__ import annotations

from pathlib import Path
import sys

import streamlit as st


REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))

from dashboard.components.common import render_app_frame  # noqa: E402
from dashboard.views import data_quality, landing, role_dashboard, upload  # noqa: E402
from hec_dashboard.app_state import (  # noqa: E402
    AppInitializationError,
    Keys,
    clear_role_draft_if_requested,
    consume_pending_navigation,
    initialize_session,
    role_context_complete,
)


st.set_page_config(
    page_title="HEC | Apoyo a decisiones",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="auto",
)

try:
    initialize_session(st.session_state)
    clear_role_draft_if_requested(st.session_state)
except AppInitializationError:
    st.error(
        "No fue posible validar el conjunto de demostración incluido. "
        "La aplicación se detuvo sin activar datos alternativos."
    )
    st.stop()

render_app_frame(st.session_state)

landing_page = st.Page(
    landing.render, title="Inicio", url_path="inicio", default=True
)
dashboard_page = None
pages = [landing_page]
if role_context_complete(st.session_state):
    dashboard_page = st.Page(
        role_dashboard.render, title="Dashboard", url_path="dashboard"
    )
    pages.append(dashboard_page)
pages.append(st.Page(upload.render, title="Carga de datos", url_path="carga"))
if st.session_state.get(Keys.ACTIVE_DATASET) is not None:
    pages.append(
        st.Page(data_quality.render, title="Calidad de datos", url_path="calidad")
    )

selected_page = st.navigation(pages)
pending_navigation = consume_pending_navigation(st.session_state)
if pending_navigation == "dashboard" and dashboard_page is not None:
    st.switch_page(dashboard_page)
if pending_navigation == "landing":
    st.switch_page(landing_page)
selected_page.run()
