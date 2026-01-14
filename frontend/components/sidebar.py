# frontend/components/sidebar.py
import streamlit as st
import uuid
from components.common import search_modal, rename_document_modal

def render_sidebar(current_proj):
    with st.sidebar:
        if st.button("🏠 홈으로", use_container_width=True): st.session_state.page = "home"; st.rerun()
        st.markdown(f"## {current_proj['title']}")
        if st.button("🔍 검색하기", use_container_width=True): search_modal(current_proj)

        st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)
        if st.button("👤  등장인물", use_container_width=True): st.session_state.page = "characters"; st.rerun()
        if st.button("📅  플롯", use_container_width=True): st.session_state.page = "plot"; st.rerun()
        if st.button("📚  자료실", use_container_width=True): st.session_state.page = "materials"; st.rerun()

        st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)
        c1, c2 = st.columns([8, 2])
        c1.caption("문서")
        if c2.button("➕", key="add_doc"):
            new_doc = {"id": str(uuid.uuid4()), "title": "새 문서", "content": ""}
            current_proj['documents'].append(new_doc)
            st.session_state.current_doc_id = new_doc['id']
            st.session_state.page = "editor"
            st.rerun()

        if "documents" not in current_proj: current_proj['documents'] = []
        for doc in current_proj['documents']:
            is_active = (doc['id'] == st.session_state.current_doc_id) and (st.session_state.page == "editor")
            btn_type = "primary" if is_active else "secondary"
            c_doc, c_opt = st.columns([8.5, 1.5], gap="small")
            with c_doc:
                if st.button(f"📄 {doc['title']}", key=f"d_{doc['id']}", type=btn_type, use_container_width=True):
                    st.session_state.current_doc_id = doc['id']
                    st.session_state.page = "editor"
                    st.rerun()
            with c_opt:
                with st.popover("⋮"):
                    if st.button("이름 변경", key=f"ren_{doc['id']}"): rename_document_modal(doc)
                    if st.button("삭제", key=f"del_{doc['id']}"):
                        current_proj['documents'].remove(doc)
                        if st.session_state.current_doc_id == doc['id']: st.session_state.current_doc_id = None
                        st.rerun()