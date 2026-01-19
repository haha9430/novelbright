import streamlit as st
import uuid
import re
import base64
from datetime import datetime

from api import save_character_api

# =========================================================
# 1. Helper Functions
# =========================================================
def get_current_project():
    if st.session_state.current_project_id is None and st.session_state.projects:
        st.session_state.current_project_id = st.session_state.projects[0]["id"]
    return next((p for p in st.session_state.projects if p["id"] == st.session_state.current_project_id), None)


def get_current_document(proj):
    if not proj.get("documents"):
        new_doc = {"id": str(uuid.uuid4()), "title": "새 문서", "content": "", "episode_no": 1}
        proj["documents"] = [new_doc]
        st.session_state.current_doc_id = new_doc["id"]
        return new_doc

    if st.session_state.current_doc_id is None:
        doc = proj["documents"][0]
        if "episode_no" not in doc:
            doc["episode_no"] = 1
        st.session_state.current_doc_id = doc["id"]
        return doc

    doc = next((d for d in proj["documents"] if d["id"] == st.session_state.current_doc_id), None)
    if not doc:
        doc = proj["documents"][0]
        if "episode_no" not in doc:
            doc["episode_no"] = 1
        st.session_state.current_doc_id = doc["id"]

    if "episode_no" not in doc:
        doc["episode_no"] = 1

    return doc


# =========================================================
# 2. Modals (Dialogs)
# =========================================================
@st.dialog("🔍 통합 검색", width="large")
def search_modal(project):
    st.markdown("### 무엇을 찾고 계신가요?")
    query = st.text_input("검색어", placeholder="문서, 자료, 인물 검색...", label_visibility="collapsed")
    if query:
        st.divider()
        found = False

        for doc in project.get("documents", []):
            clean_content = re.sub("<[^<]+?>", "", doc.get("content", ""))
            if query in doc["title"] or query in clean_content:
                found = True
                with st.container(border=True):
                    st.markdown(f"**📄 {doc['title']}**")
                    st.caption(clean_content[:100] + "...")

        for mat in project.get("materials", []):
            if query in mat["title"] or query in mat["content"]:
                found = True
                icon = "🏛️" if mat["category"] == "역사" else "⚙️"
                with st.container(border=True):
                    st.markdown(f"**{icon} {mat['title']}** <small>({mat['category']})</small>", unsafe_allow_html=True)
                    st.caption(mat["content"][:100] + "...")

        if not found:
            st.info("검색 결과가 없습니다.")
# ---------------------------------------------------------
# [추가] 이미지 -> Base64 변환 헬퍼 함수
# ---------------------------------------------------------
def _image_to_base64(uploaded_file):
    """업로드된 이미지 파일을 Base64 문자열로 변환"""
    if uploaded_file is None:
        return None
    try:
        bytes_data = uploaded_file.getvalue()
        base64_str = base64.b64encode(bytes_data).decode()
        # 이미지 타입 추출 (png, jpg 등)
        mime_type = uploaded_file.type
        return f"data:{mime_type};base64,{base64_str}"
    except Exception:
        return None


@st.dialog("새 작품 만들기")
def create_project_modal():
    st.caption("새로운 소설의 기본 정보를 입력해주세요.")

    with st.form("create_project_form", clear_on_submit=True):
        title = st.text_input("제목", placeholder="작품 제목을 입력하세요")
        desc = st.text_area("설명", placeholder="간단한 줄거리나 소개를 입력하세요")

        # [추가] 태그 입력
        tags_str = st.text_input("태그", placeholder="예: 판타지, 성장물, 로맨스 (쉼표로 구분)")

        # [추가] 썸네일 업로드
        thumbnail_file = st.file_uploader("썸네일 이미지", type=["png", "jpg", "jpeg"])

        submitted = st.form_submit_button("생성", use_container_width=True, type="primary")

        if submitted:
            if not title.strip():
                st.error("제목은 필수입니다.")
            else:
                # 1. 태그 처리 (쉼표로 분리 및 공백 제거)
                tag_list = [t.strip() for t in tags_str.split(",") if t.strip()]

                # 2. 썸네일 처리 (Base64 변환)
                thumbnail_b64 = _image_to_base64(thumbnail_file)

                # 3. 새 프로젝트 객체 생성
                new_proj = {
                    "id": str(uuid.uuid4()),
                    "title": title,
                    "desc": desc,
                    "tags": tag_list,  # 태그 리스트 저장
                    "thumbnail": thumbnail_b64,  # 썸네일 데이터 저장
                    "created_at": datetime.now().strftime("%Y년 %m월 %d일"),
                    "documents": []
                }

                # 4. 세션에 저장
                if "projects" not in st.session_state:
                    st.session_state.projects = []
                st.session_state.projects.append(new_proj)

                st.toast(f"작품 '{title}'이(가) 생성되었습니다!", icon="🎉")
                st.rerun()


@st.dialog("문서 이름 변경")
def rename_document_modal(doc):
    new_t = st.text_input("새 이름", value=doc["title"])
    if st.button("변경"):
        doc["title"] = new_t
        st.rerun()


@st.dialog("새 인물 추가")
def add_character_modal(project):
    name = st.text_input("이름")
    desc = st.text_area("설명")

    if st.button("추가"):
        if not (name and desc):
            st.warning("이름과 설명을 모두 입력해주세요.")
            return

        with st.spinner("백엔드에 캐릭터 정보를 기록 중..."):
            success = save_character_api(name, desc)

        if success:
            project["characters"].append(
                {
                    "id": str(uuid.uuid4()),
                    "name": name,
                    "tag": "주요 인물",
                    "desc": desc,
                }
            )
            st.success(f"'{name}' 설정이 저장되었습니다!")
            st.rerun()
        else:
            st.error("캐릭터 저장에 실패했습니다. (백엔드 모듈/경로를 확인하세요)")