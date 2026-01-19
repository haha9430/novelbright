import json
from pathlib import Path
import streamlit as st

from components.common import get_current_project
from components.sidebar import render_sidebar

from api import save_world_setting_api, ingest_file_to_backend
from app.common.file_input import FileProcessor


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _candidate_history_paths() -> list[Path]:
    root = _project_root()
    cwd = Path.cwd()

    # ✅ 핵심: load_state 쪽을 1순위로 추가
    p1 = root / "app" / "service" / "story_keeper_agent" / "load_state" / "story_history.json"
    p2 = cwd / "app" / "service" / "story_keeper_agent" / "load_state" / "story_history.json"

    # 기존 app/data도 혹시 몰라 유지
    p3 = root / "app" / "data" / "story_history.json"
    p4 = cwd / "app" / "data" / "story_history.json"

    return [p1, p2, p3, p4]


def _pick_history_path() -> Path | None:
    for p in _candidate_history_paths():
        if p.exists():
            return p
    return _candidate_history_paths()[0]  # 없으면 1순위로 생성 유도


def _read_story_history() -> tuple[dict, Path | None]:
    p = _pick_history_path()
    if p is None:
        return {}, None
    try:
        if not p.exists():
            return {}, p
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}, p
        return data, p
    except Exception:
        return {}, p


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
            key="world_file_uploader"
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
                st.markdown("<div class='view-box' style='color: rgba(0,0,0,0.45)'>설명을 입력하거나 파일을 업로드하세요.</div>", unsafe_allow_html=True)
        else:
            st.session_state.world_draft = st.text_area(
                "세계관 내용",
                value=st.session_state.world_draft,
                height=220,
                label_visibility="collapsed"
            )

    with st.container(border=False):
        c1, c2 = st.columns([8.5, 1.5], vertical_alignment="bottom")
        with c1:
            st.markdown("<h2 class='section-title'>📌 플롯</h2>", unsafe_allow_html=True)
        with c2:
            if st.button("📥 히스토리 불러오기", key="reload_history", use_container_width=True):
                st.toast("불러오기", icon="✅")
                st.rerun()

    history, hist_path = _read_story_history()
    if not history:
        st.info("아직 히스토리가 없습니다.")
        if hist_path:
            st.caption(f"보고 있는 경로: {hist_path}")
        return

    items = _normalize_items(history)
    st.caption(f"보고 있는 경로: {hist_path}")

    for ep_no, item, raw_keys in items:
        title = str(item.get("title", "")).strip()
        summary = str(item.get("summary", "")).strip()
        with st.expander(f"#{ep_no}화", expanded=False):
            top = st.columns([8.5, 1.5], vertical_alignment="center")
            with top[0]:
                title_html = f'<div class="episode-title">– {title}</div>' if title else ""
                st.markdown(
                    f"""<div class="episode-card"><div class="episode-header">{ep_no}화</div>{title_html}<div class="episode-summary">{summary}</div></div>""",
                    unsafe_allow_html=True
                )
            with top[1]:
                if st.button("🗑 삭제", key=f"del_ep_{ep_no}", use_container_width=True):
                    if hist_path:
                        for k in raw_keys:
                            history.pop(k, None)
                        _write_story_history(hist_path, history)
                        st.toast(f"{ep_no}화 삭제 완료", icon="✅")
                        st.rerun()
