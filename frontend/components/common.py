import streamlit as st
import uuid
import re

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


@st.dialog("새 작품 만들기")
def create_project_modal():
    title = st.text_input("제목")
    if st.button("생성"):
        st.session_state.projects.append(
            {
                "id": str(uuid.uuid4()),
                "title": title,
                "tags": [],
                "desc": "",
                "last_edited": "방금",
                "characters": [],
                "materials": [],
                "plots": [],
                "documents": [],
            }
        )
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