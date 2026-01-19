import streamlit as st
import uuid
from components.common import rename_document_modal


def render_sidebar(current_proj):
    with st.sidebar:
        # [상단] 홈으로 가기
        if st.button("🏠 홈으로", use_container_width=True):
            st.session_state.current_project_id = None
            st.session_state.page = "home"
            st.rerun()

        st.divider()

        # [프로젝트 제목]
        st.subheader(current_proj['title'])

        # [네비게이션 버튼]
        if st.button("🔍 검색하기", use_container_width=True):
            from components.common import search_modal
            search_modal(current_proj)

        if st.button("🌍 설정 (세계관/인물)", use_container_width=True):
            st.session_state.page = "universe"
            st.rerun()

        if st.button("📁 자료실", use_container_width=True):
            st.session_state.page = "materials"
            st.rerun()

        st.divider()

        # [문서 목록 영역]
        st.caption("문서")

        # + 새 문서 추가 버튼
        if st.button("＋ 새 문서 추가", use_container_width=True):
            new_doc = {
                "id": str(uuid.uuid4()),
                "title": "새 문서",
                "content": "",
                "episode_no": len(current_proj.get('documents', [])) + 1
            }
            if 'documents' not in current_proj:
                current_proj['documents'] = []

            current_proj['documents'].append(new_doc)
            st.session_state.current_doc_id = new_doc['id']
            st.session_state.page = "editor"  # 에디터로 강제 이동
            st.rerun()

        # 문서 리스트 출력
        docs = current_proj.get('documents', [])

        # 문서가 하나도 없어도 에러 없이 넘어감
        for doc in docs:
            is_selected = (doc['id'] == st.session_state.get('current_doc_id'))

            # 레이아웃: [문서 버튼] [옵션 메뉴]
            col_doc, col_opt = st.columns([4, 1])

            with col_doc:
                btn_type = "primary" if is_selected else "secondary"
                if st.button(f"📄 {doc['title']}", key=f"nav_{doc['id']}", type=btn_type, use_container_width=True):
                    st.session_state.current_doc_id = doc['id']
                    st.session_state.page = "editor"
                    st.rerun()

            with col_opt:
                # 팝오버 메뉴 (이름 변경 / 삭제)
                with st.popover("⋮", use_container_width=True):
                    if st.button("이름 변경", key=f"ren_{doc['id']}", use_container_width=True):
                        rename_document_modal(doc)

                    if st.button("삭제", key=f"del_{doc['id']}", type="primary", use_container_width=True):
                        docs.remove(doc)
                        if is_selected:
                            st.session_state.current_doc_id = None
                        st.rerun()