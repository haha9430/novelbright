import streamlit as st
import tempfile
import os
from pathlib import Path

from components.common import get_current_project
from components.sidebar import render_sidebar
from components.characters import render_characters

try:
    from api import (
        ingest_file_to_backend,
        get_story_history_api,
        get_world_setting_api,
        save_world_setting_api,
    )
    from app.common.file_input import FileProcessor
except ImportError:
    def ingest_file_to_backend(*args, **kwargs):
        return True, ""

    def get_story_history_api(*args, **kwargs):
        return {}, "ImportError: get_story_history_api"

    def get_world_setting_api(*args, **kwargs):
        return {}, "ImportError: get_world_setting_api"

    def save_world_setting_api(*args, **kwargs):
        return False

    class FileProcessor:
        @staticmethod
        def load_file_content(file):
            return "Dummy Content"


# ---------- world helpers ----------

def _ensure_world_state():
    if "world_edit_mode" not in st.session_state:
        st.session_state.world_edit_mode = False
    if "world_draft" not in st.session_state:
        st.session_state.world_draft = ""
    if "world_delete_armed" not in st.session_state:
        st.session_state.world_delete_armed = False

    # 요약/원문 캐시 (불러오기 전엔 빈 값)
    if "world_summary_view" not in st.session_state:
        st.session_state.world_summary_view = ""
    if "world_raw_view" not in st.session_state:
        st.session_state.world_raw_view = ""

    # 화면 모드
    if "world_view_mode" not in st.session_state:
        st.session_state.world_view_mode = "summary"  # summary | raw

    # ✅ 수동 로드 여부
    if "world_loaded" not in st.session_state:
        st.session_state.world_loaded = False


def _trim_preview(text: str, limit: int = 1200) -> str:
    t = (text or "").strip()
    if len(t) <= limit:
        return t
    return t[:limit].rstrip() + "\n…(더보기에서 전체 확인)"


def _pull_world_from_backend(show_toast: bool = False) -> bool:
    plot, err = get_world_setting_api()
    if err:
        if show_toast:
            st.toast(f"세계관 불러오기 실패: {err}", icon="⚠️")
        return False

    raw = str(plot.get("world_raw", "") or "").strip()

    summary = plot.get("summary")
    if isinstance(summary, list):
        summary_text = "\n".join([str(x) for x in summary if str(x).strip()]).strip()
    else:
        summary_text = str(summary or "").strip()

    st.session_state.world_raw_view = raw
    st.session_state.world_summary_view = summary_text

    # 요약이 있으면 요약 모드, 없으면 원문 모드
    if summary_text:
        st.session_state.world_view_mode = "summary"
    elif raw:
        st.session_state.world_view_mode = "raw"
    else:
        st.session_state.world_view_mode = "summary"

    st.session_state.world_loaded = True

    if show_toast:
        if summary_text:
            st.toast("세계관 요약을 불러왔습니다.", icon="✅")
        elif raw:
            st.toast("세계관 원문을 불러왔습니다.", icon="✅")
        else:
            st.toast("저장된 세계관 내용이 없습니다.", icon="ℹ️")

    return True


def _save_world_to_backend(text: str) -> bool:
    return bool(save_world_setting_api(text or ""))


def _get_current_world_text() -> str:
    mode = st.session_state.world_view_mode
    if mode == "raw":
        return (st.session_state.world_raw_view or "").strip()
    return (st.session_state.world_summary_view or "").strip()


# ---------- main render ----------

def render_universe():
    proj = get_current_project()
    if not proj:
        st.error("프로젝트를 불러올 수 없습니다.")
        st.session_state.page = "home"
        st.rerun()
        return

    render_sidebar(proj)
    _ensure_world_state()

    st.title(f"🌍 {proj['title']} - 설정")
    st.caption("작품의 등장인물, 세계관, 그리고 화별 플롯(요약)을 관리합니다.")

    tab_char, tab_world, tab_plot = st.tabs(["👤 등장인물", "🗺️ 세계관", "📌 플롯 (요약)"])

    with tab_char:
        render_characters(proj)

    with tab_world:
        _render_worldview_tab()

    with tab_plot:
        _render_plot_tab(proj)


