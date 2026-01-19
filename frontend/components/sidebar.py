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

        # [네비게이션 버튼]
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

        # 새 문서 추가 버튼
        if st.button("새 문서 추가", use_container_width=True):
            if 'documents' not in current_proj:
                current_proj['documents'] = []

            # 현재 문서 개수 + 1로 새 번호 부여 (삭제 시 재정렬되므로 항상 순서가 맞음)
            next_ep_no = len(current_proj['documents']) + 1

            new_doc = {
                "id": str(uuid.uuid4()),
                "title": f"새 문서 {next_ep_no}",
                "content": "",
                "summary": "",
                "episode_no": next_ep_no
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
                if st.button(doc['title'], key=f"nav_{doc['id']}", type=btn_type, use_container_width=True):
                    st.session_state.current_doc_id = doc['id']
                    st.session_state.page = "editor"
                    st.rerun()

            with col_opt:
                with st.popover("⋮", use_container_width=True):
                    if st.button("이름 변경", key=f"ren_{doc['id']}", use_container_width=True):
                        rename_document_modal(doc)

                    # ✅ [수정됨] 삭제 시 번호 재정렬 로직 추가
                    if st.button("삭제", key=f"del_{doc['id']}", type="primary", use_container_width=True):
                        docs.remove(doc)  # 1. 문서 삭제

                        # 2. 남은 문서들의 episode_no를 순서대로 다시 매김 (1, 2, 3...)
                        for idx, d in enumerate(docs):
                            d['episode_no'] = idx + 1

                        if is_selected:
                            st.session_state.current_doc_id = None
                        st.rerun()

        st.divider()

        # [하단] 다크모드 토글
        dark_on = st.toggle("다크 모드", value=st.session_state.get("dark_mode", False), key="sidebar_dark_toggle")
        if dark_on != st.session_state.get("dark_mode", False):
            st.session_state.dark_mode = dark_on
            st.rerun()