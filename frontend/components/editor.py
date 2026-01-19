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

    # [빈 상태 처리]
    if current_doc is None:
        if proj.get('documents') and len(proj['documents']) > 0:
            current_doc = proj['documents'][0]
            st.session_state.current_doc_id = current_doc['id']
            st.rerun()
        else:
            st.title(proj['title'])
            st.divider()
            st.info("👈 왼쪽 사이드바에서 '+ 새 문서 추가' 버튼을 눌러 집필을 시작하세요!")
            return

    # ---------------------------------------------------------
    # 에디터 상단 UI (제목 및 상태)
    # ---------------------------------------------------------
    col_title, col_save = st.columns([8, 2], vertical_alignment="bottom")

    with col_title:
        new_title = st.text_input(
            "문서 제목",
            value=current_doc['title'],
            key=f"doc_title_{current_doc['id']}",
            label_visibility="collapsed",
            placeholder="제목을 입력하세요"
        )
        if new_title != current_doc['title']:
            current_doc['title'] = new_title

    with col_save:
        content_text = current_doc.get('content', '')
        char_count = len(content_text.replace(" ", "")) if content_text else 0
        st.caption(f"**{char_count}** 자 (공백제외)")
        st.caption("✅ 대기 중 저장됨")

    st.write("")  # 간격 띄우기

    # ---------------------------------------------------------
    # ✅ [위치 변경됨] AI 도구 (Moneta) 패널 - 에디터 위쪽
    # ---------------------------------------------------------
    if "show_moneta" not in st.session_state:
        st.session_state.show_moneta = False

    # 토글 버튼
    lbl = "✖ 모네타 닫기" if st.session_state.show_moneta else "✨ AI 분석 도구 모네타 열기"

    # 버튼을 꽉 채우지 않고 적당한 크기로 배치하거나, 전체 너비로 배치
    if st.button(lbl, use_container_width=True):
        st.session_state.show_moneta = not st.session_state.show_moneta
        st.rerun()

    # 패널 렌더링 (열려있을 때만)
    if st.session_state.show_moneta:
        # 에디터가 아직 렌더링되지 않았으므로, 저장된 content를 넘김
        render_moneta_panel(current_doc, current_doc.get('content', ''))
        st.divider()  # 에디터와의 구분선

    # ---------------------------------------------------------
    # 메인 에디터 (Quill Editor)
    # ---------------------------------------------------------
    quill_key = f"quill_{current_doc['id']}"

    content = st_quill(
        value=current_doc.get('content', ''),
        placeholder="여기에서 글을 쓰기 시작하세요...",
        html=False,  # 텍스트 모드
        key=quill_key
    )

    # 내용 변경 감지 및 저장
    if content is not None and content != current_doc.get('content', ''):
        current_doc['content'] = content


# ---------------------------------------------------------
# [내부 함수] Moneta 패널 렌더링
# ---------------------------------------------------------
def render_moneta_panel(current_doc, content_source):
    if "analysis_results" not in st.session_state:
        st.session_state.analysis_results = {}

    with st.container(border=True):
        st.markdown("### 🧐 모네타 분석")

        # 민감도 설정
        sev_map = {"Low": "low", "Medium": "medium", "High": "high"}
        st.select_slider("분석 민감도", options=list(sev_map.keys()), value="Medium", key="sev_ui")

        c1, c2 = st.columns(2)

        # 스토리키퍼 버튼
        with c1:
            if st.button("🛡️ 스토리키퍼", use_container_width=True):
                if not content_source.strip():
                    st.warning("분석할 본문 내용이 없습니다.")
                else:
                    with st.spinner("스토리키퍼가 원고를 분석 중입니다..."):
                        time.sleep(1.5)  # 분석 척

                        doc_id = current_doc["id"]
                        if doc_id not in st.session_state.analysis_results:
                            st.session_state.analysis_results[doc_id] = {}

                        # 임시 결과 생성
                        st.session_state.analysis_results[doc_id]['sk'] = (
                            "✅ **분석 완료**\n\n"
                            "- **개연성**: 95점 (매우 우수)\n"
                            "- **특이사항**: 주인공의 행동 패턴이 지난 화와 일관됩니다.\n"
                        )

        # 클리오 버튼
        with c2:
            st.button("📜 클리오 (고증 체크)", use_container_width=True, disabled=True, help="준비 중입니다.")

        # 분석 결과 표시
        doc_id = current_doc["id"]
        if doc_id in st.session_state.analysis_results:
            res = st.session_state.analysis_results[doc_id]
            if 'sk' in res:
                st.markdown("---")
                st.info(res['sk'])