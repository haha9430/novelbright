

import streamlit as st
from frontend.api import get_projects, create_project, get_documents, create_document


def render_sidebar():
    """사이드바 렌더링 및 선택된 프로젝트/문서 반환"""
    selected_project = None
    selected_document = None

    with st.sidebar:
        st.header("📂 프로젝트")

        # 1. 프로젝트 목록 로드
        projects = get_projects()
        opts = {p['id']: p['name'] for p in projects}

        # 세션 상태 초기화
        if "current_project_id" not in st.session_state and projects:
            st.session_state.current_project_id = projects[0]['id']

        # 프로젝트 선택 박스
        pid = st.selectbox(
            "내 프로젝트",
            options=list(opts.keys()),
            format_func=lambda x: opts[x],
            key="sb_project_select",
            index=0 if not projects else list(opts.keys()).index(
                st.session_state.get('current_project_id', projects[0]['id']))
        )

        if pid:
            st.session_state.current_project_id = pid
            selected_project = next((p for p in projects if p['id'] == pid), None)

        # 프로젝트 생성 UI
        with st.expander("➕ 새 프로젝트"):
            new_p_name = st.text_input("프로젝트 명")
            if st.button("생성", key="btn_create_proj"):
                if create_project(new_p_name, ""):
                    st.rerun()

        st.divider()

        # 2. 문서 목록 로드
        if selected_project:
            st.subheader(f"📄 {selected_project['name']} 문서")
            docs = get_documents(selected_project['id'])

            # 문서 리스트 출력
            for doc in docs:
                btn_bg = "★" if st.session_state.get("current_doc_id") == doc['id'] else " "
                if st.button(f"{btn_bg} {doc['title']}", key=f"btn_doc_{doc['id']}", use_container_width=True):
                    st.session_state.current_doc_id = doc['id']
                    st.rerun()

            # 현재 선택된 문서 객체 찾기
            if st.session_state.get("current_doc_id"):
                selected_document = next((d for d in docs if d['id'] == st.session_state.current_doc_id), None)

            # 문서 생성 UI
            if st.button("➕ 새 문서 만들기", use_container_width=True):
                create_document(selected_project['id'], "새 문서")
                st.rerun()

    return selected_project, selected_document