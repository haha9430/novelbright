import streamlit as st
import uuid
from components.common import get_current_project
from components.sidebar import render_sidebar  # ✅ 사이드바 모듈 임포트 추가
from components.characters import render_characters


def render_universe():
    # 1. 프로젝트 로드
    proj = get_current_project()
    if not proj:
        st.error("프로젝트를 불러올 수 없습니다.")
        st.session_state.page = "home"
        st.rerun()
        return

    # ✅ [수정됨] 사이드바 렌더링 추가
    render_sidebar(proj)

    # 데이터 초기화 (없을 경우 생성)
    if "worldview" not in proj: proj["worldview"] = ""
    if "plot" not in proj: proj["plot"] = ""
    if "history" not in proj: proj["history"] = []

    # 2. 헤더
    st.title(f"🌍 {proj['title']} - 설정")
    st.caption("작품의 등장인물, 세계관, 그리고 플롯을 통합 관리합니다.")

    # ---------------------------------------------------------
    # 3. 탭 구성 (등장인물 / 세계관 / 플롯)
    # ---------------------------------------------------------
    tab_char, tab_world, tab_plot = st.tabs(["👤 등장인물", "🗺️ 세계관", "📌 플롯"])

    # (1) 등장인물 탭
    with tab_char:
        render_characters(proj)

    # (2) 세계관 탭
    with tab_world:
        _render_worldview_tab(proj)

    # (3) 플롯 탭
    with tab_plot:
        _render_plot_tab(proj)


# ==============================================================================
# 내부 렌더링 함수들
# ==============================================================================

def _render_worldview_tab(proj):
    """세계관 설정 탭 내용을 렌더링"""
    st.subheader("세계관 설명")

    with st.container(border=True):
        world_text = st.text_area(
            "이 작품의 규칙, 배경, 분위기, 기술/마법 체계 등을 기록하세요.",
            value=proj.get("worldview", ""),
            height=300,
            key="worldview_input"
        )

        if world_text != proj.get("worldview", ""):
            proj["worldview"] = world_text


def _render_plot_tab(proj):
    """플롯 및 연표 탭 내용을 렌더링"""

    # 1. 메인 플롯
    st.subheader("메인 플롯")
    with st.container(border=True):
        plot_text = st.text_area(
            "기승전결, 주요 사건, 핵심 갈등 등 전체적인 줄거리를 요약하세요.",
            value=proj.get("plot", ""),
            height=200,
            key="plot_input"
        )
        if plot_text != proj.get("plot", ""):
            proj["plot"] = plot_text

    st.divider()

    # 2. 사건 연표 (History)
    st.subheader("사건 연표 (Timeline)")
    st.caption("시간 순서대로 주요 사건을 나열해보세요.")

    # 연표 입력 폼
    with st.form("add_history_form", clear_on_submit=True):
        c1, c2 = st.columns([1, 3])
        with c1:
            h_date = st.text_input("일시 / 시점", placeholder="예: 1916년 7월 1일")
        with c2:
            h_event = st.text_input("사건 내용", placeholder="예: 솜 전투 개시, 주인공 빙의")

        if st.form_submit_button("＋ 사건 추가", use_container_width=True, type="primary"):
            if h_event:
                new_event = {
                    "id": str(uuid.uuid4()),
                    "date": h_date,
                    "event": h_event
                }
                proj["history"].append(new_event)
                st.rerun()
            else:
                st.warning("사건 내용을 입력해주세요.")

    # 연표 리스트 출력
    if proj["history"]:
        for idx, item in enumerate(proj["history"]):
            with st.container(border=True):
                c_date, c_desc, c_del = st.columns([2, 6, 1], vertical_alignment="center")

                with c_date:
                    st.markdown(f"**{item['date']}**")
                with c_desc:
                    st.write(item['event'])
                with c_del:
                    if st.button("🗑", key=f"del_hist_{item['id']}"):
                        proj["history"].remove(item)
                        st.rerun()
    else:
        st.info("등록된 사건이 없습니다. 위에서 주요 사건을 추가해보세요.")