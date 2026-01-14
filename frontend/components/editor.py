import datetime
import textwrap

import streamlit as st
from bs4 import BeautifulSoup
from streamlit_quill import st_quill

from api import analyze_text_api, save_document_api, save_story_history_api
from components.common import get_current_document, get_current_project
from components.sidebar import render_sidebar


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
    proj = get_current_project()
    if not proj:
        st.session_state.page = "home"
        st.rerun()

    current_doc = get_current_document(proj)
    quill_key = f"quill_{current_doc['id']}"

    render_sidebar(proj)

    content_raw = st.session_state.get(quill_key)
    content_source = content_raw if content_raw is not None else current_doc.get("content", "")

    if "last_save_time" not in st.session_state:
        st.session_state.last_save_time = "대기 중"

    def calculate_stats(text):
        if not text:
            return 0, 0
        plain = _strip_html_to_text(text)
        return len(plain), len(plain.replace(" ", "").replace("\n", ""))

    char_total, char_nospace = calculate_stats(content_source)

    c_title, c_stats, c_btn = st.columns([6, 2.5, 1.5], gap="small", vertical_alignment="bottom")

    with c_title:
        c_ep, c_txt = st.columns([1.2, 8.8], vertical_alignment="bottom")

        with c_ep:
            st.markdown('<div class="doc-title-input">', unsafe_allow_html=True)
            ep_str = str(current_doc.get("episode_no", 1))
            new_ep = st.text_input(
                "ep",
                value=ep_str,
                key=f"ep_{current_doc['id']}",
                label_visibility="collapsed",
                placeholder="1",
            )
            if new_ep != ep_str:
                if new_ep.isdigit():
                    current_doc["episode_no"] = int(new_ep)
                    save_document_api(current_doc["id"], current_doc["title"], content_source)
                    st.rerun()
                else:
                    st.toast("회차는 숫자만 입력 가능합니다.", icon="⚠️")
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        with c_txt:
            st.markdown('<div class="doc-title-input">', unsafe_allow_html=True)
            new_t = st.text_input(
                "t",
                value=current_doc["title"],
                key=f"t_{current_doc['id']}",
                label_visibility="collapsed",
                placeholder="제목 없음",
            )
            if new_t != current_doc["title"]:
                current_doc["title"] = new_t
                if save_document_api(current_doc["id"], current_doc["title"], content_source):
                    st.session_state.last_save_time = datetime.datetime.now().strftime("%H:%M:%S")
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    with c_stats:
        stats_placeholder = st.empty()
        stats_placeholder.markdown(
            f"""
<div style="text-align: right; color: #888; font-size: 13px; margin-bottom: 8px;">
  <span style="font-weight:bold; color:#5D4037;">{char_total:,}</span> 자
  <span style="font-size:11px; color:#aaa;">(공백제외 {char_nospace:,})</span>
  <br>
  <span style="font-size:11px; color:#4CAF50;">✅ {st.session_state.last_save_time} 저장됨</span>
</div>
""",
            unsafe_allow_html=True,
        )

    with c_btn:
        lbl = "✖ 닫기" if st.session_state.get("show_moneta", False) else "✨ Moneta"
        if st.button(lbl, use_container_width=True):
            st.session_state.show_moneta = not st.session_state.get("show_moneta", False)
            st.rerun()

    # ---------------- Moneta panel ----------------
    if st.session_state.get("show_moneta", False):
        if "sk_analyzed" not in st.session_state:
            st.session_state.sk_analyzed = False
        if "analysis_results" not in st.session_state:
            st.session_state.analysis_results = {}

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

            col_sk, col_hist = st.columns([1, 1], gap="small")

            with col_sk:
                if st.button("🛡️ 스토리키퍼 (개연성)", use_container_width=True):
                    with st.spinner("스토리키퍼가 원고를 분석 중입니다..."):
                        api_res = analyze_text_api(
                            current_doc["id"],
                            content_source,
                            episode_no=ep_num,
                            severity=severity_option,
                        )
                        st.session_state.analysis_results[current_doc["id"]] = api_res
                        st.session_state.sk_analyzed = True
                        st.rerun()

            with col_hist:
                if st.button("📚 펙트체크", use_container_width=True):
                    with st.spinner("펙트 체크 중 ..."):
                        ok, res = save_story_history_api(ep_num, content_source)
                    if ok:
                        st.success("저장 완료!")
                    else:
                        st.error(res.get("message", "저장 실패"))
                    st.rerun()

        results = st.session_state.analysis_results.get(current_doc["id"], [])

        # ✅ 같은 severity만 표시
        filtered_results = []
        for m in results:
            item_sev = str(m.get("severity", "medium")).strip().lower()
            if item_sev == severity_option:
                filtered_results.append(m)

        if st.session_state.sk_analyzed:
            label = f"🛡️ 분석 결과 ({len(filtered_results)}건)"
            with st.expander(label, expanded=True):
                if not filtered_results:
                    if len(results) > 0:
                        st.info("✅ 이 등급으로 분류된 항목은 없습니다.")
                    else:
                        st.success("✅ 현재 설정과 충돌하는 내용이 없습니다.")
                else:
                    for m in filtered_results:
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

    # ---------------- Editor ----------------
    content = st_quill(value=current_doc.get("content", ""), key=quill_key)

    if content != current_doc.get("content", ""):
        current_doc["content"] = content
        if save_document_api(current_doc["id"], current_doc["title"], content):
            now_str = datetime.datetime.now().strftime("%H:%M:%S")
            st.session_state.last_save_time = now_str

            new_total, new_nospace = calculate_stats(content)
            stats_placeholder.markdown(
                f"""
<div style="text-align: right; color: #888; font-size: 13px; margin-bottom: 8px;">
  <span style="font-weight:bold; color:#5D4037;">{new_total:,}</span> 자
  <span style="font-size:11px; color:#aaa;">(공백제외 {new_nospace:,})</span>
  <br>
  <span style="font-size:11px; color:#4CAF50;">✅ {now_str} 저장됨</span>
</div>
""",
                unsafe_allow_html=True,
            )
