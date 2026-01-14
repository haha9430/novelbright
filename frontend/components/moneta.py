import streamlit as st
from api import analyze_text

def render_moneta_panel(current_doc, content_source):
    """모네타(AI 분석) 패널 렌더링"""
    if st.session_state.get("show_moneta", False):
        with st.container(border=True):
            c_info, c_btn = st.columns([7, 3])
            with c_info:
                st.caption("역사적 고증과 설정 충돌을 분석합니다.")
            with c_btn:
                if st.button("🚀 전체 스캔", use_container_width=True, type="primary"):
                    st.session_state.analysis_results[current_doc['id']] = []
                    with st.spinner("분석 중..."):
                        # API 호출
                        res = analyze_text(current_doc['id'], content_source)
                        st.session_state.analysis_results[current_doc['id']] = res
                        st.rerun()

            # 분석 결과 표시
            msgs = st.session_state.analysis_results.get(current_doc['id'], [])
            if msgs:
                for m in msgs:
                    if isinstance(m, dict):
                        # 스타일링
                        bg = "#FFF5F5" if m.get('role') == "story" else "#F0F8FF"
                        border = "#D32F2F" if m.get('role') == "story" else "#0277BD"

                        st.markdown(
                            f"""
                            <div style="background:{bg}; padding:10px; border-radius:5px; border-left:4px solid {border}; margin-bottom:10px;">
                                <b>{m.get('msg', '')}</b><br>
                                <span style="font-size:13px; color:#555">💡 제안: {m.get('fix', '')}</span>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
            else:
                st.info("스캔 버튼을 눌러 분석을 시작하세요.")