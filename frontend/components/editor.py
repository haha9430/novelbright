import streamlit as st
import time
from streamlit_quill import st_quill
from components.common import get_current_project, get_current_document
from components.sidebar import render_sidebar


def render_editor():
    # 1. 현재 프로젝트 가져오기
    proj = get_current_project()
    if not proj:
        st.session_state.page = "home"
        st.rerun()
        return

    # 2. 사이드바 렌더링
    render_sidebar(proj)

    # 3. 현재 문서 가져오기
    current_doc = get_current_document(proj)

    # ✅ [빈 상태 처리] 문서가 없을 경우의 안전 장치
    if current_doc is None:
        if proj.get('documents') and len(proj['documents']) > 0:
            # 문서가 있는데 선택이 안 된 경우 -> 첫 번째 자동 선택
            current_doc = proj['documents'][0]
            st.session_state.current_doc_id = current_doc['id']
            st.rerun()
        else:
            # 문서가 하나도 없는 경우 -> 안내 화면 표시
            st.title(proj['title'])
            st.divider()
            st.info("👈 왼쪽 사이드바에서 '+ 새 문서 추가' 버튼을 눌러 집필을 시작하세요!")
            return

    # ---------------------------------------------------------
    # 에디터 UI (문서가 있을 때만 렌더링)
    # ---------------------------------------------------------

    # 제목 입력
    col_title, col_save = st.columns([8, 2], vertical_alignment="bottom")
    with col_title:
        new_title = st.text_input("문서 제목", value=current_doc['title'], key=f"doc_title_{current_doc['id']}",
                                  label_visibility="collapsed")
        if new_title != current_doc['title']:
            current_doc['title'] = new_title

    # 저장 상태 표시
    with col_save:
        content_text = current_doc.get('content', '')
        char_count = len(content_text.replace(" ", "")) if content_text else 0
        st.caption(f"**{char_count}** 자 (공백제외)")
        st.caption("✅ 대기 중 저장됨")

    # Quill 에디터
    quill_key = f"quill_{current_doc['id']}"
    content = st_quill(
        value=current_doc.get('content', ''),
        placeholder="여기에서 글을 쓰기 시작하세요...",
        html=False,
        key=quill_key
    )

    if content is not None and content != current_doc.get('content', ''):
        current_doc['content'] = content

    # Moneta 패널
    st.divider()
    if "show_moneta" not in st.session_state:
        st.session_state.show_moneta = False

    lbl = "✖ 닫기" if st.session_state.show_moneta else "✨ AI 분석 도구 (Moneta)"
    if st.button(lbl, use_container_width=True):
        st.session_state.show_moneta = not st.session_state.show_moneta
        st.rerun()

    if st.session_state.show_moneta:
        render_moneta_panel(current_doc, content)


def render_moneta_panel(current_doc, content_source):
    if "analysis_results" not in st.session_state:
        st.session_state.analysis_results = {}

    with st.container(border=True):
        st.markdown("### 🧐 Moneta 분석")
        sev_map = {"Low": "low", "Medium": "medium", "High": "high"}
        st.select_slider("분석 민감도", options=list(sev_map.keys()), value="Medium", key="sev_ui")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("🛡️ 스토리키퍼", use_container_width=True):
                with st.spinner("분석 중..."):
                    time.sleep(1)
                    st.success("분석 완료 (데모)")
        with c2:
            st.button("📜 클리오", use_container_width=True, disabled=True)