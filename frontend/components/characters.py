import json
from pathlib import Path
from typing import Any, Dict
import uuid

import streamlit as st

from components.common import get_current_project, add_character_modal
from components.sidebar import render_sidebar
from api import parse_file_content, save_character_api, save_characters_bulk_api, _delete_character_from_db


def _find_project_root() -> Path:
    """
    frontend/components/characters.py 같은 위치에서도
    프로젝트 루트(app/ 폴더가 있는 위치) 자동 탐색
    """
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
    """
    characters.json에서도 같이 삭제(있으면)
    """
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
    # 1. 프로젝트 데이터 확보 (인자로 안 넘어오면 스스로 찾음)
    if proj is None:
        proj = get_current_project()
        if not proj:
            st.warning("프로젝트를 찾을 수 없습니다.")
            return

    # 2. 편집 상태 초기화
    if "editing_char_id" not in st.session_state:
        st.session_state.editing_char_id = None
    if "editing_char_text" not in st.session_state:
        st.session_state.editing_char_text = ""

    # (주의) 사이드바 렌더링은 이 함수를 호출하는 '상위 페이지(universe 등)'에서 담당한다고 가정합니다.
    # 만약 단독 페이지로 쓸 때 사이드바가 필요하다면, 호출하는 쪽에서 render_sidebar(proj)를 먼저 실행해야 합니다.

    # 3. [UI 개선] 상단 액션 바 (직접 추가 & 파일 업로드)
    col_add, col_upload = st.columns([1, 2], vertical_alignment="bottom")

    with col_add:
        if st.button("＋ 인물 직접 추가", use_container_width=True):
            add_character_modal(proj)

    with col_upload:
        with st.popover("📂 파일로 일괄 추가"):
            st.markdown("JSON, TXT, PDF, Word, HWP 파일을 지원합니다.")

            # [수정됨] type 리스트에 확장자 추가
            uploaded_file = st.file_uploader(
                "파일 선택",
                type=["json", "txt", "pdf", "docx", "hwp"],  # 확장자 추가
                label_visibility="collapsed"
            )

            if uploaded_file and st.button("파일 처리 및 저장", use_container_width=True):
                # parse_file_content가 이제 모든 형식을 처리합니다.
                content = parse_file_content(uploaded_file)

    st.divider()

    # 4. 캐릭터 리스트 출력
    chars = proj.get("characters", [])
    if not chars:
        st.info("등록된 등장인물이 없습니다. 위 버튼을 눌러 추가해주세요.")
        return

    st.caption(f"총 {len(chars)}명의 등장인물")

    # [UI 개선] 카드형 리스트 (수정/삭제 기능 포함)
    for idx, char in enumerate(chars):
        char_id = char.get("id", f"idx_{idx}")
        name = str(char.get("name", "")).strip() or "(이름 없음)"
        tag = str(char.get("tag", "")).strip()
        desc = str(char.get("desc", "")).strip()

        is_editing = (st.session_state.editing_char_id == char_id)

        with st.container(border=True):
            if not is_editing:
                # 보기 모드
                c_head, c_body, c_btn = st.columns([2, 6, 2])

                with c_head:
                    st.markdown(f"**{name}**")
                    if tag:
                        st.caption(f"#{tag}")

                with c_body:
                    # 내용이 너무 길면 말줄임
                    preview = (desc[:80] + "...") if len(desc) > 80 else desc
                    st.markdown(preview if preview else "<span style='color:grey'>설명 없음</span>", unsafe_allow_html=True)

                with c_btn:
                    b1, b2 = st.columns(2)
                    if b1.button("✏️", key=f"edit_{char_id}"):
                        st.session_state.editing_char_id = char_id
                        st.session_state.editing_char_text = desc
                        st.rerun()
                    if b2.button("🗑️", key=f"del_{char_id}"):
                        try:
                            # 1) 화면 리스트 삭제
                            proj["characters"].remove(char)
                            # 2) 파일(DB) 삭제 시도
                            _delete_character_from_db(name)
                            st.toast("삭제 완료", icon="✅")
                            st.rerun()
                        except Exception:
                            st.error("삭제 실패")
            else:
                # 수정 모드
                st.markdown(f"📝 **{name}** 설명 수정")
                st.session_state.editing_char_text = st.text_area(
                    "내용 수정",
                    value=st.session_state.editing_char_text,
                    height=120,
                    label_visibility="collapsed"
                )

                bc1, bc2 = st.columns([1, 1])
                if bc1.button("💾 저장", key=f"save_{char_id}", use_container_width=True):
                    new_desc = st.session_state.editing_char_text
                    # 화면 갱신
                    char["desc"] = new_desc
                    # 백엔드/DB 갱신
                    save_character_api(name, new_desc)

                    st.session_state.editing_char_id = None
                    st.toast("수정되었습니다.", icon="✅")
                    st.rerun()

                if bc2.button("취소", key=f"cancel_{char_id}", use_container_width=True):
                    st.session_state.editing_char_id = None
                    st.rerun()