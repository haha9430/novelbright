import streamlit as st
from streamlit_quill import st_quill
from bs4 import BeautifulSoup
import datetime

# 컴포넌트 및 API 불러오기
from components.common import get_current_project, get_current_document
from components.sidebar import render_sidebar
from api import save_document_api, analyze_text_api


def render_editor():
    # ... (1~4. 헤더 영역까지 기존 코드와 동일) ...
    proj = get_current_project()
    if not proj:
        st.session_state.page = "home"
        st.rerun()
    current_doc = get_current_document(proj)
    quill_key = f"quill_{current_doc['id']}"
    render_sidebar(proj)

    content_raw = st.session_state.get(quill_key)
    content_source = content_raw if content_raw is not None else current_doc.get('content', "")
    if "last_save_time" not in st.session_state: st.session_state.last_save_time = "대기 중"

    def calculate_stats(text):
        if not text: return 0, 0
        soup = BeautifulSoup(text, "html.parser")
        plain = soup.get_text()
        return len(plain), len(plain.replace(" ", "").replace("\n", ""))

    char_total, char_nospace = calculate_stats(content_source)

    c_title, c_stats, c_btn = st.columns([6, 2.5, 1.5], gap="small", vertical_alignment="bottom")
    with c_title:
        c_ep, c_txt = st.columns([1.2, 8.8], vertical_alignment="bottom")
        with c_ep:
            st.markdown('<div class="doc-title-input">', unsafe_allow_html=True)
            ep_str = str(current_doc.get('episode_no', 1))
            new_ep = st.text_input("ep", value=ep_str, key=f"ep_{current_doc['id']}", label_visibility="collapsed",
                                   placeholder="1")
            if new_ep != ep_str:
                if new_ep.isdigit():
                    current_doc['episode_no'] = int(new_ep)
                    save_document_api(current_doc['id'], current_doc['title'], content_source)
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

    with c_stats:
        stats_placeholder = st.empty()
        stats_placeholder.markdown(f"""
            <div style="text-align: right; color: #888; font-size: 13px; margin-bottom: 8px;">
                <span style="font-weight:bold; color:#5D4037;">{char_total:,}</span> 자 
                <span style="font-size:11px; color:#aaa;">(공백제외 {char_nospace:,})</span>
                <br>
                <span style="font-size:11px; color:#4CAF50;">✅ {st.session_state.last_save_time} 저장됨</span>
            </div>""", unsafe_allow_html=True)

    with c_btn:
        lbl = "✖ 닫기" if st.session_state.show_moneta else "✨ Moneta"
        if st.button(lbl, use_container_width=True):
            st.session_state.show_moneta = not st.session_state.show_moneta
            st.rerun()

    # 5. Moneta 패널 (수정됨)
    if st.session_state.show_moneta:
        if "last_opened_expander" not in st.session_state: st.session_state.last_opened_expander = None
        if "sk_analyzed" not in st.session_state: st.session_state.sk_analyzed = False
        if "clio_analyzed" not in st.session_state: st.session_state.clio_analyzed = False

        # [NEW] 민감도 상태 초기화
        if "sensitivity_level" not in st.session_state: st.session_state.sensitivity_level = "보통"

        with st.container(border=True):
            ep_num = current_doc.get('episode_no', 1)

            # [UI] 상단: 안내문구 + 민감도 설정 슬라이더
            r1_c1, r1_c2 = st.columns([6, 4], vertical_alignment="center")
            with r1_c1:
                st.caption(f"현재 분석 대상: **{ep_num}화**")
            with r1_c2:
                # select_slider: 텍스트로 선택하지만 로직에선 숫자로 매핑 가능
                sens_opts = ["낮음", "보통", "높음"]
                selected_sens = st.select_slider(
                    "분석 민감도",
                    options=sens_opts,
                    value=st.session_state.sensitivity_level,
                    key="sens_slider",
                    label_visibility="collapsed"  # 공간 절약을 위해 라벨 숨김
                )
                # 상태 저장 (리런 시 유지)
                st.session_state.sensitivity_level = selected_sens

            # 민감도 텍스트 -> 숫자 변환 매핑
            sens_map = {"낮음": 2, "보통": 5, "높음": 9}
            sens_val = sens_map[selected_sens]

            st.divider()  # 구분선 추가

            # [UI] 하단: 버튼들
            col_sk, col_clio = st.columns(2, gap="small")
            current_results = st.session_state.analysis_results.get(current_doc['id'], [])

            with col_sk:
                # 버튼 텍스트에 민감도 표시 (선택적)
                if st.button(f"🛡️ 스토리키퍼 (민감도: {selected_sens})", use_container_width=True):
                    with st.spinner("분석 중..."):
                        api_res = analyze_text_api(
                            current_doc['id'],
                            content_source,
                            episode_no=ep_num,
                            sensitivity=sens_val,  # [핵심] 민감도 전달
                            modules=["storykeeper"]
                        )
                        new_items = [i for i in api_res if i.get('role') == 'logic']
                        filtered = [i for i in current_results if i.get('role') != 'logic']
                        st.session_state.analysis_results[current_doc['id']] = filtered + new_items
                        st.session_state.last_opened_expander = "storykeeper"
                        st.session_state.sk_analyzed = True
                        st.rerun()

            with col_clio:
                if st.button("🏛️ 클리오 (역사 고증)", use_container_width=True):
                    with st.spinner("분석 중..."):
                        api_res = analyze_text_api(
                            current_doc['id'],
                            content_source,
                            episode_no=ep_num,
                            sensitivity=sens_val,
                            modules=["clio"]
                        )
                        new_items = [i for i in api_res if i.get('role') == 'story']
                        filtered = [i for i in current_results if i.get('role') != 'story']
                        st.session_state.analysis_results[current_doc['id']] = filtered + new_items
                        st.session_state.last_opened_expander = "clio"
                        st.session_state.clio_analyzed = True
                        st.rerun()

        # 결과 표시 (기존 코드와 동일)
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

    # 6. 에디터 영역 (기존과 동일)
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
                </div>""", unsafe_allow_html=True)