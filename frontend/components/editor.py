import streamlit as st
from streamlit_quill import st_quill
from bs4 import BeautifulSoup
import datetime
import textwrap

# 컴포넌트 및 API 불러오기
from components.common import get_current_project, get_current_document
from components.sidebar import render_sidebar

# [API 연동] 실제 백엔드 통신을 위해 api 모듈에서 임포트
try:
    from api import analyze_clio_api, analyze_text_api, save_document_api
except ImportError:
    # API 모듈이 없을 경우 에러 방지용 (빈 값 반환)
    def analyze_text_api(*args, **kwargs):
        return []


    def analyze_clio_api(*args, **kwargs):
        return {"found_entities_count": 0, "historical_context": []}


    def save_document_api(*args, **kwargs):
        return True


# ---------------------------------------------------------
# 1. 헬퍼 함수
# ---------------------------------------------------------
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
    """분석 결과 스타일 (아이콘 제거, 색상/라벨만 유지)"""
    sev = (sev or "medium").strip().lower()
    if sev == "high":
        return {"border": "#FF4B4B", "bg": "#FFF5F5", "label": "[심각]"}
    if sev == "low":
        return {"border": "#4CAF50", "bg": "#F0FFF4", "label": "[양호]"}
    return {"border": "#FFA500", "bg": "#FFFAEB", "label": "[주의]"}


