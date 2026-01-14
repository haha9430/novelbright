import streamlit as st
from streamlit_quill import st_quill
from bs4 import BeautifulSoup

# 컴포넌트 및 API 불러오기
from components.common import get_current_project, get_current_document
from components.sidebar import render_sidebar
from api import save_document_api, analyze_text_api


def render_editor():
    # 1. 프로젝트 및 문서 가져오기
    proj = get_current_project()
    if not proj:
        st.session_state.page = "home"
        st.rerun()

    current_doc = get_current_document(proj)
    quill_key = f"quill_{current_doc['id']}"

    # 2. 사이드바 렌더링
    render_sidebar(proj)

    # 3. 콘텐츠 및 글자 수 로직
    content_raw = st.session_state.get(quill_key)
    content_source = content_raw if content_raw is not None else current_doc.get('content', "")

    char_count_total = 0
    char_count_no_space = 0
    if content_source:
        soup = BeautifulSoup(content_source, "html.parser")
        plain_text = soup.get_text()
        char_count_total = len(plain_text)
        char_count_no_space = len(plain_text.replace(" ", "").replace("\n", ""))

    # 4. 헤더 영역
    c_title, c_stats, c_btn = st.columns([6, 2.5, 1.5], gap="small", vertical_alignment="bottom")

    with c_title:
        st.markdown('<div class="doc-title-input">', unsafe_allow_html=True)
        new_t = st.text_input("t", value=current_doc['title'], key=f"t_{current_doc['id']}",
                              label_visibility="collapsed", placeholder="제목 없음")
        if new_t != current_doc['title']:
            current_doc['title'] = new_t
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with c_stats:
        st.markdown(f"""
            <div style="text-align: right; color: #888; font-size: 13px; margin-bottom: 8px;">
                <span style="font-weight:bold; color:#5D4037;">{char_count_total:,}</span> 자 
                <span style="font-size:11px; color:#aaa;">(공백제외 {char_count_no_space:,})</span>
            </div>
            """, unsafe_allow_html=True)

    with c_btn:
        lbl = "✖ 닫기" if st.session_state.show_moneta else "✨ Moneta"
        if st.button(lbl, use_container_width=True):
            st.session_state.show_moneta = not st.session_state.show_moneta
            st.rerun()

    # 5. Moneta 패널
    if st.session_state.show_moneta:
        # 상태 변수 초기화
        if "last_opened_expander" not in st.session_state:
            st.session_state.last_opened_expander = None

        # [NEW] 분석 상태 추적 (어떤 분석이 실행되었고 결과가 없었는지 확인용)
        if "sk_analyzed" not in st.session_state: st.session_state.sk_analyzed = False
        if "clio_analyzed" not in st.session_state: st.session_state.clio_analyzed = False

        with st.container(border=True):
            st.caption("AI 분석 도구를 선택하세요.")
            col_sk, col_clio = st.columns(2, gap="small")

            # 현재 저장된 전체 결과 가져오기
            current_results = st.session_state.analysis_results.get(current_doc['id'], [])

            # (1) 스토리키퍼 버튼 (개연성) - role: logic
            with col_sk:
                if st.button("🛡️ 스토리키퍼 (개연성)", use_container_width=True):
                    with st.spinner("스토리키퍼 분석 중..."):
                        api_res = analyze_text_api(current_doc['id'], content_source, modules=["storykeeper"])

                        # logic 결과만 추출
                        new_logic_items = [item for item in api_res if item.get('role') == 'logic']

                        # 기존 logic 결과 삭제 후 병합
                        results_without_logic = [item for item in current_results if item.get('role') != 'logic']
                        final_results = results_without_logic + new_logic_items

                        st.session_state.analysis_results[current_doc['id']] = final_results
                        st.session_state.last_opened_expander = "storykeeper"
                        st.session_state.sk_analyzed = True  # 분석 실행됨 표시
                        st.rerun()

            # (2) 클리오 버튼 (역사 고증) - role: story
            with col_clio:
                if st.button("🏛️ 클리오 (역사 고증)", use_container_width=True):
                    with st.spinner("클리오 분석 중..."):
                        api_res = analyze_text_api(current_doc['id'], content_source, modules=["clio"])

                        # story 결과만 추출
                        new_story_items = [item for item in api_res if item.get('role') == 'story']

                        # 기존 story 결과 삭제 후 병합
                        results_without_story = [item for item in current_results if item.get('role') != 'story']
                        final_results = results_without_story + new_story_items

                        st.session_state.analysis_results[current_doc['id']] = final_results
                        st.session_state.last_opened_expander = "clio"
                        st.session_state.clio_analyzed = True  # 분석 실행됨 표시
                        st.rerun()

        # ------------------------------------------------------------------
        # [결과 표시] 둘 다 Expander 적용 & 결과 없음 처리
        # ------------------------------------------------------------------
        results = st.session_state.analysis_results.get(current_doc['id'], [])

        sk_msgs = [m for m in results if m.get('role') == 'logic']
        clio_msgs = [m for m in results if m.get('role') == 'story']

        # [UI 1] 스토리키퍼 섹션
        # 분석을 실행했는데(sk_analyzed) 결과가 있거나 없거나 무조건 표시
        if st.session_state.sk_analyzed:
            is_expanded = (st.session_state.last_opened_expander == "storykeeper")

            label = f"🛡️ 스토리키퍼 결과 ({len(sk_msgs)})"
            if not sk_msgs: label = "🛡️ 스토리키퍼 (발견된 오류 없음)"

            with st.expander(label, expanded=is_expanded):
                if sk_msgs:
                    for m in sk_msgs:
                        st.markdown(f"""
                            <div class="moneta-card" style="background:#F0F8FF; border-left:4px solid #0277BD">
                                <b>{m.get('msg', '')}</b><br>
                                <span style="font-size:13px; color:#555">💡 제안: {m.get('fix', '')}</span>
                            </div>""", unsafe_allow_html=True)
                else:
                    st.success("✅ 설정 충돌이나 개연성 오류가 발견되지 않았습니다.")

        # [UI 2] 클리오 섹션
        if st.session_state.clio_analyzed:
            is_expanded = (st.session_state.last_opened_expander == "clio")

            label = f"🏛️ 클리오 결과 ({len(clio_msgs)})"
            if not clio_msgs: label = "🏛️ 클리오 (발견된 오류 없음)"

            with st.expander(label, expanded=is_expanded):
                if clio_msgs:
                    for m in clio_msgs:
                        st.markdown(f"""
                            <div class="moneta-card" style="background:#FFF5F5; border-left:4px solid #D32F2F">
                                <b>{m.get('msg', '')}</b><br>
                                <span style="font-size:13px; color:#555">💡 제안: {m.get('fix', '')}</span>
                            </div>""", unsafe_allow_html=True)
                else:
                    st.success("✅ 역사적 고증 오류가 발견되지 않았습니다.")

    # 6. 에디터 영역
    content = st_quill(value=current_doc.get('content', ""), key=quill_key)

    if content != current_doc.get('content', ""):
        current_doc['content'] = content

    with st.sidebar:
        st.divider()
        if st.button("💾 원고 저장하기", type="primary", use_container_width=True):
            with st.spinner("저장 중..."):
                if save_document_api(current_doc['id'], current_doc['title'], content):
                    st.toast("저장 완료!", icon="✅")