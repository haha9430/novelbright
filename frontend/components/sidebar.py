import streamlit as st
import uuid
from components.common import rename_document_modal


def render_sidebar(current_proj):
    with st.sidebar:
        # [상단] 홈으로 가기
        if st.button("홈으로", use_container_width=True):
            st.session_state.current_project_id = None
            st.session_state.page = "home"
            st.rerun()

        st.divider()

        # [프로젝트 제목]
        st.subheader(current_proj['title'])

        # [네비게이션 버튼] - 아이콘 제거
        if st.button("검색하기", use_container_width=True):
            from components.common import search_modal
            search_modal(current_proj)

        if st.button("설정", use_container_width=True):
            st.session_state.page = "universe"
            st.rerun()

        if st.button("자료실", use_container_width=True):
            st.session_state.page = "materials"
            st.rerun()

        st.divider()

        # [문서 목록 영역]
        st.caption("문서")

        # 새 문서 추가 버튼 - 아이콘 제거
        if st.button("새 문서 추가", use_container_width=True):
            if 'documents' not in current_proj:
                current_proj['documents'] = []

            # ✅ [필수] 회차 번호 자동 생성 (현재 문서 개수 + 1)
            next_ep_no = len(current_proj['documents']) + 1

            new_doc = {
                "id": str(uuid.uuid4()),
                "title": f"새 문서 {next_ep_no}",
                "content": "",
                "summary": "",
                "episode_no": next_ep_no  # 백엔드 필수 데이터
            }

            current_proj['documents'].append(new_doc)
            st.session_state.current_doc_id = new_doc['id']
            st.session_state.page = "editor"
            st.rerun()

        # 문서 리스트 출력
        docs = current_proj.get('documents', [])

        for doc in docs:
            is_selected = (doc['id'] == st.session_state.get('current_doc_id'))

            col_doc, col_opt = st.columns([4, 1])

            with col_doc:
                btn_type = "primary" if is_selected else "secondary"
                # 버튼 텍스트에서 아이콘 제거
                # 회차 번호를 리스트에도 보여줄지 여부는 선택사항이나, 깔끔하게 제목만 표시
                if st.button(doc['title'], key=f"nav_{doc['id']}", type=btn_type, use_container_width=True):
                    st.session_state.current_doc_id = doc['id']
                    st.session_state.page = "editor"
                    st.rerun()

            with col_opt:
                with st.popover("⋮", use_container_width=True):
                    if st.button("이름 변경", key=f"ren_{doc['id']}", use_container_width=True):
                        rename_document_modal(doc)

                    if st.button("삭제", key=f"del_{doc['id']}", type="primary", use_container_width=True):
                        docs.remove(doc)
                        if is_selected:
                            st.session_state.current_doc_id = None
                        st.rerun()

        st.divider()

        # [하단] 다크모드 토글 - 아이콘 제거
        dark_on = st.toggle("다크 모드", value=st.session_state.get("dark_mode", False), key="sidebar_dark_toggle")
        if dark_on != st.session_state.get("dark_mode", False):
            st.session_state.dark_mode = dark_on
            st.rerun()