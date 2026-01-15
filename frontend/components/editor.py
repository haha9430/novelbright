import streamlit as st
from streamlit_quill import st_quill
from bs4 import BeautifulSoup
import datetime
import textwrap

# 컴포넌트 및 API 불러오기
from components.common import get_current_project, get_current_document
from components.sidebar import render_sidebar
from frontend.api import analyze_clio_api, analyze_text_api, save_document_api, save_story_history_api

def _strip_html_to_text(html: str) -> str:
    if not isinstance(html, str):
        return ""
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text()


def _short(text: str, n: int = 220) -> str:
    t = (text or "").strip()
    if len(t) <= n:
        return t
    return t[:n].rstrip() + "..."


def _sev_style(sev: str):
    sev = (sev or "medium").strip().lower()
    if sev == "high":
        return {"border": "#FF4B4B", "bg": "#FFF5F5", "icon": "🚨"}
    if sev == "low":
        return {"border": "#4CAF50", "bg": "#F0FFF4", "icon": "✅"}
    return {"border": "#FFA500", "bg": "#FFFAEB", "icon": "⚠️"}

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
                else:
                    st.toast("회차는 숫자만 입력 가능합니다.", icon="⚠️")
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
    if st.session_state.get("show_moneta", False):
        if "last_opened_expander" not in st.session_state: st.session_state.last_opened_expander = None
        if "sk_analyzed" not in st.session_state: st.session_state.sk_analyzed = False
        if "clio_analyzed" not in st.session_state: st.session_state.clio_analyzed = False
        if "analysis_results" not in st.session_state: st.session_state.analysis_results = {}

        with st.container(border=True):
            ep_num = current_doc.get("episode_no", 1)

            # ✅ (현재 분석 대상: n화) 문구 제거
            # st.caption(f"AI 분석 도구를 선택하세요. (현재 분석 대상: {ep_num}화)")

            severity_option = st.selectbox(
                "분석 민감도(Severity)",
                options=["high", "medium", "low"],
                index=0,
                key="moneta_severity_select",
                help="선택한 등급으로 분류된 항목만 보여줍니다.",
            )

            col_sk, col_clio = st.columns([1, 1], gap="small")

            with col_sk:
                if st.button("🛡️ 스토리키퍼 (개연성)", use_container_width=True):
                    with st.spinner("스토리키퍼가 원고를 분석 중입니다..."):
                        api_res = analyze_text_api(
                            current_doc["id"],
                            content_source,
                            episode_no=ep_num,
                            severity=severity_option,
                        )

                        current_data = st.session_state.analysis_results.get(current_doc["id"])

                        if current_data is None or not isinstance(current_data, dict):
                            st.session_state.analysis_results[current_doc["id"]] = {}

                        st.session_state.analysis_results[current_doc["id"]]['sk'] = api_res
                        st.session_state.sk_analyzed = True
                        st.rerun()

            with col_clio:
                if st.button("🏛️ 클리오 (역사 고증)", use_container_width=True):
                    with st.spinner("분석 중..."):
                        api_res = analyze_clio_api(current_doc, content_source)

                        current_data = st.session_state.analysis_results.get(current_doc["id"])

                        if current_data is None or not isinstance(current_data, dict):
                            st.session_state.analysis_results[current_doc["id"]] = {}

                        st.session_state.analysis_results[current_doc['id']]['clio'] = api_res
                        #new_items = [i for i in api_res if i.get('role') == 'story']
                        #filtered = [i for i in current_results if i.get('role') != 'story']
                        #st.session_state.analysis_results[current_doc['id']] = filtered + new_items

                        st.session_state.last_opened_expander = "clio"
                        st.session_state.clio_analyzed = True
                        st.rerun()

        results = st.session_state.analysis_results.get(current_doc['id'], [])

        # ✅ 같은 severity만 표시
        target_list = []
        if isinstance(results, dict):
            # 클리오: 딕셔너리 안에 있는 'historical_context' 리스트를 사용
            target_list = results.get("historical_context", [])
        elif isinstance(results, list):
            # 스토리 키퍼: 리스트 자체를 사용
            target_list = results

        filtered_results = []

        # ---------------------------------------------------------
        # [수정됨] 저장된 결과 가져오기 (꾸러미에서 각각 꺼내기)
        # ---------------------------------------------------------
        doc_data = st.session_state.analysis_results.get(current_doc['id'], {})

        # 1. 스토리키퍼 결과 (리스트)
        sk_results = doc_data.get("sk", [])
        if not isinstance(sk_results, list): sk_results = []

        # 2. 클리오 결과 (딕셔너리)
        clio_results = doc_data.get("clio", {})
        if not isinstance(clio_results, dict): clio_results = {}

        # ---------------------------------------------------------
        # [수정됨] 스토리키퍼용 필터링 로직 (sk_results만 사용)
        # ---------------------------------------------------------
        filtered_sk_results = []
        for m in sk_results:
            if not isinstance(m, dict): continue

            # severity 필터링
            item_sev = str(m.get("severity", "medium")).strip().lower()
            if item_sev == severity_option:
                filtered_sk_results.append(m)

        # 이제 target_list는 무조건 '리스트'이므로 안전하게 돌릴 수 있습니다.
        for m in target_list:
            if not isinstance(m, dict): continue  # 안전장치

            # severity가 없는 경우(클리오)를 대비해 기본값 처리
            item_sev = str(m.get("severity", "medium")).strip().lower()

            # 클리오는 severity 필터링 없이 다 보여주거나, 필요하면 로직 추가
            # 여기서는 편의상 필터를 통과시키거나 'medium'으로 간주
            if item_sev == severity_option or isinstance(results, dict):
                filtered_results.append(m)

        doc_results = st.session_state.analysis_results.get(current_doc['id'], {})
        sk_results = doc_results.get("sk", [])      # 스토리키퍼 결과
        clio_results = doc_results.get("clio", {})  # 클리오 결과

        # 1. 🛡️ 스토리키퍼 결과 표시
        if st.session_state.sk_analyzed:
            label = f"🛡️ 스토리키퍼 결과 ({len(filtered_sk_results)}건)"
            # 데이터가 있는데 필터링 결과가 0건이면 안내 메시지
            if not filtered_sk_results and sk_results:
                label = f"🛡️ 스토리키퍼 (선택 등급 '{severity_option}' 항목 없음)"

            with st.expander(label, expanded=True):
                if not sk_results:
                    st.info("분석된 결과가 없습니다. 버튼을 눌러 분석을 시작하세요.")
                elif not filtered_sk_results:
                    st.success(f"✅ '{severity_option}' 등급으로 감지된 개연성 오류가 없습니다.")
                else:
                    for m in filtered_sk_results:
                        sev = str(m.get("severity", "medium")).strip().lower()
                        style = _sev_style(sev)

                        type_label = (m.get("type_label") or "오류").strip()
                        title = (m.get("title") or "설정 충돌").strip()
                        header_title = f"{style['icon']} {type_label} - {title}"

                        sentence = (m.get("sentence") or "").strip()
                        sentence_preview = _short(sentence, 260) if sentence else "(원문 문장 없음)"
                        reason = (m.get("reason") or "").strip() or "피드백 없음"

                        # ✅ location(몇화-몇줄) UI 표시 제거 (아예 안 씀)
                        html = f"""
        <div style="border-left: 5px solid {style['border']};
                    background-color: {style['bg']};
                    padding: 14px 16px;
                    margin-bottom: 14px;
                    border-radius: 10px;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.08);">

          <div style="font-weight: 800; font-size: 15px; color: {style['border']}; margin-bottom: 6px;">
            {header_title}
          </div>

          <div style="font-size: 15px; font-weight: 600; color: #222; line-height: 1.65; margin-bottom: 10px;">
            “{sentence_preview}”
          </div>

          <div style="background:#fff;
                      border: 1px solid rgba(0,0,0,0.08);
                      padding: 10px 12px;
                      border-radius: 10px;
                      font-size: 13px;
                      color:#444;
                      line-height: 1.7;">
            <strong>💡 피드백</strong><br/>
            {reason}
          </div>
        </div>
        """
                        st.markdown(textwrap.dedent(html).strip(), unsafe_allow_html=True)
        if st.session_state.clio_analyzed:
            # 여기서는 clio_results를 사용해야 합니다! (doc_data 아님)
            label = f"🏛️ 클리오 결과"

            with st.expander(label, expanded=(st.session_state.last_opened_expander == "clio")):
                if clio_results:

                    found_count = clio_results.get("found_entities_count", 0)
                    history_items = clio_results.get("historical_context", [])

                    if "analysis_result" in clio_results:
                        inner = clio_results["analysis_result"]
                        if isinstance(inner, dict):
                            found_count = inner.get("found_entities_count", found_count)
                            history_items = inner.get("historical_context", history_items)

                    st.divider()
                    st.subheader(f"📊 분석 결과 리포트 ({len(history_items)}건 감지)")

                    if not history_items:
                        st.info("검출된 역사적 특이사항이 없습니다.")

                    for item in history_items:
                        # 1. 데이터 준비
                        is_positive = item.get("is_positive", False)
                        keyword = item.get('keyword', '키워드 없음')
                        original_sentence = item.get('original_sentence', '')
                        reason = item.get('reason', '')

                        # 2. 카드 컨테이너 생성 (외곽선 있는 박스)
                        with st.container(border=True):

                            # [헤더 영역] 상태 아이콘과 키워드 배치
                            col_header_L, col_header_R = st.columns([0.65, 0.35])

                            with col_header_L:
                                if is_positive:
                                    st.markdown("### ✅ 고증 일치")
                                else:
                                    st.markdown("### ⚠️ 고증 오류 의심")

                            with col_header_R:
                                # 키워드를 코드 블록 스타일로 보여주어 뱃지처럼 연출
                                st.markdown(f"**KEYWORD**")
                                st.code(keyword, language="text")

                            # [원문 영역] 인용구 스타일 활용
                            st.caption("❝ 원문 발췌")
                            st.markdown(f"> *{original_sentence}*")

                            st.divider() # 구분선

                            # [분석 결과 영역] 색상 박스로 강조
                            # 일치하면 초록색 박스(success), 오류면 빨간색 박스(error) 사용
                            if is_positive:
                                st.success(f"**🕵️ 분석 결과**\n\n{reason}", icon="✅")
                            else:
                                st.error(f"**🕵️ 분석 결과**\n\n{reason}", icon="⚠️")

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