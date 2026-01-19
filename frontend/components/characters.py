import streamlit as st
import uuid
import sys
import os
from components.common import add_character_modal

# [경로 해결] 현재 실행 위치를 기준으로 최상위 novelbright_hackathon 폴더를 경로에 추가합니다.
current_dir = os.path.dirname(os.path.abspath(__file__))  # frontend/components
root_dir = os.path.abspath(os.path.join(current_dir, "../../"))  # novelbright_hackathon
if root_dir not in sys.path:
    sys.path.append(root_dir)

# [수정] 에러를 화면에 즉시 표시하도록 변경
try:
    # 1. frontend 폴더 바로 아래의 api.py 참조
    from frontend.api import save_character_api, ingest_file_to_backend
    # 2. app 폴더 아래의 common/file_input.py 참조
    from app.common.file_input import FileProcessor
except ImportError as e:
    st.error(f"🚨 [모듈 로드 실패] 서버가 파일을 찾지 못하고 있습니다: {e}")
    st.info(f"현재 시스템 경로(sys.path)에 루트가 포함되었는지 확인이 필요합니다. ({root_dir})")


    # 클릭 시 구체적인 원인을 알려주기 위한 안전장치
    def save_character_api(*args, **kwargs):
        st.error(f"백엔드 연결 실패: save_character_api를 사용할 수 없습니다. ({e})")


    def ingest_file_to_backend(*args, **kwargs):
        st.error(f"백엔드 연결 실패: ingest_file_to_backend를 사용할 수 없습니다. ({e})")
        return False


    class FileProcessor:
        @staticmethod
        def load_file_content(file):
            st.error(f"파일 처리 실패: FileProcessor 모듈이 없습니다. ({e})")
            return None


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

            # 파일 처리 및 AI 분석 시작 버튼
            if uploaded_file and st.button("🚀 파일 처리 및 AI 분석 시작", use_container_width=True):
                with st.spinner("파일을 읽고 캐릭터를 추출 중입니다..."):
                    try:
                        # 1. 텍스트 추출 (FileProcessor 사용)
                        content = FileProcessor.load_file_content(uploaded_file)

                        if content and not str(content).startswith("[Error]"):
                            # 2. 백엔드 전송 (type="character")
                            success = ingest_file_to_backend(content, "character")
                            if success:
                                st.success("✅ 캐릭터 분석 및 저장이 완료되었습니다!")
                                st.rerun()
                            else:
                                st.error("❌ 서버 전송 실패: 백엔드 API 응답을 확인하세요.")
                        else:
                            st.error(f"❌ 파일 읽기 실패: {content if content else '내용이 없습니다.'}")
                    except Exception as ex:
                        st.error(f"⚠️ 실행 중 오류 발생: {ex}")

    st.divider()

    # 2. 등장인물 리스트 렌더링
    if "characters" not in proj or not proj["characters"]:
        st.info("등록된 등장인물이 없습니다. 위 버튼을 눌러 추가해주세요.")
        return

    # 카드형 UI (2열 Grid)
    cols = st.columns(2)

    for idx, char in enumerate(proj["characters"]):
        with cols[idx % 2]:
            with st.container(border=True):
                c_img, c_info = st.columns([1, 2])

                # (1) 캐릭터 이미지 영역
                with c_img:
                    st.markdown(
                        """
                        <div style='background-color: #f0f2f6; height: 80px; display: flex; 
                             align-items: center; justify-content: center; border-radius: 5px; font-size: 24px;'>
                            👤
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                # (2) 캐릭터 정보 & 편집 영역
                with c_info:
                    st.subheader(char.get("name", "이름 없음"))
                    role = char.get('role', '역할 미정')
                    st.caption(f"{role}")

                    # 상세 정보 수정 (Expander)
                    with st.expander("상세 설정"):
                        new_name = st.text_input("이름", value=char.get("name", ""),
                                                 key=f"char_name_{char.get('id', idx)}")
                        new_desc = st.text_area("설명", value=char.get("desc", ""), height=100,
                                                key=f"char_desc_{char.get('id', idx)}")

                        if st.button("💾 저장", key=f"save_char_{char.get('id', idx)}", use_container_width=True):
                            char["name"] = new_name
                            char["desc"] = new_desc
                            save_character_api(new_name, new_desc)
                            st.toast("저장되었습니다.", icon="✅")
                            st.rerun()

                        if st.button("🗑️ 삭제", key=f"del_char_{char.get('id', idx)}", type="primary",
                                     use_container_width=True):
                            proj["characters"].remove(char)
                            st.rerun()