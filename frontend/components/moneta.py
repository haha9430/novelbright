import streamlit as st
from api import analyze_text_api


def render_moneta_panel(current_doc, content_source):
    """모네타(AI 분석) 패널 렌더링"""
    if st.session_state.get("show_moneta", False):
        with st.container(border=True):
            c_info, c_sev = st.columns([6, 4])

            ep_num = current_doc.get("episode_no", 1)

            with c_info:
                st.caption(f"현재 분석 대상: {ep_num}화")
                st.markdown("##### 🛡️ 스토리키퍼 설정")

            with c_sev:
                # 슬라이더는 보통 '낮음 -> 높음(왼쪽 -> 오른쪽)' 순서가 직관적이므로 순서를 조정했습니다.
                severity_option = st.select_slider(
                    "분석 민감도 (Severity)",
                    options=["low", "medium", "high"],  # 슬라이더 단계
                    value="medium",  # ✅ 기본값을 medium으로 변경
                    key="moneta_severity_select",
                    help="오른쪽(High)으로 갈수록 AI가 더 엄격하게 검사합니다.",
                )

            st.divider()

            if st.button("🚀 전체 스캔 시작", use_container_width=True, type="primary"):
                st.session_state.analysis_results[current_doc["id"]] = []
                with st.spinner(f"스토리키퍼가 분석 중입니다... (강도: {selected_severity.upper()})"):
                    res = analyze_text_api(
                        current_doc["id"],
                        content_source,
                        episode_no=ep_num,
                        severity=selected_severity,
                    )
                    st.session_state.analysis_results[current_doc["id"]] = res
                    st.rerun()

            msgs = st.session_state.analysis_results.get(current_doc["id"], [])
            if msgs:
                st.markdown(f"**총 {len(msgs)}건의 분석 결과가 있습니다.**")
                for m in msgs:
                    if isinstance(m, dict):
                        border_color = "#E67E22" if "캐릭터" in m.get("type_label", "") else "#3498DB"

                        st.markdown(
                            f"""
                            <div class="moneta-card" style="background:#FFFFFF; padding:12px; border-radius:6px; border-left:5px solid {border_color}; margin-bottom:12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                                <div style="display: flex; justify-content: space-between; font-size:12px; margin-bottom:5px;">
                                    <span style="color:{border_color}; font-weight:bold;">{m.get('type_label', '분석 결과')}</span>
                                    <span style="color:#888;">{m.get('location', '')}</span>
                                </div>
                                <div style="font-weight:bold; font-size:15px; margin-bottom:5px;">{m.get('title', '설정 충돌 확인')}</div>
                                <div style="font-size:14px; color:#2C3E50; line-height:1.5;">{m.get('reason', '')}</div>
                                <div style="margin-top:10px; padding-top:8px; border-top:1px dashed #EEE; font-size:13px; color:#16A085;">
                                    💡 <b>수정 제안:</b> {m.get('rewrite', '내용을 다시 검토해 보세요.')}
                                </div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
            else:
                st.info("스캔 버튼을 눌러 분석을 시작하세요.")
