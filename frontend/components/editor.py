import streamlit as st
from streamlit_quill import st_quill
from bs4 import BeautifulSoup


def render_editor_area(current_doc):
    """에디터 영역 렌더링 및 현재 본문 내용 반환"""

    quill_key = f"quill_{current_doc['id']}"

    # 1. 콘텐츠 안전하게 가져오기 (None 방지 로직)
    content_raw = st.session_state.get(quill_key)
    if content_raw is None:
        content_source = current_doc.get('content', "")
    else:
        content_source = content_raw

    # 2. 글자 수 계산
    char_count_total = 0
    char_count_no_space = 0
    if content_source:
        soup = BeautifulSoup(content_source, "html.parser")
        plain_text = soup.get_text()
        char_count_total = len(plain_text)
        char_count_no_space = len(plain_text.replace(" ", "").replace("\n", ""))

    # 3. 헤더 (제목 및 통계)
    c_title, c_stats, c_btn = st.columns([6, 2.5, 1.5], gap="small", vertical_alignment="bottom")

    with c_title:
        new_title = st.text_input("제목", value=current_doc['title'], key=f"t_{current_doc['id']}",
                                  label_visibility="collapsed")
        if new_title != current_doc['title']:
            current_doc['title'] = new_title  # (주의: 실제 저장은 저장 버튼 누를 때 함)

    with c_stats:
        st.markdown(
            f"<div style='text-align:right; color:gray;'>{char_count_total:,} 자 (공백제외 {char_count_no_space:,})</div>",
            unsafe_allow_html=True)

    with c_btn:
        btn_label = "✖ 닫기" if st.session_state.get("show_moneta") else "✨ Moneta"
        if st.button(btn_label, use_container_width=True):
            st.session_state.show_moneta = not st.session_state.get("show_moneta", False)
            st.rerun()

    # 4. 퀼 에디터
    content = st_quill(value=current_doc.get('content', ""), key=quill_key)

    return content, new_title