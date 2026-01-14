import json
from pathlib import Path
from typing import Any, Dict

import streamlit as st

from components.common import get_current_project, add_character_modal
from components.sidebar import render_sidebar

from frontend.api import save_character_api


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


def render_characters():
    _ensure_edit_state()

    proj = get_current_project()
    if not proj:
        st.session_state.page = "home"
        st.rerun()

    render_sidebar(proj)

    st.title("등장인물")

    if st.button("＋ 인물 추가"):
        add_character_modal(proj)

    st.divider()

    # proj['characters']가 없을 수도 있으니 안전하게
    chars = proj.get("characters", [])
    if not isinstance(chars, list) or not chars:
        st.info("아직 등록된 등장인물이 없습니다. '인물 추가'로 추가해 주세요.")
        return

    for idx, char in enumerate(chars):
        # 기본 키들 방어
        char_id = char.get("id", f"idx_{idx}")
        name = str(char.get("name", "")).strip()
        tag = str(char.get("tag", "")).strip()
        desc = str(char.get("desc", "")).strip()

        if not name:
            name = "(이름 없음)"

        is_editing = (st.session_state.editing_char_id == char_id)

        with st.container(border=True):
            head_l, head_r = st.columns([8.5, 1.5], vertical_alignment="center")

            with head_l:
                st.subheader(name)
                if tag:
                    st.caption(tag)

            with head_r:
                if not is_editing:
                    if st.button("✏️ 수정", key=f"edit_{char_id}", use_container_width=True):
                        st.session_state.editing_char_id = char_id
                        st.session_state.editing_char_text = desc
                        st.rerun()
                else:
                    c1, c2 = st.columns([1, 1])
                    with c1:
                        if st.button("💾 저장", key=f"save_{char_id}", use_container_width=True):
                            new_desc = (st.session_state.editing_char_text or "").strip()

                            # 1) 화면 리스트 갱신
                            char["desc"] = new_desc

                            # 2) characters.json 갱신(같은 이름이면 merge/upsert됨)
                            #    -> save_character_api가 app/service/characters.upsert_character를 호출함
                            ok = save_character_api(name=name, description=new_desc)

                            if ok:
                                st.toast("수정 저장 완료", icon="✅")
                            else:
                                st.toast("수정 저장 실패", icon="⚠️")

                            st.session_state.editing_char_id = None
                            st.session_state.editing_char_text = ""
                            st.rerun()
                    with c2:
                        if st.button("↩ 취소", key=f"cancel_{char_id}", use_container_width=True):
                            st.session_state.editing_char_id = None
                            st.session_state.editing_char_text = ""
                            st.rerun()

            # 본문
            if not is_editing:
                st.write(desc if desc else "설명이 없습니다.")
            else:
                st.session_state.editing_char_text = st.text_area(
                    "인물 설명 수정",
                    value=st.session_state.editing_char_text,
                    height=180,
                    label_visibility="collapsed",
                )

            # 삭제는 기존처럼 유지 + DB도 같이 삭제
            if st.button("삭제", key=f"dc_{char_id}"):
                try:
                    # 화면 리스트 삭제
                    proj["characters"].remove(char)
                except Exception:
                    pass

                # characters.json에서도 삭제(가능하면)
                _delete_character_from_db(name)

                st.toast("삭제 완료", icon="✅")
                st.rerun()
