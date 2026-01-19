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
    등장인물 관리 탭 UI (통합 입력 방식 + 데이터 동기화 강화)
    """
    # 1. 데이터 로드: 파일 내용을 읽어와서 확실히 리스트로 변환
    # 이 부분이 누락되면 카드가 뜨지 않습니다.
    with st.status("데이터 동기화 중...", expanded=False) as status:
        raw_data = load_characters_from_file()

        if isinstance(raw_data, list):
            proj["characters"] = raw_data
        elif isinstance(raw_data, dict):
            # {'characters': [...]} 형태이거나 캐릭터 이름이 키인 경우 대응
            proj["characters"] = raw_data.get("characters", list(raw_data.values()))
        else:
            proj["characters"] = []

        status.update(label=f"총 {len(proj['characters'])}명의 데이터를 불러왔습니다.", state="complete")

    # 2. 상단 액션 버튼 영역
    col_add, col_file = st.columns([1, 1], gap="small")

    with col_add:
        # 🟢 직접 추가: 통합 입력 방식 (나이/성별 구분 없음)
        with st.popover("➕ 인물 직접 추가", use_container_width=True):
            st.markdown("### 새로운 인물 추가")
            new_name = st.text_input("이름", placeholder="예: 이도훈", key="new_char_name")

            new_description = st.text_area(
                "인물 상세 설정",
                placeholder="나이, 성별, 직업, 특징 등을 자유롭게 나열해서 적어주세요.",
                height=250,
                key="new_char_desc"
            )

            if st.button("💾 저장하기", use_container_width=True, type="primary"):
                if not new_name.strip():
                    st.error("이름은 필수입니다!")
                else:
                    new_data = {
                        "name": new_name,
                        "job_status": new_description,
                        "age_gender": "integrated",
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
        # 📂 파일 일괄 추가: AI 분석 연동
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
                                st.success("분석 및 저장 완료!")
                                st.rerun()
                            else:
                                st.error(f"분석 실패: {msg}")
                    except Exception as e:
                        st.error(f"시스템 오류: {e}")

    st.divider()

    # 3. 등장인물 리스트 렌더링
    # 데이터가 없을 때의 예외 처리가 하단 카드 출력을 결정합니다.
    if not proj.get("characters"):
        st.info("등록된 등장인물이 없습니다. 파일을 추가하거나 직접 등록해 보세요.")
        return

    st.caption(f"총 {len(proj['characters'])}명의 등장인물")

    # 카드형 그리드 레이아웃 (2열)
    cols = st.columns(2)

    for idx, char in enumerate(proj["characters"]):
        # 개별 캐릭터 데이터에서 이름 추출 및 고유 키 생성
        if not isinstance(char, dict): continue

        char_name = char.get("name", f"인물 {idx + 1}")
        char_id = f"char_{idx}_{char_name.replace(' ', '_')}"

        with cols[idx % 2]:
            with st.container(border=True):
                c_img, c_info = st.columns([1, 2])

                with c_img:
                    # 기본 이미지 영역
                    st.markdown(
                        """
                        <div style='background-color:#f0f2f6;height:100px;display:flex;align-items:center;justify-content:center;border-radius:5px;color:#999;font-size:12px;font-weight:bold;'>
                        No Img
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                with c_info:
                    st.subheader(char_name)
                    # 통합된 정보를 요약해서 보여줌
                    desc = char.get('job_status', '정보 없음')
                    st.caption(desc[:45] + "..." if len(desc) > 45 else desc)

                    # 상세 설정 창 (여기서 주루루룩 수정 가능)
                    with st.expander("📝 상세 설정"):
                        edited_info = st.text_area(
                            "인물 설정 내용",
                            value=desc,
                            height=200,
                            key=f"edit_area_{char_id}"
                        )

                        btn_col1, btn_col2 = st.columns(2)
                        with btn_col1:
                            if st.button("💾 저장", key=f"save_btn_{char_id}", use_container_width=True, type="primary"):
                                char["job_status"] = edited_info
                                save_character_api(char_name, char)
                                st.toast(f"{char_name} 저장 완료!", icon="✅")
                                st.rerun()
                        with btn_col2:
                            if st.button("🗑️ 삭제", key=f"del_btn_{char_id}", use_container_width=True):
                                proj["characters"].pop(idx)
                                # (추가 필요 시) 삭제 API 호출 로직
                                st.rerun()