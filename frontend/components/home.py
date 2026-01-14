# frontend/components/home.py
import streamlit as st
from components.common import create_project_modal

def render_home():
    st.title("내 작품")
    if st.button("➕ 새 작품"): create_project_modal()
    st.divider()
    cols = st.columns(3)
    for i, p in enumerate(st.session_state.projects):
        with cols[i % 3]:
            with st.container(border=True):
                st.subheader(p['title'])
                st.caption(p['desc'])
                if st.button("작업하기", key=f"go_{p['id']}", use_container_width=True):
                    st.session_state.current_project_id = p['id']
                    st.session_state.page = "editor"
                    st.rerun()