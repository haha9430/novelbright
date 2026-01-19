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
    등장인물 관리 탭 UI (통합 입력 방식 + 오류 해결본)
    """
    # 🔴 데이터 로드 (함수 내부에서 수행하여 proj 변수 인식 보장)
    with st.status("데이터를 불러오는 중...", expanded=False) as status:
        proj["characters"] = load_characters_from_file()

    # 1. 상단 액션 버튼 영역
    col_add, col_file = st.columns([1, 1], gap="small")

    with col_add:
        # 🟢 [개선] 통합 입력 방식: 이름만 쓰고 나머지는 한 칸에 다 적기
        with st.popover("➕ 인물 직접 추가", use_container_width=True):
            st.markdown("### 새로운 인물 추가")
            new_name = st.text_input("이름", placeholder="예: 이도훈")

            # 현빈님이 원하신 대로 나이/성별 구분 없이 주루루룩 입력받는 칸
            new_description = st.text_area(
                "인물 상세 설정",
                placeholder="나이, 성별, 직업, 특징 등을 자유롭게 나열해서 적어주세요.",
                height=200
            )

            if st.button("💾 저장하기", use_container_width=True, type="primary"):
                if not new_name.strip():
                    st.error("이름은 필수입니다!")
                else:
                    # 백엔드 구조에 맞춰 데이터 통합 저장
                    new_data = {
                        "name": new_name,
                        "job_status": new_description,  # 모든 정보를 여기에 주루루룩 넣음
                        "age_gender": "integrated",  # 구분하지 않으므로 고정값
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
                        st.toast(f"✅ {new_name} 추가 완료!", icon="🎉")
                        st.rerun()
                    else:
                        st.error("서버 저장에 실패했습니다.")

    with col_file:
        with st.popover("📂 파일로 일괄 추가", use_container_width=True):
            st.markdown("PDF, TXT 파일을 지원하며 AI가 인물을 추출합니다.")
            uploaded_file = st.file_uploader("파일 선택", type=["txt", "pdf", "docx"], key="char_uploader")

            if uploaded_file and st.button("🚀 AI 분석 시작", use_container_width=True, type="primary"):
                with st.spinner("AI가 인물을 분석 중입니다..."):
                    try:
                        import tempfile
                        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{uploaded_file.name}") as tmp_file:
                            tmp_file.write(uploaded_file.getvalue())
                            tmp_path = tmp_file.name

                        content = FileProcessor.load_file_content(tmp_path)
                        if os.path.exists(tmp_path):
                            os.remove(tmp_path)

                        if content and not str(content).startswith("[Error]"):
                            success, msg = ingest_file_to_backend(content, "character")
                            if success:
                                st.success("분석 완료!")
                                st.rerun()
                            else:
                                st.error(f"분석 실패: {msg}")
                    except Exception as e:
                        st.error(f"시스템 오류: {e}")

    st.divider()

    # 2. 등장인물 리스트 렌더링 (🔴 들여쓰기 수정하여 Unresolved reference 'proj' 해결)
    if "characters" not in proj or not proj["characters"]:
        st.info("등록된 등장인물이 없습니다.")
        return

    st.caption(f"총 {len(proj['characters'])}명의 등장인물")

    # 카드형 그리드 레이아웃 (2열)
    cols = st.columns(2)

    for idx, char in enumerate(proj["characters"]):
        char_id = char.get("name", f"idx_{idx}")

        with cols[idx % 2]:
            with st.container(border=True):
                c_img, c_info = st.columns([1, 2])

                with c_img:
                    # 이미지 없을 때 No Img 표시
                    st.markdown(
                        "<div style='background-color:#f0f2f6;height:80px;display:flex;align-items:center;justify-content:center;border-radius:5px;color:#999;font-size:12px;font-weight:bold;'>No Img</div>",
                        unsafe_allow_html=True)

                with c_info:
                    # 이름과 통합 정보 표시
                    char_name = char.get("name", "이름 없음")
                    st.subheader(char_name)
                    # job_status에 담긴 통합 정보를 요약해서 보여줌
                    st.caption(char.get('job_status', '정보 없음')[:50] + "...")

                    with st.expander("📝 상세 설정"):
                        # 수정 시에도 한 칸에서 주루루룩 편집 가능
                        edited_info = st.text_area(
                            "인물 설정 내용",
                            value=char.get("job_status", ""),
                            height=150,
                            key=f"edit_desc_{char_id}_{idx}"
                        )

                        if st.button("💾 저장", key=f"save_btn_{idx}", use_container_width=True, type="primary"):
                            char["job_status"] = edited_info
                            save_character_api(char_name, char)
                            st.toast("저장되었습니다!", icon="✅")
                            st.rerun()

                        if st.button("🗑️ 삭제", key=f"del_btn_{idx}", use_container_width=True):
                            proj["characters"].pop(idx)
                            st.rerun()