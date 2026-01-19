# frontend/components/plot.py
import streamlit as st

from components.common import get_current_project
from components.sidebar import render_sidebar

from api import save_world_setting_api, ingest_file_to_backend, get_world_setting_api
from app.common.file_input import FileProcessor


def _ensure_state():
    if "world_edit_mode" not in st.session_state:
        st.session_state.world_edit_mode = False
    if "world_draft" not in st.session_state:
        st.session_state.world_draft = ""
    if "world_loaded_from_backend" not in st.session_state:
        st.session_state.world_loaded_from_backend = False

    # 화면에 보여줄 세계관 텍스트는 세션에 고정 (rerun 대비)
    if "world_desc_view" not in st.session_state:
        st.session_state.world_desc_view = ""

    # 삭제 확인용
    if "world_delete_armed" not in st.session_state:
        st.session_state.world_delete_armed = False


def _set_world_desc(world: dict, desc: str) -> None:
    desc = (desc or "").strip()
    st.session_state.world_desc_view = desc
    world["desc"] = desc


def _save_world_to_backend(draft: str) -> tuple[bool, str]:
    # 저장은 빈 값도 허용(삭제용)
    try:
        ok = bool(save_world_setting_api((draft or "").strip()))
        if ok:
            return True, ""
        return False, "plot.json 저장 실패"
    except Exception as e:
        return False, f"plot.json 저장 실패: {e}"


def _pull_world_raw_into_view(world: dict, show_toast: bool = False) -> None:
    plot, err = get_world_setting_api()
    if err:
        if show_toast:
            st.toast(f"세계관 불러오기 실패: {err}", icon="⚠️")
        return

    raw = str(plot.get("world_raw", "") or "").strip()
    if raw:
        _set_world_desc(world, raw)
        if show_toast:
            st.toast("plot.json에서 세계관 원문 불러옴", icon="✅")
        return

    # raw가 없으면 요약이라도
    summary = plot.get("summary")
    if isinstance(summary, list) and summary:
        s = "\n".join([str(x) for x in summary if str(x).strip()]).strip()
        _set_world_desc(world, s)
        if show_toast:
            st.toast("plot.json에서 세계관 요약 불러옴", icon="✅")
        return

    # 둘 다 없으면 비움
    _set_world_desc(world, "")
    if show_toast:
        st.toast("저장된 세계관 내용이 없습니다.", icon="ℹ️")


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

    # ✅ 최초 1회: 백엔드에서 가져와 세션/월드 동기화
    if not st.session_state.world_loaded_from_backend:
        _pull_world_raw_into_view(world, show_toast=False)
        st.session_state.world_loaded_from_backend = True
    else:
        # rerun으로 world가 초기화되는 경우 대비: 세션값으로 복구
        _set_world_desc(world, st.session_state.world_desc_view)

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
                            # ✅ 업로드 저장 성공 -> 백엔드에서 다시 pull 해서 바로 반영
                            _pull_world_raw_into_view(world, show_toast=True)

                            # 다음 rerun에서도 다시 백엔드 값을 기준으로 보이게
                            st.session_state.world_loaded_from_backend = True
                            st.session_state.world_delete_armed = False
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
            saved_now = (st.session_state.world_desc_view or "").strip()

            if not st.session_state.world_edit_mode:
                # 수정 버튼
                if st.button("✏️ 수정", key="world_edit_btn", use_container_width=True):
                    st.session_state.world_edit_mode = True
                    st.session_state.world_draft = saved_now
                    st.session_state.world_delete_armed = False
                    st.rerun()

                # 삭제 버튼(내용 있을 때만)
                if saved_now:
                    if st.button("🗑 삭제", key="world_delete_btn", use_container_width=True):
                        st.session_state.world_delete_armed = True
                        st.rerun()

            else:
                c1, c2 = st.columns([1, 1])
                with c1:
                    if st.button("💾 저장", key="world_save_btn", use_container_width=True):
                        draft = (st.session_state.world_draft or "").strip()
                        ok, msg = _save_world_to_backend(draft)
                        if ok:
                            st.toast("저장 완료", icon="✅")
                            # 저장 성공 -> 백엔드 기준으로 다시 당겨서 동기화
                            _pull_world_raw_into_view(world, show_toast=False)
                        else:
                            st.toast(f"저장 실패: {msg}".strip(), icon="⚠️")

                        st.session_state.world_edit_mode = False
                        st.session_state.world_delete_armed = False
                        st.rerun()

                with c2:
                    if st.button("↩ 취소", key="world_cancel_btn", use_container_width=True):
                        st.session_state.world_edit_mode = False
                        st.session_state.world_delete_armed = False
                        st.rerun()

        # 삭제 확인 UI
        if (not st.session_state.world_edit_mode) and st.session_state.world_delete_armed:
            st.warning("정말 삭제할까요? (plot.json의 세계관 내용이 비워집니다)")
            c1, c2 = st.columns([1, 1])
            with c1:
                if st.button("✅ 삭제 확정", key="world_delete_confirm", use_container_width=True):
                    ok, msg = _save_world_to_backend("")  # 빈 값 저장 = 삭제 처리
                    if ok:
                        st.toast("삭제 완료", icon="✅")
                        _pull_world_raw_into_view(world, show_toast=False)
                    else:
                        st.toast(f"삭제 실패: {msg}".strip(), icon="⚠️")
                    st.session_state.world_delete_armed = False
                    st.rerun()
            with c2:
                if st.button("❌ 삭제 취소", key="world_delete_cancel", use_container_width=True):
                    st.session_state.world_delete_armed = False
                    st.rerun()

        # 본문 렌더링
        if not st.session_state.world_edit_mode:
            saved = (st.session_state.world_desc_view or "").strip()
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
