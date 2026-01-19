import json
from pathlib import Path
import streamlit as st

from components.common import get_current_project
# render_sidebar는 universe.py에서 부르므로 여기선 import도 필요 없지만, 혹시 모르니 남겨둬도 호출만 안 하면 됨.
from components.sidebar import render_sidebar

# [중요] api.py에서 ingest_file_to_backend 함수 추가 Import
from api import parse_file_content, _save_world_and_plot_json, save_world_setting_api, ingest_file_to_backend


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


# -----------------------------
# story_history 경로 탐색/읽기/쓰기 (기존 로직 유지)
# -----------------------------
def _candidate_history_paths() -> list[Path]:
    root = _project_root()
    p1 = root / "app" / "data" / "story_history.json"
    p2 = root / "app" / "data" / "story_history.json"
    cwd = Path.cwd()
    p3 = cwd / "app" / "data" / "story_history.json"
    p4 = cwd / "app" / "data" / "story_history.json"
    return [p1, p2, p3, p4]


def _pick_history_path() -> Path | None:
    for p in _candidate_history_paths():
        if p.exists():
            return p
    return None


def _read_story_history() -> tuple[dict, Path | None]:
    p = _pick_history_path()
    if p is None:
        return {}, None
    try:
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


# -----------------------------
# 세계관 설명: 보기/수정 모드
# -----------------------------
def _ensure_state():
    if "world_edit_mode" not in st.session_state:
        st.session_state.world_edit_mode = False
    if "world_draft" not in st.session_state:
        st.session_state.world_draft = ""


def render_plot(proj=None):  # 유연성을 위해 인자 추가
    _ensure_state()

    # 인자로 안 넘어오면 직접 조회
    if proj is None:
        proj = get_current_project()

    if not proj:
        st.session_state.page = "home"
        st.rerun()

    if "world" not in proj or not isinstance(proj.get("world"), dict):
        proj["world"] = {"id": "world", "name": "세계관", "desc": ""}

    world = proj["world"]

    # ------------------ 스타일 ------------------
    st.markdown(
        """
        <style>
        .world-title { margin-bottom: 4px; color: #111; }
        .world-desc-title { margin-top: -6px; color: #111; }
        .section-title { margin-top: 18px; margin-bottom: 6px; color: #111; }
        .view-box {
            white-space: pre-wrap; line-height: 1.75; padding: 14px;
            border-radius: 12px; border: 1px solid rgba(0,0,0,0.08);
            background: rgba(0,0,0,0.02); min-height: 120px;
        }
        .episode-card {
            background: #ffffff; border: 1px solid #E6E8F0;
            border-radius: 12px; padding: 16px 18px; margin-top: 8px;
        }
        .episode-header {
            font-size: 22px; font-weight: 800; color: #2D3436; margin-bottom: 4px;
        }
        .episode-title {
            font-size: 16px; font-weight: 700; color: #6C5CE7; margin-bottom: 10px;
        }
        .episode-summary {
            font-size: 14px; line-height: 1.85; color: #2F3640;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # --------------------------------
    # [수정됨] 파일로 세계관 분석 요청 (백엔드 Ingest 연결)
    # --------------------------------
    with st.expander("📂 파일로 세계관 분석/업데이트"):
        st.caption("PDF, Word, HWP 파일을 업로드하면 AI가 세계관 요약 및 장르를 분석해 업데이트합니다.")

        uploaded_world = st.file_uploader(
            "세계관 파일 업로드",
            type=["txt", "md", "pdf", "docx", "hwp"],
            key="world_file_uploader"
        )

        if uploaded_world and st.button("🚀 AI 분석 및 업데이트 시작"):
            with st.spinner("파일을 읽고 AI가 세계관을 분석 중입니다..."):
                # 1. 텍스트 추출
                new_text = parse_file_content(uploaded_world)

                if new_text:
                    # 2. 백엔드 전송 (type='world')
                    is_success, msg = ingest_file_to_backend(new_text, "world")

                    if is_success:
                        st.success(f"✅ {msg}")
                        # 백엔드가 plot.json을 갱신했으므로, 데이터를 다시 읽어오기 위해 rerun 추천
                        st.rerun()
                    else:
                        st.error(f"❌ 실패: {msg}")
                else:
                    st.warning("파일에서 텍스트를 읽을 수 없습니다.")

    st.markdown("<h1 class='world-title'>🌍 세계관</h1>", unsafe_allow_html=True)

    # --------------------------------
    # 1) 세계관 설명 (보기/수정 모드)
    # --------------------------------
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

                        # api.py의 함수 호출
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
                    "<div class='view-box' style='color: rgba(0,0,0,0.45)'>"
                    "이 작품의 규칙, 배경, 분위기, 금기, 기술/마법 체계 등을 기록하세요."
                    "</div>",
                    unsafe_allow_html=True,
                )
        else:
            st.session_state.world_draft = st.text_area(
                "세계관 내용",
                value=st.session_state.world_draft,
                height=220,
                label_visibility="collapsed",
                placeholder="세계관을 입력하세요.",
            )

    # --------------------------------
    # 2) 플롯 (히스토리 표시)
    # --------------------------------
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
        st.info("아직 히스토리가 없습니다. 문서에서 1화 원고를 요약 저장한 뒤 불러와 주세요.")
        return

    items = _normalize_items(history)

    for ep_no, item, raw_keys in items:
        title = str(item.get("title", "")).strip()
        summary = str(item.get("summary", "")).strip()

        with st.expander(f"#{ep_no}화", expanded=False):
            top = st.columns([8.5, 1.5], vertical_alignment="center")

            with top[0]:
                title_html = f'<div class="episode-title">– {title}</div>' if title else ""
                summary_html = summary if summary else ""

                st.markdown(
                    f"""
                    <div class="episode-card">
                        <div class="episode-header">{ep_no}화</div>
                        {title_html}
                        <div class="episode-summary">{summary_html}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with top[1]:
                if st.button("🗑 삭제", key=f"del_ep_{ep_no}", use_container_width=True):
                    if hist_path is None:
                        st.toast("삭제 실패: story_history.json 경로를 못 찾음", icon="⚠️")
                    else:
                        for k in raw_keys:
                            if k in history:
                                del history[k]
                        _write_story_history(hist_path, history)
                        st.toast(f"{ep_no}화 삭제 완료", icon="✅")
                        st.rerun()