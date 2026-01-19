# frontend/components/plot.py
import json
from pathlib import Path
import datetime
import streamlit as st

from components.common import get_current_project
from components.sidebar import render_sidebar

from frontend.api import save_world_setting_api, ingest_file_to_backend, get_story_history_api
from app.common.file_input import FileProcessor


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _write_story_history(path: Path, history: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=4)


def _normalize_items(history: dict) -> list[tuple[int, dict, list[str]]]:
    by_ep: dict[int, dict] = {}
    keys_by_ep: dict[int, list[str]] = {}
    for k, v in history.items():
        if not isinstance(v, dict):
            continue
        ep_no = v.get("episode_no")
        if not isinstance(ep_no, int):
            try:
                ep_no = int(str(k))
            except Exception:
                continue
        keys_by_ep.setdefault(ep_no, []).append(str(k))
        by_ep[ep_no] = v
    items = sorted(by_ep.items(), key=lambda x: x[0])
    return [(ep_no, item, keys_by_ep.get(ep_no, [])) for ep_no, item in items]


def _ensure_state():
    if "world_edit_mode" not in st.session_state:
        st.session_state.world_edit_mode = False
    if "world_draft" not in st.session_state:
        st.session_state.world_draft = ""

    # ✅ 히스토리 캐시
    if "story_history_cache" not in st.session_state:
        st.session_state.story_history_cache = {}
    if "story_history_source" not in st.session_state:
        st.session_state.story_history_source = ""
    if "story_history_last_fetch" not in st.session_state:
        st.session_state.story_history_last_fetch = ""


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


def _fetch_and_cache_history(show_toast: bool = True) -> bool:
    """
    백엔드에서 히스토리 가져와서 세션에 저장
    """
    history, err = get_story_history_api()
    if err:
        if show_toast:
            st.toast(f"불러오기 실패: {err}", icon="⚠️")
        return False

    st.session_state.story_history_cache = history if isinstance(history, dict) else {}
    st.session_state.story_history_source = "backend:/story/history"
    st.session_state.story_history_last_fetch = datetime.datetime.now().strftime("%H:%M:%S")

    if show_toast:
        st.toast("히스토리 불러오기 완료", icon="✅")
    return True


def render_plot():
    _ensure_state()
    proj = get_current_project()
    if not proj:
        st.session_state.page = "home"
        st.rerun()

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
        .episode-card { background: #ffffff; border: 1px solid #E6E8F0; border-radius: 12px; padding: 16px 18px; margin-top: 8px; }
        .episode-header { font-size: 22px; font-weight: 800; color: #2D3436; margin-bottom: 4px; }
        .episode-title { font-size: 16px; font-weight: 700; color: #6C5CE7; margin-bottom: 10px; }
        .episode-summary { font-size: 14px; line-height: 1.85; color: #2F3640; }
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

    # -------------------------
    # ✅ 플롯 섹션 + 불러오기 버튼
    # -------------------------
    with st.container(border=False):
        c1, c2 = st.columns([8.5, 1.5], vertical_alignment="bottom")
        with c1:
            st.markdown("<h2 class='section-title'>📌 플롯</h2>", unsafe_allow_html=True)
        with c2:
            if st.button("📥 히스토리 불러오기", key="reload_history", use_container_width=True):
                _fetch_and_cache_history(show_toast=True)
                st.rerun()

    # ✅ 처음 들어왔는데 캐시가 비었으면 1회 자동 로드
    if not st.session_state.story_history_cache:
        _fetch_and_cache_history(show_toast=False)

    history = st.session_state.story_history_cache or {}
    source_info = st.session_state.story_history_source or "backend:/story/history"
    last_fetch = st.session_state.story_history_last_fetch or ""

    if not history:
        st.info("아직 히스토리가 없습니다.")
        st.caption(f"소스: {source_info} / 마지막 불러오기: {last_fetch}")
        return

    items = _normalize_items(history)
    st.caption(f"소스: {source_info} / 마지막 불러오기: {last_fetch}")

    for ep_no, item, _raw_keys in items:
        title = str(item.get("title", "")).strip()
        summary = str(item.get("summary", "")).strip()

        with st.expander(f"#{ep_no}화", expanded=False):
            top = st.columns([8.5, 1.5], vertical_alignment="center")
            with top[0]:
                title_html = f'<div class="episode-title">– {title}</div>' if title else ""
                st.markdown(
                    f"""<div class="episode-card"><div class="episode-header">{ep_no}화</div>{title_html}<div class="episode-summary">{summary}</div></div>""",
                    unsafe_allow_html=True,
                )
            with top[1]:
                st.button("🗑 삭제", key=f"del_ep_{ep_no}", use_container_width=True, disabled=True)
                st.caption("백엔드 삭제 API 필요")
