import streamlit as st
import uuid
from components.common import search_modal, rename_document_modal, create_project_modal


def render_sidebar(current_proj):
    with st.sidebar:
        # 1. 홈 버튼
        if st.button("🏠 홈으로", use_container_width=True):
            st.session_state.page = "home"
            st.session_state.current_project_id = None
            st.rerun()

        st.divider()

        # 2. 프로젝트 정보 (프로젝트 안에 들어왔을 때만 표시)
        if current_proj:
            st.markdown(f"### {current_proj['title']}")

            # 통합 검색
            if st.button("🔍 검색하기", use_container_width=True):
                search_modal(current_proj)

            st.write("")  # 여백

            # [수정] 메뉴 네비게이션 - '에디터' 삭제
            menus = [
                # ("editor", "📝 에디터"),  <-- 이 부분이 삭제되었습니다.
                ("characters", "👤 등장인물"),
                ("plot", "🗓️ 플롯"),
                ("materials", "🗂️ 자료실")
            ]

            for page_key, label in menus:
                # 현재 선택된 페이지는 Primary 스타일로 강조
                btn_type = "primary" if st.session_state.page == page_key else "secondary"
                if st.button(label, key=f"nav_{page_key}", use_container_width=True, type=btn_type):
                    st.session_state.page = page_key
                    st.rerun()

            st.divider()

            # 3. 문서 목록
            st.caption("문서")

            # (1) 문서 추가 버튼
            c_add, c_sort = st.columns([4, 1])
            if c_add.button("＋", key="add_doc_btn", use_container_width=True):
                new_doc = {"id": str(uuid.uuid4()), "title": "새 문서", "content": "", "episode_no": 1}
                current_proj['documents'].append(new_doc)
                st.session_state.current_doc_id = new_doc['id']
                st.session_state.page = "editor"  # 문서 추가하면 에디터로 이동
                st.rerun()

            # (2) 문서 리스트 출력
            for doc in current_proj.get('documents', []):
                # 현재 에디터 페이지이고, 이 문서가 선택되었는지 확인
                is_active = (st.session_state.page == "editor" and st.session_state.current_doc_id == doc['id'])

                # 버튼 스타일 (선택됨: primary / 아님: secondary)
                b_type = "primary" if is_active else "secondary"

                # 가로 배치: 문서 제목 버튼 + 설정(옵션) 버튼
                c1, c2 = st.columns([5, 1])

                label = doc['title'] if doc['title'] else "(제목 없음)"
                # [수정] 문서 제목을 누르면 'editor' 페이지로 이동
                if c1.button(f"📄 {label}", key=f"nav_doc_{doc['id']}", type=b_type, use_container_width=True):
                    st.session_state.current_doc_id = doc['id']
                    st.session_state.page = "editor"
                    st.rerun()

                # 팝오버 (작은 점 3개 메뉴)
                with c2.popover("⋮"):
                    if st.button("이름 변경", key=f"ren_{doc['id']}", use_container_width=True):
                        rename_document_modal(doc)

                    if st.button("삭제", key=f"del_{doc['id']}", use_container_width=True):
                        current_proj['documents'].remove(doc)
                        if st.session_state.current_doc_id == doc['id']:
                            st.session_state.current_doc_id = None
                            st.session_state.page = "home"  # 삭제 시 홈으로
                        st.rerun()

        # 4. 하단 다크모드 토글
        st.write("")
        st.write("")
        st.write("")

        mode_icon = "🌞" if st.session_state.dark_mode else "🌜"
        mode_text = "라이트 모드" if st.session_state.dark_mode else "다크 모드"

        if st.button(f"{mode_icon} {mode_text}", key="theme_toggle", use_container_width=True):
            st.session_state.dark_mode = not st.session_state.dark_mode
            st.rerun()