import streamlit as st
import uuid
import tempfile
import os
from pathlib import Path

from components.common import get_current_project
from components.sidebar import render_sidebar
from components.characters import render_characters

try:
    from api import ingest_file_to_backend, get_story_history_api
    from app.common.file_input import FileProcessor
except ImportError:
    def ingest_file_to_backend(*args, **kwargs):
        return True, ""

    def get_story_history_api(*args, **kwargs):
        return {}, "ImportError: get_story_history_api"

    class FileProcessor:
        @staticmethod
        def load_file_content(file):
            return "Dummy Content"


def render_universe():
    proj = get_current_project()
    if not proj:
        st.error("프로젝트를 불러올 수 없습니다.")
        st.session_state.page = "home"
        st.rerun()
        return

    render_sidebar(proj)

    if "worldview" not in proj:
        proj["worldview"] = ""

    st.title(f"🌍 {proj['title']} - 설정")
    st.caption("작품의 등장인물, 세계관, 그리고 화별 플롯(요약)을 관리합니다.")

    tab_char, tab_world, tab_plot = st.tabs(["👤 등장인물", "🗺️ 세계관", "📌 플롯 (요약)"])

    with tab_char:
        render_characters(proj)

    with tab_world:
        _render_worldview_tab(proj)

    with tab_plot:
        _render_plot_tab(proj)


def _render_worldview_tab(proj):
    with st.expander("파일로 세계관 자료 추가하기", expanded=False):
        st.markdown("세계관 설정이 담긴 텍스트, PDF 문서를 업로드하여 AI에게 학습시킵니다.")
        uploaded_file = st.file_uploader("파일 선택", type=["txt", "pdf", "docx"], key="world_uploader")

        if uploaded_file and st.button("세계관 분석 및 추가", use_container_width=True):
            with st.spinner("파일을 분석하여 세계관 DB에 저장 중입니다..."):
                tmp_path = ""
                try:
                    # UploadedFile -> 임시 파일로 저장 (FileProcessor는 경로를 받는 구조라서)
                    suffix = Path(uploaded_file.name).suffix or ".tmp"
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                        tmp.write(uploaded_file.getbuffer())
                        tmp_path = tmp.name

                    content = FileProcessor.load_file_content(tmp_path)

                    if content and not content.startswith("[Error]"):
                        success, msg = ingest_file_to_backend(content, "world")
                        if success:
                            proj["worldview"] = (
                                proj.get("worldview", "").rstrip()
                                + "\n\n"
                                + content.strip()
                            ).strip()
                            st.success("세계관 자료가 성공적으로 추가되었습니다!")
                            st.rerun()
                        else:
                            st.error(msg or "서버 전송 실패")
                    else:
                        st.error(content if content else "파일 내용을 읽을 수 없습니다.")

                except Exception as e:
                    st.error(f"오류 발생: {e}")

                finally:
                    # 임시파일 정리
                    if tmp_path:
                        try:
                            os.remove(tmp_path)
                        except Exception:
                            pass

    st.divider()

    st.subheader("세계관 설명 (직접 입력)")
    with st.container(border=True):
        world_text = st.text_area(
            "이 작품의 규칙, 배경, 분위기, 기술/마법 체계 등을 기록하세요.",
            value=proj.get("worldview", ""),
            height=400,
            key="worldview_input"
        )

        if world_text != proj.get("worldview", ""):
            proj["worldview"] = world_text


def _normalize_history_items(history: dict) -> list[tuple[int, dict]]:
    by_ep: dict[int, dict] = {}
    for k, v in (history or {}).items():
        if not isinstance(v, dict):
            continue

        ep_no = v.get("episode_no")
        if not isinstance(ep_no, int):
            try:
                ep_no = int(str(k))
            except Exception:
                continue

        by_ep[ep_no] = v

    return sorted(by_ep.items(), key=lambda x: x[0])


def _fetch_and_cache_history(show_toast: bool = True) -> bool:
    raw, err = get_story_history_api()
    if err:
        if show_toast:
            st.toast(f"불러오기 실패: {err}", icon="⚠️")
        return False

    history = raw.get("history") if isinstance(raw, dict) and "history" in raw else raw
    if not isinstance(history, dict):
        history = {}

    st.session_state.story_history_cache = history

    if show_toast:
        st.toast("히스토리 불러오기 완료", icon="✅")
    return True


def _render_plot_tab(proj):
    st.subheader("스토리 요약")
    st.caption("각 화의 내용이 자동으로 요약되어 표시되는 공간입니다.")

    if "story_history_cache" not in st.session_state:
        st.session_state.story_history_cache = {}

    c1, c2 = st.columns([8.5, 1.5], vertical_alignment="bottom")
    with c1:
        st.empty()
    with c2:
        if st.button("📥 히스토리 불러오기", use_container_width=True, key="history_reload_btn"):
            _fetch_and_cache_history(show_toast=True)
            st.rerun()

    if not st.session_state.story_history_cache:
        _fetch_and_cache_history(show_toast=False)

    history = st.session_state.story_history_cache or {}

    if not history:
        st.info("아직 요약 히스토리가 없습니다.")
        return

    items = _normalize_history_items(history)

    for ep_no, item in items:
        title = str(item.get("title", "")).strip()
        summary = str(item.get("summary", "")).strip()

        with st.container(border=True):
            st.markdown(f"#### 📄 {ep_no}화" + (f" — {title}" if title else ""))

            st.text_area(
                label="AI 요약 내용",
                value=summary,
                height=150,
                key=f"history_summary_view_{ep_no}",
                disabled=True,
                placeholder="요약이 없습니다."
            )
