# frontend/components/plot.py
import streamlit as st

from components.common import get_current_project
from components.sidebar import render_sidebar

from api import save_world_setting_api, ingest_file_to_backend
from app.common.file_input import FileProcessor


def _ensure_state():
    if "world_edit_mode" not in st.session_state:
        st.session_state.world_edit_mode = False
    if "world_draft" not in st.session_state:
        st.session_state.world_draft = ""


def _save_world_and_plot_json(draft: str) -> tuple[bool, str]:
    draft = (draft or "").strip()
    if not draft:
        return False, "세계관 내용이 비어있음"
    try:
        ok = bool(save_world_setting_api(draft))
        if ok:
            return True, ""
        return False, "plot.json 저장 실패"
    except Exception as e:
        return False, f"plot.json 저장 실패: {e}"


def render_plot():
    _ensure_state()
    proj = get_current_project()
    if not proj:
        st.session_state.page = "home"
        st.rerun()
        return

    if "world" not in proj or not isinstance(proj.get("world"), dict):
        proj["world"] = {"id": "world", "name": "세계관", "desc": ""}
    world = proj["world"]

    render_sidebar(proj)

    st.markdown(
        """
        <style>
        .world-title { margin-bottom: 4px; color: #111; }
        .world-desc-title { margin-top: -6px; color: #111; }
        .section-title { margin-top: 18px; margin-bottom: 6px; color: #111; }
        .view-box { white-space: pre-wrap; line-height: 1.75; padding: 14px; border-radius: 12px; border: 1px solid rgba(0,0,0,0.08); background: rgba(0,0,0,0.02); min-height: 120px; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<h1 class='world-title'>🌍 세계관</h1>", unsafe_allow_html=True)

    with st.expander("📂 세계관 파일 업로드 (AI 자동 분석)", expanded=False):
        uploaded_file = st.file_uploader(
            "세계관 설정 파일(PDF, DOCX, TXT)을 올리면 AI가 분석하여 자동 저장합니다.",
            type=["pdf", "docx", "txt"],
            key="world_file_uploader",
        )
        if uploaded_file:
            if st.button("🚀 AI 분석 및 저장 시작", key="world_ingest_btn", use_container_width=True):
                with st.spinner("AI가 세계관을 분석 중입니다..."):
                    text = FileProcessor.load_file_content(uploaded_file)
                    if text and not text.startswith("[Error]"):
                        ok, msg = ingest_file_to_backend(text, "world")
                        if ok:
                            st.rerun()
                        else:
                            st.error(msg)
                    else:
                        st.error("파일에서 텍스트를 추출하지 못했습니다.")

    with st.container(border=True):
        left, right = st.columns([8.0, 2.0], vertical_alignment="bottom")
        with left:
            st.markdown("<h3 class='world-desc-title'>🧾 세계관 설명</h3>", unsafe_allow_html=True)
        with right:
            if not st.session_state.world_edit_mode:
                if st.button("✏️ 수정", key="world_edit_btn", use_container_width=True):
                    st.session_state.world_edit_mode = True
                    st.session_state.world_draft = world.get("desc", "")
                    st.rerun()
            else:
                c1, c2 = st.columns([1, 1])
                with c1:
                    if st.button("💾 저장", key="world_save_btn", use_container_width=True):
                        draft = (st.session_state.world_draft or "").strip()
                        world["desc"] = draft
                        ok, msg = _save_world_and_plot_json(draft)
                        if ok:
                            st.toast("저장 완료", icon="✅")
                        else:
                            st.toast(f"저장 실패: {msg}".strip(), icon="⚠️")
                        st.session_state.world_edit_mode = False
                        st.rerun()
                with c2:
                    if st.button("↩ 취소", key="world_cancel_btn", use_container_width=True):
                        st.session_state.world_edit_mode = False
                        st.rerun()

        if not st.session_state.world_edit_mode:
            saved = (world.get("desc") or "").strip()
            if saved:
                st.markdown(f"<div class='view-box'>{saved}</div>", unsafe_allow_html=True)
            else:
                st.markdown(
                    "<div class='view-box' style='color: rgba(0,0,0,0.45)'>설명을 입력하거나 파일을 업로드하세요.</div>",
                    unsafe_allow_html=True,
                )
        else:
            st.session_state.world_draft = st.text_area(
                "세계관 내용",
                value=st.session_state.world_draft,
                height=220,
                label_visibility="collapsed",
            )
