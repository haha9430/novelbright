import streamlit as st
import uuid
from components.common import add_character_modal

# 파일 처리 로직 try-except 처리
try:
    from api import save_character_api, ingest_file_to_backend
    from app.common.file_input import FileProcessor
except ImportError:
    # API나 모듈이 없을 경우를 대비한 더미 함수 (UI 테스트용)
    def save_character_api(*args, **kwargs):
        pass


    def ingest_file_to_backend(*args, **kwargs):
        return True


    class FileProcessor:
        @staticmethod
        def load_file_content(file): return "Dummy Content"


def render_characters(proj):
    """
    등장인물 관리 탭 UI (통합 버전)
    """
    # 1. 상단 액션 버튼 영역
    col_add, col_file = st.columns([1, 2], gap="small")

    with col_add:
        if st.button("＋ 인물 직접 추가", use_container_width=True):
            add_character_modal(proj)

    with col_file:
        with st.popover("📂 파일로 일괄 추가", use_container_width=True):
            st.markdown("PDF, Word, TXT 파일을 지원하며 AI가 인물을 추출합니다.")
            uploaded_file = st.file_uploader(
                "파일 선택",
                type=["txt", "pdf", "docx"],
                key="char_uploader"
            )

            # [통합] 팀원의 파일 처리 로직 적용
            if uploaded_file and st.button("🚀 파일 처리 및 AI 분석 시작", use_container_width=True):
                with st.spinner("파일을 읽고 캐릭터를 추출 중입니다..."):
                    try:
                        # 1. 텍스트 추출
                        content = FileProcessor.load_file_content(uploaded_file)

                        if content and not content.startswith("[Error]"):
                            # 2. 백엔드 전송
                            success = ingest_file_to_backend(content, "character")
                            if success:
                                st.success("캐릭터 분석 및 저장이 완료되었습니다!")
                                st.rerun()
                            else:
                                st.error("서버 전송 실패")
                        else:
                            st.error("파일 내용을 읽을 수 없습니다.")
                    except Exception as e:
                        st.error(f"처리 중 오류 발생: {e}")

    st.divider()

    # 2. 등장인물 리스트 렌더링
    if "characters" not in proj or not proj["characters"]:
        st.info("등록된 등장인물이 없습니다. 위 버튼을 눌러 추가해주세요.")
        return

    # [통합] 사용자님의 카드형 UI (Grid) 유지
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
                    role = char.get('role', '역할 미정')
                    age = char.get('age', '나이 미상')
                    st.caption(f"{role} | {age}")

                    # 상세 정보 토글 (Expander 활용)
                    with st.expander("상세 설정"):
                        # 이름 수정
                        new_name = st.text_input("이름", value=char["name"], key=f"char_name_{char['id']}")

                        # 설명 수정
                        new_desc = st.text_area("설명", value=char.get("desc", ""), height=100,
                                                key=f"char_desc_{char['id']}")

                        # [통합] 저장 버튼 추가 (API 호출용)
                        if st.button("💾 저장", key=f"save_char_{char['id']}", use_container_width=True):
                            char["name"] = new_name
                            char["desc"] = new_desc
                            # 팀원의 API 호출 로직 사용
                            save_character_api(new_name, new_desc)
                            st.toast("저장되었습니다.", icon="✅")
                            st.rerun()

                        # 삭제 버튼
                        if st.button("🗑️ 삭제", key=f"del_char_{char['id']}", type="primary", use_container_width=True):
                            proj["characters"].remove(char)
                            st.rerun()