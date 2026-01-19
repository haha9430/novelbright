import streamlit as st
import uuid
import requests
import io
import zlib
import struct
import olefile
from docx import Document
import fitz  # PyMuPDF
from components.common import get_current_project
from components.sidebar import render_sidebar

# [핵심] 파일 파싱 함수 가져오기
try:
    from api import save_material_api, delete_material_api, parse_file_content, BASE_URL
except ImportError:
    # 로컬 테스트용 폴백 (api.py가 같은 폴더에 없을 경우)
    import os

    BASE_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")


    def parse_file_content(file):
        return "파일 파싱 함수 로드 실패"


def render_materials():
    proj = get_current_project()
    if not proj:
        st.session_state.page = "home"
        st.rerun()

    if "materials" not in proj: proj['materials'] = []

    if "selected_material_id" not in st.session_state:
        st.session_state.selected_material_id = None

    render_sidebar(proj)

    st.title(f"자료실")
    st.caption("설정에 참고할 자료를 텍스트로 보관하거나 파일을 불러와 저장합니다.")
    st.divider()

    c_list, c_edit = st.columns([1, 2], gap="large")

    # ---------------------------------------------------------
    # 1. 왼쪽: 자료 목록
    # ---------------------------------------------------------
    with c_list:
        c1, c2 = st.columns([2, 1])
        c1.subheader("목록")

        if c2.button("＋ 추가", use_container_width=True):
            new_mat = {"id": str(uuid.uuid4()), "title": "새 자료", "content": ""}
            proj['materials'].insert(0, new_mat)
            st.session_state.selected_material_id = new_mat['id']
            st.rerun()

        if not proj['materials']:
            st.info("등록된 자료가 없습니다.")

        for mat in proj['materials']:
            is_sel = (mat['id'] == st.session_state.selected_material_id)
            icon = "📂" if is_sel else "📄"
            btn_type = "primary" if is_sel else "secondary"

            if st.button(f"{icon} {mat['title']}", key=f"m_{mat['id']}", use_container_width=True, type=btn_type):
                st.session_state.selected_material_id = mat['id']
                st.rerun()

    # ---------------------------------------------------------
    # 2. 오른쪽: 상세 편집 (파일 업로드 추가됨)
    # ---------------------------------------------------------
    with c_edit:
        sel_mat = next((m for m in proj['materials'] if m['id'] == st.session_state.selected_material_id), None)

        if sel_mat:
            with st.container(border=True):
                c_head, c_btn = st.columns([8, 1])
                c_head.caption("자료 상세 내용")

                # 1. 삭제 버튼
                if c_btn.button("🗑", key=f"del_m_{sel_mat['id']}"):
                    requests.delete(f"{BASE_URL}/history/material/{sel_mat['id']}", json=sel_mat)
                    proj['materials'].remove(sel_mat)
                    st.session_state.selected_material_id = None
                    st.toast("자료가 삭제되었습니다.")
                    st.rerun()

                # =================================================
                # 2. [위치 이동] 파일 업로드 로직을 먼저 수행해야 함
                # =================================================
                with st.expander("파일에서 내용 불러오기 (HWP, PDF, Word)", expanded=False):
                    uploaded_file = st.file_uploader(
                        "파일을 업로드하면 텍스트를 추출하여 아래 내용에 덮어씁니다.",
                        type=["txt", "md", "pdf", "docx", "hwp"],
                        key="mat_uploader"
                    )

                    if uploaded_file is not None:
                        if st.button("파일 내용 적용하기", use_container_width=True):
                            with st.spinner("파일 내용을 분석 중입니다..."):
                                extracted_text = parse_file_content(uploaded_file)

                                if extracted_text:
                                    # 데이터 업데이트
                                    sel_mat['content'] = extracted_text
                                    sel_mat['title'] = uploaded_file.name

                                    # [중요] 여기서 세션 상태를 업데이트합니다.
                                    # 아직 st.text_input이 그려지지 않았으므로 에러가 나지 않습니다.
                                    st.session_state["mat_content"] = extracted_text
                                    st.session_state["mat_title"] = uploaded_file.name

                                    st.toast(f"'{uploaded_file.name}' 내용을 불러왔습니다!", icon="✅")
                                    st.rerun()
                                else:
                                    st.error("텍스트를 추출하지 못했습니다.")

                # =================================================
                # 3. [위치 이동] 제목 및 내용 편집 위젯은 로직 '아래'에 있어야 함
                # =================================================

                # 제목 편집 (이제 위에서 st.session_state["mat_title"]을 바꿔도 반영됨)
                new_t = st.text_input("제목", value=sel_mat['title'], key="mat_title")
                if new_t != sel_mat['title']: sel_mat['title'] = new_t

                # 내용 편집 (TextArea)
                new_ctx = st.text_area(
                    "내용",
                    value=sel_mat.get('content', ''),
                    height=500,
                    placeholder="직접 내용을 입력하거나 위에서 파일을 불러오세요.",
                    key="mat_content"
                )
                if new_ctx != sel_mat.get('content', ''): sel_mat['content'] = new_ctx

                st.divider()

                # 4. 저장 버튼
                if st.button("💾 저장하기", type="primary", use_container_width=True):
                    try:
                        requests.post(f"{BASE_URL}/history/upsert", json=sel_mat)
                        st.toast("자료가 저장되었습니다!", icon="✅")
                    except Exception as e:
                        st.error(f"저장 중 오류가 발생했습니다: {e}")


