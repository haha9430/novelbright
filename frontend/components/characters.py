import streamlit as st
from components.common import get_current_project, add_character_modal
from components.sidebar import render_sidebar

def render_characters():
    proj = get_current_project()
    if not proj: st.session_state.page = "home"; st.rerun()
    render_sidebar(proj)
    st.title("등장인물")
    if st.button("＋ 인물 추가"): add_character_modal(proj)
    st.divider()
    for char in proj['characters']:
        with st.container(border=True):
            st.subheader(char['name'])
            st.caption(char['tag'])
            st.write(char['desc'])
            if st.button("삭제", key=f"dc_{char['id']}"):
                proj['characters'].remove(char); st.rerun()