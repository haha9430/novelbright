import streamlit as st
import uuid
import requests
from components.common import get_current_project
from components.sidebar import render_sidebar

# [핵심] 파일 파싱 함수 가져오기
try:
    from api import save_material_api, delete_material_api, parse_file_content, BASE_URL
except ImportError:
    # 로컬 테스트용 폴백 (api.py가 같은 폴더에 없을 경우)
    import os

    BASE_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")


    def parse_file_content(file):
        return "파일 파싱 함수 로드 실패"


def render_materials():
    proj = get_current_project()
    if not proj:
        st.session_state.page = "home"
        st.rerun()

    if "materials" not in proj: proj['materials'] = []

    if "selected_material_id" not in st.session_state:
        st.session_state.selected_material_id = None

    render_sidebar(proj)

    st.title(f"자료실")
    st.caption("설정에 참고할 자료를 텍스트로 보관하거나 파일을 불러와 저장합니다.")
    st.divider()

    c_list, c_edit = st.columns([1, 2], gap="large")

    # ---------------------------------------------------------
    # 1. 왼쪽: 자료 목록
    # ---------------------------------------------------------
    with c_list:
        c1, c2 = st.columns([2, 1])
        c1.subheader("목록")

        if c2.button("＋ 추가", use_container_width=True):
            new_mat = {"id": str(uuid.uuid4()), "title": "새 자료", "content": ""}
            proj['materials'].insert(0, new_mat)
            st.session_state.selected_material_id = new_mat['id']
            st.rerun()

        if not proj['materials']:
            st.info("등록된 자료가 없습니다.")

        for mat in proj['materials']:
            is_sel = (mat['id'] == st.session_state.selected_material_id)
            icon = "📂" if is_sel else "📄"
            btn_type = "primary" if is_sel else "secondary"

            if st.button(f"{icon} {mat['title']}", key=f"m_{mat['id']}", use_container_width=True, type=btn_type):
                st.session_state.selected_material_id = mat['id']
                st.rerun()

    # ---------------------------------------------------------
    # 2. 오른쪽: 상세 편집 (파일 업로드 추가됨)
    # ---------------------------------------------------------
    with c_edit:
        sel_mat = next((m for m in proj['materials'] if m['id'] == st.session_state.selected_material_id), None)

        if sel_mat:
            with st.container(border=True):
                c_head, c_btn = st.columns([8, 1])
                c_head.caption("자료 상세 내용")

                # 삭제 버튼
                if c_btn.button("🗑", key=f"del_m_{sel_mat['id']}"):
                    proj['materials'].remove(sel_mat)
                    st.session_state.selected_material_id = None
                    st.toast("자료가 삭제되었습니다.")
                    st.rerun()

                # 제목 편집
                new_t = st.text_input("제목", value=sel_mat['title'], key="mat_title")
                if new_t != sel_mat['title']: sel_mat['title'] = new_t

                # =================================================
                # [NEW] 파일 업로드 영역 (텍스트 추출)
                # =================================================
                with st.expander("파일에서 내용 불러오기 (HWP, PDF, Word)", expanded=False):
                    uploaded_file = st.file_uploader(
                        "파일을 업로드하면 텍스트를 추출하여 아래 내용에 덮어씁니다.",
                        type=["txt", "md", "pdf", "docx", "hwp"],
                        key="mat_uploader"
                    )

                    if uploaded_file is not None:
                        if st.button("파일 내용 적용하기", use_container_width=True):
                            with st.spinner("파일 내용을 분석 중입니다..."):
                                extracted_text = parse_file_content(uploaded_file)

                                if extracted_text:
                                    sel_mat['content'] = extracted_text
                                    sel_mat['title'] = uploaded_file.name  # 파일명으로 제목 자동 변경 (편의상)
                                    st.toast(f"'{uploaded_file.name}' 내용을 불러왔습니다!", icon="✅")
                                    st.rerun()
                                else:
                                    st.error("텍스트를 추출하지 못했습니다.")

                # 내용 편집 (TextArea)
                # 파일에서 불러온 내용이 여기에 표시됩니다.
                new_ctx = st.text_area(
                    "내용",
                    value=sel_mat.get('content', ''),
                    height=500,
                    placeholder="직접 내용을 입력하거나 위에서 파일을 불러오세요.",
                    key="mat_content"
                )
                if new_ctx != sel_mat.get('content', ''): sel_mat['content'] = new_ctx

                st.divider()

                # 저장 버튼
                if st.button("💾 저장하기", type="primary", use_container_width=True):
                    try:
                        # 백엔드 API 연결 시 사용 (현재는 세션에만 저장)
                        # requests.post(f"{BASE_URL}/history/upsert", json=sel_mat)
                        st.toast("자료가 저장되었습니다!", icon="✅")
                    except Exception as e:
                        st.error(f"저장 중 오류가 발생했습니다: {e}")

        else:
            if proj['materials']:
                st.info("왼쪽 목록에서 자료를 선택해주세요.")
            else:
                st.info("'추가' 버튼을 눌러 새로운 자료 공간을 만드세요.")