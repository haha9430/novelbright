import streamlit as st
from streamlit_quill import st_quill
from bs4 import BeautifulSoup
import datetime

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

    if "last_save_time" not in st.session_state:
        st.session_state.last_save_time = "대기 중"

    def calculate_stats(text):
        if not text: return 0, 0
        soup = BeautifulSoup(text, "html.parser")
        plain = soup.get_text()
        return len(plain), len(plain.replace(" ", "").replace("\n", ""))

    char_total, char_nospace = calculate_stats(content_source)

    # 4. 헤더 영역
    # [수정] vertical_alignment="bottom"을 줘서 제목과 버튼, 통계의 라인을 맞춤
    c_title, c_stats, c_btn = st.columns([6, 2.5, 1.5], gap="small", vertical_alignment="bottom")

    with c_title:
        # [수정] 회차(1.2) : 제목(8.8) 비율로 나눔 + 하단 정렬
        c_ep, c_txt = st.columns([1.2, 8.8], vertical_alignment="bottom")

        with c_ep:
            # 제목과 동일한 스타일 클래스 적용 (큰 글씨, 투명 배경)
            st.markdown('<div class="doc-title-input">', unsafe_allow_html=True)

            # number_input 대신 text_input 사용 (디자인 통일 위해)
            ep_str = str(current_doc.get('episode_no', 1))
            new_ep = st.text_input("ep", value=ep_str, key=f"ep_{current_doc['id']}",
                                   label_visibility="collapsed", placeholder="1")

            if new_ep != ep_str:
                # 숫자만 입력했는지 확인
                if new_ep.isdigit():
                    current_doc['episode_no'] = int(new_ep)
                    save_document_api(current_doc['id'], current_doc['title'], content_source)
                    st.rerun()
                else:
                    st.toast("회차는 숫자만 입력 가능합니다.", icon="⚠️")
                    # 잘못된 입력 시 새로고침하여 원상복구
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        with c_txt:
            st.markdown('<div class="doc-title-input">', unsafe_allow_html=True)
            new_t = st.text_input("t", value=current_doc['title'], key=f"t_{current_doc['id']}",
                                  label_visibility="collapsed", placeholder="제목 없음")
            if new_t != current_doc['title']:
                current_doc['title'] = new_t
                if save_document_api(current_doc['id'], current_doc['title'], content_source):
                    st.session_state.last_save_time = datetime.datetime.now().strftime("%H:%M:%S")
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    # 통계 및 상태 표시 영역
    with c_stats:
        stats_placeholder = st.empty()
        stats_placeholder.markdown(f"""
            <div style="text-align: right; color: #888; font-size: 13px; margin-bottom: 8px;">
                <span style="font-weight:bold; color:#5D4037;">{char_total:,}</span> 자 
                <span style="font-size:11px; color:#aaa;">(공백제외 {char_nospace:,})</span>
                <br>
                <span style="font-size:11px; color:#4CAF50;">✅ {st.session_state.last_save_time} 저장됨</span>
            </div>
            """, unsafe_allow_html=True)

    with c_btn:
        lbl = "✖ 닫기" if st.session_state.show_moneta else "✨ Moneta"
        if st.button(lbl, use_container_width=True):
            st.session_state.show_moneta = not st.session_state.show_moneta
            st.rerun()

    # 5. Moneta 패널 (기존 유지)
    if st.session_state.show_moneta:
        if "last_opened_expander" not in st.session_state: st.session_state.last_opened_expander = None
        if "sk_analyzed" not in st.session_state: st.session_state.sk_analyzed = False
        if "clio_analyzed" not in st.session_state: st.session_state.clio_analyzed = False

        with st.container(border=True):
            # [안내 문구] 현재 회차 표시
            ep_num = current_doc.get('episode_no', 1)
            st.caption(f"AI 분석 도구를 선택하세요. (현재 분석 대상: {ep_num}화)")

            col_sk, col_clio = st.columns(2, gap="small")
            current_results = st.session_state.analysis_results.get(current_doc['id'], [])

            with col_sk:
                if st.button("🛡️ 스토리키퍼 (개연성)", use_container_width=True):
                    with st.spinner("분석 중..."):
                        api_res = analyze_text_api(current_doc['id'], content_source,
                                                   episode_no=ep_num,
                                                   modules=["storykeeper"])
                        new_items = [i for i in api_res if i.get('role') == 'logic']
                        filtered = [i for i in current_results if i.get('role') != 'logic']
                        st.session_state.analysis_results[current_doc['id']] = filtered + new_items
                        st.session_state.last_opened_expander = "storykeeper"
                        st.session_state.sk_analyzed = True
                        st.rerun()

            with col_clio:
                if st.button("🏛️ 클리오 (역사 고증)", use_container_width=True):
                    with st.spinner("분석 중..."):
                        api_res = analyze_text_api(current_doc['id'], content_source,
                                                   episode_no=ep_num,
                                                   modules=["clio"])
                        new_items = [i for i in api_res if i.get('role') == 'story']
                        filtered = [i for i in current_results if i.get('role') != 'story']
                        st.session_state.analysis_results[current_doc['id']] = filtered + new_items
                        st.session_state.last_opened_expander = "clio"
                        st.session_state.clio_analyzed = True
                        st.rerun()

        # 결과 표시 (Expander)
        results = st.session_state.analysis_results.get(current_doc['id'], [])
        sk_msgs = [m for m in results if m.get('role') == 'logic']
        clio_msgs = [m for m in results if m.get('role') == 'story']

        if st.session_state.sk_analyzed:
            label = f"🛡️ 스토리키퍼 결과 ({len(sk_msgs)})" if sk_msgs else "🛡️ 스토리키퍼 (발견된 오류 없음)"
            with st.expander(label, expanded=(st.session_state.last_opened_expander == "storykeeper")):
                if sk_msgs:
                    for m in sk_msgs:
                        st.markdown(
                            f"""<div class="moneta-card" style="background:#F0F8FF; border-left:4px solid #0277BD"><b>{m.get('msg')}</b><br><span style="font-size:13px; color:#555">💡 제안: {m.get('fix')}</span></div>""",
                            unsafe_allow_html=True)
                else:
                    st.success("✅ 설정 충돌 없음")

        if st.session_state.clio_analyzed:
            label = f"🏛️ 클리오 결과 ({len(clio_msgs)})" if clio_msgs else "🏛️ 클리오 (발견된 오류 없음)"
            with st.expander(label, expanded=(st.session_state.last_opened_expander == "clio")):
                if clio_msgs:
                    for m in clio_msgs:
                        st.markdown(
                            f"""<div class="moneta-card" style="background:#FFF5F5; border-left:4px solid #D32F2F"><b>{m.get('msg')}</b><br><span style="font-size:13px; color:#555">💡 제안: {m.get('fix')}</span></div>""",
                            unsafe_allow_html=True)
                else:
                    st.success("✅ 고증 오류 없음")

    # 6. 에디터 영역
    content = st_quill(value=current_doc.get('content', ""), key=quill_key)

    if content != current_doc.get('content', ""):
        current_doc['content'] = content
        if save_document_api(current_doc['id'], current_doc['title'], content):
            now_str = datetime.datetime.now().strftime("%H:%M:%S")
            st.session_state.last_save_time = now_str
            new_total, new_nospace = calculate_stats(content)
            stats_placeholder.markdown(f"""
                <div style="text-align: right; color: #888; font-size: 13px; margin-bottom: 8px;">
                    <span style="font-weight:bold; color:#5D4037;">{new_total:,}</span> 자 
                    <span style="font-size:11px; color:#aaa;">(공백제외 {new_nospace:,})</span>
                    <br>
                    <span style="font-size:11px; color:#4CAF50;">✅ {now_str} 저장됨</span>
                </div>
                """, unsafe_allow_html=True)