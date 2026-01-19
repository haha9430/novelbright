import streamlit as st
import uuid
from components.common import add_character_modal

# [통합] API 및 파일 처리 모듈 임포트
# 팀원의 코드 기능(FileProcessor 등)을 수용하되, 경로 에러 방지 처리
try:
    from api import save_character_api, ingest_file_to_backend
    from app.common.file_input import FileProcessor
except ImportError:
    # 모듈이 없을 경우를 대비한 더미 함수 (앱이 멈추지 않도록 함)
    def save_character_api(*args, **kwargs):
        pass


    def ingest_file_to_backend(*args, **kwargs):
        return True


    class FileProcessor:
        @staticmethod
        def load_file_content(file): return "Dummy Content"


def render_characters(proj):
    """
    등장인물 관리 탭 UI (팀원 기능 통합 + 카드형 UI 유지 + 아이콘 제거)
    """
    # 1. 상단 액션 버튼 영역
    col_add, col_file = st.columns([1, 2], gap="small")

    with col_add:
        if st.button("인물 직접 추가", use_container_width=True):
            add_character_modal(proj)

    with col_file:
        with st.popover("파일로 일괄 추가", use_container_width=True):
            st.markdown("PDF, Word, TXT 파일을 지원하며 AI가 인물을 추출합니다.")
            uploaded_file = st.file_uploader(
                "파일 선택",
                type=["txt", "pdf", "docx"],
                key="char_uploader"
            )

            # FileProcessor 및 백엔드 전송 로직
            # 🚀 파일 처리 및 AI 분석 시작 버튼 로직
            if uploaded_file and st.button("🚀 파일 처리 및 AI 분석 시작", use_container_width=True):
                with st.spinner("파일을 읽고 캐릭터를 추출 중입니다..."):
                    try:
                        # 1. 텍스트 추출 (FileProcessor 사용)
                        content = FileProcessor.load_file_content(uploaded_file)

                        if content and not str(content).startswith("[Error]"):
                            # [핵심] 성공 여부와 상세 메시지를 동시에 받음
                            success, msg = ingest_file_to_backend(content, "character")

                            if success:
                                st.success(f"✅ {msg}")
                                st.rerun()
                            else:
                                # 이제 백엔드에서 왜 실패했는지(예: 경로 오류 등)를 화면에 띄워줍니다.
                                st.error(f"❌ 분석 실패: {msg}")
                        else:
                            st.error(f"❌ 파일 읽기 실패: {content}")
                    except Exception as e:
                        st.error(f"⚠️ 시스템 오류 발생: {e}")

    st.divider()

    # 2. 등장인물 리스트 렌더링
    if "characters" not in proj or not proj["characters"]:
        st.info("등록된 등장인물이 없습니다.")
        return

    st.caption(f"총 {len(proj['characters'])}명의 등장인물")

    # [UI 유지] 카드형 그리드 레이아웃 (2열)
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
                        # 아이콘 제거 (No Img 텍스트)
                        st.markdown(
                            """
                            <div style='
                                background-color: #f0f2f6; 
                                height: 80px; 
                                display: flex; 
                                align-items: center; 
                                justify-content: center; 
                                border-radius: 5px;
                                color: #999;
                                font-weight: bold;
                                font-size: 12px;'>
                                No Img
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

                    # 상세 정보 토글
                    with st.expander("상세 설정"):
                        new_name = st.text_input("이름", value=char["name"], key=f"char_name_{char['id']}")
                        new_desc = st.text_area("설명", value=char.get("desc", ""), height=100,
                                                key=f"char_desc_{char['id']}")

                        # [팀원 기능 반영] 저장 시 API 호출
                        if st.button("저장", key=f"save_char_{char['id']}", use_container_width=True):
                            char["name"] = new_name
                            char["desc"] = new_desc
                            save_character_api(new_name, new_desc)  # 백엔드 동기화
                            st.toast("저장되었습니다.", icon="✅")
                            st.rerun()

                        # 삭제 버튼
                        if st.button("삭제", key=f"del_char_{char['id']}", type="primary", use_container_width=True):
                            proj["characters"].remove(char)
                            st.rerun()