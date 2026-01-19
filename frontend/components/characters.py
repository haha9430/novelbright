import streamlit as st
import uuid
from components.common import add_character_modal

# ✅ [수정] 'frontend.api' -> 'api' 로 변경 (실행 경로 기준)
# api.py가 없거나 임포트 실패 시에도 앱이 멈추지 않도록 예외 처리
try:
    from api import save_character_api, ingest_file_to_backend
except ImportError:
    # API 파일이 준비되지 않았을 경우를 위한 더미 함수
    def save_character_api(*args, **kwargs):
        pass


    def ingest_file_to_backend(*args, **kwargs):
        pass


def render_characters(proj):
    """
    등장인물 관리 탭 UI
    """
    # 1. 상단 액션 버튼 영역
    col_add, col_file = st.columns([1, 1], gap="small")

    with col_add:
        if st.button("＋ 인물 직접 추가", use_container_width=True):
            add_character_modal(proj)

    with col_file:
        with st.popover("📂 파일로 일괄 추가", use_container_width=True):
            st.markdown("캐릭터 설정이 담긴 텍스트/PDF 파일을 업로드하세요.")
            uploaded_file = st.file_uploader("파일 선택", type=["txt", "pdf", "docx"], key="char_uploader")
            if uploaded_file and st.button("분석 및 추가"):
                with st.spinner("파일을 분석하여 등장인물을 추출 중입니다..."):
                    # 실제 구현 시 ingest_file_to_backend 호출
                    # ingest_file_to_backend(uploaded_file, proj['id'])
                    st.success("분석 완료! (데모)")

    st.divider()

    # 2. 등장인물 리스트 렌더링
    if "characters" not in proj or not proj["characters"]:
        st.info("등록된 등장인물이 없습니다. 위 버튼을 눌러 추가해주세요.")
        return

    # 캐릭터 카드를 2열 또는 3열로 배치
    cols = st.columns(2)

    for idx, char in enumerate(proj["characters"]):
        with cols[idx % 2]:
            with st.container(border=True):
                c_img, c_info = st.columns([1, 2])

                # (1) 캐릭터 이미지
                with c_img:
                    if char.get("image"):
                        st.image(char["image"], use_container_width=True)
                    else:
                        # 기본 아이콘 (회색 박스)
                        st.markdown(
                            """
                            <div style='
                                background-color: #f0f2f6; 
                                height: 80px; 
                                display: flex; 
                                align-items: center; 
                                justify-content: center; 
                                border-radius: 5px;
                                font-size: 24px;'>
                                👤
                            </div>
                            """,
                            unsafe_allow_html=True
                        )

                # (2) 캐릭터 정보 & 편집
                with c_info:
                    st.subheader(char["name"])
                    st.caption(f"{char.get('role', '역할 미정')} | {char.get('age', '나이 미상')}")

                    # 상세 정보 토글 (Expander)
                    with st.expander("상세 설정"):
                        # 이름 수정
                        new_name = st.text_input("이름", value=char["name"], key=f"char_name_{char['id']}")
                        if new_name != char["name"]:
                            char["name"] = new_name

                        # 설명 수정
                        new_desc = st.text_area("설명", value=char.get("desc", ""), height=100,
                                                key=f"char_desc_{char['id']}")
                        if new_desc != char.get("desc", ""):
                            char["desc"] = new_desc

                        # 삭제 버튼
                        if st.button("삭제", key=f"del_char_{char['id']}", type="primary"):
                            proj["characters"].remove(char)
                            st.rerun()