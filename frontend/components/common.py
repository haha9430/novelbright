import streamlit as st
import uuid
import base64
from datetime import datetime


# ❌ [삭제됨] 여기에 있던 'from components.common import ...' 줄을 제거했습니다.
# 이 파일은 함수들을 정의하는 곳이므로 자기 자신을 임포트할 필요가 없습니다.

# ---------------------------------------------------------
# 1. 헬퍼 함수
# ---------------------------------------------------------
def _image_to_base64(uploaded_file):
    if uploaded_file is None:
        return None
    try:
        bytes_data = uploaded_file.getvalue()
        base64_str = base64.b64encode(bytes_data).decode()
        mime_type = uploaded_file.type
        return f"data:{mime_type};base64,{base64_str}"
    except Exception:
        return None


# ---------------------------------------------------------
# 2. 공통 유틸리티
# ---------------------------------------------------------
def get_current_project():
    if not st.session_state.get("current_project_id"):
        return None

    projects = st.session_state.get("projects", [])
    return next((p for p in projects if p["id"] == st.session_state.current_project_id), None)


def get_current_document(proj=None):
    if proj is None:
        proj = get_current_project()

    if not proj or not st.session_state.get("current_doc_id"):
        return None

    docs = proj.get("documents", [])
    return next((d for d in docs if d["id"] == st.session_state.current_doc_id), None)


# ---------------------------------------------------------
# 3. 모달: 새 작품 만들기
# ---------------------------------------------------------
@st.dialog("새 작품 만들기")
def create_project_modal():
    st.caption("새로운 소설의 기본 정보를 입력해주세요.")

    with st.form("create_project_form", clear_on_submit=True):
        title = st.text_input("제목", placeholder="작품 제목을 입력하세요")
        desc = st.text_area("설명", placeholder="간단한 줄거리나 소개를 입력하세요")
        tags_str = st.text_input("태그", placeholder="예: 판타지, 성장물, 로맨스 (쉼표로 구분)")
        thumbnail_file = st.file_uploader("썸네일 이미지", type=["png", "jpg", "jpeg"])

        submitted = st.form_submit_button("생성", use_container_width=True, type="primary")

        if submitted:
            if not title.strip():
                st.error("제목은 필수입니다.")
            else:
                tag_list = [t.strip() for t in tags_str.split(",") if t.strip()]
                thumbnail_b64 = _image_to_base64(thumbnail_file)

                # 빈 프로젝트 구조 생성
                new_proj = {
                    "id": str(uuid.uuid4()),
                    "title": title,
                    "desc": desc,
                    "tags": tag_list,
                    "thumbnail": thumbnail_b64,
                    "created_at": datetime.now().strftime("%Y년 %m월 %d일"),
                    "documents": [],
                    "materials": [],
                    "characters": [],
                    "groups": [],
                    "history": []
                }

                if "projects" not in st.session_state:
                    st.session_state.projects = []
                st.session_state.projects.append(new_proj)

                st.toast(f"작품 '{title}'이(가) 생성되었습니다!", icon="🎉")
                st.rerun()


# ---------------------------------------------------------
# 4. 모달: 작품 정보 수정
# ---------------------------------------------------------
@st.dialog("작품 정보 수정")
def edit_project_modal(proj):
    st.caption(f"'{proj['title']}'의 정보를 수정합니다.")
    default_tags = ", ".join(proj.get("tags", []))

    with st.form("edit_project_form"):
        new_title = st.text_input("제목", value=proj['title'])
        new_desc = st.text_area("설명", value=proj.get('desc', ''))
        new_tags_str = st.text_input("태그", value=default_tags)

        st.markdown("**썸네일 이미지**")
        if proj.get("thumbnail"):
            st.image(proj["thumbnail"], width=100)

        new_thumbnail_file = st.file_uploader("변경할 이미지 (선택)", type=["png", "jpg", "jpeg"])

        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("수정 저장", use_container_width=True, type="primary"):
                if not new_title.strip():
                    st.error("제목은 비워둘 수 없습니다.")
                else:
                    proj['title'] = new_title
                    proj['desc'] = new_desc
                    proj['tags'] = [t.strip() for t in new_tags_str.split(",") if t.strip()]
                    if new_thumbnail_file:
                        new_b64 = _image_to_base64(new_thumbnail_file)
                        if new_b64:
                            proj['thumbnail'] = new_b64
                    st.toast("수정되었습니다.", icon="✅")
                    st.rerun()

        with col2:
            if st.form_submit_button("작품 삭제", use_container_width=True):
                st.session_state.projects.remove(proj)
                if st.session_state.current_project_id == proj['id']:
                    st.session_state.current_project_id = None
                    st.session_state.page = "home"
                st.toast("삭제되었습니다.", icon="🗑")
                st.rerun()


# ---------------------------------------------------------
# 5. 모달: 등장인물 추가
# ---------------------------------------------------------
@st.dialog("새 등장인물 추가")
def add_character_modal(proj):
    st.caption("새로운 캐릭터를 등록합니다.")
    with st.form("add_char_form", clear_on_submit=True):
        col_img, col_info = st.columns([1, 2])
        with col_img:
            img_file = st.file_uploader("이미지", type=["png", "jpg"], key="new_char_img")
        with col_info:
            name = st.text_input("이름", placeholder="캐릭터 이름")
            role = st.selectbox("역할", ["주연", "조연", "엑스트라", "악역"], index=0)
            age = st.text_input("나이", placeholder="예: 24세")

        desc = st.text_area("특징 / 설명", placeholder="성격, 외모, 배경 설정 등...", height=100)

        if st.form_submit_button("등록하기", type="primary", use_container_width=True):
            if not name.strip():
                st.error("이름을 입력해주세요.")
            else:
                if "characters" not in proj: proj["characters"] = []
                img_b64 = _image_to_base64(img_file)
                new_char = {"id": str(uuid.uuid4()), "name": name, "role": role, "age": age, "desc": desc,
                            "image": img_b64}
                proj["characters"].append(new_char)
                st.toast(f"'{name}' 캐릭터가 추가되었습니다!", icon="✅")
                st.rerun()


# ---------------------------------------------------------
# 6. 모달: 문서 이름 변경
# ---------------------------------------------------------
@st.dialog("문서 이름 변경")
def rename_document_modal(doc):
    new_name = st.text_input("새로운 제목", value=doc['title'])
    if st.button("변경 저장", type="primary"):
        doc['title'] = new_name
        st.rerun()


# ---------------------------------------------------------
# 7. 모달: 통합 검색
# ---------------------------------------------------------
@st.dialog("🔍 통합 검색")
def search_modal(current_proj):
    if not current_proj:
        st.error("선택된 프로젝트가 없습니다.")
        return

    query = st.text_input("검색어 입력", placeholder="찾고 싶은 내용을 입력하세요...")

    if query:
        st.markdown(f"**'{query}'** 검색 결과")
        results_found = False

        docs = current_proj.get('documents', [])
        for doc in docs:
            if query in doc['title'] or query in doc.get('content', ''):
                st.button(f"📄 {doc['title']}", key=f"search_doc_{doc['id']}")
                results_found = True

        if not results_found:
            st.caption("검색 결과가 없습니다.")