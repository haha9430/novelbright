import streamlit as st
import uuid
from components.common import get_current_project
from components.sidebar import render_sidebar
from api import save_plot_api


def render_plot():
    proj = get_current_project()
    if not proj:
        st.session_state.page = "home"
        st.rerun()

    if "plots" not in proj:
        # 기본 플롯 데이터 초기화
        proj['plots'] = [{"id": "def", "name": "메인 플롯", "desc": "", "parts": []}]

    # 1. 사이드바 렌더링
    render_sidebar(proj)

    # 2. 메인 화면 헤더
    st.title("🗓️ 플롯 (Plot)")
    st.divider()

    current_plot = proj['plots'][0]

    # 3. 전체 줄거리 영역 (이름 입력 삭제됨)
    with st.container(border=True):
        # 상단: 제목("전체 줄거리") + 저장 버튼
        c_label, c_btn = st.columns([8.5, 1.5], vertical_alignment="bottom")

        with c_label:
            st.markdown("### 📜 전체 줄거리")

        with c_btn:
            if st.button("💾 저장", key="save_plot_desc", use_container_width=True):
                # 이름은 기존 값('메인 플롯') 그대로 전송
                if save_plot_api(current_plot['id'], current_plot['name'], current_plot['desc']):
                    st.toast("줄거리가 저장되었습니다!", icon="✅")
                else:
                    st.toast("저장에 실패했습니다.", icon="🚫")

        # 줄거리 입력창
        desc = st.text_area(
            "줄거리 내용",
            value=current_plot.get('desc', ''),
            height=200,
            label_visibility="collapsed",
            placeholder="이 이야기의 전체적인 흐름이나 시놉시스를 기록하세요."
        )

        if desc != current_plot.get('desc', ''):
            current_plot['desc'] = desc

    # 4. 파트(Part) 리스트 영역
    st.subheader("구성 단계 (Parts)")

    if st.button("＋ 파트 추가"):
        new_part = {"id": str(uuid.uuid4()), "title": "새 파트", "summary": ""}
        current_plot['parts'].append(new_part)
        st.rerun()

    for idx, part in enumerate(current_plot['parts']):
        with st.expander(f"#{idx + 1} {part['title']}", expanded=False):
            # 파트 제목
            new_p_title = st.text_input(f"파트 제목 ({idx + 1})", value=part['title'], key=f"p_t_{part['id']}")
            part['title'] = new_p_title

            # 파트 요약
            new_p_sum = st.text_area(f"내용 요약 ({idx + 1})", value=part['summary'], key=f"p_s_{part['id']}")
            part['summary'] = new_p_sum

            # 파트 삭제
            if st.button("삭제", key=f"del_p_{part['id']}"):
                current_plot['parts'].remove(part)
                st.rerun()