import streamlit as st
import sys
import os
from pathlib import Path
import json


# frontend/components/characters.py 의 load_characters_from_file 수정
def load_characters_from_file():
    try:
        # 1. API를 통해 백엔드에서 직접 데이터를 가져옵니다.
        from api import get_characters_api
        data = get_characters_api()

        if data and isinstance(data, dict):
            print(f"✅ API를 통해 {len(data)}명의 캐릭터 로드 성공")
            return list(data.values())
    except Exception as e:
        print(f"⚠️ API 호출 실패, 로컬 파일 시도: {e}")

    # [Fallback] 만약 API가 실패하면 기존처럼 로컬 파일 시도
    file_path = "/app/app/data/characters.json"
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return list(data.values()) if isinstance(data, dict) else data
    return []


# [해결 핵심] 프로젝트 루트를 파이썬 경로에 추가하여 루트에 있는 api.py를 찾게 만듭니다.
root_path = str(Path(__file__).resolve().parents[2])
if root_path not in sys.path:
    sys.path.append(root_path)

try:
    # 이제 루트 폴더의 api.py를 정상적으로 불러옵니다.
    from api import save_character_api, ingest_file_to_backend
    from app.common.file_input import FileProcessor
except ImportError as error:
    # 만약의 경우 실행될 더미 함수도 반드시 값 2개를 돌려주도록 수정합니다.
    def ingest_file_to_backend(*args, **kwargs):
        return False, f"API 로드 실패 (경로 오류: {error})"


    def save_character_api(*args, **kwargs):
        return False


    # FileProcessor가 없을 경우를 대비한 더미
    class FileProcessor:
        @staticmethod
        def load_file_content(path):
            return f"[Error] Module not found: {error}"


    print(f"⚠️ [Import Warning] 모듈을 불러오지 못해 더미 함수를 사용합니다: {error}")


def render_characters(proj):
    """
    등장인물 관리 탭 UI (팀원 기능 통합 + 카드형 UI 유지 + 아이콘 제거)
    """
    # 🔴 매번 렌더링할 때마다 최신 파일을 읽어오도록 설정합니다.
    with st.status("render_characters를 시작합니다...", expanded=True) as status:
        st.write("load_charachters_from_file 호출")
        proj["characters"] = load_characters_from_file()

    # 1. 상단 액션 버튼 영역
    col_add, col_file = st.columns([1, 2], gap="small")

    with col_add:
        # 입력창 통합
        with st.popover("➕ 인물 직접 추가", use_container_width=True):
            st.markdown("### 새로운 인물 추가")
            new_name = st.text_input("이름", placeholder="예: 이도훈")

            integrated_info = st.text_area(
                "상세 설정",
                placeholder="나이, 성별, 직업 등을 자유롭게 주루루룩 적어주세요.",
                height=250
            )

            if st.button("💾 저장하기", use_container_width=True, type="primary"):
                if not new_name.strip():
                    st.error("이름은 필수입니다!")
                else:
                    # 기존 로직 유지 (데이터 구조는 그대로 보냄)
                    new_data = {
                        "name": new_name,
                        "job_status": integrated_info,  # 통합 정보를 여기에 넣음
                        "age_gender": "none",
                        "core_traits": [],
                        "personality": {"pros": "none", "cons": "none"},
                        "relationships": [],
                        "outer_goal": "none",
                        "inner_goal": "none",
                        "trauma_weakness": "none",
                        "speech_habit": "none"
                    }
                    success = save_character_api(new_name, new_data)
                    if success:
                        st.toast(f"✅ {new_name} 추가 완료!")
                        st.rerun()
                    else:
                        st.error("서버 저장에 실패했습니다. API 로그를 확인하세요.")

    with col_file:
        with st.popover("파일로 일괄 추가", use_container_width=True):
            st.markdown("PDF, Word, TXT 파일을 지원하며 AI가 인물을 추출합니다.")
            uploaded_file = st.file_uploader(
                "파일 선택",
                type=["txt", "pdf", "docx"],
                key="char_uploader"
            )

            # FileProcessor 및 백엔드 전송 로직
            if uploaded_file and st.button("🚀 파일 처리 및 AI 분석 시작", use_container_width=True):
                with st.spinner("파일을 읽고 캐릭터를 추출 중입니다..."):
                    try:
                        import tempfile
                        # 임시 파일을 생성하여 uploaded_file의 내용을 씁니다.
                        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{uploaded_file.name}") as tmp_file:
                            tmp_file.write(uploaded_file.getvalue())
                            tmp_path = tmp_file.name

                        # 1. 파일 경로(str)를 전달합니다.
                        content = FileProcessor.load_file_content(tmp_path)

                        # 사용 후 임시 파일 삭제
                        if os.path.exists(tmp_path):
                            os.remove(tmp_path)

                        if content and not str(content).startswith("[Error]"):
                            # [핵심] 성공 여부와 상세 메시지를 동시에 받음
                            success, msg = ingest_file_to_backend(content, "character")

                            if success:
                                st.success(f"✅ {msg}")
                                st.rerun()
                            else:
                                st.error(f"❌ 분석 실패: {msg}")
                        else:
                            st.error(f"❌ 파일 읽기 실패: {content}")

                    except Exception as error:
                        # 🟢 아까 해결한 'error' 정의 에러 방지
                        st.error(f"⚠️ 시스템 오류 발생: {error}")

    st.divider()

# 2. 등장인물 리스트 렌더링
    if "characters" not in proj or not proj["characters"]:
        st.info("등록된 등장인물이 없습니다.")
        return

    st.caption(f"총 {len(proj['characters'])}명의 등장인물")

    # 카드형 그리드 레이아웃 (2열)
    cols = st.columns(2)

    for idx, char in enumerate(proj["characters"]):
        # 캐릭터 고유 ID 설정
        char_id = char.get("name", f"idx_{idx}")

        with cols[idx % 2]:
            with st.container(border=True):
                c_img, c_info = st.columns([1, 2])

                # (1) 캐릭터 이미지 영역
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
                    # 🟢 Solar AI가 보내주는 실제 키값(job_status, age_gender)으로 수정했습니다.
                    st.subheader(char.get("name", "이름 없음"))
                    role = char.get('job_status', '역할 미정')
                    age = char.get('age_gender', '정보 없음')
                    st.caption(f"{role} | {age}")

                    # 상세 정보 토글
                    with st.expander("상세 설정"):
                        new_name = st.text_input("이름", value=char.get("name", ""), key=f"char_name_{char_id}")
                        new_desc = st.text_area(
                            "직업/신분",
                            value=char.get("job_status", ""),
                            height=100,
                            key=f"char_desc_{char_id}"
                        )

                        # 저장 시 API 호출
                        if st.button("저장", key=f"save_char_{char_id}", use_container_width=True):
                            save_character_api(new_name, new_desc)  # 백엔드 동기화
                            st.toast("저장되었습니다.", icon="✅")
                            st.rerun()

                        # 삭제 버튼
                        if st.button("삭제", key=f"del_char_{char_id}", type="primary", use_container_width=True):
                            # 삭제 API 로직이 있다면 여기에 추가
                            st.rerun()