def _render_worldview_tab():
    st.markdown(
        """
        <style>
        .world-desc-title { margin-top: 2px; color: #111; }
        .view-box {
            white-space: pre-wrap; line-height: 1.75;
            padding: 14px; border-radius: 12px;
            border: 1px solid rgba(0,0,0,0.08);
            background: rgba(0,0,0,0.02);
            min-height: 160px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("파일로 세계관 자료 추가하기", expanded=False):
        st.markdown("세계관 설정 파일(TXT, PDF, DOCX)을 업로드하면 AI가 분석 후 plot.json에 저장합니다.")
        uploaded_file = st.file_uploader("파일 선택", type=["txt", "pdf", "docx"], key="world_uploader")

        if uploaded_file and st.button("세계관 분석 및 추가", use_container_width=True, key="world_ingest_btn"):
            with st.spinner("파일을 분석하여 세계관 DB에 저장 중입니다..."):
                tmp_path = ""
                try:
                    suffix = Path(uploaded_file.name).suffix or ".tmp"
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                        tmp.write(uploaded_file.getbuffer())
                        tmp_path = tmp.name

                    content = FileProcessor.load_file_content(tmp_path)
                    if content and not content.startswith("[Error]"):
                        success, msg = ingest_file_to_backend(content, "world")
                        if success:
                            # ✅ 업로드 성공 시: 자동으로 불러오기까지는 해줌 (원하면 이 줄도 빼면 됨)
                            
                            st.session_state.world_delete_armed = False
                            st.rerun()
                        else:
                            st.error(msg or "서버 전송 실패")
                    else:
                        st.error(content if content else "파일 내용을 읽을 수 없습니다.")
                except Exception as e:
                    st.error(f"오류 발생: {e}")
                finally:
                    if tmp_path:
                        try:
                            os.remove(tmp_path)
                        except Exception:
                            pass

    st.divider()

    st.subheader("세계관 설명")
    with st.container(border=True):
        left, right = st.columns([8.0, 2.0], vertical_alignment="bottom")
        with left:
            st.markdown("<h3 class='world-desc-title'>🧾 저장된 세계관</h3>", unsafe_allow_html=True)

        with right:
            # ✅ 버튼 눌렀을 때만 불러오기
            if st.button("📥 불러오기", use_container_width=True, key="world_load_btn"):
                _pull_world_from_backend(show_toast=True)
                st.session_state.world_delete_armed = False
                st.session_state.world_edit_mode = False
                st.rerun()

        # ---- 불러오기 전 화면 ----
        if not st.session_state.world_loaded:
            st.markdown(
                "<div class='view-box' style='color: rgba(0,0,0,0.45)'>아직 불러온 세계관이 없습니다. 오른쪽 상단의 '불러오기'를 눌러주세요.</div>",
                unsafe_allow_html=True,
            )
            return

        # ---- 불러온 후 화면 ----
        saved_summary = (st.session_state.world_summary_view or "").strip()
        saved_raw = (st.session_state.world_raw_view or "").strip()

        # 보기 모드 토글(요약/원문 둘 다 있을 때만)
        if saved_summary and saved_raw:
            c1, c2 = st.columns([1, 1])
            with c1:
                if st.button("요약 보기", use_container_width=True, key="world_mode_summary"):
                    st.session_state.world_view_mode = "summary"
                    st.rerun()
            with c2:
                if st.button("원문 보기", use_container_width=True, key="world_mode_raw"):
                    st.session_state.world_view_mode = "raw"
                    st.rerun()

        # 상단 액션 버튼(수정/삭제)
        top_left, top_right = st.columns([8.0, 2.0], vertical_alignment="bottom")
        with top_left:
            st.empty()

        with top_right:
            if not st.session_state.world_edit_mode:
                if st.button("✏️ 수정", use_container_width=True, key="world_edit_btn"):
                    st.session_state.world_edit_mode = True
                    st.session_state.world_draft = _get_current_world_text()
                    st.session_state.world_delete_armed = False
                    st.rerun()

                if _get_current_world_text():
                    if st.button("🗑 삭제", use_container_width=True, key="world_delete_btn"):
                        st.session_state.world_delete_armed = True
                        st.rerun()
            else:
                c1, c2 = st.columns([1, 1])
                with c1:
                    if st.button("💾 저장", use_container_width=True, key="world_save_btn"):
                        draft = (st.session_state.world_draft or "").strip()
                        ok = _save_world_to_backend(draft)
                        if ok:
                            st.toast("저장 완료", icon="✅")
                            _pull_world_from_backend(show_toast=False)
                        else:
                            st.toast("저장 실패", icon="⚠️")
                        st.session_state.world_edit_mode = False
                        st.session_state.world_delete_armed = False
                        st.rerun()
                with c2:
                    if st.button("↩ 취소", use_container_width=True, key="world_cancel_btn"):
                        st.session_state.world_edit_mode = False
                        st.session_state.world_delete_armed = False
                        st.rerun()

        # 삭제 확인
        if (not st.session_state.world_edit_mode) and st.session_state.world_delete_armed:
            st.warning("정말 삭제할까요? (plot.json의 세계관 내용이 비워집니다)")
            c1, c2 = st.columns([1, 1])
            with c1:
                if st.button("✅ 삭제 확정", use_container_width=True, key="world_delete_confirm"):
                    ok = _save_world_to_backend("")
                    if ok:
                        st.toast("삭제 완료", icon="✅")
                        _pull_world_from_backend(show_toast=False)
                    else:
                        st.toast("삭제 실패", icon="⚠️")
                    st.session_state.world_delete_armed = False
                    st.rerun()
            with c2:
                if st.button("❌ 삭제 취소", use_container_width=True, key="world_delete_cancel"):
                    st.session_state.world_delete_armed = False
                    st.rerun()

        # 본문
        if not st.session_state.world_edit_mode:
            text_now = _get_current_world_text()
            if text_now:
                # 기본은 미리보기 + 전체는 expander
                preview = _trim_preview(text_now, limit=1200)
                st.markdown(f"<div class='view-box'>{preview}</div>", unsafe_allow_html=True)

                if len(text_now) > 1200:
                    with st.expander("전체 내용 보기", expanded=False):
                        st.text_area(
                            "전체 세계관",
                            value=text_now,
                            height=300,
                            disabled=True,
                            key="world_full_view"
                        )
            else:
                st.markdown(
                    "<div class='view-box' style='color: rgba(0,0,0,0.45)'>저장된 내용이 없습니다.</div>",
                    unsafe_allow_html=True,
                )
        else:
            st.session_state.world_draft = st.text_area(
                "세계관 내용",
                value=st.session_state.world_draft,
                height=320,
                label_visibility="collapsed",
                key="world_editor_textarea",
            )


# ---------- plot tab (history) ----------

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
