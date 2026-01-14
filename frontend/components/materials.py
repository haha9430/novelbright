import streamlit as st
import uuid
from components.common import get_current_project
from components.sidebar import render_sidebar
from api import save_material_api, delete_material_api


def render_materials():
    proj = get_current_project()
    if not proj:
        st.session_state.page = "home"
        st.rerun()

    if "materials" not in proj: proj['materials'] = []

    render_sidebar(proj)
    st.title("📚 자료실")
    st.divider()

    c_list, c_edit = st.columns([1, 2], gap="large")

    # 1. 왼쪽: 자료 목록
    with c_list:
        c1, c2 = st.columns([2, 1])
        c1.subheader("목록")

        # [수정됨] category 데이터 완전 삭제
        if c2.button("＋ 추가", use_container_width=True):
            new_mat = {"id": str(uuid.uuid4()), "title": "새 자료", "content": ""}
            proj['materials'].insert(0, new_mat)
            st.session_state.selected_material_id = new_mat['id']
            st.rerun()

        for mat in proj['materials']:
            is_sel = (mat['id'] == st.session_state.selected_material_id)
            icon = "📄"

            if st.button(f"{icon} {mat['title']}", key=f"m_{mat['id']}", use_container_width=True,
                         type="primary" if is_sel else "secondary"):
                st.session_state.selected_material_id = mat['id']
                st.rerun()

    # 2. 오른쪽: 상세 편집
    with c_edit:
        sel_mat = next((m for m in proj['materials'] if m['id'] == st.session_state.selected_material_id), None)

        if sel_mat:
            with st.container(border=True):
                c1, c2 = st.columns([8, 1])
                c1.caption("자료 상세 편집")

                # 삭제 버튼
                if c2.button("🗑", key=f"del_m_{sel_mat['id']}"):
                    if delete_material_api(sel_mat['id']):
                        proj['materials'].remove(sel_mat)
                        st.session_state.selected_material_id = None
                        st.toast("삭제됨")
                        st.rerun()
                    else:
                        st.error("삭제 실패")

                # 제목 편집
                new_t = st.text_input("제목", value=sel_mat['title'])
                if new_t != sel_mat['title']: sel_mat['title'] = new_t

                # 내용 편집
                new_ctx = st.text_area("내용", value=sel_mat.get('content', ''), height=400)
                if new_ctx != sel_mat.get('content', ''): sel_mat['content'] = new_ctx

                st.divider()

                # 저장 버튼
                if st.button("💾 저장하기", type="primary", use_container_width=True):
                    # api.py는 딕셔너리를 그대로 보내므로 수정 불필요
                    if save_material_api(sel_mat):
                        st.toast("저장 완료!", icon="✅")
                    else:
                        st.error("저장 실패")
        else:
            st.info("👈 왼쪽 목록에서 자료를 선택하거나 추가하세요.")