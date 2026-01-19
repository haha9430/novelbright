import streamlit as st
from components.sidebar import render_sidebar
from components.common import get_current_project
from components.characters import render_characters
from components.plot import render_plot


def render_universe():
    proj = get_current_project()
    if not proj:
        st.session_state.page = "home"
        st.rerun()

    render_sidebar(proj)

    st.title(f"🌍설정")
    st.caption("작품의 세계관과 등장인물을 통합 관리합니다.")

    # 탭으로 분리하여 깔끔한 UI 제공
    tab1, tab2 = st.tabs(["👤 등장인물", "🗺️ 세계관"])

    with tab1:
        render_characters(proj)

    with tab2:
        render_plot(proj)