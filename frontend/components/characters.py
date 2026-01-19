import json
from pathlib import Path
from typing import Any, Dict
import uuid
import streamlit as st

from components.common import get_current_project, add_character_modal
from components.sidebar import render_sidebar

# [수정] api.py 및 공용 모듈에서 필요한 함수들만 정확히 Import
from api import save_character_api, ingest_file_to_backend
from app.common.file_input import FileProcessor # parse_file_content 대신 프로젝트 공용 모듈 사용

def _find_project_root() -> Path:
    p = Path(__file__).resolve()
    for parent in [p.parent, *p.parents]:
        if (parent / "app").exists():
            return parent
    return Path.cwd()

def _characters_db_path() -> Path:
    return _find_project_root() / "app" / "data" / "characters.json"

def _read_json_safe(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def _delete_character_from_db(name: str) -> bool:
    path = _characters_db_path()
    db = _read_json_safe(path)
    if name in db:
        del db[name]
        _write_json(path, db)
    return True

def _ensure_edit_state():
    if "editing_char_id" not in st.session_state:
        st.session_state.editing_char_id = None
    if "editing_char_text" not in st.session_state:
        st.session_state.editing_char_text = ""

def render_characters(proj=None):
    if proj is None:
        proj = get_current_project()
        if not proj:
            st.warning("프로젝트를 찾을 수 없습니다.")
            return

    _ensure_edit_state()

    # 상단 액션 바
    col_add, col_upload = st.columns([1, 2], vertical_alignment="bottom")

    with col_add:
        if st.button("＋ 인물 직접 추가", use_container_width=True):
            add_character_modal(proj)

    with col_upload:
        with st.popover("📂 파일로 일괄 추가"):
            st.markdown("PDF, Word, TXT 파일을 지원하며 AI가 인물을 추출합니다.")
            uploaded_file = st.file_uploader(
                "파일 선택",
                type=["txt", "pdf", "docx"],
                label_visibility="collapsed"
            )

            if uploaded_file and st.button("🚀 파일 처리 및 AI 분석 시작", use_container_width=True):
                with st.spinner("파일을 읽고 캐릭터를 추출 중입니다..."):
                    # 1. 텍스트 추출 (프로젝트 공용 FileProcessor 사용)
                    content = FileProcessor.load_file_content(uploaded_file)

                    if content and not content.startswith("[Error]"):
                        # 2. 백엔드 전송 (type="character")
                        # api.py의 ingest_file_to_backend는 True/False를 반환함
                        success = ingest_file_to_backend(content, "character")

                        if success:
                            st.success("캐릭터 분석 및 저장이 완료되었습니다.")
                            st.rerun()
                    else:
                        st.error("파일에서 텍스트를 읽을 수 없습니다.")

    st.divider()

    # 캐릭터 리스트 출력
    chars = proj.get("characters", [])
    if not chars:
        st.info("등록된 등장인물이 없습니다. 위 버튼을 눌러 추가해주세요.")
        return

    st.caption(f"총 {len(chars)}명의 등장인물")

    for idx, char in enumerate(chars):
        char_id = char.get("id", f"idx_{idx}")
        name = str(char.get("name", "")).strip() or "(이름 없음)"
        tag = str(char.get("tag", "")).strip()
        desc = str(char.get("desc", "")).strip()

        is_editing = (st.session_state.editing_char_id == char_id)

        with st.container(border=True):
            if not is_editing:
                c_head, c_body, c_btn = st.columns([2, 6, 2])
                with c_head:
                    st.markdown(f"**{name}**")
                    if tag: st.caption(f"#{tag}")
                with c_body:
                    preview = (desc[:80] + "...") if len(desc) > 80 else desc
                    st.markdown(preview if preview else "<span style='color:grey'>설명 없음</span>", unsafe_allow_html=True)
                with c_btn:
                    b1, b2 = st.columns(2)
                    if b1.button("✏️", key=f"edit_{char_id}"):
                        st.session_state.editing_char_id = char_id
                        st.session_state.editing_char_text = desc
                        st.rerun()
                    if b2.button("🗑️", key=f"del_{char_id}"):
                        proj["characters"].remove(char)
                        _delete_character_from_db(name)
                        st.toast("삭제 완료", icon="✅")
                        st.rerun()
            else:
                st.markdown(f"📝 **{name}** 설명 수정")
                st.session_state.editing_char_text = st.text_area(
                    "내용 수정", value=st.session_state.editing_char_text, height=120, label_visibility="collapsed"
                )
                bc1, bc2 = st.columns(2)
                if bc1.button("💾 저장", key=f"save_{char_id}", use_container_width=True):
                    char["desc"] = st.session_state.editing_char_text
                    save_character_api(name, st.session_state.editing_char_text)
                    st.session_state.editing_char_id = None
                    st.toast("수정되었습니다.", icon="✅")
                    st.rerun()
                if bc2.button("취소", key=f"cancel_{char_id}", use_container_width=True):
                    st.session_state.editing_char_id = None
                    st.rerun()