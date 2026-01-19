import streamlit as st
from components.common import create_project_modal, edit_project_modal  # edit_project_modal 임포트 추가


def render_home():
    # ---------------------------------------------------------
    # 1. 사이드바
    # ---------------------------------------------------------
    with st.sidebar:
        st.markdown("### NovellBright")
        st.divider()
        st.button("🏠 홈", use_container_width=True, type="primary")
        st.button("📂 내 작품", use_container_width=True)
        st.button("📰 아티클", use_container_width=True)
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
        st.tabs([f"모든 작품 ({project_count})", "즐겨찾기 (0)"])

    with col_btn:
        if st.button("＋ 새 작품", type="primary", use_container_width=True):
            create_project_modal()

    st.divider()

    # ---------------------------------------------------------
    # 3. 프로젝트 리스트
    # ---------------------------------------------------------
    projects = st.session_state.get("projects", [])

    if not projects:
        st.info("아직 생성된 작품이 없습니다. 우측 상단의 '새 작품' 버튼을 눌러보세요!")
        return

    # 2열 그리드 배치
    cols = st.columns(2)

    for idx, proj in enumerate(projects):
        with cols[idx % 2]:

            with st.container(border=True):
                # [수정] 카드 상단: 제목 + 수정 버튼(톱니바퀴)
                c_head_title, c_head_edit = st.columns([9, 1])
                with c_head_title:
                    st.subheader(proj['title'])
                with c_head_edit:
                    # ⚙️ 버튼 클릭 시 수정 모달 오픈
                    if st.button("⚙️", key=f"edit_btn_{proj['id']}", help="작품 정보 수정"):
                        edit_project_modal(proj)

                # 내부 내용 [이미지 : 텍스트]
                c_img, c_text = st.columns([1, 2])

                # (1) 왼쪽: 썸네일 이미지
                with c_img:
                    if proj.get("thumbnail"):
                        st.image(proj["thumbnail"], use_container_width=True)
                    else:
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
                    desc = proj.get('desc', '')
                    if len(desc) > 40:
                        desc = desc[:40] + "..."
                    st.caption(desc if desc else "설명 없음")

                    tags = proj.get("tags", [])
                    if tags:
                        tag_str = " ".join([f"`{t}`" for t in tags])
                        st.markdown(tag_str)

                    st.caption(f"📅 {proj.get('created_at', '2026.01.19')}")

                # (3) 하단: 작업하기 버튼
                if st.button("작업하기 ➜", key=f"btn_{proj['id']}", use_container_width=True):
                    st.session_state.current_project_id = proj["id"]
                    st.session_state.page = "editor"
                    st.rerun()