# ---------------------------------------------------------
# 2. 메인 에디터 렌더링
# ---------------------------------------------------------
def render_editor():
    proj = get_current_project()
    if not proj:
        st.session_state.page = "home"
        st.rerun()
        return

    # 사이드바 먼저 렌더링
    render_sidebar(proj)

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

    quill_key = f"quill_{current_doc['id']}"

    # 내용 로드
    content_raw = st.session_state.get(quill_key)
    content_source = content_raw if content_raw is not None else current_doc.get('content', "")

    if "last_save_time" not in st.session_state:
        st.session_state.last_save_time = "대기 중"

    # 통계 계산
    def calculate_stats(text):
        if not text: return 0, 0
        soup = BeautifulSoup(text, "html.parser")
        plain = soup.get_text()
        return len(plain), len(plain.replace(" ", "").replace("\n", ""))

    char_total, char_nospace = calculate_stats(content_source)

    # ---------------------------------------------------------
    # [상단 UI]
    # ---------------------------------------------------------
    c_title, c_stats, c_btn = st.columns([6, 2.5, 1.5], gap="small", vertical_alignment="bottom")

    with c_title:
        c_ep, c_txt = st.columns([1.2, 8.8], vertical_alignment="bottom")

        # 회차 번호
        with c_ep:
            ep_str = str(current_doc.get('episode_no', 1))
            new_ep = st.text_input("ep", value=ep_str, key=f"ep_{current_doc['id']}", label_visibility="collapsed",
                                   placeholder="1")
            if new_ep != ep_str:
                if new_ep.isdigit():
                    current_doc['episode_no'] = int(new_ep)
                    save_document_api(current_doc['id'], current_doc['title'], content_source)
                    st.rerun()

        # 제목 입력
        with c_txt:
            new_t = st.text_input("t", value=current_doc['title'], key=f"t_{current_doc['id']}",
                                  label_visibility="collapsed", placeholder="제목 없음")
            if new_t != current_doc['title']:
                current_doc['title'] = new_t
                if save_document_api(current_doc['id'], current_doc['title'], content_source):
                    st.session_state.last_save_time = datetime.datetime.now().strftime("%H:%M:%S")
                st.rerun()

    # 통계 표시
    with c_stats:
        stats_placeholder = st.empty()
        stats_placeholder.markdown(f"""
            <div style="text-align: right; color: #888; font-size: 13px; margin-bottom: 8px;">
                <span style="font-weight:bold; color:#5D4037;">{char_total:,}</span> 자 
                <span style="font-size:11px; color:#aaa;">(공백제외 {char_nospace:,})</span>
                <br>
                <span style="font-size:11px; color:#4CAF50;">[저장됨] {st.session_state.last_save_time}</span>
            </div>""", unsafe_allow_html=True)

    # Moneta 토글 버튼
    with c_btn:
        lbl = "닫기" if st.session_state.get("show_moneta", False) else "Moneta 열기"
        if st.button(lbl, use_container_width=True):
            st.session_state.show_moneta = not st.session_state.get("show_moneta", False)
            st.rerun()

    # ---------------------------------------------------------
    # [Moneta 패널]
    # ---------------------------------------------------------
    if st.session_state.get("show_moneta", False):
        if "last_opened_expander" not in st.session_state: st.session_state.last_opened_expander = None
        if "sk_analyzed" not in st.session_state: st.session_state.sk_analyzed = False
        if "clio_analyzed" not in st.session_state: st.session_state.clio_analyzed = False
        if "analysis_results" not in st.session_state: st.session_state.analysis_results = {}

        with st.container(border=True):
            ep_num = current_doc.get("episode_no", 1)

            # 민감도 선택
            severity_option = st.selectbox(
                "분석 민감도(Severity)",
                options=["high", "medium", "low"],
                index=0,
                key="moneta_severity_select",
            )

            col_sk, col_clio = st.columns([1, 1], gap="small")

            # 1) 스토리키퍼 분석 버튼
            with col_sk:
                if st.button("스토리키퍼 (개연성)", use_container_width=True):
                    with st.spinner("스토리키퍼가 원고를 분석 중입니다..."):
                        api_res = analyze_text_api(
                            current_doc["id"],
                            content_source,
                            episode_no=ep_num,
                            severity=severity_option,
                        )

                        # [Fix] API가 None을 반환하면 빈 리스트로 처리
                        if api_res is None:
                            api_res = []

                        if current_doc["id"] not in st.session_state.analysis_results:
                            st.session_state.analysis_results[current_doc["id"]] = {}

                        st.session_state.analysis_results[current_doc["id"]]['sk'] = api_res
                        st.session_state.sk_analyzed = True
                        st.rerun()

            # 2) 클리오 분석 버튼
            with col_clio:
                if st.button("클리오 (역사 고증)", use_container_width=True):
                    with st.spinner("클리오가 역사적 사실을 대조하고 있습니다..."):
                        api_res = analyze_clio_api(current_doc, content_source)

                        # [Fix] API가 None을 반환하면 빈 딕셔너리로 처리
                        if api_res is None:
                            api_res = {}

                        if current_doc["id"] not in st.session_state.analysis_results:
                            st.session_state.analysis_results[current_doc["id"]] = {}

                        st.session_state.analysis_results[current_doc['id']]['clio'] = api_res
                        st.session_state.last_opened_expander = "clio"
                        st.session_state.clio_analyzed = True
                        st.rerun()

        # ---------------------------------------------------------
        # [결과 렌더링]
        # ---------------------------------------------------------
        doc_data = st.session_state.analysis_results.get(current_doc['id'], {})

        # [Fix] 가져온 값이 None이면 빈 구조체로 대체 (서버 연결 실패 시 방어)
        sk_results = doc_data.get("sk")
        if sk_results is None: sk_results = []

        clio_results = doc_data.get("clio")
        if clio_results is None: clio_results = {}

        # (1) 스토리키퍼 결과
        if st.session_state.sk_analyzed:
            filtered_sk_results = []
            if isinstance(sk_results, list):
                for m in sk_results:
                    if not isinstance(m, dict): continue
                    if str(m.get("severity", "medium")).lower() == severity_option:
                        filtered_sk_results.append(m)

            label = f"스토리키퍼 결과 ({len(filtered_sk_results)}건)"

            with st.expander(label, expanded=True):
                if not sk_results:
                    st.info("분석된 결과가 없습니다. (서버 응답 없음)")
                elif not filtered_sk_results:
                    st.success(f"'{severity_option}' 등급으로 감지된 개연성 오류가 없습니다.")
                else:
                    for m in filtered_sk_results:
                        sev = str(m.get("severity", "medium")).strip().lower()
                        style = _sev_style(sev)

                        type_label = m.get("type_label") or "오류"
                        title = m.get("title") or "내용 없음"
                        header_title = f"{style['label']} {type_label} - {title}"

                        sentence = m.get("sentence") or ""
                        sentence_preview = _short(sentence, 260) if sentence else "(원문 문장 없음)"
                        reason = m.get("reason") or "피드백 없음"

                        html = f"""
                        <div style="border-left: 5px solid {style['border']}; background-color: {style['bg']}; padding: 14px 16px; margin-bottom: 14px; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.08);">
                          <div style="font-weight: 800; font-size: 15px; color: {style['border']}; margin-bottom: 6px;">
                            {header_title}
                          </div>
                          <div style="font-size: 15px; font-weight: 600; color: #222; line-height: 1.65; margin-bottom: 10px;">
                            “{sentence_preview}”
                          </div>
                          <div style="background:#fff; border: 1px solid rgba(0,0,0,0.08); padding: 10px 12px; border-radius: 10px; font-size: 13px; color:#444; line-height: 1.7;">
                            <strong>피드백</strong><br/>
                            {reason}
                          </div>
                        </div>
                        """
                        st.markdown(textwrap.dedent(html).strip(), unsafe_allow_html=True)

        # (2) 클리오 결과
        if st.session_state.clio_analyzed:
            label = f"클리오 결과"
            with st.expander(label, expanded=(st.session_state.last_opened_expander == "clio")):

                # [Fix] clio_results가 딕셔너리인지 확실히 확인 후 사용
                history_items = []
                if isinstance(clio_results, dict):
                    history_items = clio_results.get("historical_context", [])
                    if "analysis_result" in clio_results and isinstance(clio_results["analysis_result"], dict):
                        history_items = clio_results["analysis_result"].get("historical_context", [])

                st.divider()
                st.subheader(f"분석 리포트 ({len(history_items)}건 감지)")

                if not history_items:
                    st.info("검출된 역사적 특이사항이 없습니다.")

                for item in history_items:
                    is_positive = item.get("is_positive", False)
                    keyword = item.get('keyword', '키워드 없음')
                    original_sentence = item.get('original_sentence', '')
                    reason = item.get('reason', '')

                    with st.container(border=True):
                        col_h1, col_h2 = st.columns([0.65, 0.35])
                        with col_h1:
                            st.markdown("### [고증 일치]" if is_positive else "### [고증 오류 의심]")
                        with col_h2:
                            st.caption("KEYWORD")
                            st.code(keyword, language="text")

                        st.caption("원문 발췌")
                        st.markdown(f"> *{original_sentence}*")
                        st.divider()

                        msg = f"**분석 결과**\n\n{reason}"
                        if is_positive:
                            st.success(msg)
                        else:
                            st.error(msg)

    # ---------------------------------------------------------
    # 3. Quill 에디터
    # ---------------------------------------------------------
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
                    <span style="font-size:11px; color:#4CAF50;">[저장됨] {now_str}</span>
                </div>""", unsafe_allow_html=True)