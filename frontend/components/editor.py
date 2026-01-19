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
            st.info("왼쪽 사이드바에서 '새 문서 추가' 버튼을 눌러 집필을 시작하세요!")
            return

    # ---------------------------------------------------------
    # 에디터 상단 UI (회차 번호 + 제목 + 상태)
    # ---------------------------------------------------------

    # [수정됨] 레이아웃: [회차번호] [제목입력] [저장상태]
    col_no, col_title, col_save = st.columns([1, 7, 2], vertical_alignment="bottom")

    # 1. 회차 번호 표시 (백엔드 필수 데이터)
    ep_no = current_doc.get('episode_no', 1)
    with col_no:
        # 제목 인풋 높이에 맞춰서 정렬
        st.markdown(f"<h3 style='margin-bottom: 0px; text-align: center;'>#{ep_no}</h3>", unsafe_allow_html=True)

    # 2. 제목 입력
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

    # 3. 저장 상태
    with col_save:
        content_text = current_doc.get('content', '')
        char_count = len(content_text.replace(" ", "")) if content_text else 0
        st.caption(f"{char_count} 자 (공백제외)")
        st.caption("대기 중 저장됨")

    st.write("")  # 간격 띄우기

    # ---------------------------------------------------------
    # AI 도구 (Moneta) 패널 - 아이콘 제거
    # ---------------------------------------------------------
    if "show_moneta" not in st.session_state:
        st.session_state.show_moneta = False

    # 토글 버튼 (아이콘 제거)
    lbl = "Moneta 닫기" if st.session_state.show_moneta else "AI 분석 도구 (Moneta) 열기"

    if st.button(lbl, use_container_width=True):
        st.session_state.show_moneta = not st.session_state.show_moneta
        st.rerun()

    # 패널 렌더링
    if st.session_state.show_moneta:
        render_moneta_panel(current_doc, current_doc.get('content', ''))
        st.divider()

    # ---------------------------------------------------------
    # 메인 에디터 (Quill Editor)
    # ---------------------------------------------------------
    quill_key = f"quill_{current_doc['id']}"

    content = st_quill(
        value=current_doc.get('content', ''),
        placeholder="여기에서 글을 쓰기 시작하세요...",
        html=False,
        key=quill_key
    )

    if content is not None and content != current_doc.get('content', ''):
        current_doc['content'] = content


# ---------------------------------------------------------
# [내부 함수] Moneta 패널 렌더링 (아이콘 제거)
# ---------------------------------------------------------
def render_moneta_panel(current_doc, content_source):
    if "analysis_results" not in st.session_state:
        st.session_state.analysis_results = {}

    with st.container(border=True):
        st.markdown("### Moneta 분석")

        sev_map = {"Low": "low", "Medium": "medium", "High": "high"}
        st.select_slider("분석 민감도", options=list(sev_map.keys()), value="Medium", key="sev_ui")

        c1, c2 = st.columns(2)

        # 스토리키퍼
        with c1:
            if st.button("스토리키퍼 (개연성 체크)", use_container_width=True):
                if not content_source.strip():
                    st.warning("분석할 본문 내용이 없습니다.")
                else:
                    with st.spinner("스토리키퍼가 원고를 분석 중입니다..."):
                        time.sleep(1.5)
                        doc_id = current_doc["id"]
                        if doc_id not in st.session_state.analysis_results:
                            st.session_state.analysis_results[doc_id] = {}

                        st.session_state.analysis_results[doc_id]['sk'] = (
                            "**[스토리키퍼] 분석 완료**\n\n"
                            "- **개연성**: 95점 (매우 우수)\n"
                            "- **피드백**: 주인공의 행동 패턴이 지난 화와 일관되며, 전개 속도가 적절합니다."
                        )

        # 클리오
        with c2:
            if st.button("클리오 (고증 체크)", use_container_width=True):
                if not content_source.strip():
                    st.warning("분석할 본문 내용이 없습니다.")
                else:
                    with st.spinner("클리오가 역사적 사실을 대조하고 있습니다..."):
                        time.sleep(1.5)
                        doc_id = current_doc["id"]
                        if doc_id not in st.session_state.analysis_results:
                            st.session_state.analysis_results[doc_id] = {}

                        st.session_state.analysis_results[doc_id]['clio'] = (
                            "**[클리오] 고증 분석 완료**\n\n"
                            "- **시대 배경**: 1916년 1차 세계대전\n"
                            "- **발견된 이슈**: 없음. 당시 무기 체계 및 군사 용어가 적절하게 사용되었습니다."
                        )

        # 결과 표시
        doc_id = current_doc["id"]
        if doc_id in st.session_state.analysis_results:
            res = st.session_state.analysis_results[doc_id]
            if 'sk' in res:
                st.markdown("---")
                st.info(res['sk'])
            if 'clio' in res:
                st.markdown("---")
                st.success(res['clio'])