# =================================================
# [Helper] 파일 파싱 함수 정의
# =================================================
def get_hwp_text(file_obj):
    """
    HWP 파일에서 텍스트를 추출하는 헬퍼 함수 (HWP 5.0 이상)
    """
    try:
        # [중요] 파일 포인터를 맨 앞으로 초기화해야 olefile이 읽을 수 있음
        file_obj.seek(0)

        f = olefile.OleFileIO(file_obj)
        dirs = f.listdir()

        # HWP 파일 구조 확인
        if ["FileHeader"] not in dirs or ["BodyText"] not in dirs:
            st.warning("지원되지 않는 HWP 포맷이거나 암호화된 파일입니다.")
            return None

        sections = [d[1] for d in dirs if d[0] == "BodyText"]
        text = ""

        for section in sections:
            bodytext = f.openstream("BodyText/" + section).read()

            # 압축 해제 시도
            try:
                unpacked_data = zlib.decompress(bodytext, -15)
                decoded_text = unpacked_data.decode('utf-16-le')
                text += decoded_text.replace("\r", "\n").replace("\x00", "")
            except Exception:
                # 압축 해제 실패 시 건너뜀
                continue

        return text

    except Exception as e:
        # 구체적인 에러 메시지 확인용
        print(f"HWP Parsing Error: {e}")
        return None


def parse_file_content(uploaded_file):
    """
    업로드된 파일 객체를 받아 텍스트를 추출하여 반환
    """
    file_ext = uploaded_file.name.split('.')[-1].lower()
    text = ""

    try:
        uploaded_file.seek(0)
        # 1. TXT / MD 파일
        if file_ext in ['txt', 'md']:
            # UTF-8 시도 후 실패 시 EUC-KR(한글) 시도
            raw_data = uploaded_file.read()
            try:
                text = raw_data.decode('utf-8')
            except UnicodeDecodeError:
                text = raw_data.decode('euc-kr')

        # 2. PDF 파일
        elif file_ext == 'pdf':
            with fitz.open(stream=uploaded_file.read(), filetype="pdf") as doc:
                for page in doc:
                    text += page.get_text()

            # ---------------------------------------------------------
            # [✅ 추가된 로직] PDF 줄바꿈 보정 (전처리)
            # ---------------------------------------------------------
            if text:
                # 원리: "마침표(.)나 물음표(?), 느낌표(!)가 아닌 글자" 뒤에 오는 줄바꿈(\n)을 공백으로 치환
                # 이렇게 하면 문장 중간에 잘린 줄바꿈은 사라지고, 진짜 문단 바꿈은 유지됩니다.
                text = re.sub(r'(?<![\.\?\!])\n', ' ', text)

                # 혹시 모를 다중 공백 제거 (선택사항)
                text = re.sub(r'  +', ' ', text)

        # 3. Word (DOCX) 파일
        elif file_ext == 'docx':
            doc = Document(uploaded_file)
            for para in doc.paragraphs:
                text += para.text + "\n"

        # 4. HWP (한글) 파일
        elif file_ext == 'hwp':
            text = get_hwp_text(uploaded_file)

        else:
            st.error("지원하지 않는 파일 형식입니다.")
            return None

        return text.strip()

    except Exception as e:
        st.error(f"파일 처리 중 오류가 발생했습니다: {e}")
        return None