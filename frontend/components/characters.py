import streamlit as st
import sys
import os
from pathlib import Path
import json

# [해결 핵심] 프로젝트 루트를 파이썬 경로에 추가하여 루트에 있는 api.py를 찾게 만듭니다.
root_path = str(Path(__file__).resolve().parents[2])
if root_path not in sys.path:
    sys.path.append(root_path)


# ==========================================
# 1. 데이터 로드 및 변환 함수 (최종 수정본)
# ==========================================
def load_characters_from_file():
    """
    백엔드 API를 통해 데이터를 가져오고, 리스트 형식을 보장합니다.
    """
    try:
        from api import get_characters_api
        data = get_characters_api()

        if data:
            # 🔵 디버깅 상태창: 데이터가 오면 무조건 화면에 찍어줍니다.
            with st.status("load_characters_from_flie 데이터 확인 중...", expanded=False) as status:
                st.write(data)
                status.update(label="✅ 데이터 로드 성공", state="complete")

            # 🔴 핵심: 백엔드가 리스트([])를 주면 그대로, 딕셔너리({})를 주면 리스트로 변환
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return list(data.values())
            return data
    except Exception as e:
        print(f"⚠️ API 호출 실패, 로컬 파일 시도: {e}")

    # [Fallback] API 실패 시 로컬 파일 직접 읽기
    file_path = "/app/app/data/characters.json"
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                if isinstance(data, list): return data
                if isinstance(data, dict): return list(data.values())
                return data
            except Exception as e:
                print(f"⚠️ JSON 파싱 실패: {e}")
    return []


# ==========================================
# 2. 외부 모듈 임포트 설정
# ==========================================
try:
    from api import save_character_api, ingest_file_to_backend
    from app.common.file_input import FileProcessor
except ImportError as error:
    def ingest_file_to_backend(*args, **kwargs):
        return False, f"API 로드 실패: {error}"


    def save_character_api(*args, **kwargs):
        return False


    class FileProcessor:
        @staticmethod
        def load_file_content(path): return f"[Error] {error}"


# ==========================================
# 3. 메인 렌더링 함수
# ==========================================
def render_characters(proj):
    """
    등장인물 관리 탭 UI
    """
    # 매번 렌더링할 때마다 최신 데이터를 읽어옵니다.
    proj["characters"] = load_characters_from_file()

    # 1. 상단 액션 버튼 영역
    col_add, col_file = st.columns([1, 2], gap="small")

    with col_add:
        with st.popover("➕ 인물 직접 추가", use_container_width=True):
            st.markdown("### 새로운 인물 추가")
            new_name = st.text_input("이름", placeholder="예: 이도훈")
            new_job = st.text_input("직업/신분", placeholder="예: 장교")

            if st.button("💾 저장하기", use_container_width=True, type="primary"):
                if not new_name.strip():
                    st.error("이름은 필수입니다!")
                else:
                    new_data = {"name": new_name, "job_status": new_job or "none"}
                    if save_character_api(new_name, new_data):
                        st.toast(f"✅ {new_name} 추가 완료!", icon="🎉")
                        st.rerun()

    with col_file:
        with st.popover("파일로 일괄 추가", use_container_width=True):
            st.markdown("PDF, Word, TXT 파일을 지원하며 AI가 인물을 추출합니다.")
            uploaded_file = st.file_uploader("파일 선택", type=["txt", "pdf", "docx"], key="char_uploader")

            if uploaded_file and st.button("🚀 AI 분석 시작", use_container_width=True):
                with st.spinner("파일을 읽고 캐릭터를 추출 중입니다..."):
                    try:
                        import tempfile
                        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{uploaded_file.name}") as tmp_file:
                            tmp_file.write(uploaded_file.getvalue())
                            tmp_path = tmp_file.name
                        content = FileProcessor.load_file_content(tmp_path)
                        if os.path.exists(tmp_path): os.remove(tmp_path)

                        if content and not str(content).startswith("[Error]"):
                            success, msg = ingest_file_to_backend(content, "character")
                            if success:
                                st.success(f"✅ {msg}")
                                st.rerun()
                            else:
                                st.error(f"❌ 분석 실패: {msg}")
                    except Exception as error:
                        st.error(f"⚠️ 시스템 오류: {error}")

    st.divider()

    # 2. 등장인물 리스트 렌더링
    chars = proj.get("characters", [])
    if not chars:
        st.info("등록된 등장인물이 없습니다.")
        return

    st.caption(f"총 {len(chars)}명의 등장인물")

    # 카드형 그리드 레이아웃 (2열)
    cols = st.columns(2)
    for idx, char in enumerate(chars):
        if not isinstance(char, dict): continue
        char_id = char.get("name", f"idx_{idx}")

        with cols[idx % 2]:
            with st.container(border=True):
                c_img, c_info = st.columns([1, 2])
                with c_img:
                    st.markdown(
                        "<div style='background-color:#f0f2f6;height:80px;display:flex;align-items:center;justify-content:center;border-radius:5px;color:#999;font-weight:bold;font-size:12px;'>No Img</div>",
                        unsafe_allow_html=True)
                with c_info:
                    st.subheader(char.get("name", "이름 없음"))
                    role = char.get('job_status', '역할 미정')
                    age = char.get('age_gender', '정보 없음')
                    st.caption(f"{role} | {age}")

                    with st.expander("상세 설정"):
                        new_name = st.text_input("이름", value=char.get("name", ""), key=f"n_{char_id}")
                        new_desc = st.text_area("직업/신분", value=role, height=100, key=f"d_{char_id}")
                        if st.button("저장", key=f"s_{char_id}", use_container_width=True):
                            save_character_api(new_name, new_desc)
                            st.toast("저장되었습니다.", icon="✅")
                            st.rerun()