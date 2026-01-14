import streamlit as st
import uuid
from components.common import get_current_project
from components.sidebar import render_sidebar


def render_characters():
    # 1. 프로젝트 가져오기
    proj = get_current_project()
    if not proj:
        st.session_state.page = "home"
        st.rerun()

    # 캐릭터 리스트가 없으면 초기화
    if "characters" not in proj: proj['characters'] = []

    # 2. 사이드바 렌더링
    render_sidebar(proj)

    # 3. 메인 화면
    c_head, c_btn = st.columns([8, 2], vertical_alignment="bottom")
    with c_head:
        st.title("👤 등장인물")
    with c_btn:
        if st.button("＋ 인물 추가", use_container_width=True):
            new_char = {
                "id": str(uuid.uuid4()),
                "name": "새 인물",
                "role": "주연",
                "desc": ""
            }
            proj['characters'].insert(0, new_char)  # 맨 위에 추가
            st.rerun()

    st.divider()

    # 4. 캐릭터 리스트 출력 (카드 형태)
    if not proj['characters']:
        st.info("등록된 등장인물이 없습니다. '인물 추가' 버튼을 눌러보세요.")
        return

    for char in proj['characters']:
        # 각 인물을 박스로 감싸기
        with st.container(border=True):
            # [상단] 이름(수정 가능) + 삭제 버튼
            c1, c2 = st.columns([9, 1])

            with c1:
                # [수정] 이름 크기를 줄이기 위해 text_input을 사용하되,
                # 라벨을 숨기고 큰 글씨 느낌을 주기 위한 스타일링은 main.py의 CSS에 의존하거나
                # 깔끔하게 기본 입력창으로 처리
                new_name = st.text_input(
                    "이름",
                    value=char['name'],
                    key=f"char_name_{char['id']}",
                    label_visibility="collapsed",
                    placeholder="이름을 입력하세요"
                )
                if new_name != char['name']:
                    char['name'] = new_name

            with c2:
                if st.button("🗑", key=f"del_char_{char['id']}", help="삭제"):
                    proj['characters'].remove(char)
                    st.rerun()

            # [하단] 상세 설정 (역할, 설명 등)
            c_role, c_desc = st.columns([2, 8])

            with c_role:
                # 역할(주연/조연/엑스트라 등) 입력
                new_role = st.text_input(
                    "역할",
                    value=char.get('role', ''),
                    key=f"char_role_{char['id']}",
                    placeholder="역할 (예: 주인공)"
                )
                if new_role != char.get('role', ''):
                    char['role'] = new_role

            with c_desc:
                # 설명 입력
                new_desc = st.text_input(
                    "설명",
                    value=char.get('desc', ''),
                    key=f"char_desc_{char['id']}",
                    placeholder="한 줄 설명"
                )
                if new_desc != char.get('desc', ''):
                    char['desc'] = new_desc