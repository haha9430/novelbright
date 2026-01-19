import streamlit as st
from components.common import create_project_modal


def render_home():
    # ---------------------------------------------------------
    # 1. 사이드바
    # ---------------------------------------------------------
    with st.sidebar:
        st.markdown("### NovellBright")
        st.divider()
        st.button("홈", use_container_width=True, type="primary")
        st.button("내 작품", use_container_width=True)
        st.button("아티클", use_container_width=True)
        st.write("")
        st.caption("설정")
        st.button("⚙️ 이용 가이드", use_container_width=True)
        st.button("💬 1:1 문의", use_container_width=True)

    # ---------------------------------------------------------
    # 2. 메인 헤더
    # ---------------------------------------------------------
    col_title, col_btn = st.columns([8, 2], vertical_alignment="bottom")
    with col_title:
        st.markdown("## 내 작품")
        project_count = len(st.session_state.get('projects', []))
        st.tabs([f"모든 작품 ({project_count})", "즐겨찾기 (0)"])  # 탭 UI만 표시

    with col_btn:
        if st.button("＋ 새 작품", type="primary", use_container_width=True):
            create_project_modal()

    st.divider()

    # ---------------------------------------------------------
    # 3. 프로젝트 리스트 (Streamlit Native Layout)
    # ---------------------------------------------------------
    projects = st.session_state.get("projects", [])

    if not projects:
        st.info("아직 생성된 작품이 없습니다. 우측 상단의 '새 작품' 버튼을 눌러보세요!")
        return

    # 2열 그리드 배치
    cols = st.columns(2)

    for idx, proj in enumerate(projects):
        # 홀수/짝수 인덱스에 따라 컬럼 선택
        with cols[idx % 2]:

            # ✅ st.container(border=True)를 사용하여 카드 테두리 생성
            with st.container(border=True):

                # 내부를 [이미지 : 텍스트] 비율로 나눔
                c_img, c_text = st.columns([1, 2])

                # (1) 왼쪽: 썸네일 이미지
                with c_img:
                    if proj.get("thumbnail"):
                        # 이미지가 있으면 표시
                        st.image(proj["thumbnail"], use_container_width=True)
                    else:
                        # 이미지가 없으면 기본 아이콘 표시 (회색 박스 느낌)
                        st.markdown(
                            """
                            <div style='
                                background-color: #f0f2f6; 
                                height: 100px; 
                                display: flex; 
                                align-items: center; 
                                justify-content: center; 
                                border-radius: 5px;
                                font-size: 30px;'>
                                📘
                            </div>
                            """,
                            unsafe_allow_html=True
                        )

                # (2) 오른쪽: 텍스트 정보
                with c_text:
                    # 제목 (클릭 불가능하므로 텍스트로 표시)
                    st.subheader(proj['title'])

                    # 설명 (너무 길면 자르기)
                    desc = proj.get('desc', '')
                    if len(desc) > 40:
                        desc = desc[:40] + "..."
                    st.caption(desc if desc else "설명 없음")

                    # 태그 표시 (Badge 스타일)
                    tags = proj.get("tags", [])
                    if tags:
                        # Streamlit 마크다운으로 태그 느낌 내기 (`태그`)
                        tag_str = " ".join([f"`{t}`" for t in tags])
                        st.markdown(tag_str)

                    # 날짜
                    st.caption(f"📅 {proj.get('created_at', '2026.01.19')}")

                # (3) 하단: 작업하기 버튼
                if st.button("작업하기 ➜", key=f"btn_{proj['id']}", use_container_width=True):
                    st.session_state.current_project_id = proj["id"]
                    st.session_state.page = "editor"
                    st.rerun()